from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.site import Site, SiteStatus
from app.services.frequency import calculate_next_check_at
from app.services.sitemap_checker import run_sitemap_check
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.sitemap_tasks.check_sitemap_task", lazy=False)
def check_sitemap_task(site_id: int) -> dict[str, int | str]:
    with SessionLocal() as db:
        result = run_sitemap_check(db, site_id)
        return {
            "check_id": result.check_id,
            "status": result.status,
            "url_count": result.url_count,
            "added_count": result.added_count,
            "removed_count": result.removed_count,
            "updated_count": result.updated_count,
        }


@celery_app.task(name="app.tasks.sitemap_tasks.dispatch_due_checks_task", lazy=False)
def dispatch_due_checks_task() -> dict[str, int]:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        sites = db.scalars(
            select(Site)
            .where(
                Site.status == SiteStatus.active.value,
                Site.next_check_at.is_not(None),
                Site.next_check_at <= now,
            )
            .order_by(Site.next_check_at.asc())
            .limit(settings.scheduler_batch_size)
        ).all()

        for site in sites:
            site.next_check_at = calculate_next_check_at(now, site.check_frequency)
            check_sitemap_task.delay(site.id)

        db.commit()
        return {"dispatched": len(sites)}
