import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, or_, select

from database.db import get_session
from models.user import Conversation, Message, User
from security.encryption import decrypt_message, encrypt_message
from security.hashing import hash_password, verify_password

router = APIRouter()

class RegisterIn(BaseModel):
    first_name: str
    last_name: str
    username: str
    password: str

class LoginIn(BaseModel):
    username: str
    password: str

class ConversationCreateIn(BaseModel):
    other_user_id: int

class MessageSendIn(BaseModel):
    conversation_id: int
    receiver_id: int
    content: str
    delivered: bool = False

class UserPublic(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str

class LoginOut(UserPublic):
    token: str

class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    receiver_id: int
    content: str
    created_at: datetime
    delivered: bool
    read: bool

class ConversationOut(BaseModel):
    id: int
    user_one_id: int
    user_two_id: int
    created_at: datetime
    other_user: UserPublic
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0

class ConversationDetailOut(BaseModel):
    id: int
    user_one_id: int
    user_two_id: int
    other_user: UserPublic
    messages: List[MessageOut]

def _secret_key() -> bytes:
    return os.getenv("SECRET_KEY", "").encode("utf-8")

def _token_ttl() -> int:
    try:
        return int(os.getenv("TOKEN_TTL_SECONDS", "86400"))
    except ValueError:
        return 86400

def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "exp": int(time.time()) + _token_ttl(),
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b"=")
    signature = hmac.new(_secret_key(), payload_b64, hashlib.sha256).hexdigest()
    return payload_b64.decode("utf-8") + "." + signature

def decode_token(token: str) -> dict:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Formato de token inválido.") from exc

    expected = hmac.new(
        _secret_key(), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Firma de token inválida.")

    padding = "=" * (-len(payload_b64) % 4)
    payload_json = base64.urlsafe_b64decode(payload_b64 + padding)
    payload = json.loads(payload_json)

    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expirado.")
    return payload

def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado de autorización.",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user = session.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado."
        )
    return user

def _public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )

def _ensure_participant(conversation: Conversation, user_id: int) -> None:
    if user_id not in (conversation.user_one_id, conversation.user_two_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No perteneces a esta conversación.",
        )

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, session: Session = Depends(get_session)):
    """Registra un nuevo usuario (estilo Instagram: sin correo electrónico)."""
    first_name = data.first_name.strip()
    last_name = data.last_name.strip()
    username = data.username.strip()
    password = data.password

    if not first_name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío.")
    if not last_name:
        raise HTTPException(status_code=400, detail="El apellido no puede estar vacío.")
    if not username:
        raise HTTPException(
            status_code=400, detail="El nombre de usuario no puede estar vacío."
        )
    if not password:
        raise HTTPException(
            status_code=400, detail="La contraseña no puede estar vacía."
        )
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="El nombre de usuario ya está en uso."
        )
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _public(user)

@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, session: Session = Depends(get_session)):
    username = data.username.strip()
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail="Usuario o contraseña incorrectos."
        )
    return LoginOut(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        token=create_token(user),
    )

@router.get("/users/search", response_model=List[UserPublic])
def search_users(
    q: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    pattern = f"%{q.strip()}%"
    users = session.exec(
        select(User)
        .where(User.username.like(pattern))
        .where(User.id != current_user.id)
        .limit(20)
    ).all()
    return [_public(u) for u in users]

@router.post("/conversation/create", response_model=ConversationOut)
def create_conversation(
    data: ConversationCreateIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if data.other_user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="No puedes crear una conversación contigo mismo."
        )
    other = session.get(User, data.other_user_id)
    if not other:
        raise HTTPException(status_code=404, detail="Usuario destino no encontrado.")

    a, b = current_user.id, other.id
    conversation = session.exec(
        select(Conversation).where(
            or_(
                (Conversation.user_one_id == a) & (Conversation.user_two_id == b),
                (Conversation.user_one_id == b) & (Conversation.user_two_id == a),
            )
        )
    ).first()
    if not conversation:
        conversation = Conversation(user_one_id=a, user_two_id=b)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
    return ConversationOut(
        id=conversation.id,
        user_one_id=conversation.user_one_id,
        user_two_id=conversation.user_two_id,
        created_at=conversation.created_at,
        other_user=_public(other),
    )

@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    conversations = session.exec(
        select(Conversation).where(
            or_(
                Conversation.user_one_id == current_user.id,
                Conversation.user_two_id == current_user.id,
            )
        )
    ).all()
    result: List[ConversationOut] = []
    for conv in conversations:
        other_id = (
            conv.user_two_id
            if conv.user_one_id == current_user.id
            else conv.user_one_id
        )
        other = session.get(User, other_id)
        if not other:
            continue
        last = session.exec(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
        ).first()
        unread = len(
            session.exec(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .where(Message.receiver_id == current_user.id)
                .where(Message.read == False)  # noqa: E712
            ).all()
        )
        result.append(
            ConversationOut(
                id=conv.id,
                user_one_id=conv.user_one_id,
                user_two_id=conv.user_two_id,
                created_at=conv.created_at,
                other_user=_public(other),
                last_message=decrypt_message(last.encrypted_message) if last else None,
                last_message_at=last.created_at if last else conv.created_at,
                unread_count=unread,
            )
        )
    result.sort(key=lambda c: c.last_message_at or c.created_at, reverse=True)
    return result

@router.get("/conversation/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    _ensure_participant(conversation, current_user.id)

    other_id = (
        conversation.user_two_id
        if conversation.user_one_id == current_user.id
        else conversation.user_one_id
    )
    other = session.get(User, other_id)

    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    ).all()

    return ConversationDetailOut(
        id=conversation.id,
        user_one_id=conversation.user_one_id,
        user_two_id=conversation.user_two_id,
        other_user=_public(other),
        messages=[
            MessageOut(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_id=m.sender_id,
                receiver_id=m.receiver_id,
                content=decrypt_message(m.encrypted_message),
                created_at=m.created_at,
                delivered=m.delivered,
                read=m.read,
            )
            for m in messages
        ],
    )

@router.post("/message/send", response_model=MessageOut)
def send_message(
    data: MessageSendIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    conversation = session.get(Conversation, data.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    _ensure_participant(conversation, current_user.id)
    _ensure_participant(conversation, data.receiver_id)

    content = data.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    message = Message(
        conversation_id=data.conversation_id,
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        encrypted_message=encrypt_message(content),
        delivered=data.delivered,
        read=False,
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        receiver_id=message.receiver_id,
        content=content,
        created_at=message.created_at,
        delivered=message.delivered,
        read=message.read,
    )

@router.put("/message/read/{message_id}", response_model=MessageOut)
def mark_read(
    message_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")
    if message.receiver_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Solo el destinatario puede marcar como leído."
        )

    message.delivered = True
    message.read = True
    session.add(message)
    session.commit()
    session.refresh(message)

    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        receiver_id=message.receiver_id,
        content=decrypt_message(message.encrypted_message),
        created_at=message.created_at,
        delivered=message.delivered,
        read=message.read,
    )