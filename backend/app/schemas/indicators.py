from datetime import date
from typing import Literal

from pydantic import BaseModel, HttpUrl

from app.schemas.environmental import DatasetStatus, MetricStatus
from app.schemas.location import Coordinates, Location


class TerrainResponse(BaseModel):
    location: Location
    status: MetricStatus
    elevation_m: float | None = None
    dataset: str = "srtm90m"
    source: str = "Open Topo Data / NASA SRTM"
    data_type: Literal["observed"] = "observed"
    spatial_resolution_m: int = 90
    limitations: list[str]


class NdviObservation(BaseModel):
    date: date
    value: float | None
    pixel_reliability: int | None
    status: Literal["available", "insufficient_data"]


class NdviResponse(BaseModel):
    location: Location
    status: DatasetStatus
    product: str = "MOD13Q1"
    source: str = "NASA MODIS / ORNL DAAC"
    data_type: Literal["observed"] = "observed"
    spatial_resolution_m: int = 250
    composite_days: int = 16
    latest: NdviObservation | None = None
    observations: list[NdviObservation]
    limitations: list[str]


class SoilProperty(BaseModel):
    property: str
    unit: str
    value: float | None
    depth_cm: tuple[int, int] = (0, 5)
    status: MetricStatus


class SoilResponse(BaseModel):
    location: Location
    status: DatasetStatus
    source: str = "ISRIC SoilGrids WCS"
    data_type: Literal["estimated"] = "estimated"
    spatial_resolution_m: int = 250
    properties: list[SoilProperty]
    limitations: list[str]


class HydrologyStation(BaseModel):
    code: str
    name: str
    location: Coordinates
    distance_km: float
    operating: bool | None
    measurement_type: Literal["stream_discharge"] = "stream_discharge"


class HydrologyResponse(BaseModel):
    location: Location
    status: DatasetStatus
    source: str = "ANA / SNIRH"
    search_radius_km: int
    stations: list[HydrologyStation]
    observations_status: Literal["unavailable"] = "unavailable"
    limitations: list[str]


RiskLevel = Literal["low", "moderate", "high", "insufficient_data"]


class RiskIndicator(BaseModel):
    type: Literal["frost", "heat", "heavy_rain", "strong_wind", "water_deficit"]
    level: RiskLevel
    justification: str
    reference_date: date | None = None
    values: dict[str, float | None]
    source: str = "Open-Meteo"
    criteria_url: HttpUrl | None = None
    limitations: list[str]


class RisksResponse(BaseModel):
    location: Location
    status: DatasetStatus
    data_type: Literal["forecast"] = "forecast"
    period_start: date | None
    period_end: date | None
    requested_days: int
    crop_id: str | None
    indicators: list[RiskIndicator]
    limitations: list[str]
