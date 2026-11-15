import argparse
import calendar
import csv
import gzip
import logging
import re
import tempfile
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from sys import intern

from app.schemas.crop import (
    Crop,
    MunicipalityCoverage,
    SuitabilityRequest,
    ZarcConditions,
    ZarcCoverage,
    ZarcPeriod,
    ZarcResult,
    ZarcScenario,
    ZarcStatus,
)

SOURCE_URL = "https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico"
SEASON_RESOURCES = {
    2026: "139e5a60-1f43-4cc8-aeab-a35dbbf816c0",
    2025: "f9d597f9-0fee-47eb-9344-8642274ca9da",
}
SEASON_FILENAME = re.compile(r"(\d{4})-(\d{4})\.csv(?:\.gz)?")
DECENDIOS = tuple(f"dec{number}" for number in range(1, 37))
CONDITION_COLUMNS = {
    "soil_code": "cod_solo",
    "cultivar_group_code": "cod_ciclo",
    "management_code": "cod_outros_manejos",
    "climate_code": "cod_clima",
    "management_level_code": "cod_nm",
    "productivity": "produtividade",
}
REQUIRED_COLUMNS = {
    "uf", "geocodigo", "municipio", "safraini", "safrafin", "nome_cultura", "cod_cultura",
    "cod_solo", "cod_ciclo", "cod_outros_manejos", "cod_clima", "portaria",
    *DECENDIOS,
}
RISK_CODES = {"20": 20, "30": 30, "40": 40}
UNAVAILABLE_MESSAGES = {
    "season_unavailable": "A safra solicitada está indisponível na base local do MAPA.",
    "municipality_unresolved": "A identificação segura do município é necessária para consultar o ZARC.",
    "no_municipality_records": "A base importada para esta safra não contém registros do município.",
    "no_crop_records": "A base importada não contém uma modalidade da cultura do catálogo para este município e safra.",
    "no_matching_conditions": "A base importada não contém registros para a combinação de condições informada.",
}
CONDITIONAL_LIMITATION = (
    "Cada nível de risco se aplica ao decêndio e às condições do respectivo registro oficial."
)

logger = logging.getLogger(__name__)


def season_label(year: int) -> str:
    return f"{year}/{year + 1}"


def season_source(year: int) -> str:
    resource = SEASON_RESOURCES.get(year)
    return f"{SOURCE_URL}/resource/{resource}" if resource else SOURCE_URL


@lru_cache(maxsize=128)
def normalize_name(value: str) -> str:
    plain = "".join(
        letter for letter in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(letter)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain.casefold()).split())


@dataclass(frozen=True, slots=True)
class Record:
    name: str
    code: str
    conditions: ZarcConditions
    ordinance: str | None
    decendios: tuple[str, ...]


@dataclass
class MunicipalityRecords:
    name: str
    crops: dict[str, list[Record]] = field(default_factory=dict)


class ZarcIndex:
    def __init__(self, directory: Path):
        self.seasons: dict[int, dict[str, MunicipalityRecords]] = {}
        for path in sorted(directory.glob("*.csv*")):
            match = SEASON_FILENAME.fullmatch(path.name)
            if match is None:
                continue
            year = int(match[1])
            try:
                if int(match[2]) != year + 1 or year in self.seasons:
                    raise ValueError("Use um arquivo por safra no formato AAAA-AAAA.csv[.gz].")
                self.seasons[year] = read_season(path, year)
            except (OSError, EOFError, UnicodeError, csv.Error, ValueError) as exc:
                logger.warning("zarc_import_failed file=%s error=%s", path.name, exc)

    def coverage(self, season: int) -> ZarcCoverage:
        municipalities = self.seasons.get(season, {})
        covered = []
        all_crops = set()
        for code, municipality in sorted(municipalities.items()):
            names = sorted({records[0].name for records in municipality.crops.values()})
            all_crops.update(names)
            covered.append(MunicipalityCoverage(ibge_code=code, name=municipality.name, crops=names))
        return ZarcCoverage(
            status="available" if municipalities else "unavailable",
            source_url=season_source(season),
            available_seasons=[season_label(year) for year in sorted(self.seasons, reverse=True)],
            season=season_label(season),
            municipalities=covered,
            crops=sorted(all_crops),
        )

    def query(self, code: str | None, crop: Crop, request: SuitabilityRequest) -> ZarcResult:
        season = request.season
        result = ZarcResult(status="available", source_url=season_source(season), season=season_label(season))
        if code is None:
            return unavailable(result, "municipality_unresolved")
        if season not in self.seasons:
            return unavailable(result, "season_unavailable")
        municipality = self.seasons[season].get(code)
        if municipality is None:
            return unavailable(result, "no_municipality_records")

        names = dict.fromkeys(normalize_name(alias) for alias in crop.zarc_names)
        records = [record for name in names for record in municipality.crops.get(name, ())]
        if not records:
            return unavailable(result, "no_crop_records")

        filters = request.zarc_conditions.model_dump(exclude_none=True)
        result.scenarios = [
            ZarcScenario(
                crop_name=record.name,
                crop_code=record.code,
                conditions=record.conditions,
                missing_conditions=[
                    name for name in CONDITION_COLUMNS
                    if name not in filters and getattr(record.conditions, name) is not None
                    and (name != "climate_code" or record.conditions.climate_code != 0)
                ],
                ordinance=record.ordinance,
                periods=requested_periods(record, request),
            )
            for record in records
            if all(getattr(record.conditions, name) == value for name, value in filters.items())
        ]
        if not result.scenarios:
            return unavailable(result, "no_matching_conditions")
        result.limitations = [CONDITIONAL_LIMITATION]
        return result


