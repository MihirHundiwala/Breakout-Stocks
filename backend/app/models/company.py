from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.instrument import Instrument


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "name = btrim(name) AND name <> ''",
            name="ck_companies_name_normalized",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    instruments: Mapped[list["Instrument"]] = relationship(
        back_populates="company",
    )
