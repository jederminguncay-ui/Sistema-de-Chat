package routes

import (
	"net/http"

	"SistemadeChat/gochatservices/handlers"
	"SistemadeChat/gochatservices/services"
	"SistemadeChat/gochatservices/utils"
)

func RegisterRoutes(mux *http.ServeMux, hub *services.Hub, cfg *utils.Config) {
	mux.HandleFunc("/ws", handlers.ServeWS(hub, cfg))

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"gochatservices"}`))
	})
}
