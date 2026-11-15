from pydantic import BaseModel

from app.schemas.environmental import RegionSummary
from app.schemas.indicators import HydrologyResponse, NdviResponse, RisksResponse, SoilResponse, TerrainResponse


class RegionIndicators(BaseModel):
    vegetation: NdviResponse
    terrain: TerrainResponse
    soil: SoilResponse
    hydrology: HydrologyResponse
    risks: RisksResponse


class RegionWithIndicators(RegionSummary):
    indicators: RegionIndicators
