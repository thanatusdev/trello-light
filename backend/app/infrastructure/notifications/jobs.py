"""The work behind the Celery tasks, as plain async functions so tests can call them."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import date, timedelta
from itertools import groupby
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.notifications.email import EmailMessage, EmailSender
from app.infrastructure.queries.notifications import get_assignment_details, list_due_soon

type SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def send_task_assigned_email(
    sessions: SessionFactory,
    sender: EmailSender,
    *,
    task_id: UUID,
    assignee_id: UUID,
    assigned_by_id: UUID,
) -> bool:
    """Returns whether an email was sent. Skips silently if the assignment no longer holds."""
    async with sessions() as session:
        details = await get_assignment_details(
            session, task_id=task_id, assignee_id=assignee_id, assigned_by_id=assigned_by_id
        )
    if details is None:
        return False

    by = details.assigned_by_name or "Someone"
    due = f"\nDue: {details.due_date.isoformat()}" if details.due_date else ""
    sender.send(
        EmailMessage(
            to=details.assignee_email,
            subject=f"You were assigned: {details.task_title}",
            body=f"Hi {details.assignee_name},\n\n{by} assigned you to "
            f'"{details.task_title}".{due}\n',
        )
    )
    return True


async def send_due_soon_digests(
    sessions: SessionFactory, sender: EmailSender, *, today: date
) -> int:
    """One email per assignee listing their open tasks due today or tomorrow.

    ``due_date`` is a date, so "within 24 hours" means today or tomorrow (UTC).
    Returns the number of emails sent.
    """
    async with sessions() as session:
        tasks = await list_due_soon(session, start=today, end=today + timedelta(days=1))

    sent = 0
    for (email, name), group in groupby(tasks, key=lambda t: (t.assignee_email, t.assignee_name)):
        items = list(group)
        lines = "\n".join(f"- {t.title} (due {t.due_date.isoformat()})" for t in items)
        noun, these = ("task", "This task is") if len(items) == 1 else ("tasks", "These tasks are")
        sender.send(
            EmailMessage(
                to=email,
                subject=f"{len(items)} {noun} due soon",
                body=f"Hi {name},\n\n{these} due within the next day:\n{lines}\n",
            )
        )
        sent += 1
    return sent
