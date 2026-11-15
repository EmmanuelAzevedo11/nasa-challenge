from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.schemas.crop import CropAssessment, MonthlyClimate, Reference, SuitabilityRequest
from app.schemas.location import Location

RotationObjective = Literal[
    "soil_conservation", "diversification", "grain_production", "risk_reduction",
]
StrategyType = Literal["rotation_candidate", "succession", "cover_crop", "sequence_to_validate"]


class RotationRequest(SuitabilityRequest):
    previous_crop: str = Field(min_length=1, max_length=40)
    objective: RotationObjective
    previous_planting_date: date | None = None

    @field_validator("previous_planting_date")
    @classmethod
    def validate_previous_date(cls, value: date | None, info: ValidationInfo) -> date | None:
        year, month = info.data.get("planting_year"), info.data.get("planting_month")
        if value and year and month and value >= date(year, month, info.data.get("planting_day") or 1):
            raise ValueError("A semeadura anterior deve preceder o período do próximo plantio.")
        return value


class StrategyCrop(BaseModel):
    crop_id: str
    name: str
    family: str
    planting_year: int | None
    planting_month: int | None
    role: Literal["previous", "grain", "cover"]


class RotationStrategy(BaseModel):
    name: str
    objective: RotationObjective
    strategy_type: StrategyType
    sequence: list[StrategyCrop]
    benefits: list[str]
    restrictions: list[str]
    justification: str
    assessment: CropAssessment
    references: list[Reference]


class RotationResponse(BaseModel):
    location: Location
    objective: RotationObjective
    season: str
    season_inferred: bool
    planting_year: int
    planting_month: int
    planting_day: int | None
    status: Literal["available", "insufficient_data", "no_eligible_window"]
    climate: MonthlyClimate
    strategies: list[RotationStrategy]
    limitations: list[str]
