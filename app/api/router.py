from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_owner_user_id
from app.db.session import get_db
from app.models.site import Site, SiteStatus
from app.models.sitemap_check import SitemapCheck
from app.models.sitemap_url import SitemapUrl
from app.models.sitemap_url_change import ChangeType, SitemapUrlChange
from app.schemas.common import MessageResponse, TaskResponse
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.schemas.sitemap_check import SitemapCheckWithChangesRead
from app.schemas.sitemap_url import (
    SitemapUrlListRead,
    UrlInsightsOverviewRead,
    UrlInsightsRead,
    UrlInsightsStructureNodeRead,
    UrlInsightsUpdatesRead,
)
from app.services.frequency import calculate_next_check_at
from app.services.url_utils import derive_site_name
from app.tasks.sitemap_tasks import build_site_baseline_task, check_sitemap_task

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
OwnerUserId = Annotated[str, Depends(get_owner_user_id)]
URL_INSIGHTS_MAX_DEPTH = 5
URL_INSIGHTS_MAX_CHILDREN = 20


class UrlTreeNode:
    def __init__(self, path: str) -> None:
        self.path = path
        self.url_count = 0
        self.children: dict[str, UrlTreeNode] = {}


def url_path_segments(url: str) -> list[str]:
    path = urlsplit(url.strip()).path or "/"
    return [segment for segment in path.strip("/").split("/") if segment]


def child_path(parent_path: str, segment: str) -> str:
    if parent_path == "/":
        return f"/{segment}"
    return f"{parent_path}/{segment}"


def as_utc(datetime_value: datetime) -> datetime:
    if datetime_value.tzinfo is None:
        return datetime_value.replace(tzinfo=UTC)
    return datetime_value.astimezone(UTC)


def build_url_structure(urls: list[str]) -> UrlInsightsStructureNodeRead:
    root = UrlTreeNode("/")
    for url in urls:
        root.url_count += 1
        node = root
        for segment in url_path_segments(url)[:URL_INSIGHTS_MAX_DEPTH]:
            if segment not in node.children:
                node.children[segment] = UrlTreeNode(child_path(node.path, segment))
            node = node.children[segment]
            node.url_count += 1

    def serialize(node: UrlTreeNode) -> UrlInsightsStructureNodeRead:
        children = sorted(
            node.children.values(),
            key=lambda child: (-child.url_count, child.path),
        )[:URL_INSIGHTS_MAX_CHILDREN]
        return UrlInsightsStructureNodeRead(
            path=node.path,
            url_count=node.url_count,
            children=[serialize(child) for child in children],
        )

    return serialize(root)


def get_owned_site(db: Session, owner_user_id: str, site_id: UUID) -> Site:
    site = db.scalar(
        select(Site).where(
            Site.id == site_id,
            Site.owner_user_id == owner_user_id,
        )
    )
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


