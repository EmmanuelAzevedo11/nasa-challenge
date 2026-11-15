import type {
  AIChatResponse,
  Availability,
  ClimateHistory,
  CropSuitability,
  CropRotationStrategy,
  EnvironmentalRisk,
  EnvironmentalSummary,
  Indicator,
  RotationObjective,
  WeatherData,
} from "./contracts";

type Status = "available" | "partial" | "unavailable" | "insufficient_data" | "provider_error";

type Measurement = {
  status: Status;
  value: number | null;
  unit: string | null;
  source: string;
  reference_time: string | null;
};

type DailyValues = {
  date: string;
  temperature: number | null;
  precipitation: number | null;
  relative_humidity: number | null;
};

export type HistoryResponse = {
  source: string;
  last_available_date: string | null;
  daily: (DailyValues & { wind_speed: number | null })[];
};

export type ForecastResponse = {
  source: string;
  current: { reference_time: string | null };
  daily: (DailyValues & {
    wind_speed_max: number | null;
    precipitation_probability_max: number | null;
  })[];
};

export type SummaryResponse = {
  weather: {
    reference_time: string | null;
    temperature: Measurement;
    precipitation: Measurement;
    relative_humidity: Measurement;
    wind_speed: Measurement;
    soil_moisture: Measurement[];
  };
};

export type TerrainResponse = {
  status: Status;
  elevation_m: number | null;
  source: string;
};

export const soilLabels = {
  ph_water: "pH do solo (0 a 5 cm)",
  clay: "Argila (0 a 5 cm)",
  sand: "Areia (0 a 5 cm)",
  silt: "Silte (0 a 5 cm)",
  organic_carbon: "Carbono orgânico (0 a 5 cm)",
};

export type SoilResponse = {
  source: string;
  properties: {
    property: keyof typeof soilLabels;
    value: number | null;
    unit: string;
    status: Status;
  }[];
};

const riskLabels = {
  frost: "Geada potencial",
  heat: "Calor excessivo",
  heavy_rain: "Chuva intensa",
  strong_wind: "Vento forte",
  water_deficit: "Déficit hídrico",
};

const riskLevels = {
  low: "Baixo",
  moderate: "Moderado",
  high: "Alto",
  insufficient_data: "Indisponível",
} as const;

export type RisksResponse = {
  period_start: string | null;
  period_end: string | null;
  indicators: {
    type: keyof typeof riskLabels;
    level: keyof typeof riskLevels;
    justification: string;
    reference_date: string | null;
    source: string;
    criteria_url?: string | null;
  }[];
};

const classifications = {
  potentially_favorable: "Condições potencialmente favoráveis",
  restricted: "Condições com restrições",
  unfavorable: "Sem janela no ZARC",
  insufficient_data: "Dados insuficientes",
};

export const rotationObjectives: Record<RotationObjective, string> = {
  soil_conservation: "Conservação do solo",
  diversification: "Diversificar a produção",
  grain_production: "Produção de grãos",
  risk_reduction: "Reduzir riscos climáticos",
};

type Reference = { title: string; url: string };

type Assessment = {
  crop_id: string;
  name: string;
  classification: keyof typeof classifications;
  climate_requirements: string;
  water_requirements: string | null;
  favorable_factors: string[];
  restrictions: string[];
  limitations: string[];
  zarc: {
    source: string;
    source_url: string;
    season: string | null;
    limitations: string[];
    scenarios: {
      crop_name: string;
      missing_conditions: string[];
      periods: { start_on: string; end_on: string; status: string; risk_percent: number | null }[];
    }[];
  };
  references: Reference[];
};

export type SuitabilityResponse = {
  alternatives: Assessment[];
};

export type RotationResponse = {
  strategies: {
    name: string;
    objective: RotationObjective;
    sequence: {
      crop_id: string | null;
      name: string;
      planting_year: number | null;
      planting_month: number | null;
      planting_day?: number | null;
      role: "previous" | "grain" | "cover";
    }[];
    benefits: string[];
    restrictions: string[];
    references: Reference[];
  }[];
  limitations: string[];
};

export type ChatResponse = {
  status: NonNullable<AIChatResponse["status"]>;
  answer: string;
  sources: Reference[];
  limitations: string[];
};

const availability = (status: Status): Availability =>
  status === "available" || status === "partial" ? status : "unavailable";
const distinct = <T>(items: T[]) => [...new Set(items)];
const localDate = (date: string) => date.split("-").reverse().join("/");

export function summaryView({ weather }: SummaryResponse): EnvironmentalSummary {
  const indicators: Indicator[] = [];
  const measurements = [
    ["temperature", "Temperatura", weather.temperature],
    ["precipitation", "Precipitação", weather.precipitation],
    ["humidity", "Umidade relativa", weather.relative_humidity],
    ["wind", "Vento", weather.wind_speed],
    ["soil", "Umidade estimada do solo", weather.soil_moisture[0]],
  ] as const;
  for (const [id, label, metric] of measurements) {
    if (!metric) continue;
    indicators.push({
      id,
      label,
      value: metric.value,
      unit: metric.unit ?? "",
      source: metric.source,
      status: availability(metric.status),
      reference_date: metric.reference_time,
      kind: "estimated",
    });
  }
  return { updated_at: weather.reference_time, indicators };
}

