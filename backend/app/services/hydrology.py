from math import asin, cos, radians, sin, sqrt

from app.core.config import Settings
from app.core.http_client import ProviderClient, ProviderError
from app.schemas.indicators import HydrologyResponse, HydrologyStation
from app.schemas.location import Coordinates, Location
from app.services.environmental_data import numeric, object_value

SOURCE_URL = "https://www.snirh.gov.br/arcgis/rest/services/SGH/REDE_HIDROMETEOROLOGICA_NACIONAL/MapServer/3"
MANUAL_URL = (
    "https://www.gov.br/ana/pt-br/assuntos/monitoramento-e-eventos-criticos/"
    "monitoramento-hidrologico/orientacoes-manuais/manuais/manual-hidrowebservice_publica.pdf"
)


def distance_km(first: Coordinates, second: Coordinates) -> float:
    dlat = radians(second.latitude - first.latitude)
    dlon = radians(second.longitude - first.longitude)
    a = sin(dlat / 2) ** 2 + cos(radians(first.latitude)) * cos(radians(second.latitude)) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(min(1.0, a)))


def parse_stations(payload: dict, location: Location, radius_km: int) -> list[HydrologyStation]:
    if "error" in payload or payload.get("exceededTransferLimit") or not isinstance(payload.get("features"), list):
        raise ValueError("Inventário indisponível ou incompleto.")
    stations = {}
    for feature in payload["features"]:
        feature = object_value(feature)
        attr, point = object_value(feature.get("attributes")), object_value(feature.get("geometry"))
        lat, lon = numeric(point.get("y")), numeric(point.get("x"))
        code, name = attr.get("CODIGO"), attr.get("NOME")
        if lat is None or lon is None or code is None or not isinstance(name, str) or not name:
            continue
        coords = Coordinates(latitude=lat, longitude=lon)
        distance = distance_km(location, coords)
        if distance > radius_km:
            continue
        operating = str(attr.get("OPERANDO", "")).strip().casefold()
        stations[str(code)] = HydrologyStation(
            code=str(code), name=name, location=coords, distance_km=round(distance, 2),
            operating={"1": True, "0": False, "true": True, "false": False, "sim": True, "não": False}.get(operating),
        )
    return sorted(stations.values(), key=lambda station: station.distance_km)[:5]


async def get_hydrology(
    client: ProviderClient, settings: Settings, location: Location, radius_km: int = 50,
) -> HydrologyResponse:
    lat, lon = location.latitude, location.longitude
    dy = radius_km / 110
    dx = dy / cos(radians(lat))
    try:
        stations = await client.get(
            "ANA / SNIRH", str(settings.ana_station_url),
            {
                "f": "json", "where": "1=1", "inSR": "4326", "outSR": "4326",
                "geometryType": "esriGeometryEnvelope",
                "geometry": f"{lon - dx},{lat - dy},{lon + dx},{lat + dy}",
                "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "true",
                "outFields": "CODIGO,NOME,OPERANDO",
            },
            21600, lambda payload: parse_stations(payload, location, radius_km),
        )
        status = "partial" if stations else "insufficient_data"
    except ProviderError:
        stations, status = [], "provider_error"

    return HydrologyResponse(
        location=location, status=status, stations=stations, search_radius_km=radius_km,
        limitations=[
            "Inventário de estações com medição de descarga, por distância em linha reta.",
            "As séries de níveis e vazões exigem acesso autorizado ao HidroWebService da ANA.",
            "A disponibilidade de água para irrigação exige avaliação da bacia e das condições locais.",
        ],
    )
