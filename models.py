from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy import Table, ForeignKey, Column, Integer, String, MetaData, DateTime, UniqueConstraint
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

metadata = MetaData()

groups = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("name", String, nullable=False),
    Column("created_at", DateTime(timezone=True), default=datetime.utcnow, nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
)

repositories = Table(
    "messages",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("text", Text, nullable=False),
    Column("senser", ForeignKey="users.id"),
    Column("recipient", ForeignKey="users.id"),
    Column("send_time", DateTime(timezone=True), default=datetime.utcnow, nullable=False),
    Column("readed_at", DateTime(timezone=True), nullable=True),
)