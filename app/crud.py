from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models

KeyFields = tuple[str | None, str | None, str | None, str | None]


def create_project(session: Session, name: str, description: str | None) -> models.Project:
    project = models.Project(name=name, description=description)
    session.add(project)
    session.flush()
    return project


def create_sheet(session: Session, project: models.Project, name: str) -> models.Sheet:
    sheet = models.Sheet(name=name, project=project)
    session.add(sheet)
    session.flush()
    return sheet


def bulk_insert_records(
    session: Session,
    sheet: models.Sheet,
    rows: Iterable[dict],
) -> None:
    records = []
    for row in rows:
        record = models.Record(
            sheet=sheet,
            row_index=row["row_index"],
            company=row.get("company"),
            field=row.get("field"),
            well_name=row.get("well_name"),
            formation=row.get("formation"),
            data=row.get("data", {}),
        )
        records.append(record)
    session.add_all(records)


def list_projects(session: Session) -> Sequence[models.Project]:
    stmt = select(models.Project).order_by(models.Project.created_at.desc())
    return session.execute(stmt).scalars().all()


def get_project(session: Session, project_id: int) -> models.Project | None:
    stmt = select(models.Project).where(models.Project.id == project_id)
    return session.execute(stmt).scalar_one_or_none()


def list_records(
    session: Session,
    project_id: int,
    sheet_name: str | None = None,
    offset: int = 0,
    limit: int = 100,
    row_start: int | None = None,
    row_end: int | None = None,
) -> Sequence[models.Record]:
    stmt = (
        select(models.Record)
        .join(models.Record.sheet)
        .where(models.Sheet.project_id == project_id)
        .options(selectinload(models.Record.sheet))
        .order_by(models.Record.row_index)
        .offset(offset)
        .limit(limit)
    )
    if sheet_name:
        stmt = stmt.where(models.Sheet.name == sheet_name)
    if row_start is not None:
        stmt = stmt.where(models.Record.row_index >= row_start)
    if row_end is not None:
        stmt = stmt.where(models.Record.row_index <= row_end)
    return session.execute(stmt).scalars().all()


def list_sheets(session: Session, project_id: int) -> Sequence[models.Sheet]:
    stmt = select(models.Sheet).where(models.Sheet.project_id == project_id).order_by(
        models.Sheet.name
    )
    return session.execute(stmt).scalars().all()


def compute_stats(records: Sequence[models.Record]) -> dict:
    by_company: Counter[str] = Counter()
    by_field: Counter[str] = Counter()
    by_formation: Counter[str] = Counter()
    by_sheet: Counter[str] = Counter()
    row_buckets: Counter[str] = Counter()
    sheet_rows: defaultdict[str, int] = defaultdict(int)

    for record in records:
        sheet_name = record.sheet.name if record.sheet else "Unknown"
        by_sheet[sheet_name] += 1
        sheet_rows[sheet_name] += 1

        if record.company:
            by_company[record.company] += 1
        if record.field:
            by_field[record.field] += 1
        if record.formation:
            by_formation[record.formation] += 1

        bucket = f"{(record.row_index // 10) * 10}-{(record.row_index // 10) * 10 + 9}"
        row_buckets[bucket] += 1

    return {
        "wells_by_company": dict(by_company),
        "wells_by_field": dict(by_field),
        "wells_by_formation": dict(by_formation),
        "wells_by_sheet": dict(by_sheet),
        "wells_per_row_bucket": dict(row_buckets),
        "sheet_row_counts": dict(sheet_rows),
    }
