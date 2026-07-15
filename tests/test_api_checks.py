from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Site, SitemapCheck, SitemapUrl, SitemapUrlChange
from app.models.site import CheckFrequency, SiteStatus
from app.models.sitemap_check import CheckStatus
from app.models.sitemap_url_change import ChangeType


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)

    with session_local() as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_site_with_checks(db: Session) -> tuple[Site, SitemapCheck, SitemapCheck]:
    now = datetime.now(UTC)
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.active.value,
        check_frequency=CheckFrequency.daily.value,
        baseline_completed_at=now,
        next_check_at=now + timedelta(days=1),
    )
    db.add(site)
    db.flush()

    older_check = SitemapCheck(
        owner_user_id=site.owner_user_id,
        site_id=site.id,
        status=CheckStatus.completed.value,
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2, seconds=-5),
        url_count=10,
        added_count=1,
        removed_count=0,
        updated_count=0,
    )
    newer_check = SitemapCheck(
        owner_user_id=site.owner_user_id,
        site_id=site.id,
        status=CheckStatus.completed.value,
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(hours=1, seconds=-5),
        url_count=10,
        added_count=0,
        removed_count=1,
        updated_count=0,
    )
    db.add_all([older_check, newer_check])
    db.flush()
    db.add_all(
        [
            SitemapUrlChange(
                owner_user_id=site.owner_user_id,
                site_id=site.id,
                check_id=older_check.id,
                url_id=None,
                change_type=ChangeType.added.value,
                url="https://example.com/a",
                old_lastmod=None,
                new_lastmod="2026-07-14",
                created_at=older_check.finished_at or older_check.started_at,
            ),
            SitemapUrlChange(
                owner_user_id=site.owner_user_id,
                site_id=site.id,
                check_id=newer_check.id,
                url_id=None,
                change_type=ChangeType.removed.value,
                url="https://example.com/b",
                old_lastmod="2026-07-13",
                new_lastmod=None,
                created_at=newer_check.finished_at or newer_check.started_at,
            ),
        ]
    )
    db.commit()
    return site, older_check, newer_check


