import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from database.db import create_db_and_tables  # noqa: E402
from routes.auth import router as auth_router  # noqa: E402

app = FastAPI(title="Sistema de Chat - Auth Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Crea la base de datos y las tablas si no existen."""
    create_db_and_tables()


@app.get("/health")
def health() -> dict:
    """Endpoint simple para verificar que el servicio está activo."""
    return {"status": "ok", "service": "authservice"}

app.include_router(auth_router)

<<<<<<< HEAD
    if not data.username.strip():
        raise HTTPException(
            status_code=400,
            detail="El nombre de usuario es obligatorio"
        )

    if not data.password.strip():
        raise HTTPException(
            status_code=400,
            detail="La contraseña es obligatoria"
        )

    with Session(engine) as session:

        existing_user = session.exec(
            select(User).where(User.username == data.username)
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Ese nombre de usuario ya está registrado"
            )

        hashed_password = hash_password(data.password)

        user = User(
            username=data.username,
            password=hashed_password
        )

        session.add(user)
        session.commit()

    return {
        "message": "Usuario registrado"
    }

# =========================
# LOGIN (FIXED)
# =========================
@app.post("/login")
def login(data: LoginRequest):

    with Session(engine) as session:
        statement = select(User).where(User.username == data.username)
        user = session.exec(statement).first()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if not verify_password(data.password, user.password):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

        token = base64.b64encode(data.username.encode()).decode()
        active_tokens[token] = data.username

        return {
            "token": token,
            "username": data.username
        }

# =========================
# VERIFY TOKEN
# =========================
@app.get("/verify-token")
def verify_token(token: str):

    username = active_tokens.get(token)

    if not username:
        raise HTTPException(status_code=401, detail="Token inválido")

    return {
        "valid": True,
        "username": username
    }

# =========================
# LOGOUT
# =========================
@app.post("/logout")
def logout(token: str):

    if token in active_tokens:
        del active_tokens[token]

    return {"message": "Sesión cerrada"}
    
=======
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CLIENT_DIR = os.getenv("CLIENT_DIR") or os.path.join(_BASE_DIR, "..", "cliente")
if os.path.isdir(_CLIENT_DIR):
    app.mount("/", StaticFiles(directory=_CLIENT_DIR, html=True), name="cliente")
>>>>>>> 5b64070bc752a27436172e15cbe32d2ca1eb1f1c
