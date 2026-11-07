from celery import Celery
from celery.schedules import crontab

from app.infrastructure.config import Settings, get_settings


def create_celery(settings: Settings) -> Celery:
    app = Celery("trello_light", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
        # Nothing reads task results; don't fill Redis with them.
        task_ignore_result=True,
        beat_schedule={
            "due-soon-digests": {
                "task": "notifications.due_soon_digests",
                "schedule": crontab(hour=settings.due_soon_hour_utc, minute=0),
            },
        },
    )
    app.autodiscover_tasks(["app.infrastructure"])
    return app


celery_app = create_celery(get_settings())
