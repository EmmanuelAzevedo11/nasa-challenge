import calendar
from datetime import date, datetime
from math import fsum
from statistics import fmean

from app.core.config import Settings
from app.core.http_client import ProviderClient
from app.schemas.crop import (
    Classification,
    Crop,
    CropAssessment,
    MonthlyClimate,
    Reference,
    SuitabilityRequest,
    SuitabilityResponse,
    ZarcResult,
)
from app.schemas.environmental import ClimateHistory, DatasetStatus, HistoryDays
from app.schemas.location import Location
from app.services.crop_catalog import get_crops
from app.services.nasa_power import LOCAL_TIMEZONE, get_climate_history
from app.services.zarc import ZarcIndex, season_label

NASA_REFERENCE = Reference(
    title="NASA POWER — API diária",
    url="https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
)
REGIONAL_LIMITATION = (
    "Avaliação orientativa de escala regional. Considere análise local de solo e orientação "
    "agronômica para decidir o manejo."
)
HISTORY_LIMITATION = (
    "A série usa o mês homólogo completo mais recente pelo calendário. É uma referência "
    "histórica de um ano, com variabilidade entre safras."
)


def climate_period(request: SuitabilityRequest, today: date) -> tuple[date, date]:
    month = request.planting_month
    anchor = min(today, date(request.planting_year, month, 1))
    year = anchor.year - int(month >= anchor.month)
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def summarize_climate(history: ClimateHistory, start: date, end: date) -> MonthlyClimate:
    days = [day for day in history.daily if start <= day.date <= end]
    expected = (end - start).days + 1
    temperatures = [day.temperature for day in days if day.temperature is not None]
    rain = [day.precipitation for day in days if day.precipitation is not None]
    temperature = (
        round(fmean(temperatures), 2)
        if len(temperatures) == expected and history.metrics["temperature"].unit == "°C"
        else None
    )
    precipitation = (
        round(fsum(rain), 2)
        if len(rain) == expected and history.metrics["precipitation"].unit == "mm/day"
        else None
    )
    status: DatasetStatus
    if history.status == "provider_error":
        status = "provider_error"
    elif temperature is None and precipitation is None:
        status = "insufficient_data"
    elif temperature is None or precipitation is None:
        status = "partial"
    else:
        status = "available"

    return MonthlyClimate(
        status=status,
        reference_start=start,
        reference_end=end,
        expected_days=expected,
        temperature_days=len(temperatures),
        precipitation_days=len(rain),
        mean_air_temperature_c=temperature,
        total_precipitation_mm=precipitation,
        spatial_resolution=history.spatial_resolution,
    )


def assess_crop(crop: Crop, climate: MonthlyClimate, zarc: ZarcResult) -> CropAssessment:
    favorable = []
    restrictions = list(crop.restrictions)
    limits = [REGIONAL_LIMITATION, *zarc.limitations]
    considered = ["Catálogo agronômico"]
    if climate.mean_air_temperature_c is not None:
        considered.append("Temperatura média mensal do ar da NASA POWER")
    if climate.total_precipitation_mm is not None:
        considered.append("Precipitação acumulada no mês histórico da NASA POWER")
        limits.append("A disponibilidade hídrica durante o ciclo depende de balanço hídrico e dados locais.")
    if climate.status != "available":
        limits.append("Há indicadores históricos mensais indisponíveis para o período de referência.")

    temperature_range = crop.air_temperature_c
    temperature = climate.mean_air_temperature_c
    thermal_restriction = False
    if temperature_range is not None and temperature is not None:
        lower, upper = temperature_range.minimum, temperature_range.maximum
        thermal_restriction = temperature < lower or temperature > upper
        observation = f"Média histórica do ar de {temperature:g} °C"
        reference = f"faixa de {lower:g} a {upper:g} °C descrita para o desenvolvimento"
        if thermal_restriction:
            restrictions.append(f"{observation} fora da {reference}.")
        else:
            favorable.append(f"{observation} dentro da {reference}.")
        limits.append("Temperatura do solo e extremos durante o ciclo exigem dados próprios.")

    if temperature_range is None:
        limits.append("As referências da cultura oferecem contexto qualitativo para o clima mensal.")

    classification: Classification = "insufficient_data"
    if zarc.status == "available":
        considered.append("Tábua de Risco do ZARC por município, safra e cenário")
        periods = [period for scenario in zarc.scenarios for period in scenario.periods]
        risks = sorted({period.risk_percent for period in periods if period.risk_percent is not None})
        missing_conditions = any(scenario.missing_conditions for scenario in zarc.scenarios)
        if all(period.status == "no_window" for period in periods):
            classification = "unfavorable"
            restrictions.append("A Tábua de Risco indica ausência de janela nos cenários e decêndios consultados.")
        elif risks:
            levels = ", ".join(f"{risk}%" for risk in risks)
            favorable.append(f"Há indicação de plantio do ZARC em ao menos um cenário e decêndio, com risco de {levels}.")
            classification = "restricted"
            if missing_conditions:
                restrictions.append("Informe as condições do registro, como solo, cultivar e manejo, para filtrar as janelas.")
            if any(period.risk_percent != 20 for period in periods):
                restrictions.append("A indicação de menor risco não abrange todos os cenários ou decêndios consultados.")
            elif not missing_conditions and not thermal_restriction and climate.status == "available":
                classification = "potentially_favorable"
        else:
            limits.append("Os valores do ZARC retornados para o período não permitem interpretar uma janela.")

    references = [*crop.references]
    if climate.status in {"available", "partial"}:
        references.append(NASA_REFERENCE)
    if zarc.status == "available":
        references.append(Reference(title=zarc.source, url=zarc.source_url))
    return CropAssessment(
        crop_id=crop.id,
        name=crop.name,
        classification=classification,
        climate_requirements=crop.climate_requirements,
        water_requirements=crop.water_requirements,
        favorable_factors=favorable,
        restrictions=restrictions,
        data_considered=considered,
        zarc=zarc,
        references=references,
        limitations=limits,
    )


async def analyze_suitability(
    client: ProviderClient,
    settings: Settings,
    index: ZarcIndex,
    location: Location,
    request: SuitabilityRequest,
) -> SuitabilityResponse:
    start, end = climate_period(request, datetime.now(LOCAL_TIMEZONE).date())
    history = await get_climate_history(client, settings, location, HistoryDays.QUARTER, end=end)
    climate = summarize_climate(history, start, end)
    return SuitabilityResponse(
        location=location,
        planting_month=request.planting_month,
        planting_year=request.planting_year,
        planting_day=request.planting_day,
        season=season_label(request.season),
        season_inferred=request.season_start_year is None,
        climate=climate,
        alternatives=[
            assess_crop(crop, climate, index.query(location.municipality_ibge_code, crop, request))
            for crop in get_crops()
        ],
        limitations=[REGIONAL_LIMITATION, HISTORY_LIMITATION],
    )
