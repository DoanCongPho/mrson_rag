from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

import app.tracing
from app.auth import get_current_user, router as auth_router
from app.context import to_context
from app.conversations import get_owned_conversation, router as conversations_router
from app.llm import build_prompt, client
from app.memory import history_as_text, history_messages, load_history, update_summary
from app.retrieval import retrieve
from app.router import route
from app.schemas import ChatRequest, ChatResponse, SourceOut
from db.models import Conversation, Message, RetrievalLog, User
from config import settings
from db.session import check_connection, get_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load and warm up the reranker and open the first DB connection at startup,
    # so the first request doesn't pay for them.
    if settings.reranker_enabled:
        from app import reranker

        reranker.warmup()
    check_connection()
    yield


app = FastAPI(title="Mr Son RAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Cookies require explicit origins (not "*") and allow_credentials.
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(conversations_router)


NO_RETRIEVAL_ANSWER = "Mr.Son: Hỏi gì thiếu minh bạch rõ ràng."


def check_daily_limit(db: Session, user: User) -> None:
    if settings.daily_message_limit <= 0:
        return
    sent = (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user.id,
            Message.role == "user",
            Message.created_at >= func.now() - timedelta(days=1),
        )
        .scalar()
    )
    if sent >= settings.daily_message_limit:
        raise HTTPException(status_code=429, detail="Daily message limit reached")


def get_or_create_conversation(db: Session, user: User, request: ChatRequest) -> Conversation:
    if request.conversation_id is not None:
        conversation = get_owned_conversation(db, user, request.conversation_id)
        if request.category and conversation.category and request.category != conversation.category:
            raise HTTPException(status_code=400, detail="Conversation belongs to another mode")
        return conversation

    if request.category is None:
        raise HTTPException(status_code=400, detail="category is required for a new conversation")
    conversation = Conversation(title=request.query[:255], user_id=user.id, category=request.category)
    db.add(conversation)
    db.flush()
    return conversation


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_daily_limit(db, user)
    conversation = get_or_create_conversation(db, user, request)
    conversation.updated_at = func.now()
    # Loaded before the new question is saved, so it is not part of its own history.
    history = load_history(db, conversation.id)

    user_message = Message(
        role="user",
        content=request.query,
        token_count=0,
        conversation_id=conversation.id,
    )
    db.add(user_message)

    router_history = history[-2 * settings.router_history_turns:] if settings.router_history_turns > 0 else []
    decision = route(
        request.query,
        history_text=history_as_text(router_history, settings.history_message_max_tokens),
        summary=conversation.summary,
    )

    if not decision.should_retrieve:
        db.add(Message(role="assistant", content=NO_RETRIEVAL_ANSWER, token_count=0, conversation_id=conversation.id))
        db.commit()
        background_tasks.add_task(update_summary, conversation.id)
        return ChatResponse(conversation_id=conversation.id, answer=NO_RETRIEVAL_ANSWER, sources=[])

    # The chat's stored mode wins; old chats without one fall back to the router's choice.
    category = conversation.category or (None if decision.category == "all" else decision.category)
    # Search with the rewritten question so follow-ups ("cho ví dụ ý 2") find the right chunks.
    results = retrieve(
        decision.standalone_query,
        top_k=decision.top_k,
        category=category,
    )
    prompt = build_prompt(to_context([chunk for chunk, _ in results]), summary=conversation.summary)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                *history_messages(history),
                {"role": "user", "content": request.query},
            ],
            temperature=0.8,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="LLM request failed") from exc

    answer = response.choices[0].message.content
    usage = response.usage

    if usage is not None:
        user_message.token_count = usage.prompt_tokens

    assistant_message = Message(
        role="assistant",
        content=answer,
        token_count=usage.completion_tokens if usage is not None else 0,
        conversation_id=conversation.id,
    )
    db.add(assistant_message)
    db.flush()

    sources = []
    for rank, (chunk, score) in enumerate(results, start=1):
        db.add(
            RetrievalLog(
                score=score,
                rank=rank,
                message_id=assistant_message.id,
                chunk_id=chunk.id,
            )
        )
        sources.append(
            SourceOut(
                rank=rank,
                score=score,
                source_file=chunk.source_file,
                section_title=chunk.section_title,
                doc_url=chunk.doc_url,
            )
        )

    db.commit()
    # After the response is sent: fold messages that left the history window into the summary.
    background_tasks.add_task(update_summary, conversation.id)

    return ChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        sources=sources,
    )
