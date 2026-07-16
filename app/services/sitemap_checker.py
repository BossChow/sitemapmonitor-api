from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.site import Site, SiteStatus
from app.models.sitemap_check import CheckStatus, SitemapCheck
from app.models.sitemap_url import SitemapUrl
from app.models.sitemap_url_change import ChangeType, SitemapUrlChange
from app.services.frequency import calculate_next_check_at
from app.services.sitemap_discovery import SitemapDiscovery
from app.services.sitemap_parser import SitemapEntry, SitemapParser
from app.services.url_utils import hash_url, parse_sitemap_lastmod

URL_LOOKUP_BATCH_SIZE = 1000


@dataclass(frozen=True)
class CheckResult:
    check_id: UUID
    status: str
    url_count: int
    added_count: int
    removed_count: int
    updated_count: int


@dataclass(frozen=True)
class BaselineResult:
    site_id: UUID
    status: str
    url_count: int
    error_message: str | None = None


class SitemapDiscoveryError(Exception):
    pass


def is_tracked_change(site: Site, change_type: ChangeType) -> bool:
    return change_type.value in set(site.tracked_change_types or [])


def collect_unique_entries(entries: list[SitemapEntry]) -> dict[str, SitemapEntry]:
    unique_entries: dict[str, SitemapEntry] = {}
    for entry in entries:
        url_hash = hash_url(entry.url)
        if url_hash not in unique_entries:
            unique_entries[url_hash] = entry
    return unique_entries


def load_existing_urls(
    db: Session,
    site_id: UUID,
    url_hashes: list[str],
) -> dict[str, SitemapUrl]:
    existing_urls: dict[str, SitemapUrl] = {}
    for index in range(0, len(url_hashes), URL_LOOKUP_BATCH_SIZE):
        batch = url_hashes[index : index + URL_LOOKUP_BATCH_SIZE]
        rows = db.scalars(
            select(SitemapUrl).where(
                SitemapUrl.site_id == site_id,
                SitemapUrl.url_hash.in_(batch),
            )
        )
        existing_urls.update((row.url_hash, row) for row in rows)
    return existing_urls


def acquire_site_check_lock(db: Session, site_id: UUID, locked_at: datetime) -> bool:
    stale_before = locked_at - timedelta(seconds=settings.site_check_lock_timeout_seconds)
    result = db.execute(
        update(Site)
        .where(
            Site.id == site_id,
            or_(
                Site.checking_started_at.is_(None),
                Site.checking_started_at < stale_before,
            ),
        )
        .values(checking_started_at=locked_at)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def acquire_site_baseline(db: Session, site_id: UUID, started_at: datetime) -> bool:
    result = db.execute(
        update(Site)
        .where(
            Site.id == site_id,
            Site.status == SiteStatus.initializing.value,
            Site.baseline_started_at.is_(None),
        )
        .values(
            baseline_started_at=started_at,
            baseline_completed_at=None,
            baseline_error_message=None,
            next_check_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def collect_baseline_entries(site: Site, parser: SitemapParser) -> list[SitemapEntry]:
    if site.sitemap_url is not None:
        return parser.collect(site.sitemap_url)

    for sitemap_url in SitemapDiscovery().candidates(site.root_url):
        try:
            entries = parser.collect(sitemap_url)
        except Exception:
            continue
        site.sitemap_url = sitemap_url
        return entries

    raise SitemapDiscoveryError("No valid sitemap found for this site")


def build_site_baseline(db: Session, site_id: UUID) -> BaselineResult:
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"Site {site_id} not found")

    now = datetime.now(UTC)
    if not acquire_site_baseline(db, site_id, now):
        db.commit()
        return BaselineResult(
            site_id=site_id,
            status="already_running",
            url_count=0,
            error_message="Site baseline is not ready to run",
        )

    db.commit()
    db.refresh(site)

    try:
        parser = SitemapParser()
        entries = collect_baseline_entries(site, parser)
        unique_entries = collect_unique_entries(entries)

        for url_hash, entry in unique_entries.items():
            lastmod_at = parse_sitemap_lastmod(entry.lastmod)
            db.add(
                SitemapUrl(
                    site_id=site.id,
                    url_hash=url_hash,
                    url=entry.url,
                    lastmod=entry.lastmod,
                    lastmod_at=lastmod_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_seen_check_id=None,
                    removed_at=None,
                )
            )

        completed_at = datetime.now(UTC)
        site.status = SiteStatus.active.value
        site.baseline_completed_at = completed_at
        site.baseline_error_message = None
        site.next_check_at = calculate_next_check_at(completed_at, site.check_frequency)
        db.commit()

        return BaselineResult(
            site_id=site.id,
            status=site.status,
            url_count=len(unique_entries),
        )
    except Exception as exc:
        db.rollback()
        site = db.get(Site, site_id)
        if site is not None:
            site.status = SiteStatus.failed.value
            site.baseline_error_message = str(exc)
            site.next_check_at = None
            db.commit()
        raise


def run_sitemap_check(db: Session, site_id: UUID) -> CheckResult:
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"Site {site_id} not found")

    now = datetime.now(UTC)
    if site.status != SiteStatus.active.value:
        check = SitemapCheck(
            owner_user_id=site.owner_user_id,
            site_id=site.id,
            status=CheckStatus.skipped.value,
            started_at=now,
            finished_at=now,
            error_message="Site is not active",
        )
        db.add(check)
        db.commit()
        return CheckResult(
            check_id=check.id,
            status=check.status,
            url_count=0,
            added_count=0,
            removed_count=0,
            updated_count=0,
        )

    if not acquire_site_check_lock(db, site_id, now):
        check = SitemapCheck(
            owner_user_id=site.owner_user_id,
            site_id=site.id,
            status=CheckStatus.skipped.value,
            started_at=now,
            finished_at=now,
            error_message="Site check already running",
        )
        db.add(check)
        db.commit()
        return CheckResult(
            check_id=check.id,
            status=check.status,
            url_count=0,
            added_count=0,
            removed_count=0,
            updated_count=0,
        )

    db.commit()
    db.refresh(site)

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
        unique_entries = collect_unique_entries(entries)
        existing_urls = load_existing_urls(db, site.id, list(unique_entries))
        added_count = 0
        updated_count = 0

        for url_hash, entry in unique_entries.items():
            existing = existing_urls.get(url_hash)
            lastmod_at = parse_sitemap_lastmod(entry.lastmod)

            if existing is None:
                url_row = SitemapUrl(
                    site_id=site.id,
                    url_hash=url_hash,
                    url=entry.url,
                    lastmod=entry.lastmod,
                    lastmod_at=lastmod_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_seen_check_id=check.id,
                    removed_at=None,
                )
                db.add(url_row)
                db.flush()
                if is_tracked_change(site, ChangeType.added):
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
                if is_tracked_change(site, ChangeType.added):
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
            elif old_lastmod != entry.lastmod and is_tracked_change(site, ChangeType.updated):
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
            existing.lastmod_at = lastmod_at

        db.flush()
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
        removed_count = 0

        for removed_url in removed_urls:
            removed_url.removed_at = now
            if is_tracked_change(site, ChangeType.removed):
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
                removed_count += 1

        check.status = CheckStatus.completed.value
        check.finished_at = now
        check.url_count = len(unique_entries)
        check.added_count = added_count
        check.removed_count = removed_count
        check.updated_count = updated_count
        site.last_checked_at = now
        site.checking_started_at = None
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
        site.checking_started_at = None
        site.next_check_at = calculate_next_check_at(failed_at, site.check_frequency)
        db.commit()
        raise
