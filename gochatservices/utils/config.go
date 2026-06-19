package utils

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"strings"
	"time"
)

type Config struct {
	Port           string
	AuthServiceURL string
	SecretKey      string
}

func LoadConfig() *Config {
	loadEnvFile()

	return &Config{
		Port:           getEnv("PORT", "8080"),
		AuthServiceURL: getEnv("AUTH_SERVICE_URL", "http://localhost:8000"),
		SecretKey:      getEnv("SECRET_KEY", ""),
	}
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func loadEnvFile() {
	path := os.Getenv("CHAT_ENV_FILE")
	if path == "" {
		path = "authservice/.env"
	}

	file, err := os.Open(path)
	if err != nil {
		return
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		if _, exists := os.LookupEnv(key); !exists {
			_ = os.Setenv(key, value)
		}
	}
}

type tokenPayload struct {
	Sub      int    `json:"sub"`
	Username string `json:"username"`
	Exp      int64  `json:"exp"`
}

func ValidateToken(token, secret string) (int, string, error) {
	if token == "" {
		return 0, "", errors.New("token vacío")
	}
	parts := strings.SplitN(token, ".", 2)
	if len(parts) != 2 {
		return 0, "", errors.New("formato de token inválido")
	}
	payloadB64, signature := parts[0], parts[1]

	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payloadB64))
	expected := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(expected), []byte(signature)) {
		return 0, "", errors.New("firma de token inválida")
	}

	payloadJSON, err := base64.RawURLEncoding.DecodeString(payloadB64)
	if err != nil {
		return 0, "", errors.New("payload de token inválido")
	}

	var payload tokenPayload
	if err := json.Unmarshal(payloadJSON, &payload); err != nil {
		return 0, "", errors.New("payload de token ilegible")
	}

	if payload.Exp < time.Now().Unix() {
		return 0, "", errors.New("token expirado")
	}
	return payload.Sub, payload.Username, nil
}
