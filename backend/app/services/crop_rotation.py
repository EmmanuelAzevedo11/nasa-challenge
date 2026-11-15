from fastapi import HTTPException

from app.core.config import Settings
from app.core.http_client import ProviderClient
from app.schemas.crop import Crop, CropAssessment, Reference
from app.schemas.location import Location
from app.schemas.rotation import RotationRequest, RotationResponse, RotationStrategy, StrategyCrop, StrategyType
from app.services.crop_analysis import analyze_suitability
from app.services.crop_catalog import get_crops
from app.services.zarc import ZarcIndex, normalize_name

ROTATION_SOURCE = Reference(
    title="Embrapa — Sistema Plantio Direto, 500 perguntas e 500 respostas",
    url="https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/98258/1/500perguntassistemaplantiodireto.pdf",
)
COVER_SOURCE = Reference(
    title="Embrapa — Adubação verde e plantas de cobertura no Brasil",
    url="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1153241/1/ADUBACAO-VERDE-VOL-01-ed02-2023.pdf",
)
COVER_CROPS = {"oat", "sunn_hemp"}
PLAN_LIMIT = (
    "Confirme a data de colheita, o ciclo da cultivar, o estoque de água, "
    "o histórico fitossanitário da área e a janela na portaria."
)


def build_strategy(
    previous: StrategyCrop, candidate: Crop, assessment: CropAssessment, request: RotationRequest,
) -> RotationStrategy:
    earlier = request.previous_planting_date
    cover = candidate.id in COVER_CROPS and request.objective == "soil_conservation"
    kind: StrategyType = "sequence_to_validate"
    if cover:
        kind = "cover_crop"
    elif earlier:
        earlier_season = earlier.year - int(earlier.month <= 6)
        if earlier_season == request.season:
            kind = "succession"
        elif earlier.month == request.planting_month:
            kind = "rotation_candidate"

    benefits = list(candidate.rotation_roles)
    restrictions = [*assessment.restrictions, PLAN_LIMIT]
    if previous.family is None:
        restrictions.append(
            "A cultura anterior está fora do catálogo. Confirme a família botânica e a compatibilidade da sequência."
        )
    elif previous.family != candidate.family:
        benefits.append("Alternância entre famílias botânicas.")
    else:
        restrictions.append("As duas culturas são da mesma família. Revise alvos fitossanitários em comum.")
    if cover:
        restrictions.append(
            "Confirme se a janela e a portaria do ZARC abrangem a finalidade de cobertura "
            "e planeje o manejo da biomassa."
        )
    if kind == "sequence_to_validate":
        restrictions.append("Confirme as épocas da sequência para avaliar se ela compõe uma rotação ou sucessão.")

    return RotationStrategy(
        name=f"{candidate.name} após {previous.name}",
        objective=request.objective,
        strategy_type=kind,
        sequence=[
            previous,
            StrategyCrop(
                crop_id=candidate.id, name=candidate.name, family=candidate.family,
                planting_month=request.planting_month, planting_year=request.planting_year,
                planting_day=request.planting_day, role="cover" if cover else "grain",
            ),
        ],
        benefits=benefits,
        restrictions=restrictions,
        justification=(
            "Há janela oficial em pelo menos um decêndio e cenário da safra selecionada. "
            "A estratégia considera a função agronômica da cultura e a classificação regional de plantio."
        ),
        assessment=assessment,
        references=[*assessment.references, ROTATION_SOURCE, *([COVER_SOURCE] if cover else [])],
    )


def priority(strategy: RotationStrategy) -> tuple:
    previous, candidate = strategy.sequence
    different_family = previous.family is not None and previous.family != candidate.family
    lowest_risk = min(
        period.risk_percent
        for row in strategy.assessment.zarc.scenarios
        for period in row.periods
        if period.risk_percent is not None
    )
    favorable = strategy.assessment.classification == "potentially_favorable"
    if strategy.objective == "risk_reduction":
        return lowest_risk, not favorable, not different_family, strategy.assessment.crop_id
    if strategy.objective == "soil_conservation":
        return candidate.role != "cover", not different_family, not favorable, lowest_risk, strategy.assessment.crop_id
    return not different_family, not favorable, lowest_risk, strategy.assessment.crop_id


async def analyze_rotation(
    client: ProviderClient, settings: Settings, index: ZarcIndex,
    location: Location, request: RotationRequest,
) -> RotationResponse:
    crops = {crop.id: crop for crop in get_crops()}
    if request.previous_crop_name is not None:
        name = normalize_name(request.previous_crop_name)
        previous_crop = next((
            crop for crop in crops.values()
            if any(normalize_name(alias) == name for alias in [crop.name, *crop.zarc_names])
        ), None)
        previous_name = previous_crop.name if previous_crop else request.previous_crop_name
    else:
        previous_crop = crops.get(request.previous_crop or "")
        if previous_crop is None:
            raise HTTPException(422, detail={
                "code": "unknown_crop", "message": "O identificador da cultura anterior não consta no catálogo.",
            })
        previous_name = previous_crop.name

    earlier = request.previous_planting_date
    previous = StrategyCrop(
        crop_id=previous_crop.id if previous_crop else None,
        name=previous_name, family=previous_crop.family if previous_crop else None,
        planting_year=earlier.year if earlier else None, planting_month=earlier.month if earlier else None,
        planting_day=earlier.day if earlier else None, role="previous",
    )
    suitability = await analyze_suitability(client, settings, index, location, request)
    strategies = []
    incomplete = False
    for assessment in suitability.alternatives:
        crop = crops[assessment.crop_id]
        if crop.id == previous.crop_id or (
            request.objective == "grain_production"
            and not {"Produção de grãos", "Grãos"}.intersection(crop.purposes)
        ):
            continue
        if assessment.classification == "insufficient_data":
            incomplete = True
        elif assessment.classification in {"restricted", "potentially_favorable"}:
            strategies.append(build_strategy(previous, crop, assessment, request))

    strategies.sort(key=priority)
    limits = [*suitability.limitations, PLAN_LIMIT]
    if incomplete:
        limits.append("Parte do catálogo está sem registros suficientes do ZARC para a consulta.")
    if suitability.climate.status != "available":
        limits.append("Parte dos indicadores climáticos mensais está indisponível. Use as janelas com cautela.")
    if not strategies:
        limits.append("A busca não identificou uma alternativa com janela confirmada para o cenário consultado.")
    return RotationResponse(
        location=location, objective=request.objective, season=suitability.season,
        season_inferred=suitability.season_inferred, planting_year=request.planting_year,
        planting_month=request.planting_month, planting_day=request.planting_day,
        status="available" if strategies else "insufficient_data" if incomplete else "no_eligible_window",
        climate=suitability.climate, strategies=strategies[:3], limitations=limits,
    )
