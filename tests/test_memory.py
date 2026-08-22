import pytest

from core.ai.memory import MemoryManager, categorise
from core.persistence.database import Database


@pytest.fixture()
def memory(tmp_path):
    return MemoryManager(Database(tmp_path / "glitch.db"))


def test_remember_that_stores_a_fact(memory):
    reply = memory.capture("remember that I prefer dark themes")
    assert reply is not None
    assert memory.recall() == ["I prefer dark themes"]


@pytest.mark.parametrize(
    "message",
    [
        "Remember: I use two monitors",
        "please remember that I use two monitors",
        "note that I use two monitors",
        "keep in mind I use two monitors",
    ],
)
def test_phrasings_are_all_recognised(memory, message):
    assert memory.capture(message) is not None
    assert memory.recall()


def test_ordinary_messages_are_not_memories(memory):
    assert memory.capture("what are you doing?") is None
    assert memory.recall() == []


def test_a_trailing_full_stop_is_trimmed(memory):
    memory.capture("remember that I like tea.")
    assert memory.recall() == ["I like tea"]


def test_storing_the_same_fact_twice_keeps_one_row(memory):
    memory.capture("remember that I like tea")
    memory.capture("remember that I like tea")
    assert len(memory.recall()) == 1


def test_a_too_short_fact_is_ignored(memory):
    assert memory.capture("remember it") is None


def test_forget_everything_clears_the_store(memory):
    memory.capture("remember that I like tea")
    assert memory.capture("forget everything") is not None
    assert memory.recall() == []


def test_long_facts_are_truncated(memory):
    memory.capture("remember that " + "x" * 900)
    assert len(memory.recall()[0]) <= 300


def test_memory_without_a_database_reports_itself(tmp_path):
    memory = MemoryManager(None)
    reply = memory.capture("remember that I like tea")
    assert reply is not None and "isn't working" in reply
    assert memory.recall() == []


@pytest.mark.parametrize(
    "content, category",
    [
        ("I prefer dark themes", "preference"),
        ("I am working on Glitch", "project"),
        ("my name is Sam", "identity"),
        ("the kettle boiled", "fact"),
    ],
)
def test_facts_are_categorised(content, category):
    assert categorise(content) == category


# ------------------------------------------------------------------ database
def test_conversations_round_trip(tmp_path):
    db = Database(tmp_path / "glitch.db")
    conversation_id = db.start_conversation()
    db.add_message(conversation_id, "user", "hello")
    db.add_message(conversation_id, "assistant", "hi")
    messages = db.recent_messages(conversation_id)
    assert [m.role for m in messages] == ["user", "assistant"]
    db.close()


def test_recent_messages_returns_the_newest_in_order(tmp_path):
    db = Database(tmp_path / "glitch.db")
    conversation_id = db.start_conversation()
    for index in range(10):
        db.add_message(conversation_id, "user", f"message {index}")
    messages = db.recent_messages(conversation_id, limit=3)
    assert [m.content for m in messages] == ["message 7", "message 8", "message 9"]
    db.close()


def test_usage_totals_accumulate(tmp_path):
    db = Database(tmp_path / "glitch.db")
    db.record_usage("gpt-4o-mini", 10, 20, 500, True)
    db.record_usage("gpt-4o-mini", 5, 5, 300, False, "timeout")
    totals = db.usage_totals()
    assert totals["requests"] == 2
    assert totals["input_tokens"] == 15
    assert totals["successes"] == 1
    db.close()


def test_an_unusable_path_degrades_instead_of_raising(tmp_path):
    # A file where a directory should be: the parent cannot be created.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    db = Database(blocker / "sub" / "glitch.db")
    assert not db.available
    # Every operation stays safe once the database is unavailable.
    assert db.start_conversation() is None
    assert db.recent_messages(1) == []
    assert db.memories() == []
