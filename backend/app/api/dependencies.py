from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request

from app.core.config import Settings
from app.core.http_client import ProviderClient
from app.schemas.location import Coordinates, Location

Latitude = Annotated[float, Query(ge=-90, le=90, description="Latitude WGS84 em graus decimais.")]
Longitude = Annotated[float, Query(ge=-180, le=180, description="Longitude WGS84 em graus decimais.")]


@dataclass
class Services:
    settings: Settings
    client: ProviderClient


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_location(request: Request, latitude: Latitude, longitude: Longitude) -> Location:
    coordinates = Coordinates(latitude=latitude, longitude=longitude)
    return request.app.state.boundaries.locate(coordinates)


ServiceDependency = Annotated[Services, Depends(get_services)]
LocationDependency = Annotated[Location, Depends(get_location)]