def test_list_site_checks_returns_checks_grouped_with_changes(
    client: TestClient,
    db: Session,
) -> None:
    site, older_check, newer_check = create_site_with_checks(db)

    response = client.get(
        f"/sites/{site.id}/checks",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [check["id"] for check in payload] == [str(newer_check.id), str(older_check.id)]
    assert payload[0]["change_count"] == 1
    assert payload[0]["changes"][0]["change_type"] == "removed"
    assert payload[1]["change_count"] == 1
    assert payload[1]["changes"][0]["change_type"] == "added"


def test_change_type_filters_nested_changes_without_hiding_checks(
    client: TestClient,
    db: Session,
) -> None:
    site, older_check, newer_check = create_site_with_checks(db)

    response = client.get(
        f"/sites/{site.id}/checks?change_type=added",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [check["id"] for check in payload] == [str(newer_check.id), str(older_check.id)]
    assert payload[0]["change_count"] == 0
    assert payload[0]["changes"] == []
    assert payload[1]["change_count"] == 1
    assert payload[1]["changes"][0]["change_type"] == "added"


def test_get_check_supports_change_type_filter(
    client: TestClient,
    db: Session,
) -> None:
    _, older_check, _ = create_site_with_checks(db)

    response = client.get(
        f"/checks/{older_check.id}?change_type=removed",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(older_check.id)
    assert payload["change_count"] == 0
    assert payload["changes"] == []


def test_create_site_starts_initializing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued_site_ids: list[str] = []

    class FakeBaselineTask:
        @staticmethod
        def delay(site_id: str) -> None:
            queued_site_ids.append(site_id)

    monkeypatch.setattr("app.api.router.build_site_baseline_task", FakeBaselineTask)

    response = client.post(
        "/sites",
        headers={"X-Owner-User-Id": "test-user"},
        json={
            "root_url": "https://example.com",
            "check_frequency": "daily",
            "tracked_change_types": ["added", "removed", "updated"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == SiteStatus.initializing.value
    assert payload["name"] == "Example"
    assert payload["sitemap_url"] is None
    assert payload["error_message"] is None
    assert payload["baseline_completed_at"] is None
    assert payload["next_check_at"] is None
    assert queued_site_ids == [payload["id"]]


@pytest.mark.parametrize("field", ["check_frequency", "tracked_change_types"])
def test_create_site_requires_check_settings(
    client: TestClient,
    field: str,
) -> None:
    payload: dict[str, object] = {
        "root_url": "https://example.com",
        "check_frequency": "daily",
        "tracked_change_types": ["added"],
    }
    payload.pop(field)

    response = client.post(
        "/sites",
        headers={"X-Owner-User-Id": "test-user"},
        json=payload,
    )

    assert response.status_code == 422


def test_site_read_exposes_error_message_for_failed_site(
    client: TestClient,
    db: Session,
) -> None:
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/missing-sitemap.xml",
        status=SiteStatus.failed.value,
        check_frequency=CheckFrequency.daily.value,
        baseline_error_message="404 Not Found",
        next_check_at=None,
    )
    db.add(site)
    db.commit()

    response = client.get(
        f"/sites/{site.id}",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == SiteStatus.failed.value
    assert payload["error_message"] == "404 Not Found"


def test_delete_site_removes_related_data(
    client: TestClient,
    db: Session,
) -> None:
    now = datetime.now(UTC)
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.active.value,
        check_frequency=CheckFrequency.daily.value,
        baseline_completed_at=now,
    )
    db.add(site)
    db.flush()
    check = SitemapCheck(
        owner_user_id=site.owner_user_id,
        site_id=site.id,
        status=CheckStatus.completed.value,
        started_at=now,
        finished_at=now,
    )
    db.add(check)
    db.flush()
    url = SitemapUrl(
        site_id=site.id,
        url_hash="hash-a",
        url="https://example.com/a",
        lastmod=None,
        first_seen_at=now,
        last_seen_at=now,
        last_seen_check_id=check.id,
        removed_at=None,
    )
    db.add(url)
    db.flush()
    change = SitemapUrlChange(
        owner_user_id=site.owner_user_id,
        site_id=site.id,
        check_id=check.id,
        url_id=url.id,
        change_type=ChangeType.added.value,
        url=url.url,
        old_lastmod=None,
        new_lastmod=None,
        created_at=now,
    )
    db.add(change)
    db.commit()

    response = client.delete(
        f"/sites/{site.id}",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Site deleted"}
    assert db.get(Site, site.id) is None
    assert db.get(SitemapCheck, check.id) is None
    assert db.get(SitemapUrl, url.id) is None
    assert db.get(SitemapUrlChange, change.id) is None


def test_delete_site_rejects_other_owner(
    client: TestClient,
    db: Session,
) -> None:
    site = Site(
        owner_user_id="other-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.active.value,
        check_frequency=CheckFrequency.daily.value,
    )
    db.add(site)
    db.commit()

    response = client.delete(
        f"/sites/{site.id}",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 404
    assert db.get(Site, site.id) is not None


def test_trigger_site_check_rejects_incomplete_baseline(
    client: TestClient,
    db: Session,
) -> None:
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.initializing.value,
        check_frequency=CheckFrequency.daily.value,
        next_check_at=None,
    )
    db.add(site)
    db.commit()

    response = client.post(
        f"/sites/{site.id}/checks",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Site is not active"


def test_list_site_urls_returns_total_for_filtered_result(
    client: TestClient,
    db: Session,
) -> None:
    now = datetime.now(UTC)
    site = Site(
        owner_user_id="test-user",
        name="Example",
        root_url="https://example.com",
        sitemap_url="https://example.com/sitemap.xml",
        status=SiteStatus.active.value,
        check_frequency=CheckFrequency.daily.value,
        baseline_completed_at=now,
    )
    db.add(site)
    db.flush()
    db.add_all(
        [
            SitemapUrl(
                site_id=site.id,
                url_hash="hash-a",
                url="https://example.com/a",
                lastmod=None,
                first_seen_at=now,
                last_seen_at=now,
                removed_at=None,
            ),
            SitemapUrl(
                site_id=site.id,
                url_hash="hash-b",
                url="https://example.com/b",
                lastmod=None,
                first_seen_at=now,
                last_seen_at=now - timedelta(minutes=1),
                removed_at=None,
            ),
            SitemapUrl(
                site_id=site.id,
                url_hash="hash-c",
                url="https://example.com/c",
                lastmod=None,
                first_seen_at=now,
                last_seen_at=now - timedelta(minutes=2),
                removed_at=now,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"/sites/{site.id}/urls?limit=1&offset=0",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["url"] == "https://example.com/a"

    include_removed_response = client.get(
        f"/sites/{site.id}/urls?include_removed=true&limit=10&offset=0",
        headers={"X-Owner-User-Id": "test-user"},
    )

    assert include_removed_response.status_code == 200
    assert include_removed_response.json()["total"] == 3
