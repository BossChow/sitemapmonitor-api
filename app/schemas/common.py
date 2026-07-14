from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    limit: int = 50
    offset: int = 0


class TaskResponse(BaseModel):
    task_id: str


class MessageResponse(BaseModel):
    message: str


class TimestampedModel(OrmModel):
    created_at: datetime
    updated_at: datetime

