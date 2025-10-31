from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    sheets: Mapped[list[Sheet]] = relationship("Sheet", back_populates="project")


class Sheet(Base):
    __tablename__ = "sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="sheets")
    records: Mapped[list[Record]] = relationship(
        "Record", back_populates="sheet", cascade="all, delete-orphan"
    )


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("sheets.id"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    well_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    formation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    sheet: Mapped[Sheet] = relationship("Sheet", back_populates="records")
