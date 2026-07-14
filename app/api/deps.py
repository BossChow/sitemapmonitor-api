from typing import Annotated

from fastapi import Header, HTTPException, status


def get_owner_user_id(
    x_owner_user_id: Annotated[str | None, Header(alias="X-Owner-User-Id")] = None,
) -> str:
    if not x_owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Owner-User-Id header is required",
        )
    return x_owner_user_id

