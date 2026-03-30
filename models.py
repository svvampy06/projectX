# models.py
from sqlalchemy import UUID, create_engine, Table, Column, String, Text, MetaData, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
# models.py
import os

# Используйте переменные окружения или правильные значения для Docker
DB_USER = os.getenv("DB_USERNAME", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "supersecret")
DB_HOST = os.getenv("DB_HOST", "postgres")  # В Docker это "postgres", не localhost
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "projector")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=True, pool_size=10, max_overflow=20)


metadata = MetaData()


users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
)

# Исправленное определение таблицы messages
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