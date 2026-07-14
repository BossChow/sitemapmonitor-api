from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.site import Site
from app.models.sitemap_check import CheckStatus, SitemapCheck
from app.models.sitemap_url import SitemapUrl
from app.models.sitemap_url_change import ChangeType, SitemapUrlChange
from app.services.frequency import calculate_next_check_at
from app.services.sitemap_parser import SitemapParser
from app.services.url_utils import hash_url


@dataclass(frozen=True)
class CheckResult:
    check_id: int
    status: str
    url_count: int
    added_count: int
    removed_count: int
    updated_count: int


def run_sitemap_check(db: Session, site_id: int) -> CheckResult:
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"Site {site_id} not found")

    now = datetime.now(UTC)
    check = SitemapCheck(
        owner_user_id=site.owner_user_id,
        site_id=site.id,
        status=CheckStatus.running.value,
        started_at=now,
    )
    db.add(check)
    db.flush()

    try:
        parser = SitemapParser()
        entries = parser.collect(site.sitemap_url)
        seen_hashes: set[str] = set()
        added_count = 0
        updated_count = 0

        for entry in entries:
            url_hash = hash_url(entry.url)
            if url_hash in seen_hashes:
                continue
            seen_hashes.add(url_hash)
            existing = db.scalar(
                select(SitemapUrl).where(
                    SitemapUrl.site_id == site.id,
                    SitemapUrl.url_hash == url_hash,
                )
            )

            if existing is None:
                url_row = SitemapUrl(
                    site_id=site.id,
                    url_hash=url_hash,
                    url=entry.url,
                    lastmod=entry.lastmod,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_seen_check_id=check.id,
                    removed_at=None,
                )
                db.add(url_row)
                db.flush()
                db.add(
                    SitemapUrlChange(
                        owner_user_id=site.owner_user_id,
                        site_id=site.id,
                        check_id=check.id,
                        url_id=url_row.id,
                        change_type=ChangeType.added.value,
                        url=entry.url,
                        old_lastmod=None,
                        new_lastmod=entry.lastmod,
                        created_at=now,
                    )
                )
                added_count += 1
                continue

            old_lastmod = existing.lastmod
            was_removed = existing.removed_at is not None
            existing.url = entry.url
            existing.last_seen_at = now
            existing.last_seen_check_id = check.id
            existing.removed_at = None

            if was_removed:
                db.add(
                    SitemapUrlChange(
                        owner_user_id=site.owner_user_id,
                        site_id=site.id,
                        check_id=check.id,
                        url_id=existing.id,
                        change_type=ChangeType.added.value,
                        url=entry.url,
                        old_lastmod=old_lastmod,
                        new_lastmod=entry.lastmod,
                        created_at=now,
                    )
                )
                added_count += 1
            elif old_lastmod != entry.lastmod:
                db.add(
                    SitemapUrlChange(
                        owner_user_id=site.owner_user_id,
                        site_id=site.id,
                        check_id=check.id,
                        url_id=existing.id,
                        change_type=ChangeType.updated.value,
                        url=entry.url,
                        old_lastmod=old_lastmod,
                        new_lastmod=entry.lastmod,
                        created_at=now,
                    )
                )
                updated_count += 1

            existing.lastmod = entry.lastmod

        removed_urls = db.scalars(
            select(SitemapUrl).where(
                SitemapUrl.site_id == site.id,
                SitemapUrl.removed_at.is_(None),
                or_(
                    SitemapUrl.last_seen_check_id.is_(None),
                    SitemapUrl.last_seen_check_id != check.id,
                ),
            )
        ).all()
        removed_count = len(removed_urls)

        for removed_url in removed_urls:
            removed_url.removed_at = now
            db.add(
                SitemapUrlChange(
                    owner_user_id=site.owner_user_id,
                    site_id=site.id,
                    check_id=check.id,
                    url_id=removed_url.id,
                    change_type=ChangeType.removed.value,
                    url=removed_url.url,
                    old_lastmod=removed_url.lastmod,
                    new_lastmod=None,
                    created_at=now,
                )
            )

        check.status = CheckStatus.completed.value
        check.finished_at = now
        check.url_count = len(seen_hashes)
        check.added_count = added_count
        check.removed_count = removed_count
        check.updated_count = updated_count
        site.last_checked_at = now
        site.next_check_at = calculate_next_check_at(now, site.check_frequency)
        db.commit()

        return CheckResult(
            check_id=check.id,
            status=check.status,
            url_count=check.url_count,
            added_count=added_count,
            removed_count=removed_count,
            updated_count=updated_count,
        )
    except Exception as exc:
        failed_at = datetime.now(UTC)
        check.status = CheckStatus.failed.value
        check.finished_at = failed_at
        check.error_message = str(exc)
        site.last_checked_at = failed_at
        site.next_check_at = calculate_next_check_at(failed_at, site.check_frequency)
        db.commit()
        raise
