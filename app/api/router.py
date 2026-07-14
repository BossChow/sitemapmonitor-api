from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_owner_user_id
from app.db.session import get_db
from app.models.site import Site, SiteStatus
from app.models.sitemap_check import SitemapCheck
from app.models.sitemap_url import SitemapUrl
from app.models.sitemap_url_change import SitemapUrlChange
from app.schemas.common import MessageResponse, TaskResponse
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.schemas.sitemap_check import SitemapCheckRead
from app.schemas.sitemap_url import SitemapUrlRead
from app.schemas.sitemap_url_change import SitemapUrlChangeRead
from app.services.frequency import calculate_next_check_at
from app.tasks.sitemap_tasks import check_sitemap_task

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
OwnerUserId = Annotated[str, Depends(get_owner_user_id)]


def get_owned_site(db: Session, owner_user_id: str, site_id: int) -> Site:
    site = db.scalar(
        select(Site).where(
            Site.id == site_id,
            Site.owner_user_id == owner_user_id,
        )
    )
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


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
    now = datetime.now(UTC)
    site = Site(
        owner_user_id=owner_user_id,
        name=payload.name,
        root_url=str(payload.root_url),
        sitemap_url=str(payload.sitemap_url),
        status=SiteStatus.active.value,
        check_frequency=payload.check_frequency.value,
        next_check_at=calculate_next_check_at(now, payload.check_frequency.value),
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/sites/{site_id}", response_model=SiteRead)
def get_site(site_id: int, db: DbSession, owner_user_id: OwnerUserId) -> Site:
    return get_owned_site(db, owner_user_id, site_id)


@router.patch("/sites/{site_id}", response_model=SiteRead)
def update_site(
    site_id: int,
    payload: SiteUpdate,
    db: DbSession,
    owner_user_id: OwnerUserId,
) -> Site:
    site = get_owned_site(db, owner_user_id, site_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is None:
            continue
        if field in {"root_url", "sitemap_url"} and value is not None:
            setattr(site, field, str(value))
        elif field in {"status", "check_frequency"} and value is not None:
            setattr(site, field, value.value)
        else:
            setattr(site, field, value)

    if payload.check_frequency is not None:
        site.next_check_at = calculate_next_check_at(datetime.now(UTC), site.check_frequency)

    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/{site_id}", response_model=MessageResponse)
def delete_site(site_id: int, db: DbSession, owner_user_id: OwnerUserId) -> MessageResponse:
    site = get_owned_site(db, owner_user_id, site_id)
    db.delete(site)
    db.commit()
    return MessageResponse(message="Site deleted")


@router.post(
    "/sites/{site_id}/checks",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_site_check(site_id: int, db: DbSession, owner_user_id: OwnerUserId) -> TaskResponse:
    get_owned_site(db, owner_user_id, site_id)
    task = check_sitemap_task.delay(site_id)
    return TaskResponse(task_id=task.id)


@router.get("/sites/{site_id}/checks", response_model=list[SitemapCheckRead])
def list_site_checks(
    site_id: int,
    db: DbSession,
    owner_user_id: OwnerUserId,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SitemapCheck]:
    get_owned_site(db, owner_user_id, site_id)
    return list(
        db.scalars(
            select(SitemapCheck)
            .where(SitemapCheck.site_id == site_id)
            .order_by(SitemapCheck.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/checks/{check_id}", response_model=SitemapCheckRead)
def get_check(check_id: int, db: DbSession, owner_user_id: OwnerUserId) -> SitemapCheck:
    check = db.scalar(
        select(SitemapCheck).where(
            SitemapCheck.id == check_id,
            SitemapCheck.owner_user_id == owner_user_id,
        )
    )
    if check is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    return check


@router.get("/sites/{site_id}/changes", response_model=list[SitemapUrlChangeRead])
def list_site_changes(
    site_id: int,
    db: DbSession,
    owner_user_id: OwnerUserId,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SitemapUrlChange]:
    get_owned_site(db, owner_user_id, site_id)
    return list(
        db.scalars(
            select(SitemapUrlChange)
            .where(SitemapUrlChange.site_id == site_id)
            .order_by(SitemapUrlChange.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/sites/{site_id}/urls", response_model=list[SitemapUrlRead])
def list_site_urls(
    site_id: int,
    db: DbSession,
    owner_user_id: OwnerUserId,
    include_removed: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SitemapUrl]:
    get_owned_site(db, owner_user_id, site_id)
    query = select(SitemapUrl).where(SitemapUrl.site_id == site_id)
    if not include_removed:
        query = query.where(SitemapUrl.removed_at.is_(None))
    return list(
        db.scalars(query.order_by(SitemapUrl.last_seen_at.desc()).limit(limit).offset(offset))
    )
