from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "sitemap_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sitemap_tasks"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.task_always_eager = False
celery_app.conf.beat_schedule = {
    "dispatch-due-sitemap-checks": {
        "task": "app.tasks.sitemap_tasks.dispatch_due_checks_task",
        "schedule": crontab(minute="*/5"),
    },
}

