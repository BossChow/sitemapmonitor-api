from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Site, SitemapCheck, SitemapUrl, SitemapUrlChange
from app.models.site import CheckFrequency, SiteStatus
from app.models.sitemap_check import CheckStatus
from app.models.sitemap_url_change import ChangeType
from app.services.sitemap_checker import build_site_baseline, run_sitemap_check
from app.services.sitemap_parser import SitemapEntry


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_local() as session:
        yield session


def create_site(db: Session, tracked_change_types: list[str] | None = None) -> Site:
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.active.value,
        check_frequency=CheckFrequency.daily.value,
        tracked_change_types=tracked_change_types
        or [
            ChangeType.added.value,
            ChangeType.removed.value,
            ChangeType.updated.value,
        ],
        baseline_completed_at=datetime.now(UTC),
        next_check_at=datetime.now(UTC),
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def reset_site_baseline(db: Session, site: Site) -> None:
    site.status = SiteStatus.initializing.value
    site.baseline_started_at = None
    site.baseline_completed_at = None
    site.baseline_error_message = None
    site.next_check_at = None
    db.commit()


def count_rows(db: Session, model: type[object]) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_sitemap_check_records_added_urls_after_completed_baseline(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-13"),
                SitemapEntry(url="https://example.com/b", lastmod=None),
            ]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = run_sitemap_check(db, site.id)

    assert result.status == "completed"
    assert result.url_count == 2
    assert result.added_count == 2
    assert result.removed_count == 0
    assert result.updated_count == 0
    assert count_rows(db, SitemapUrl) == 2
    assert count_rows(db, SitemapUrlChange) == 2


def test_build_site_baseline_creates_urls_without_check_or_changes(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    reset_site_baseline(db, site)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-13"),
                SitemapEntry(url="https://example.com/b", lastmod=None),
            ]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = build_site_baseline(db, site.id)
    db.refresh(site)

    assert result.status == SiteStatus.active.value
    assert result.url_count == 2
    assert site.status == SiteStatus.active.value
    assert site.baseline_completed_at is not None
    assert site.checking_started_at is None
    assert site.next_check_at is not None
    assert count_rows(db, SitemapUrl) == 2
    assert count_rows(db, SitemapCheck) == 0
    assert count_rows(db, SitemapUrlChange) == 0


