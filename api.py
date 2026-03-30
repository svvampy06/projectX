from typing import List, Dict, Optional
import logging
from datetime import datetime
import uuid  # Добавьте эту строку

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from models import users, messages, engine
from database import get_db

logger = logging.getLogger("app.api")
router = APIRouter()

# Pydantic схемы для запросов и ответов
class UserCreate(BaseModel):
    name: str

class UserOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    last_login: Optional[datetime] = None

class MessageCreate(BaseModel):
    text: str
    sender_id: str
    recipient_id: str

class MessageOut(BaseModel):
    id: str
    text: str
    sender_id: Optional[str]
    recipient_id: Optional[str]
    send_time: datetime
    readed_at: Optional[datetime] = None

# Эндпоинты для пользователей
@router.post(
    "/api/users",
    response_model=UserOut,
    summary="Создать нового пользователя"
)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Создание нового пользователя"""
    try:
        new_user_id = str(uuid.uuid4())
        stmt = users.insert().values(
            id=new_user_id,
            name=user.name,
            created_at=datetime.utcnow()
        ).returning(users)
        
        result = await db.execute(stmt)
        await db.commit()
        
        created_user = result.fetchone()
        if created_user:
            return UserOut(**created_user._asdict())
        raise HTTPException(status_code=500, detail="Failed to create user")
    except Exception as e:
        logger.exception("Error creating user")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/api/users/{user_id}",
    response_model=UserOut,
    summary="Получить информацию о пользователе"
)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Получение пользователя по ID"""
    try:
        stmt = select(users).where(users.c.id == user_id)
        result = await db.execute(stmt)
        user = result.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserOut(**user._asdict())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting user")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/api/users",
    response_model=List[UserOut],
    summary="Получить список всех пользователей"
)
async def list_users(db: AsyncSession = Depends(get_db)):
    """Получение списка всех пользователей"""
    try:
        stmt = select(users).order_by(users.c.created_at.desc())
        result = await db.execute(stmt)
        users_list = result.fetchall()
        
        return [UserOut(**user._asdict()) for user in users_list]
    except Exception as e:
        logger.exception("Error listing users")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/api/users/{user_id}/last-login",
    response_model=UserOut,
    summary="Обновить время последнего входа пользователя"
)
async def update_last_login(user_id: str, db: AsyncSession = Depends(get_db)):
    """Обновление времени последнего входа пользователя"""
    try:
        stmt = users.update().where(users.c.id == user_id).values(
            last_login=datetime.utcnow()
        ).returning(users)
        
        result = await db.execute(stmt)
        await db.commit()
        
        updated_user = result.fetchone()
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserOut(**updated_user._asdict())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating last login")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинты для сообщений
@router.post(
    "/api/messages",
    response_model=MessageOut,
    summary="Отправить новое сообщение"
)
async def send_message(message: MessageCreate, db: AsyncSession = Depends(get_db)):
    """Создание нового сообщения"""
    try:
        # Проверяем существование отправителя и получателя
        sender_stmt = select(users).where(users.c.id == message.sender_id)
        recipient_stmt = select(users).where(users.c.id == message.recipient_id)
        
        sender_result = await db.execute(sender_stmt)
        recipient_result = await db.execute(recipient_stmt)
        
        if not sender_result.fetchone():
            raise HTTPException(status_code=404, detail="Sender not found")
        if not recipient_result.fetchone():
            raise HTTPException(status_code=404, detail="Recipient not found")
        
        # Создаем сообщение
        new_message_id = str(uuid.uuid4())
        stmt = messages.insert().values(
            id=new_message_id,
            text=message.text,
            sender=message.sender_id,
            recipient=message.recipient_id,
            send_time=datetime.utcnow()
        ).returning(messages)
        
        result = await db.execute(stmt)
        await db.commit()
        
        created_message = result.fetchone()
        if created_message:
            return MessageOut(**created_message._asdict())
        raise HTTPException(status_code=500, detail="Failed to create message")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error sending message")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/api/messages/{message_id}",
    response_model=MessageOut,
    summary="Получить сообщение по ID"
)
async def get_message(message_id: str, db: AsyncSession = Depends(get_db)):
    """Получение сообщения по ID"""
    try:
        stmt = select(messages).where(messages.c.id == message_id)
        result = await db.execute(stmt)
        message = result.fetchone()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return MessageOut(**message._asdict())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting message")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/api/users/{user_id}/messages",
    response_model=List[MessageOut],
    summary="Получить все сообщения пользователя"
)
async def get_user_messages(
    user_id: str,
    unread_only: bool = Query(False, description="Только непрочитанные сообщения"),
    db: AsyncSession = Depends(get_db)
):
    """Получение всех сообщений пользователя (как отправленных, так и полученных)"""
    try:
        # Проверяем существование пользователя
        user_stmt = select(users).where(users.c.id == user_id)
        user_result = await db.execute(user_stmt)
        if not user_result.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Формируем запрос для сообщений
        stmt = select(messages).where(
            or_(messages.c.sender == user_id, messages.c.recipient == user_id)
        ).order_by(messages.c.send_time.desc())
        
        if unread_only:
            stmt = stmt.where(messages.c.readed_at.is_(None))
        
        result = await db.execute(stmt)
        user_messages = result.fetchall()
        
        return [MessageOut(**msg._asdict()) for msg in user_messages]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting user messages")
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/api/messages/{message_id}/read",
    response_model=MessageOut,
    summary="Отметить сообщение как прочитанное"
)
async def mark_message_as_read(message_id: str, db: AsyncSession = Depends(get_db)):
    """Отметка сообщения как прочитанного"""
    try:
        stmt = messages.update().where(messages.c.id == message_id).values(
            readed_at=datetime.utcnow()
        ).returning(messages)
        
        result = await db.execute(stmt)
        await db.commit()
        
        updated_message = result.fetchone()
        if not updated_message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return MessageOut(**updated_message._asdict())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error marking message as read")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/api/conversation/{user1_id}/{user2_id}",
    response_model=List[MessageOut],
    summary="Получить переписку между двумя пользователями"
)
async def get_conversation(
    user1_id: str,
    user2_id: str,
    limit: int = Query(50, ge=1, le=200, description="Максимальное количество сообщений"),
    db: AsyncSession = Depends(get_db)
):
    """Получение переписки между двумя пользователями"""
    try:
        # Проверяем существование обоих пользователей
        for uid in [user1_id, user2_id]:
            user_stmt = select(users).where(users.c.id == uid)
            user_result = await db.execute(user_stmt)
            if not user_result.fetchone():
                raise HTTPException(status_code=404, detail=f"User {uid} not found")
        
        # Получаем сообщения между пользователями
        stmt = select(messages).where(
            or_(
                (messages.c.sender == user1_id) & (messages.c.recipient == user2_id),
                (messages.c.sender == user2_id) & (messages.c.recipient == user1_id)
            )
        ).order_by(messages.c.send_time.desc()).limit(limit)
        
        result = await db.execute(stmt)
        conversation = result.fetchall()
        
        return [MessageOut(**msg._asdict()) for msg in conversation]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting conversation")
        raise HTTPException(status_code=500, detail=str(e))