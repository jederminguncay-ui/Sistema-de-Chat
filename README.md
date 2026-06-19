# Sistema de Chat — Proyecto Integrador (UIDE)

Sistema de mensajería privada en tiempo real, al estilo de WhatsApp o Instagram
Direct Messages, desarrollado como **Proyecto Integrador** de la carrera de
**Ingeniería en Sistemas** de la **Universidad Internacional del Ecuador (UIDE)**.

El proyecto integra las áreas de **Programación**, **Redes** y **Seguridad**:

- **Programación:** Python, Go, FastAPI, HTML, CSS, JavaScript y WebSockets.
- **Redes:** comunicación cliente-servidor, mensajería en tiempo real con
  WebSockets y arquitectura distribuida en servicios separados con Docker.
- **Seguridad:** hashing de contraseñas con bcrypt + Salt + Pepper, cifrado de
  mensajes con AES-256-CBC, tokens de sesión firmados (HMAC-SHA256) y manejo de
  secretos mediante variables de entorno.

---

## Funcionalidades

- Registro de usuarios (nombre, apellido, usuario único y contraseña).
- Inicio de sesión únicamente con usuario y contraseña (sin correo).
- Búsqueda de usuarios por nombre de usuario.
- Creación de conversaciones privadas uno a uno.
- Envío y recepción de mensajes en tiempo real.
- Historial persistente: las conversaciones permanecen tras cerrar sesión.
- Fecha y hora de cada mensaje, agrupadas por día.
- Estados de mensaje: **enviado**, **entregado** y **leído** (estilo WhatsApp).
- Almacenamiento seguro de credenciales y mensajes (nunca en texto plano).

---

## Arquitectura

El sistema se compone de dos servicios independientes y un cliente web:

```
                 navegador (cliente/)
                /                    \
         REST  /                      \  WebSocket
              v                        v
   authservice (FastAPI)  <----->  gochatservices (Go)
   Python · puerto 8000    REST    Gorilla · puerto 8080
   - Usuarios y datos              - Conexiones en tiempo real
   - Seguridad (hash/AES)          - Entrega instantánea
   - Base de datos SQLite          - Recibos de lectura
```

- **authservice (Python / FastAPI, puerto 8000):** es el dueño de toda la
  persistencia. Gestiona la base de datos SQLite con SQLModel, implementa la
  seguridad (hashing y cifrado), expone los ocho endpoints REST y además sirve
  el cliente web como archivos estáticos.
- **gochatservices (Go, puerto 8080):** mantiene las conexiones WebSocket
  concurrentes con Gorilla WebSocket. No accede directamente a la base de datos:
  cuando recibe un mensaje, lo persiste llamando a la API REST de FastAPI usando
  el token del usuario, y entrega el mensaje en vivo al destinatario conectado.
- **cliente (HTML/CSS/JS puro):** usa REST para registro, inicio de sesión,
  búsqueda, conversaciones e historial, y WebSocket para enviar y recibir
  mensajes en tiempo real, incluidos los recibos de lectura.

Ambos servicios comparten la misma `SECRET_KEY`, de modo que el servicio Go
puede validar localmente los tokens emitidos por FastAPI sin consultar la base
de datos en cada conexión.

---

## Estructura del proyecto

```
Sistema-de-Chat/
├── cliente/
│   ├── index.html        # Interfaz (login, registro, chat)
│   ├── style.css         # Estilos
│   └── app.js            # Lógica del cliente (REST + WebSocket)
├── gochatservices/
│   ├── handlers/websocket.go    # Endpoint /ws y ciclos de lectura/escritura
│   ├── models/message.go        # Frames del protocolo WebSocket
│   ├── services/chatservice.go  # Hub de conexiones y llamadas a FastAPI
│   ├── routes/routes.go         # Registro de rutas HTTP
│   ├── utils/config.go          # Configuración y validación de tokens
│   ├── Dockerfile
│   └── main.go
├── authservice/
│   ├── database/db.py           # Motor SQLModel y creación de tablas
│   ├── models/user.py           # Modelos User, Conversation, Message
│   ├── routes/auth.py           # Los 8 endpoints REST y autenticación
│   ├── security/hashing.py      # bcrypt + Salt + Pepper
│   ├── security/encryption.py   # AES-256-CBC
│   ├── Dockerfile
│   ├── .env
│   ├── requirements.txt
│   └── main.py
├── docs/                  # Informe técnico
├── docker-compose.yml
├── go.mod
├── go.sum
├── README.md
└── .gitignore
```

