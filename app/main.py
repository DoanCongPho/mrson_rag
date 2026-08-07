from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.tracing
from app.llm import build_prompt, client
from app.retrieval import retrieve
from app.schemas import ChatRequest, ChatResponse, SourceOut
from db.models import Conversation, Message, RetrievalLog, User
from db.session import get_db

app = FastAPI(title="Mr Son RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_or_create_user(db: Session, name: str) -> User:
    user = db.query(User).filter(User.name == name).first()
    if user is None:
        user = User(name=name)
        db.add(user)
        db.flush()
    return user


def get_or_create_conversation(
    db: Session, user: User, conversation_id: int | None, title: str
) -> Conversation:
    if conversation_id is not None:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
            .first()
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    conversation = Conversation(title=title[:255], user_id=user.id)
    db.add(conversation)
    db.flush()
    return conversation


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    user = get_or_create_user(db, request.user_name)
    conversation = get_or_create_conversation(
        db, user, request.conversation_id, title=request.query
    )

    results = retrieve(request.query)
    chunks = [chunk for chunk, _ in results]
    prompt = build_prompt(chunks)

    user_message = Message(
        role="user",
        content=request.query,
        token_count=0,
        conversation_id=conversation.id,
    )
    db.add(user_message)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
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
    for rank, (chunk, distance) in enumerate(results, start=1):
        score = 1 - distance
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
            )
        )

    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        sources=sources,
    )
