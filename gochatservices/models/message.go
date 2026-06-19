package models

type ClientFrame struct {
	Type           string `json:"type"`
	TempID         string `json:"temp_id,omitempty"`
	ConversationID int    `json:"conversation_id,omitempty"`
	ReceiverID     int    `json:"receiver_id,omitempty"`
	Content        string `json:"content,omitempty"`
	MessageIDs     []int  `json:"message_ids,omitempty"`
}

type ServerFrame struct {
	Type           string `json:"type"`
	TempID         string `json:"temp_id,omitempty"`
	ID             int    `json:"id,omitempty"`
	ConversationID int    `json:"conversation_id,omitempty"`
	SenderID       int    `json:"sender_id,omitempty"`
	ReceiverID     int    `json:"receiver_id,omitempty"`
	Content        string `json:"content,omitempty"`
	CreatedAt      string `json:"created_at,omitempty"`
	Delivered      bool   `json:"delivered,omitempty"`
	Read           bool   `json:"read,omitempty"`
	Detail         string `json:"detail,omitempty"`
}

type SendRequest struct {
	ConversationID int    `json:"conversation_id"`
	ReceiverID     int    `json:"receiver_id"`
	Content        string `json:"content"`
	Delivered      bool   `json:"delivered"`
}

type SavedMessage struct {
	ID             int    `json:"id"`
	ConversationID int    `json:"conversation_id"`
	SenderID       int    `json:"sender_id"`
	ReceiverID     int    `json:"receiver_id"`
	Content        string `json:"content"`
	CreatedAt      string `json:"created_at"`
	Delivered      bool   `json:"delivered"`
	Read           bool   `json:"read"`
}