---

## Requisitos

**Con Docker (recomendado):**

- Docker y Docker Compose.

**Sin Docker:**

- Python 3.12 o superior.
- Go 1.26 o superior.
- Un navegador web moderno.

---

## Ejecución con Docker

Desde la raíz del repositorio:

```bash
docker compose up --build
```

Esto construye y levanta ambos servicios. Cuando estén activos, abre en el
navegador:

```
http://localhost:8000
```

La base de datos SQLite se crea automáticamente y se guarda en un volumen
persistente (`chat_data`), por lo que los datos sobreviven a los reinicios.

Para detener el sistema:

```bash
docker compose down
```

---

## Ejecución sin Docker

Se necesitan **dos terminales**.

**1) Servicio de autenticación y datos (FastAPI):**

```bash
cd authservice
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**2) Servicio de chat en tiempo real (Go):**

Desde la **raíz** del repositorio (para que `go.mod` y `authservice/.env`
sean visibles):

```bash
go run ./gochatservices
```

Finalmente, abre el cliente en el navegador:

```
http://localhost:8000
```

> Nota: al ejecutar sin Docker, el servicio Go lee la `SECRET_KEY` del archivo
> `authservice/.env`. Por eso debe iniciarse desde la raíz del repositorio.

---

## Variables de entorno

Se definen en `authservice/.env`:

| Variable            | Descripción                                                        |
|---------------------|--------------------------------------------------------------------|
| `PEPPER`            | Cadena secreta añadida a la contraseña antes del hashing (Pepper). |
| `AES_KEY`           | Clave AES-256 en hexadecimal (64 caracteres = 32 bytes).           |
| `SECRET_KEY`        | Clave para firmar los tokens de sesión (HMAC-SHA256).              |
| `DATABASE_URL`      | Cadena de conexión SQLite gestionada por SQLModel.                 |
| `TOKEN_TTL_SECONDS` | Tiempo de validez del token de sesión, en segundos.               |
| `CLIENT_DIR`        | Ruta de la carpeta del cliente web servida como archivos estáticos.|

> Los valores incluidos son de **desarrollo**. En un despliegue real deben
> reemplazarse por secretos generados aleatoriamente y no subirse a un
> repositorio público.

---

## Seguridad

**Contraseñas — bcrypt + Salt + Pepper.**
La contraseña nunca se almacena en texto plano. El proceso es:

1. Se concatena la contraseña con el **Pepper** (secreto global del `.env`).
2. Se aplica un pre-hash SHA-256 (evita el límite de 72 bytes de bcrypt).
3. Se aplica **bcrypt**, que añade automáticamente un **Salt** único por
   usuario (12 rondas de coste).

Solo se guarda el resultado en `password_hash`.

**Mensajes — AES-256-CBC.**
Cada mensaje se cifra con AES-256 en modo CBC. Se genera un **IV aleatorio** de
16 bytes por mensaje y se aplica relleno PKCS7. En la base de datos se almacena
únicamente `base64(IV || texto_cifrado)`. Al consultar una conversación, el
servidor descifra automáticamente para mostrar el contenido.

**Tokens de sesión — HMAC-SHA256.**
Al iniciar sesión se emite un token con formato `base64url(payload).hmac_hex`,
donde el payload contiene el id de usuario, el username y la expiración. La firma
se valida tanto en FastAPI (REST) como en Go (WebSocket) con la misma
`SECRET_KEY`.

---

## Base de datos

SQLite gestionada con SQLModel. Las tablas se crean automáticamente al iniciar
el servicio.

**users**

| Campo           | Tipo     | Detalle                  |
|-----------------|----------|--------------------------|
| id              | INTEGER  | Clave primaria           |
| first_name      | TEXT     |                          |
| last_name       | TEXT     |                          |
| username        | TEXT     | Único                    |
| password_hash   | TEXT     | Hash bcrypt              |
| created_at      | DATETIME |                          |

**conversations**

| Campo        | Tipo     | Detalle                       |
|--------------|----------|-------------------------------|
| id           | INTEGER  | Clave primaria                |
| user_one_id  | INTEGER  | Clave foránea → users.id      |
| user_two_id  | INTEGER  | Clave foránea → users.id      |
| created_at   | DATETIME |                               |

**messages**

| Campo             | Tipo     | Detalle                              |
|-------------------|----------|--------------------------------------|
| id                | INTEGER  | Clave primaria                       |
| conversation_id   | INTEGER  | Clave foránea → conversations.id     |
| sender_id         | INTEGER  | Clave foránea → users.id             |
| receiver_id       | INTEGER  | Clave foránea → users.id             |
| encrypted_message | TEXT     | Contenido cifrado (AES-256-CBC)      |
| created_at        | DATETIME |                                      |
| delivered         | BOOLEAN  | Entregado                            |
| read              | BOOLEAN  | Leído                                |

Estados del mensaje a partir de `delivered` y `read`:

- `delivered=false, read=false` → **enviado** (✓)
- `delivered=true, read=false` → **entregado** (✓✓)
- `read=true` → **leído** (✓✓ en azul)

---

## API REST (FastAPI)

| Método | Ruta                       | Descripción                              |
|--------|----------------------------|------------------------------------------|
| POST   | `/register`                | Registrar un usuario.                    |
| POST   | `/login`                   | Iniciar sesión y obtener un token.       |
| GET    | `/users/search?q=`         | Buscar usuarios por nombre de usuario.   |
| POST   | `/conversation/create`     | Crear u obtener una conversación.        |
| GET    | `/conversations`           | Listar las conversaciones del usuario.   |
| GET    | `/conversation/{id}`       | Obtener el historial de una conversación.|
| POST   | `/message/send`            | Guardar un mensaje (cifrado).            |
| PUT    | `/message/read/{id}`       | Marcar un mensaje como leído.            |

Todos los endpoints, salvo `/register` y `/login`, requieren el encabezado
`Authorization: Bearer <token>`.

---

## WebSockets (Go · Gorilla)

Punto de conexión: `ws://localhost:8080/ws?token=<token>`.

**Frames del cliente al servidor:**

- `{"type":"send", "temp_id":"...", "conversation_id":1, "receiver_id":2, "content":"hola"}`
- `{"type":"read", "message_ids":[10,11,12]}`

**Frames del servidor al cliente:**

- `{"type":"sent", ...}` — confirmación de guardado al remitente.
- `{"type":"message", ...}` — mensaje entrante en tiempo real.
- `{"type":"read", ...}` — aviso de lectura al remitente.
- `{"type":"error", "detail":"..."}` — notificación de error.

---

## Docker

- `authservice/Dockerfile`: imagen de FastAPI (Python 3.12) que también copia y
  sirve el cliente web.
- `gochatservices/Dockerfile`: compilación multietapa de Go que produce un
  binario estático ejecutado sobre Alpine.
- `docker-compose.yml`: orquesta ambos servicios, comparte el archivo `.env` y
  define el volumen persistente de la base de datos.

---

## Autores

Estudiantes de Ingeniería en Sistemas — UIDE:

- Joaquín Carranza
- Gabriel Terán
- Jedermin Ulco
