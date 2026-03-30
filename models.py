# models.py
from sqlalchemy import create_engine, Table, Column, String, Text, MetaData, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
import os

DB_USER = "postgres"  # или ваш реальный пользователь
DB_PASSWORD = "supersecret"  # ваш реальный пароль
DB_HOST = "postgres"
DB_PORT = "5432"
DB_NAME = "projector"

DATABASE_URL = "postgresql://username:password@localhost:5432/messenger_db"

# Если вы используете переменные окружения
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/messenger_db")

# Создаем engine для PostgreSQL
engine = create_engine(DATABASE_URL, echo=True, pool_size=10, max_overflow=20)

# Создаем metadata
metadata = MetaData()

# Определение таблицы users
users = Table(
    "users",
    metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
)

# Определение таблицы messages
messages = Table(
    "messages",
    metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("text", Text, nullable=False),
    Column("sender", String(36), ForeignKey("users.id", ondelete="SET NULL")),
    Column("recipient", String(36), ForeignKey("users.id", ondelete="SET NULL")),
    Column("send_time", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("readed_at", DateTime(timezone=True), nullable=True),
)

# Создание индексов для оптимизации запросов
from sqlalchemy import Index
Index('idx_messages_sender', messages.c.sender)
Index('idx_messages_recipient', messages.c.recipient)
Index('idx_messages_send_time', messages.c.send_time)
Index('idx_users_name', users.c.name)

# Создание таблиц
try:
    metadata.create_all(engine)
    print("✅ Таблицы успешно созданы в PostgreSQL")
    print(f"   База данных: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
except Exception as e:
    print(f"❌ Ошибка при создании таблиц: {e}")
    print("   Убедитесь, что PostgreSQL запущен и параметры подключения верны")

# Для проверки, что экспортируется
__all__ = ['users', 'messages', 'engine', 'metadata']