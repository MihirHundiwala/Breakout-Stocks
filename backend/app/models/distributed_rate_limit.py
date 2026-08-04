from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DistributedRateLimitBucket(Base):
    __tablename__ = "distributed_rate_limit_buckets"
    __table_args__ = (
        CheckConstraint(
            "bucket_key = btrim(bucket_key) AND bucket_key <> ''",
            name="ck_distributed_rate_limit_bucket_key",
        ),
    )

    bucket_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    next_permit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
