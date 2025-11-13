from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

from . import crud, excel_loader, log_loader, models, schemas
from .database import Base, engine, get_session

app = FastAPI(title="MICP Data Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/projects/import", response_model=schemas.ProjectRead)
def import_project(
    project_name: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> schemas.ProjectRead:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix
    if suffix.lower() not in {".xls", ".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    uploads_dir = Path(__file__).resolve().parent / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_path = uploads_dir / file.filename

    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        sheets = excel_loader.load_excel(temp_path)
    except excel_loader.ExcelIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    project = crud.create_project(session, project_name, description)

    for sheet_name, rows in sheets.items():
        sheet = crud.create_sheet(session, project, sheet_name)
        crud.bulk_insert_records(session, sheet, rows)

    session.refresh(project)
    return schemas.ProjectRead.from_orm(project)


@app.post("/api/logs/preview", response_model=schemas.WellLogPreview)
def preview_well_log(file: UploadFile = File(...)) -> schemas.WellLogPreview:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in log_loader.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    uploads_dir = Path(__file__).resolve().parent / "data" / "logs"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_path = uploads_dir / file.filename

    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        summary = log_loader.load_summary(temp_path)
    except log_loader.WellLogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return schemas.WellLogPreview(**summary.to_dict())


@app.get("/api/projects", response_model=List[schemas.ProjectRead])
def get_projects(session: Session = Depends(get_session)) -> List[schemas.ProjectRead]:
    projects = crud.list_projects(session)
    return [schemas.ProjectRead.from_orm(project) for project in projects]


@app.get("/api/projects/{project_id}/sheets", response_model=List[schemas.SheetRead])
def get_project_sheets(
    project_id: int, session: Session = Depends(get_session)
) -> List[schemas.SheetRead]:
    project = crud.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sheets = crud.list_sheets(session, project_id)
    return [schemas.SheetRead.from_orm(sheet) for sheet in sheets]


@app.get("/api/projects/{project_id}/records", response_model=List[schemas.RecordRead])
def get_project_records(
    project_id: int,
    sheet: Optional[str] = None,
    offset: int = 0,
    limit: int = 200,
    row_start: Optional[int] = None,
    row_end: Optional[int] = None,
    session: Session = Depends(get_session),
) -> List[schemas.RecordRead]:
    project = crud.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    records = crud.list_records(
        session,
        project_id,
        sheet_name=sheet,
        offset=offset,
        limit=min(limit, 500),
        row_start=row_start,
        row_end=row_end,
    )

    return [
        schemas.RecordRead(
            id=record.id,
            sheet_id=record.sheet_id,
            row_index=record.row_index,
            sheet_name=record.sheet.name if record.sheet else None,
            company=record.company,
            field=record.field,
            wellName=record.well_name,
            formation=record.formation,
            data=record.data,
        )
        for record in records
    ]


@app.get("/api/projects/{project_id}/stats", response_model=schemas.StatsResponse)
def get_project_stats(
    project_id: int, session: Session = Depends(get_session)
) -> schemas.StatsResponse:
    project = crud.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        session.query(models.Record)
        .join(models.Record.sheet)
        .options(selectinload(models.Record.sheet))
        .filter(models.Sheet.project_id == project_id)
    )
    records = stmt.all()

    stats = crud.compute_stats(records)
    return schemas.StatsResponse(**stats)
