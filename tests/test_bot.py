import pytest

from conftest import COMPLAINT_KWARGS


@pytest.fixture(autouse=True)
def _clean_bot_state():
    import bot

    bot.conversations.clear()
    bot.fallback_cases.clear()
    bot.filed_sessions.clear()
    bot._last_active.clear()
    yield
    bot.conversations.clear()
    bot.fallback_cases.clear()
    bot.filed_sessions.clear()
    bot._last_active.clear()


def test_chat_files_complaint_exactly_once(monkeypatch, isolated_store):
    import bot

    responses = iter(
        [
            {"message": "what's your name?", "current_field": "name"},
            {
                "message": "thanks, all set!",
                "current_field": "complete",
                "complaint": dict(
                    name=COMPLAINT_KWARGS["name"],
                    email=COMPLAINT_KWARGS["email"],
                    order_number=COMPLAINT_KWARGS["order_number"],
                    item=COMPLAINT_KWARGS["item"],
                    issue=COMPLAINT_KWARGS["issue"],
                    resolution=COMPLAINT_KWARGS["resolution"],
                    phone=COMPLAINT_KWARGS["phone"],
                    urgency="normal",
                ),
            },
        ]
    )
    monkeypatch.setattr(bot, "ask", lambda history, system: next(responses))

    _, filed1, field1 = bot.chat("sess-x", "hello")
    assert filed1 is False
    assert field1 == "name"

    _, filed2, field2 = bot.chat("sess-x", "here's everything")
    assert filed2 is True
    assert field2 == "complete"
    assert len(isolated_store.load_complaints()) == 1

    # The model has no instruction to stop calling the tool once done, so a
    # naive implementation re-files on every later message — this is the bug
    # a live test caught. Confirm it can't call the model again at all.
    def fail_if_called(history, system):
        raise AssertionError("must not ask the model again once filed")

    monkeypatch.setattr(bot, "ask", fail_if_called)
    _, filed3, field3 = bot.chat("sess-x", "still there?")
    assert filed3 is True
    assert field3 == "complete"
    assert len(isolated_store.load_complaints()) == 1


def test_incomplete_complaint_payload_is_not_filed(monkeypatch, isolated_store):
    import bot

    monkeypatch.setattr(
        bot,
        "ask",
        lambda history, system: {
            "message": "almost done",
            "current_field": "phone",
            "complaint": {"name": "Ann"},  # missing required fields
        },
    )
    _, filed, _ = bot.chat("sess-y", "test")
    assert filed is False
    assert isolated_store.load_complaints() == []


def test_provider_failure_falls_back_to_local_flow(monkeypatch, isolated_store):
    import bot

    def boom(history, system):
        raise RuntimeError("provider down")

    monkeypatch.setattr(bot, "ask", boom)
    _, filed, field = bot.chat("sess-z", "my kettle broke")
    assert filed is False
    assert field == "name"


def test_fallback_flow_files_once_end_to_end(monkeypatch, isolated_store):
    import bot

    def boom(history, system):
        raise RuntimeError("provider down")

    monkeypatch.setattr(bot, "ask", boom)

    bot.chat("sess-f", "my kettle broke")
    bot.chat("sess-f", "Ann Example")
    bot.chat("sess-f", "ann@example.com")
    bot.chat("sess-f", "KC-1")
    bot.chat("sess-f", "Kettle")
    bot.chat("sess-f", "Refund")
    _, filed, field = bot.chat("sess-f", "555-0000")

    assert filed is True
    assert field == "complete"
    assert len(isolated_store.load_complaints()) == 1

    _, filed_again, field_again = bot.chat("sess-f", "hello again")
    assert filed_again is True
    assert field_again == "complete"
    assert len(isolated_store.load_complaints()) == 1
