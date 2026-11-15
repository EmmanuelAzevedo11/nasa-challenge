from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import LocationDependency, ServiceDependency
from app.schemas.indicators import HydrologyResponse, NdviResponse, RisksResponse, SoilResponse, TerrainResponse
from app.services.hydrology import get_hydrology
from app.services.modis import get_vegetation_index
from app.services.open_meteo import get_weather_forecast
from app.services.opentopodata import get_terrain
from app.services.risk_analysis import analyze_risks
from app.services.soilgrids import get_soil

router = APIRouter(tags=["Indicadores complementares"])


@router.get("/vegetation/ndvi", summary="Consultar índice de vegetação NASA MODIS")
async def vegetation(
    location: LocationDependency, services: ServiceDependency, limit: Annotated[int, Query(ge=1, le=10)] = 6,
) -> NdviResponse:
    return await get_vegetation_index(services.client, services.settings, location, limit)


@router.get("/terrain", summary="Consultar altitude SRTM")
async def terrain(location: LocationDependency, services: ServiceDependency) -> TerrainResponse:
    return await get_terrain(services.client, services.settings, location)


@router.get("/soil", summary="Consultar propriedades superficiais do SoilGrids")
async def soil(location: LocationDependency, services: ServiceDependency) -> SoilResponse:
    return await get_soil(services.client, services.settings, location)


@router.get("/hydrology", summary="Consultar estações fluviométricas próximas")
async def hydrology(
    location: LocationDependency, services: ServiceDependency,
    radius_km: Annotated[int, Query(ge=5, le=100)] = 50,
) -> HydrologyResponse:
    return await get_hydrology(services.client, services.settings, location, radius_km)


@router.get("/risks", summary="Consultar triagem de riscos agroambientais")
async def risks(
    location: LocationDependency, services: ServiceDependency,
    days: Annotated[int, Query(ge=1, le=7)] = 7,
    crop_id: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
) -> RisksResponse:
    forecast = await get_weather_forecast(services.client, services.settings, location, days=days)
    return analyze_risks(forecast, crop_id)
