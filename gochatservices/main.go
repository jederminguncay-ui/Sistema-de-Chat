package main

import (
	"log"
	"net/http"

	"SistemadeChat/gochatservices/routes"
	"SistemadeChat/gochatservices/services"
	"SistemadeChat/gochatservices/utils"
)

func main() {
	cfg := utils.LoadConfig()
	if cfg.SecretKey == "" {
		log.Println("ADVERTENCIA: SECRET_KEY está vacía; los tokens no podrán validarse.")
	}

	hub := services.NewHub(cfg.AuthServiceURL)

	mux := http.NewServeMux()
	routes.RegisterRoutes(mux, hub, cfg)

	addr := ":" + cfg.Port
	log.Printf("servicio de chat (WebSocket) escuchando en %s", addr)
	log.Printf("servicio de autenticación: %s", cfg.AuthServiceURL)

	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("error al iniciar el servidor: %v", err)
	}
}
