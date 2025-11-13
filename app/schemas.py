from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class SheetRead(BaseModel):
    id: int
    name: str
    project_id: int

    class Config:
        orm_mode = True


class RecordRead(BaseModel):
    id: int
    sheet_id: int
    row_index: int
    sheet_name: Optional[str]
    company: Optional[str]
    field: Optional[str]
    well_name: Optional[str] = Field(alias="wellName")
    formation: Optional[str]
    data: dict[str, Any]

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class StatsResponse(BaseModel):
    wells_by_company: dict[str, int]
    wells_by_field: dict[str, int]
    wells_by_formation: dict[str, int]
    wells_by_sheet: dict[str, int]
    wells_per_row_bucket: dict[str, int]
    sheet_row_counts: dict[str, int]


class WellLogPreview(BaseModel):
    file_name: str
    format: str
    well_names: list[str] = Field(default_factory=list)
    curve_names: list[str] = Field(default_factory=list)
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    depth_unit: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
