from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
from typing import List
from pgvector.sqlalchemy import Vector

EMBEDDING_DIM = 1536  # text-embedding-3-small

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__= 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")



class Conversation(Base):
    __tablename__ = 'conversations'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(15))
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation_id: Mapped[int] = mapped_column(ForeignKey('conversations.id'))
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    retrieval_logs: Mapped[List["RetrievalLog"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = 'chunks'

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255))
    section_title: Mapped[str] = mapped_column(String(255))
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    retrieval_logs: Mapped[List["RetrievalLog"]] = relationship(back_populates="chunk")


class RetrievalLog(Base):
    __tablename__ = 'retrieval_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    message_id: Mapped[int] = mapped_column(ForeignKey('messages.id'))
    message: Mapped["Message"] = relationship(back_populates="retrieval_logs")

    chunk_id: Mapped[int] = mapped_column(ForeignKey('chunks.id'))
    chunk: Mapped["Chunk"] = relationship(back_populates="retrieval_logs")



