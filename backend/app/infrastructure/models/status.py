from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class StatusModel(Base):
    __tablename__ = "statuses"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    position: Mapped[float] = mapped_column(Float)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# Names keep the user's casing but must be unique case-insensitively.
Index("uq_statuses_name_lower", func.lower(StatusModel.name), unique=True)
