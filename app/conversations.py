from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.schemas import Category, ConversationOut, ConversationUpdate, MessageOut, SourceOut
from db.models import Chunk, Conversation, Message, RetrievalLog, User
from db.session import get_db

router = APIRouter()


def get_owned_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    # 404 (not 403) for other users' chats, so ids of other users' chats are not revealed.
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _to_out(c: Conversation) -> ConversationOut:
    return ConversationOut(id=c.id, title=c.title, category=c.category, created_at=c.created_at, updated_at=c.updated_at)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    category: Category | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Conversation).filter(Conversation.user_id == user.id)
    if category is not None:
        q = q.filter(Conversation.category == category)
    return [_to_out(c) for c in q.order_by(Conversation.updated_at.desc(), Conversation.id.desc())]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = get_owned_conversation(db, user, conversation_id)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )

    # Sources of every assistant message in one query, rebuilt from retrieval_logs.
    sources: dict[int, list[SourceOut]] = defaultdict(list)
    rows = (
        db.query(RetrievalLog, Chunk)
        .join(Chunk, RetrievalLog.chunk_id == Chunk.id)
        .filter(RetrievalLog.message_id.in_([m.id for m in messages]))
        .order_by(RetrievalLog.message_id, RetrievalLog.rank)
        .all()
    )
    for log, chunk in rows:
        sources[log.message_id].append(SourceOut(
            rank=log.rank, score=log.score, source_file=chunk.source_file,
            section_title=chunk.section_title, doc_url=chunk.doc_url,
        ))

    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at, sources=sources.get(m.id, []))
        for m in messages
    ]


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: int, body: ConversationUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    conversation = get_owned_conversation(db, user, conversation_id)
    conversation.title = body.title.strip()[:255] or conversation.title
    db.commit()
    return _to_out(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = get_owned_conversation(db, user, conversation_id)
    db.delete(conversation)  # messages and their retrieval_logs cascade
    db.commit()