def test_build_site_baseline_preserves_url_text_and_parses_lastmod(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    reset_site_baseline(db, site)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [
                SitemapEntry(
                    url="HTTPS://Example.COM/a?b=2&a=1#section",
                    lastmod="2026-07-13T08:30:00+08:00",
                ),
                SitemapEntry(
                    url="https://example.com/a?a=1&b=2",
                    lastmod="2026-07-14T08:30:00+08:00",
                ),
            ]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = build_site_baseline(db, site.id)
    url = db.scalar(select(SitemapUrl))

    assert result.url_count == 1
    assert url is not None
    assert url.url == "HTTPS://Example.COM/a?b=2&a=1#section"
    assert url.lastmod == "2026-07-13T08:30:00+08:00"
    assert url.lastmod_at == datetime(2026, 7, 13, 0, 30)


def test_build_site_baseline_discovers_sitemap_when_not_provided(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    site.sitemap_url = None
    reset_site_baseline(db, site)

    class FakeDiscovery:
        def candidates(self, root_url: str) -> list[str]:
            assert root_url == "https://example.com"
            return ["https://example.com/discovered-sitemap.xml"]

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            assert sitemap_url == "https://example.com/discovered-sitemap.xml"
            return [SitemapEntry(url="https://example.com/a", lastmod=None)]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapDiscovery", FakeDiscovery)
    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = build_site_baseline(db, site.id)
    db.refresh(site)

    assert result.status == SiteStatus.active.value
    assert site.sitemap_url == "https://example.com/discovered-sitemap.xml"


def test_build_site_baseline_fails_when_sitemap_cannot_be_discovered(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    site.sitemap_url = None
    reset_site_baseline(db, site)

    class FakeDiscovery:
        def candidates(self, root_url: str) -> list[str]:
            return ["https://example.com/sitemap.xml"]

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            raise ValueError("Not a sitemap")

    monkeypatch.setattr("app.services.sitemap_checker.SitemapDiscovery", FakeDiscovery)
    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    with pytest.raises(Exception, match="No valid sitemap found for this site"):
        build_site_baseline(db, site.id)

    db.refresh(site)
    assert site.status == SiteStatus.failed.value
    assert site.baseline_error_message == "No valid sitemap found for this site"


def test_sitemap_check_skips_when_baseline_is_not_completed(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    reset_site_baseline(db, site)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            raise AssertionError("Parser should not run before baseline is completed")

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = run_sitemap_check(db, site.id)
    check = db.get(SitemapCheck, result.check_id)

    assert result.status == CheckStatus.skipped.value
    assert check is not None
    assert check.error_message == "Site is not active"


def test_subsequent_sitemap_check_records_new_urls(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    reset_site_baseline(db, site)
    sitemap_entries = iter(
        [
            [SitemapEntry(url="https://example.com/a", lastmod="2026-07-13")],
            [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-13"),
                SitemapEntry(url="https://example.com/b", lastmod="2026-07-14"),
            ],
        ]
    )

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return next(sitemap_entries)

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    baseline_result = build_site_baseline(db, site.id)
    changed_result = run_sitemap_check(db, site.id)

    change = db.scalar(select(SitemapUrlChange))

    assert baseline_result.status == SiteStatus.active.value
    assert changed_result.url_count == 2
    assert changed_result.added_count == 1
    assert count_rows(db, SitemapUrl) == 2
    assert count_rows(db, SitemapUrlChange) == 1
    assert change is not None
    assert change.change_type == "added"
    assert change.url == "https://example.com/b"


def test_unchanged_sitemap_check_does_not_mark_urls_removed(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    reset_site_baseline(db, site)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-13"),
                SitemapEntry(url="https://example.com/b", lastmod="2026-07-13"),
            ]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    build_site_baseline(db, site.id)
    result = run_sitemap_check(db, site.id)
    removed_urls = list(
        db.scalars(
            select(SitemapUrl).where(
                SitemapUrl.site_id == site.id,
                SitemapUrl.removed_at.is_not(None),
            )
        )
    )

    assert result.url_count == 2
    assert result.added_count == 0
    assert result.removed_count == 0
    assert result.updated_count == 0
    assert removed_urls == []
    assert count_rows(db, SitemapUrlChange) == 0


def test_sitemap_check_only_records_tracked_change_types(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db, tracked_change_types=[ChangeType.added.value])
    reset_site_baseline(db, site)
    sitemap_entries = iter(
        [
            [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-13"),
                SitemapEntry(url="https://example.com/b", lastmod="2026-07-13"),
            ],
            [
                SitemapEntry(url="https://example.com/a", lastmod="2026-07-14"),
                SitemapEntry(url="https://example.com/c", lastmod="2026-07-14"),
            ],
        ]
    )

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return next(sitemap_entries)

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    build_site_baseline(db, site.id)
    changed_result = run_sitemap_check(db, site.id)
    changes = list(db.scalars(select(SitemapUrlChange)))
    removed_url = db.scalar(select(SitemapUrl).where(SitemapUrl.url == "https://example.com/b"))

    assert changed_result.added_count == 1
    assert changed_result.removed_count == 0
    assert changed_result.updated_count == 0
    assert [change.change_type for change in changes] == [ChangeType.added.value]
    assert changes[0].url == "https://example.com/c"
    assert removed_url is not None
    assert removed_url.removed_at is not None


def test_sitemap_check_skips_when_site_check_lock_is_active(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    site.checking_started_at = datetime.now(UTC)
    db.commit()

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            raise AssertionError("Parser should not run when the site lock is active")

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = run_sitemap_check(db, site.id)
    check = db.get(SitemapCheck, result.check_id)

    assert result.status == CheckStatus.skipped.value
    assert result.url_count == 0
    assert check is not None
    assert check.status == CheckStatus.skipped.value
    assert check.error_message == "Site check already running"


def test_sitemap_check_releases_site_check_lock_after_completion(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [SitemapEntry(url="https://example.com/a", lastmod="2026-07-13")]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = run_sitemap_check(db, site.id)
    db.refresh(site)

    assert result.status == CheckStatus.completed.value
    assert site.checking_started_at is None


def test_sitemap_check_can_take_over_stale_site_check_lock(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)
    site.checking_started_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            return [SitemapEntry(url="https://example.com/a", lastmod="2026-07-13")]

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    result = run_sitemap_check(db, site.id)
    db.refresh(site)

    assert result.status == CheckStatus.completed.value
    assert site.checking_started_at is None


def test_sitemap_check_releases_site_check_lock_after_failure(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = create_site(db)

    class FakeParser:
        def collect(self, sitemap_url: str) -> list[SitemapEntry]:
            raise RuntimeError("Fetch failed")

    monkeypatch.setattr("app.services.sitemap_checker.SitemapParser", FakeParser)

    with pytest.raises(RuntimeError, match="Fetch failed"):
        run_sitemap_check(db, site.id)

    db.refresh(site)
    check = db.scalar(select(SitemapCheck))

    assert site.checking_started_at is None
    assert check is not None
    assert check.status == CheckStatus.failed.value
    assert check.error_message == "Fetch failed"