def unavailable(result: ZarcResult, status: ZarcStatus) -> ZarcResult:
    return result.model_copy(update={"status": status, "limitations": [UNAVAILABLE_MESSAGES[status]]})


def requested_periods(record: Record, request: SuitabilityRequest) -> list[ZarcPeriod]:
    year, month, day = request.planting_year, request.planting_month, request.planting_day
    month_end = calendar.monthrange(year, month)[1]
    periods = []
    for index, (first, last) in enumerate(((1, 10), (11, 20), (21, month_end)), start=1):
        if day is not None and not first <= day <= last:
            continue
        number = (month - 1) * 3 + index
        raw = record.decendios[number - 1]
        risk = RISK_CODES.get(raw)
        periods.append(ZarcPeriod(
            decendio=number,
            start_on=date(year, month, first),
            end_on=date(year, month, last),
            status="window" if risk is not None else "no_window" if raw == "0" else "unknown",
            risk_percent=risk,
            source_value=raw or None,
        ))
    return periods


def read_sp_rows(path: Path, season: int) -> Iterator[tuple[list[str], dict[str, str]]]:
    open_csv = gzip.open if path.suffix == ".gz" else open
    with open_csv(path, "rt", encoding="utf-8-sig", newline="") as stream:
        header = stream.readline()
        delimiter = ";" if header.count(";") > header.count(",") else ","
        columns = [field.strip().casefold() for field in next(csv.reader([header], delimiter=delimiter))]
        missing = REQUIRED_COLUMNS - set(columns)
        if missing or len(set(columns)) != len(columns):
            raise ValueError(f"Cabeçalho ZARC inválido. Colunas ausentes: {', '.join(sorted(missing))}.")
        rows = csv.DictReader(stream, fieldnames=columns, delimiter=delimiter, strict=True)
        for row in rows:
            if (row.get("uf") or "").strip().upper() != "SP":
                continue
            if None in row or None in row.values():
                raise ValueError(f"Linha {rows.line_num + 1} com quantidade incorreta de colunas.")
            if (row["safraini"].strip(), row["safrafin"].strip()) != (str(season), str(season + 1)):
                raise ValueError(f"Linha {rows.line_num + 1} pertence a outra safra.")
            if not re.fullmatch(r"35\d{5}", row["geocodigo"].strip()):
                raise ValueError(f"Geocódigo paulista inválido na linha {rows.line_num + 1}.")
            if not all(row[name].strip() for name in ("municipio", "nome_cultura", "cod_cultura")):
                raise ValueError(f"Identificação incompleta na linha {rows.line_num + 1}.")
            yield columns, row


def read_season(path: Path, season: int) -> dict[str, MunicipalityRecords]:
    municipalities: dict[str, MunicipalityRecords] = {}
    condition_sets: dict[tuple[str, ...], ZarcConditions] = {}
    risk_patterns: dict[tuple[str, ...], tuple[str, ...]] = {}
    for _, row in read_sp_rows(path, season):
        code = intern(row["geocodigo"].strip())
        municipality = municipalities.get(code)
        if municipality is None:
            municipality = MunicipalityRecords(name=row["municipio"].strip())
            municipalities[code] = municipality
        name = intern(row["nome_cultura"].strip())
        condition_values = tuple(row.get(column, "").strip() for column in CONDITION_COLUMNS.values())
        if condition_values not in condition_sets:
            condition_sets[condition_values] = ZarcConditions.model_validate({
                name: value or None for name, value in zip(CONDITION_COLUMNS, condition_values)
            })
        decendios = tuple(row[column].strip() for column in DECENDIOS)
        record = Record(
            name=name,
            code=intern(row["cod_cultura"].strip()),
            conditions=condition_sets[condition_values],
            ordinance=intern(row["portaria"].strip()) or None,
            decendios=risk_patterns.setdefault(decendios, decendios),
        )
        municipality.crops.setdefault(normalize_name(name), []).append(record)
    if not municipalities:
        raise ValueError("Nenhum registro da safra foi encontrado em São Paulo.")
    return municipalities


def import_csv(source: Path, directory: Path, season: int) -> tuple[Path, int]:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{season}-{season + 1}.csv.gz"
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".csv.gz", delete=False) as temp:
        temporary_path = Path(temp.name)
    try:
        with gzip.open(temporary_path, "wt", encoding="utf-8", newline="", compresslevel=6) as output:
            writer = None
            count = 0
            for columns, row in read_sp_rows(source, season):
                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=columns, delimiter=";")
                    writer.writeheader()
                writer.writerow(row)
                count += 1
        read_season(temporary_path, season)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination, count


def main() -> None:
    from app.core.config import Settings

    parser = argparse.ArgumentParser(description="Importar registros de São Paulo de um CSV oficial do ZARC.")
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--safra-inicio", type=int, required=True)
    args = parser.parse_args()
    if not 1981 <= args.safra_inicio <= 2100:
        parser.error("Informe o ano inicial da safra entre 1981 e 2100.")
    try:
        path, rows = import_csv(args.arquivo, Settings().resolved_zarc_data_dir, args.safra_inicio)
    except (OSError, EOFError, UnicodeError, csv.Error, ValueError) as exc:
        parser.exit(1, f"Falha na importação do ZARC: {exc}\n")
    print(f"{rows} registros de São Paulo importados para {path}.")


if __name__ == "__main__":
    main()
