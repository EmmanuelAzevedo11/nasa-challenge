from collections.abc import Callable
from math import fsum

from app.schemas.environmental import WeatherForecast
from app.schemas.indicators import RiskIndicator, RiskLevel, RisksResponse

SOURCE_URL = "https://open-meteo.com/en/docs"
FROST_URL = "https://avisos.inmet.gov.br/56121"
INMET_URL = "https://www.gov.br/mdr/pt-br/centrais-de-conteudo/publicacoes/protecao-e-defesa-civil-sedec/guiapraticodesastres.pdf"
EMBRAPA_SOY_URL = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1123928/1/SP-17-2020-online-1.pdf"
EMBRAPA_CORN_URL = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/748759/1/Milho-Plantio.pdf"
SUGARCANE_HEAT_URL = "https://portal.inmet.gov.br/uploads/publicacoesDigitais/agrometeorologia_dos_cultivos.pdf#page=122"
HEAT_CRITERIA = {
    "soybean": (40, EMBRAPA_SOY_URL),
    "corn": (35, EMBRAPA_CORN_URL),
    "sugarcane": (35, SUGARCANE_HEAT_URL),
}
LIMITATION = "Triagem regional baseada em previsão. Para avisos oficiais, consulte o INMET."


def threshold_indicator(
    forecast: WeatherForecast, kind: str, field: str, unit: str,
    reducer: Callable, classify: Callable[[float], RiskLevel],
    criterion: str, limitations: list[str], criteria_url: str | None,
) -> RiskIndicator:
    samples = [
        (getattr(day, field), day.date)
        for day in forecast.daily if getattr(day, field) is not None
    ]
    metadata = forecast.daily_metrics.get(field)
    if metadata is None or metadata.unit != unit:
        samples = []
    value, when = reducer(samples) if samples else (None, None)
    level = classify(value) if value is not None else "insufficient_data"
    if level == "low" and len(samples) < forecast.requested_days:
        level = "insufficient_data"
    justification = (
        f"Indicador calculado com {len(samples)} de {forecast.requested_days} dias. {criterion}"
        if level != "insufficient_data" else
        f"Evidência insuficiente no período analisado. {criterion}"
    )
    return RiskIndicator(
        type=kind, level=level, justification=justification, reference_date=when,
        values={field: value}, limitations=[LIMITATION, *limitations], criteria_url=criteria_url,
    )


def water_deficit(forecast: WeatherForecast) -> RiskIndicator:
    soil = next((
        metric.value for metric in forecast.current.soil_moisture
        if metric.depth_cm == (3, 9) and metric.unit == "m³/m³" and metric.status == "available"
    ), None)
    rain = [day.precipitation for day in forecast.daily if day.precipitation is not None]
    et0 = [
        day.reference_evapotranspiration
        for day in forecast.daily if day.reference_evapotranspiration is not None
    ]
    complete = (
        len(rain) == len(et0) == forecast.requested_days
        and all(
            field in forecast.daily_metrics and forecast.daily_metrics[field].unit == "mm"
            for field in ("precipitation", "reference_evapotranspiration")
        )
    )
    rain_total = fsum(rain) if complete else None
    et0_total = fsum(et0) if complete else None
    balance = rain_total - et0_total if complete else None
    if balance is None or forecast.requested_days < 5 or soil is None:
        level = "insufficient_data"
        justification = "A triagem requer pelo menos cinco dias completos de chuva e ET₀, além de umidade estimada do solo."
    elif balance < 0:
        level = "moderate"
        justification = "A chuva prevista é inferior à evapotranspiração de referência no período."
    else:
        level = "low"
        justification = "A chuva acumulada prevista iguala ou supera a evapotranspiração de referência no período."
    return RiskIndicator(
        type="water_deficit", level=level, justification=justification, criteria_url=SOURCE_URL,
        values={
            "precipitation_mm": round(rain_total, 2) if rain_total is not None else None,
            "reference_et0_mm": round(et0_total, 2) if et0_total is not None else None,
            "precipitation_minus_et0_mm": round(balance, 2) if balance is not None else None,
            "soil_moisture_3_to_9cm_m3_m3": soil,
        },
        limitations=[
            "A diferença chuva menos ET₀ caracteriza demanda atmosférica de referência.",
            "A umidade superficial contextualiza o sinal. O balanço da zona radicular exige dados da cultura e do solo.",
        ],
    )


def analyze_risks(forecast: WeatherForecast, crop_id: str | None = None) -> RisksResponse:
    heat_limit, heat_url = HEAT_CRITERIA.get(crop_id, (None, None))
    indicators = [
        threshold_indicator(
            forecast, "frost", "temperature_min", "°C", min,
            lambda t: "high" if t <= 0 else "moderate" if t <= 3 else "low",
            "A triagem sinaliza mínimas do ar até 3 °C e dá destaque a valores até 0 °C.",
            ["A formação de geada depende do microclima e da temperatura junto à superfície."], FROST_URL,
        ),
        threshold_indicator(
            forecast, "heat", "temperature_max", "°C", max,
            lambda t: (
                "insufficient_data" if heat_limit is None else "high" if t > heat_limit else "low"
            ),
            f"A triagem sinaliza máxima diária prevista acima de {heat_limit} °C para a cultura selecionada."
            if heat_limit is not None else "Há critérios de calor disponíveis para soja, milho e cana-de-açúcar.",
            ["O efeito térmico depende do estágio, da duração da exposição e da cultivar."], heat_url,
        ),
        threshold_indicator(
            forecast, "heavy_rain", "precipitation", "mm", max,
            lambda v: "high" if v > 100 else "moderate" if v >= 50 else "low",
            "Triagem pelo maior acumulado diário a partir de 50 mm, com destaque acima de 100 mm.",
            ["Picos horários e condições locais exigem avaliação própria."], INMET_URL,
        ),
        threshold_indicator(
            forecast, "strong_wind", "wind_gusts_max", "km/h", max,
            lambda v: "high" if v > 100 else "moderate" if v >= 60 else "low",
            "Triagem pela maior rajada diária a partir de 60 km/h, com destaque acima de 100 km/h.",
            ["A exposição local depende do relevo e da cobertura."], INMET_URL,
        ),
        water_deficit(forecast),
    ]
    assessed = sum(item.level != "insufficient_data" for item in indicators)
    if forecast.status == "provider_error":
        status = "provider_error"
    elif assessed == len(indicators):
        status = "available"
    else:
        status = "partial" if assessed else "insufficient_data"
    dates = [day.date for day in forecast.daily]
    return RisksResponse(
        location=forecast.location, status=status, period_start=min(dates, default=None),
        period_end=max(dates, default=None), requested_days=forecast.requested_days,
        crop_id=crop_id, indicators=indicators, limitations=[LIMITATION],
    )