export function historyView(data: HistoryResponse): ClimateHistory {
  return {
    source: data.source,
    reference_date: data.last_available_date,
    days: data.daily.map(({ date, temperature, precipitation, relative_humidity, wind_speed }) => ({
      date,
      temperature,
      precipitation,
      humidity: relative_humidity,
      wind: wind_speed,
      source: data.source,
      reference_date: date,
    })),
  };
}

export function forecastView(data: ForecastResponse): WeatherData[] {
  return data.daily.map((day) => ({
    date: day.date,
    temperature: day.temperature,
    precipitation: day.precipitation,
    humidity: day.relative_humidity,
    wind: day.wind_speed_max,
    rain_probability: day.precipitation_probability_max,
    source: data.source,
    reference_date: data.current.reference_time?.slice(0, 10) ?? null,
  }));
}

export function risksView(data: RisksResponse): EnvironmentalRisk[] {
  return data.indicators.map((risk) => ({
    id: risk.type,
    name: riskLabels[risk.type],
    level: riskLevels[risk.level],
    explanation: risk.justification,
    period:
      data.period_start && data.period_end
        ? `${localDate(data.period_start)} a ${localDate(data.period_end)}`
        : "Período indisponível",
    source: risk.source,
    reference_date: risk.reference_date,
    criteria_url: risk.criteria_url ?? null,
  }));
}

export function terrainView(data: TerrainResponse): Indicator[] {
  return [
    {
      id: "altitude",
      label: "Altitude",
      value: data.elevation_m,
      unit: "m",
      source: data.source,
      reference_date: null,
      status: availability(data.status),
      kind: "observed",
    },
  ];
}

export function soilView(data: SoilResponse): Indicator[] {
  return data.properties.map((property) => ({
    id: property.property,
    label: soilLabels[property.property],
    value: property.value,
    unit: property.unit,
    source: data.source,
    reference_date: null,
    status: availability(property.status),
    kind: "estimated",
  }));
}

export function suitabilityView(data: SuitabilityResponse): CropSuitability[] {
  return data.alternatives.map((item) => {
    const windows = distinct(
      item.zarc.scenarios.flatMap((row) =>
        row.periods
          .filter((period) => period.status === "window")
          .map(
            (period) =>
              `${item.zarc.season === null ? `${row.crop_name}: ` : ""}${localDate(period.start_on)} a ${localDate(period.end_on)} (${period.risk_percent}% de risco)`,
          ),
      ),
    ).sort((a, b) => a.localeCompare(b, "pt-BR", { numeric: true }));
    const restrictions = distinct([
      ...item.restrictions,
      ...item.zarc.limitations,
      ...item.limitations,
    ]);
    return {
      crop: { id: item.crop_id, name: item.name },
      classification: classifications[item.classification],
      justification:
        item.favorable_factors.join(" ") ||
        item.restrictions[0] ||
        classifications[item.classification],
      planting_window: windows.join(" · ") || "Nenhuma janela confirmada no cenário consultado.",
      climate: item.climate_requirements,
      water: item.water_requirements ?? "Requisito hídrico não informado",
      restrictions,
      zarc_url: item.zarc.source_url,
      zarc: `${item.zarc.source} · ${item.zarc.season ? `Safra ${item.zarc.season}` : "Culturas sem safra"}${item.zarc.scenarios.some((row) => row.missing_conditions.length) ? ". As janelas variam conforme as condições do cenário." : ""}`,
      sources: distinct([...item.references.map((reference) => reference.title), item.zarc.source]),
    };
  });
}

export function rotationView(data: RotationResponse): {
  strategies: CropRotationStrategy[];
  limitations: string[];
} {
  const roles = { previous: "Cultivo anterior", grain: "Produção", cover: "Cobertura" };
  return {
    limitations: data.limitations,
    strategies: data.strategies.map((strategy) => ({
      id: strategy.sequence.map((step) => step.crop_id ?? step.name).join("-"),
      name: strategy.name,
      objective: rotationObjectives[strategy.objective],
      sequence: strategy.sequence.map((step) => ({
        season: roles[step.role],
        crop: step.name,
        period:
          step.planting_month && step.planting_year
            ? `${step.planting_day ? `${String(step.planting_day).padStart(2, "0")}/` : ""}${String(step.planting_month).padStart(2, "0")}/${step.planting_year}`
            : "Época não informada",
      })),
      benefits: strategy.benefits,
      restrictions: strategy.restrictions,
      sources: distinct(strategy.references.map((reference) => reference.title)),
    })),
  };
}

export function chatView(data: ChatResponse): AIChatResponse {
  return {
    answer: data.answer,
    sources: distinct(data.sources.map((reference) => reference.title)),
    kind: "interpretation",
    status: data.status,
    insufficient_data: data.status === "partial",
    limitations: data.limitations,
  };
}