def build_check_response(
    check: SitemapCheck,
    changes: list[SitemapUrlChange],
) -> SitemapCheckWithChangesRead:
    return SitemapCheckWithChangesRead(
        id=check.id,
        site_id=check.site_id,
        status=check.status,
        started_at=check.started_at,
        finished_at=check.finished_at,
        url_count=check.url_count,
        added_count=check.added_count,
        removed_count=check.removed_count,
        updated_count=check.updated_count,
        error_message=check.error_message,
        change_count=len(changes),
        changes=changes,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sites", response_model=list[SiteRead])
def list_sites(
    db: DbSession,
    owner_user_id: OwnerUserId,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Site]:
    return list(
        db.scalars(
            select(Site)
            .where(Site.owner_user_id == owner_user_id)
            .order_by(Site.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/sites", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
def create_site(payload: SiteCreate, db: DbSession, owner_user_id: OwnerUserId) -> Site:
    site = Site(
        owner_user_id=owner_user_id,
        name=payload.name or derive_site_name(str(payload.root_url)),
        root_url=str(payload.root_url),
        sitemap_url=str(payload.sitemap_url) if payload.sitemap_url is not None else None,
        status=SiteStatus.initializing.value,
        check_frequency=payload.check_frequency.value,
        tracked_change_types=[change_type.value for change_type in payload.tracked_change_types],
        next_check_at=None,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    build_site_baseline_task.delay(str(site.id))
    return site


@router.get("/sites/{site_id}", response_model=SiteRead)
def get_site(site_id: UUID, db: DbSession, owner_user_id: OwnerUserId) -> Site:
    return get_owned_site(db, owner_user_id, site_id)


@router.patch("/sites/{site_id}", response_model=SiteRead)
def update_site(
    site_id: UUID,
    payload: SiteUpdate,
    db: DbSession,
    owner_user_id: OwnerUserId,
) -> Site:
    site = get_owned_site(db, owner_user_id, site_id)
    update_data = payload.model_dump(exclude_unset=True)
    should_rebuild_baseline = "sitemap_url" in update_data
    if should_rebuild_baseline and site.checking_started_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Site sitemap task is already running",
        )

    for field, value in update_data.items():
        if value is None:
            continue
        if field in {"root_url", "sitemap_url"} and value is not None:
            setattr(site, field, str(value))
        elif field == "status" and value is not None:
            if value not in {SiteStatus.active, SiteStatus.paused}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Status can only be changed to active or paused",
                )
            if value == SiteStatus.active and site.baseline_completed_at is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Site baseline is not completed",
                )
            setattr(site, field, value.value)
        elif field == "check_frequency" and value is not None:
            setattr(site, field, value.value)
        elif field == "tracked_change_types":
            setattr(site, field, [change_type.value for change_type in value])
        else:
            setattr(site, field, value)

    if payload.check_frequency is not None:
        if site.status == SiteStatus.active.value:
            site.next_check_at = calculate_next_check_at(datetime.now(UTC), site.check_frequency)

    if should_rebuild_baseline:
        db.execute(delete(SitemapUrlChange).where(SitemapUrlChange.site_id == site.id))
        db.execute(delete(SitemapUrl).where(SitemapUrl.site_id == site.id))
        db.execute(delete(SitemapCheck).where(SitemapCheck.site_id == site.id))
        site.status = SiteStatus.initializing.value
        site.baseline_started_at = None
        site.baseline_completed_at = None
        site.baseline_error_message = None
        site.last_checked_at = None
        site.next_check_at = None

    db.commit()
    db.refresh(site)
    if should_rebuild_baseline:
        build_site_baseline_task.delay(str(site.id))
    return site


@router.delete("/sites/{site_id}", response_model=MessageResponse)
def delete_site(site_id: UUID, db: DbSession, owner_user_id: OwnerUserId) -> MessageResponse:
    site = get_owned_site(db, owner_user_id, site_id)
    db.execute(delete(SitemapUrlChange).where(SitemapUrlChange.site_id == site.id))
    db.execute(delete(SitemapUrl).where(SitemapUrl.site_id == site.id))
    db.execute(delete(SitemapCheck).where(SitemapCheck.site_id == site.id))
    db.delete(site)
    db.commit()
    return MessageResponse(message="Site deleted")


@router.post(
    "/sites/{site_id}/checks",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_site_check(site_id: UUID, db: DbSession, owner_user_id: OwnerUserId) -> TaskResponse:
    site = get_owned_site(db, owner_user_id, site_id)
    if site.status != SiteStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Site is not active",
        )
    task = check_sitemap_task.delay(str(site_id))
    return TaskResponse(task_id=task.id)


@router.get("/sites/{site_id}/checks", response_model=list[SitemapCheckWithChangesRead])
def list_site_checks(
    site_id: UUID,
    db: DbSession,
    owner_user_id: OwnerUserId,
    change_type: Annotated[ChangeType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SitemapCheckWithChangesRead]:
    get_owned_site(db, owner_user_id, site_id)
    checks = list(
        db.scalars(
            select(SitemapCheck)
            .where(SitemapCheck.site_id == site_id)
            .order_by(SitemapCheck.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    check_ids = [check.id for check in checks]
    changes_by_check_id: dict[UUID, list[SitemapUrlChange]] = {
        check_id: [] for check_id in check_ids
    }
    if check_ids:
        changes_query = select(SitemapUrlChange).where(SitemapUrlChange.check_id.in_(check_ids))
        if change_type is not None:
            changes_query = changes_query.where(SitemapUrlChange.change_type == change_type.value)

        changes = db.scalars(
            changes_query.order_by(
                SitemapUrlChange.created_at.desc(),
                SitemapUrlChange.id.desc(),
            )
        )
        for change in changes:
            changes_by_check_id[change.check_id].append(change)

    return [build_check_response(check, changes_by_check_id[check.id]) for check in checks]


@router.get("/checks/{check_id}", response_model=SitemapCheckWithChangesRead)
def get_check(
    check_id: UUID,
    db: DbSession,
    owner_user_id: OwnerUserId,
    change_type: Annotated[ChangeType | None, Query()] = None,
) -> SitemapCheckWithChangesRead:
    check = db.scalar(
        select(SitemapCheck).where(
            SitemapCheck.id == check_id,
            SitemapCheck.owner_user_id == owner_user_id,
        )
    )
    if check is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")

    changes_query = select(SitemapUrlChange).where(SitemapUrlChange.check_id == check.id)
    if change_type is not None:
        changes_query = changes_query.where(SitemapUrlChange.change_type == change_type.value)

    changes = list(
        db.scalars(
            changes_query.order_by(
                SitemapUrlChange.created_at.desc(),
                SitemapUrlChange.id.desc(),
            )
        )
    )
    return build_check_response(check, changes)


@router.get("/sites/{site_id}/url-insights", response_model=UrlInsightsRead)
def get_site_url_insights(
    site_id: UUID,
    db: DbSession,
    owner_user_id: OwnerUserId,
) -> UrlInsightsRead:
    get_owned_site(db, owner_user_id, site_id)
    query = select(SitemapUrl).where(
        SitemapUrl.site_id == site_id,
        SitemapUrl.removed_at.is_(None),
    )
    urls = list(db.scalars(query))
    total_urls = len(urls)
    with_lastmod = sum(1 for url in urls if url.lastmod_at is not None)
    now = datetime.now(UTC)
    lastmod_values = [as_utc(url.lastmod_at) for url in urls if url.lastmod_at is not None]

    return UrlInsightsRead(
        overview=UrlInsightsOverviewRead(
            total_urls=total_urls,
            with_lastmod=with_lastmod,
            without_lastmod=total_urls - with_lastmod,
        ),
        structure=build_url_structure([url.url for url in urls]),
        updates=UrlInsightsUpdatesRead(
            modified_last_24h=sum(
                1 for lastmod_at in lastmod_values if lastmod_at >= now - timedelta(days=1)
            ),
            modified_last_7d=sum(
                1 for lastmod_at in lastmod_values if lastmod_at >= now - timedelta(days=7)
            ),
            modified_last_30d=sum(
                1 for lastmod_at in lastmod_values if lastmod_at >= now - timedelta(days=30)
            ),
        ),
    )


@router.get("/sites/{site_id}/urls", response_model=SitemapUrlListRead)
def list_site_urls(
    site_id: UUID,
    db: DbSession,
    owner_user_id: OwnerUserId,
    include_removed: bool = False,
    sort_by: Literal["last_seen_at", "first_seen_at", "lastmod_at"] = "last_seen_at",
    sort_order: Literal["asc", "desc"] = "desc",
    lastmod_from: datetime | None = None,
    lastmod_to: datetime | None = None,
    first_seen_from: datetime | None = None,
    first_seen_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SitemapUrlListRead:
    get_owned_site(db, owner_user_id, site_id)
    query = select(SitemapUrl).where(SitemapUrl.site_id == site_id)
    if not include_removed:
        query = query.where(SitemapUrl.removed_at.is_(None))
    if lastmod_from is not None:
        query = query.where(SitemapUrl.lastmod_at >= lastmod_from)
    if lastmod_to is not None:
        query = query.where(SitemapUrl.lastmod_at <= lastmod_to)
    if first_seen_from is not None:
        query = query.where(SitemapUrl.first_seen_at >= first_seen_from)
    if first_seen_to is not None:
        query = query.where(SitemapUrl.first_seen_at <= first_seen_to)

    sort_column = {
        "last_seen_at": SitemapUrl.last_seen_at,
        "first_seen_at": SitemapUrl.first_seen_at,
        "lastmod_at": SitemapUrl.lastmod_at,
    }[sort_by]
    ordered_column = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            query.order_by(sort_column.is_(None), ordered_column)
            .limit(limit)
            .offset(offset)
        )
    )
    return SitemapUrlListRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
