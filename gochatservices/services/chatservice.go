package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"SistemadeChat/gochatservices/models"
)

type Client struct {
	UserID int
	Token  string
	Send   chan []byte
}

type Hub struct {
	clients map[int]*Client
	mu      sync.RWMutex
	authURL string
	http    *http.Client
}

func NewHub(authURL string) *Hub {
	return &Hub{
		clients: make(map[int]*Client),
		authURL: authURL,
		http:    &http.Client{Timeout: 10 * time.Second},
	}
}

func (h *Hub) Register(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if old, ok := h.clients[c.UserID]; ok {
		close(old.Send)
	}
	h.clients[c.UserID] = c
}

func (h *Hub) Unregister(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if current, ok := h.clients[c.UserID]; ok && current == c {
		delete(h.clients, c.UserID)
		close(c.Send)
	}
}

func (h *Hub) IsOnline(userID int) bool {
	h.mu.RLock()
	defer h.mu.RUnlock()
	_, ok := h.clients[userID]
	return ok
}

func (h *Hub) SendToUser(userID int, payload []byte) bool {
	h.mu.RLock()
	client, ok := h.clients[userID]
	h.mu.RUnlock()
	if !ok {
		return false
	}
	select {
	case client.Send <- payload:
		return true
	default:
		return false
	}
}

func (h *Hub) PersistMessage(token string, req models.SendRequest) (*models.SavedMessage, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequest(
		http.MethodPost, h.authURL+"/message/send", bytes.NewReader(body),
	)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+token)

	return h.doMessageRequest(httpReq)
}

func (h *Hub) MarkRead(token string, messageID int) (*models.SavedMessage, error) {
	url := fmt.Sprintf("%s/message/read/%d", h.authURL, messageID)
	httpReq, err := http.NewRequest(http.MethodPut, url, nil)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Authorization", "Bearer "+token)

	return h.doMessageRequest(httpReq)
}

func (h *Hub) doMessageRequest(req *http.Request) (*models.SavedMessage, error) {
	resp, err := h.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("authservice respondió %d: %s", resp.StatusCode, string(data))
	}

	var saved models.SavedMessage
	if err := json.Unmarshal(data, &saved); err != nil {
		return nil, err
	}
	return &saved, nil
}
