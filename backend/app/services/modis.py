import asyncio
from datetime import date, datetime

from app.core.config import Settings
from app.core.http_client import ProviderClient, ProviderError
from app.schemas.indicators import NdviObservation, NdviResponse
from app.schemas.location import Location
from app.services.environmental_data import numeric

SOURCE = "NASA MODIS / ORNL DAAC"
SOURCE_URL = "https://modis.ornl.gov/data/modis_webservice.html"
NDVI_BAND = "250m_16_days_NDVI"
QUALITY_BAND = "250m_16_days_pixel_reliability"


def modis_day(value: str) -> date:
    return datetime.strptime(value, "A%Y%j").date()


def parse_dates(payload: dict | list) -> list[str]:
    dates = payload["dates"] if isinstance(payload, dict) else payload
    return sorted({item["modis_date"] for item in dates}, key=modis_day)


def verify_bands(payload: dict | list) -> bool:
    rows = payload["bands"] if isinstance(payload, dict) else payload
    bands = {band["band"] if isinstance(band, dict) else band for band in rows}
    if not {NDVI_BAND, QUALITY_BAND} <= bands:
        raise ValueError("As bandas de NDVI e qualidade não estão disponíveis.")
    return True


def parse_pixels(payload: dict) -> dict[tuple[str, str], float | None]:
    if int(payload["ncols"]) != 1 or int(payload["nrows"]) != 1:
        raise ValueError("O subconjunto geográfico deve conter um pixel.")
    pixels = {}
    for row in payload["subset"]:
        if row["band"] not in {NDVI_BAND, QUALITY_BAND}:
            continue
        data = row["data"]
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError("Quantidade inválida de pixels.")
        pixels[(row["modis_date"], row["band"])] = numeric(data[0])
    return pixels


async def get_vegetation_index(
    client: ProviderClient, settings: Settings, location: Location, limit: int = 6,
) -> NdviResponse:
    url = f"{str(settings.modis_base_url).rstrip('/')}/MOD13Q1"
    coords = {"latitude": str(location.latitude), "longitude": str(location.longitude)}
    observations = []
    latest = None
    try:
        dates, _ = await asyncio.gather(
            client.get(SOURCE, f"{url}/dates", coords, 21600, parse_dates, allow_array=True),
            client.get(SOURCE, f"{url}/bands", {}, 86400, verify_bands, allow_array=True),
        )
        dates = dates[-limit:]
        if dates:
            pixels = await client.get(
                SOURCE, f"{url}/subset",
                {
                    **coords, "startDate": dates[0], "endDate": dates[-1],
                    "kmAboveBelow": "0", "kmLeftRight": "0",
                },
                21600, parse_pixels,
            )
            for key in dates:
                raw = pixels.get((key, NDVI_BAND))
                quality = pixels.get((key, QUALITY_BAND))
                valid = quality == 0 and raw is not None and -2000 <= raw <= 10000
                observations.append(NdviObservation(
                    date=modis_day(key), value=round(raw * 0.0001, 4) if valid else None,
                    pixel_reliability=int(quality) if quality in {-1, 0, 1, 2, 3} else None,
                    status="available" if valid else "insufficient_data",
                ))
        latest = next((item for item in reversed(observations) if item.status == "available"), None)
        if latest is None:
            status = "insufficient_data"
        elif any(item.status != "available" for item in observations):
            status = "partial"
        else:
            status = "available"
    except ProviderError:
        status = "provider_error"

    return NdviResponse(
        location=location, status=status, latest=latest, observations=observations,
        limitations=[
            "NDVI do pixel de 250 m na composição de 16 dias, com uso de observações de boa qualidade.",
            "O pixel pode misturar coberturas. Fertilidade, nutrientes e produtividade exigem evidências próprias.",
        ],
    )
