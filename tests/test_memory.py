"""Conversation memory: trimming, history window, what /chat sends to the router,
retrieval and LLM, and the router fallback."""
from types import SimpleNamespace

import app.router as router
from app.memory import enc, history_messages, load_history, trim_assistant
from db.models import Conversation, Message, User
from db.session import SessionLocal
from tests.test_conversations import fake_pipeline, make_client, secret  # noqa: F401 (fixtures)


def test_trim_assistant_drops_sources_and_citations():
    answer = "**VALUE LINE** là câu kết [1]. Ví dụ [1][3].\n\nNguồn tham khảo:\n[1] file.docx > Value line"
    assert trim_assistant(answer, 300) == "**VALUE LINE** là câu kết. Ví dụ."


def test_trim_assistant_caps_tokens():
    long = "từ " * 1000
    trimmed = trim_assistant(long, 50)
    assert len(enc.encode(trimmed)) <= 52 and trimmed.endswith("…")


def test_load_history_returns_last_turns_oldest_first():
    with SessionLocal() as db:
        user = User(name="test", google_sub="test-memory-window")
        db.add(user)
        db.flush()
        conv = Conversation(title="t", user_id=user.id, category="part2")
        db.add(conv)
        db.flush()
        for i in range(1, 6):
            db.add(Message(role="user", content=f"q{i}", token_count=0, conversation_id=conv.id))
            db.add(Message(role="assistant", content=f"a{i}", token_count=0, conversation_id=conv.id))
        db.flush()
        try:
            history = load_history(db, conv.id, turns=2)
            assert [m.content for m in history] == ["q4", "a4", "q5", "a5"]
            assert history_messages(history)[0] == {"role": "user", "content": "q4"}
            assert load_history(db, conv.id, turns=0) == []
        finally:
            db.rollback()


def test_chat_sends_history_and_searches_standalone_query(make_client, fake_pipeline):  # noqa: F811
    client = make_client()
    cid = client.post("/chat", json={"query": "value line là gì", "category": "part2"}).json()["conversation_id"]
    client.post("/chat", json={"query": "cho ví dụ ý 2", "conversation_id": cid})

    # First question: no history. Second: the first exchange is replayed.
    assert fake_pipeline.route_calls[0]["history_text"] == ""
    assert "Learner: value line là gì" in fake_pipeline.route_calls[1]["history_text"]
    assert fake_pipeline.searched == ["standalone: value line là gì", "standalone: cho ví dụ ý 2"]

    second = fake_pipeline.llm_messages[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1]["content"] == "value line là gì"
    assert second[2]["content"] == "answer"  # "[1]" stripped from the replayed answer
    assert second[3]["content"] == "cho ví dụ ý 2"  # the LLM answers the original wording


def test_router_falls_back_to_original_query(monkeypatch):
    def boom(**kw):
        raise RuntimeError("openai down")

    monkeypatch.setattr(router.client.chat.completions, "parse", boom)
    decision = router.route("cho ví dụ ý 2", history_text="Learner: value line là gì")
    assert decision.should_retrieve and decision.standalone_query == "cho ví dụ ý 2"


def test_router_uses_rewrite_and_sees_history(monkeypatch):
    seen = {}

    def fake_parse(**kw):
        seen["user"] = kw["messages"][1]["content"]
        parsed = router.RouteDecision(should_retrieve=True, category="part2", top_k=20, standalone_query="  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    monkeypatch.setattr(router.client.chat.completions, "parse", fake_parse)
    decision = router.route("cho ví dụ", history_text="Learner: value line là gì", summary="Đang học value line")
    assert "Recent conversation:\nLearner: value line là gì" in seen["user"]
    assert "Summary of earlier conversation:\nĐang học value line" in seen["user"]
    assert seen["user"].endswith("NEW question:\ncho ví dụ")
    assert decision.top_k == router.MAX_TOP_K  # still clamped
    assert decision.standalone_query == "cho ví dụ"  # blank rewrite falls back to the question
