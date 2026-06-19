from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, create_engine, Session, select
from pydantic import BaseModel
import base64

from models.user import User
from routes.auth import hash_password, verify_password

app = FastAPI()

# =========================
# 🔥 CORS (ARREGLA ERROR OPTIONS 405)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# DB
# =========================
engine = create_engine("sqlite:///database.db")
SQLModel.metadata.create_all(engine)

active_tokens = {}

# =========================
# MODELOS
# =========================
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str

# =========================
# REGISTER (FIXED)
# =========================
@app.post("/register")
def register(data: RegisterRequest):

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
    