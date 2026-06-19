package handlers

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"

	"SistemadeChat/gochatservices/models"
	"SistemadeChat/gochatservices/services"
	"SistemadeChat/gochatservices/utils"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 8192
	sendBuffer     = 32
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

type wsClient struct {
	conn *websocket.Conn
	hub  *services.Hub
	base *services.Client
}

func ServeWS(hub *services.Hub, cfg *utils.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token := r.URL.Query().Get("token")
		userID, _, err := utils.ValidateToken(token, cfg.SecretKey)
		if err != nil {
			http.Error(w, "no autorizado: "+err.Error(), http.StatusUnauthorized)
			return
		}

		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Printf("error al actualizar a WebSocket: %v", err)
			return
		}

		base := &services.Client{
			UserID: userID,
			Token:  token,
			Send:   make(chan []byte, sendBuffer),
		}
		client := &wsClient{conn: conn, hub: hub, base: base}
		hub.Register(base)
		log.Printf("usuario %d conectado", userID)

		go client.writePump()
		client.readPump()
	}
}

func (c *wsClient) readPump() {
	defer func() {
		c.hub.Unregister(c.base)
		_ = c.conn.Close()
		log.Printf("usuario %d desconectado", c.base.UserID)
	}()

	c.conn.SetReadLimit(maxMessageSize)
	_ = c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		return c.conn.SetReadDeadline(time.Now().Add(pongWait))
	})

	for {
		_, raw, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(
				err, websocket.CloseGoingAway, websocket.CloseNormalClosure,
			) {
				log.Printf("error de lectura (usuario %d): %v", c.base.UserID, err)
			}
			break
		}

		var frame models.ClientFrame
		if err := json.Unmarshal(raw, &frame); err != nil {
			c.sendError("formato de mensaje inválido")
			continue
		}

		switch frame.Type {
		case "send":
			c.handleSend(frame)
		case "read":
			c.handleRead(frame)
		default:
			c.sendError("tipo de mensaje no soportado")
		}
	}
}

func (c *wsClient) handleSend(frame models.ClientFrame) {
	receiverOnline := c.hub.IsOnline(frame.ReceiverID)

	saved, err := c.hub.PersistMessage(c.base.Token, models.SendRequest{
		ConversationID: frame.ConversationID,
		ReceiverID:     frame.ReceiverID,
		Content:        frame.Content,
		Delivered:      receiverOnline,
	})
	if err != nil {
		log.Printf("error al guardar mensaje: %v", err)
		c.sendError("no se pudo guardar el mensaje")
		return
	}

	ack, _ := json.Marshal(models.ServerFrame{
		Type:           "sent",
		TempID:         frame.TempID,
		ID:             saved.ID,
		ConversationID: saved.ConversationID,
		SenderID:       saved.SenderID,
		ReceiverID:     saved.ReceiverID,
		CreatedAt:      saved.CreatedAt,
		Delivered:      saved.Delivered,
		Read:           saved.Read,
	})
	c.base.Send <- ack

	if receiverOnline {
		incoming, _ := json.Marshal(models.ServerFrame{
			Type:           "message",
			ID:             saved.ID,
			ConversationID: saved.ConversationID,
			SenderID:       saved.SenderID,
			ReceiverID:     saved.ReceiverID,
			Content:        saved.Content,
			CreatedAt:      saved.CreatedAt,
			Delivered:      true,
			Read:           false,
		})
		c.hub.SendToUser(frame.ReceiverID, incoming)
	}
}

func (c *wsClient) handleRead(frame models.ClientFrame) {
	for _, id := range frame.MessageIDs {
		saved, err := c.hub.MarkRead(c.base.Token, id)
		if err != nil {
			log.Printf("error al marcar leído (mensaje %d): %v", id, err)
			continue
		}
		notice, _ := json.Marshal(models.ServerFrame{
			Type:           "read",
			ID:             saved.ID,
			ConversationID: saved.ConversationID,
		})
		c.hub.SendToUser(saved.SenderID, notice)
	}
}

func (c *wsClient) sendError(detail string) {
	payload, _ := json.Marshal(models.ServerFrame{Type: "error", Detail: detail})
	select {
	case c.base.Send <- payload:
	default:
	}
}

func (c *wsClient) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		_ = c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.base.Send:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				_ = c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-ticker.C:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
