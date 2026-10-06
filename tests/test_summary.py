"""Rolling summary: what gets folded, batching, no double folding, and the summary
reaching the router and the answer prompt."""
import uuid
from types import SimpleNamespace

import pytest

import app.memory as memory
from app.llm import build_prompt
from config import settings
from db.models import Conversation, Message, User
from db.session import SessionLocal
from tests.test_conversations import fake_pipeline, make_client, secret  # noqa: F401 (fixtures)


@pytest.fixture
def small_window(monkeypatch):
    monkeypatch.setattr(settings, "history_turns", 1)  # window = last 2 messages
    monkeypatch.setattr(settings, "summary_batch_turns", 1)  # fold every exchange that leaves it


@pytest.fixture
def fake_summarizer(monkeypatch):
    calls = []
    # /chat uses the same OpenAI client: answer only summary requests, pass the rest on.
    passthrough = memory.client.chat.completions.create

    def create(**kw):
        if not kw["messages"][0]["content"].startswith("You maintain a running summary"):
            return passthrough(**kw)
        calls.append(kw["messages"][1]["content"])
        text = f"summary #{len(calls)}"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    monkeypatch.setattr(memory.client.chat.completions, "create", create)
    return calls


@pytest.fixture
def conversation():
    with SessionLocal() as db:
        user = User(name="test", google_sub=f"test-{uuid.uuid4()}")
        db.add(user)
        db.flush()
        conv = Conversation(title="t", user_id=user.id, category="part2")
        db.add(conv)
        db.commit()
        ids = SimpleNamespace(user=user.id, conv=conv.id)
    yield ids
    with SessionLocal() as db:
        db.delete(db.get(User, ids.user))
        db.commit()


def add_exchanges(conv_id, start, count):
    with SessionLocal() as db:
        for i in range(start, start + count):
            db.add(Message(role="user", content=f"q{i}", token_count=0, conversation_id=conv_id))
            db.add(Message(role="assistant", content=f"a{i} [1]\n\nNguồn tham khảo:\n[1] x", token_count=0,
                           conversation_id=conv_id))
        db.commit()


def summary_state(conv_id):
    with SessionLocal() as db:
        c = db.get(Conversation, conv_id)
        last = db.query(Message.id).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
        return c.summary, c.summary_until_message_id, [m.id for m in last]


def test_nothing_to_fold_inside_window(conversation, small_window, fake_summarizer):
    add_exchanges(conversation.conv, 1, 1)
    memory.update_summary(conversation.conv)
    assert fake_summarizer == [] and summary_state(conversation.conv)[0] is None


def test_folds_only_messages_outside_window(conversation, small_window, fake_summarizer):
    add_exchanges(conversation.conv, 1, 3)
    memory.update_summary(conversation.conv)
    summary, until, ids = summary_state(conversation.conv)
    assert summary == "summary #1"
    assert until == ids[3]  # q1 a1 q2 a2 folded; q3 a3 still in the window
    folded = fake_summarizer[0]
    assert "Learner: q1" in folded and "Learner: q2" in folded and "q3" not in folded
    assert "Nguồn tham khảo" not in folded and "[1]" not in folded
    assert "EXISTING SUMMARY:\n(none)" in folded

    # Running again folds nothing new.
    memory.update_summary(conversation.conv)
    assert len(fake_summarizer) == 1

    # Next exchange pushes q3/a3 out: merged with the existing summary.
    add_exchanges(conversation.conv, 4, 1)
    memory.update_summary(conversation.conv)
    summary, until, ids = summary_state(conversation.conv)
    assert summary == "summary #2" and until == ids[5]
    assert "EXISTING SUMMARY:\nsummary #1" in fake_summarizer[1] and "q1" not in fake_summarizer[1]


def test_waits_for_a_full_batch(conversation, small_window, fake_summarizer, monkeypatch):
    monkeypatch.setattr(settings, "summary_batch_turns", 2)
    add_exchanges(conversation.conv, 1, 2)  # only 1 exchange outside the window
    memory.update_summary(conversation.conv)
    assert fake_summarizer == []
    add_exchanges(conversation.conv, 3, 1)  # now 2
    memory.update_summary(conversation.conv)
    assert len(fake_summarizer) == 1


def test_concurrent_update_is_not_overwritten(conversation, small_window, monkeypatch):
    add_exchanges(conversation.conv, 1, 3)

    def create(**kw):
        # Another worker advances the summary while this LLM call is running.
        with SessionLocal() as db:
            c = db.get(Conversation, conversation.conv)
            c.summary, c.summary_until_message_id = "other worker", 1
            db.commit()
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="stale"))])

    monkeypatch.setattr(memory.client.chat.completions, "create", create)
    memory.update_summary(conversation.conv)
    assert summary_state(conversation.conv)[0] == "other worker"


def test_llm_failure_keeps_old_summary(conversation, small_window, monkeypatch):
    add_exchanges(conversation.conv, 1, 3)

    def boom(**kw):
        raise RuntimeError("openai down")

    monkeypatch.setattr(memory.client.chat.completions, "create", boom)
    memory.update_summary(conversation.conv)
    assert summary_state(conversation.conv)[:2] == (None, None)


def test_build_prompt_includes_summary_only_when_present():
    assert "Tóm tắt cuộc trò chuyện" not in build_prompt([])
    prompt = build_prompt([], summary="- Đang luyện VALUE LINE cho đề advice")
    assert "- Đang luyện VALUE LINE cho đề advice" in prompt
    assert prompt.index("Tóm tắt cuộc trò chuyện") < prompt.index("[Context]")


def test_chat_runs_summary_and_uses_it(make_client, fake_pipeline, small_window, fake_summarizer):  # noqa: F811
    client = make_client()
    cid = client.post("/chat", json={"query": "q1", "category": "part2"}).json()["conversation_id"]
    for q in ["q2", "q3"]:
        client.post("/chat", json={"query": q, "conversation_id": cid})

    # TestClient runs background tasks before returning: after q2 the q1 exchange left
    # the window, so it was summarized; q3's router call and prompt got that summary.
    assert len(fake_summarizer) >= 1
    assert fake_pipeline.route_calls[2]["summary"] == "summary #1"
    assert "summary #1" in fake_pipeline.llm_messages[2][0]["content"]
