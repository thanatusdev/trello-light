import logging
from typing import Any
from uuid import uuid4

import pytest

from app.infrastructure.celery_app import create_celery
from app.infrastructure.config import Settings
from app.infrastructure.logging import configure_logging
from app.infrastructure.notifications.email import ConsoleEmailSender, EmailMessage
from app.infrastructure.notifications.notifier import CeleryNotifier, NullNotifier


async def test_celery_notifier_queues_ids_as_strings() -> None:
    calls: list[tuple[str, ...]] = []
    notifier = CeleryNotifier(enqueue=lambda *args: calls.append(args))
    task_id, assignee_id, by_id = uuid4(), uuid4(), uuid4()

    await notifier.task_assigned(task_id=task_id, assignee_id=assignee_id, assigned_by_id=by_id)

    assert calls == [(str(task_id), str(assignee_id), str(by_id))]


async def test_celery_notifier_logs_and_swallows_enqueue_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(*_: Any) -> None:
        raise ConnectionError("broker down")

    notifier = CeleryNotifier(enqueue=broken)

    with caplog.at_level(logging.ERROR):
        await notifier.task_assigned(task_id=uuid4(), assignee_id=uuid4(), assigned_by_id=uuid4())

    assert "Could not queue assignment notification" in caplog.text


async def test_null_notifier_does_nothing() -> None:
    await NullNotifier().task_assigned(task_id=uuid4(), assignee_id=uuid4(), assigned_by_id=uuid4())


def test_console_email_sender_logs_the_message(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        ConsoleEmailSender().send(EmailMessage(to="bob@example.com", subject="Hi", body="Body"))

    assert "to=bob@example.com" in caplog.text
    assert "'Hi'" in caplog.text
    assert "Body" in caplog.text


def test_beat_runs_due_soon_digests_daily_at_configured_hour(test_settings: Settings) -> None:
    celery = create_celery(test_settings.model_copy(update={"due_soon_hour_utc": 6}))

    entry = celery.conf.beat_schedule["due-soon-digests"]

    assert entry["task"] == "notifications.due_soon_digests"
    assert entry["schedule"].hour == {6}
    assert entry["schedule"].minute == {0}


def test_configure_logging_sets_app_logger_once() -> None:
    logger = logging.getLogger("app")
    saved = (logger.level, logger.handlers[:], logger.propagate)
    logger.handlers.clear()
    try:
        configure_logging("DEBUG")
        configure_logging("DEBUG")

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
    finally:
        logger.setLevel(saved[0])
        logger.handlers[:] = saved[1]
        logger.propagate = saved[2]
