import type { Location, ClimateSeries, Crop, FarmRequest, AIChatRequest } from "./contracts";
import {
  type SummaryResponse,
  type HistoryResponse,
  type ForecastResponse,
  type RisksResponse,
  type SoilResponse,
  type TerrainResponse,
  type SuitabilityResponse,
  type RotationResponse,
  type ChatResponse,
  summaryView,
  historyView,
  forecastView,
  risksView,
  soilView,
  terrainView,
  suitabilityView,
  rotationView,
  chatView,
} from "./fastapi";
import municipalities from "@/data/sp-municipalities.json";

export const API_CONFIGURED = Boolean(import.meta.env["VITE_API_BASE_URL"]);

async function request<T>(
  path: string,
  params?: Record<string, string | number>,
  body?: unknown,
): Promise<T> {
  const base = import.meta.env["VITE_API_BASE_URL"];
  if (!base) throw new Error("O serviço de dados ainda não está conectado.");
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) query.set(key, String(value));
  const response = await fetch(base.replace(/\/$/, "") + path + (query.size ? "?" + query : ""), {
    method: body ? "POST" : "GET",
    ...(body
      ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : {}),
    signal: AbortSignal.timeout(path === "/api/v1/ai/chat" ? 60000 : 30000),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const message = data?.detail?.message ?? data?.answer;
    throw new Error(message || `Não foi possível obter os dados (${response.status}).`);
  }
  return response.json();
}

const coords = (p: Location) => ({ latitude: p.lat, longitude: p.lon });

function planting(body: FarmRequest) {
  const [year, month, day] = body.planting_date.split("-").map(Number);
  return {
    location: coords(body.location),
    planting_year: year,
    planting_month: month,
    planting_day: day,
  };
}

export const api = {
  summary: (p: Location) =>
    request<SummaryResponse>("/api/v1/regions/summary", coords(p)).then(summaryView),
  history: (p: Location, days: number) =>
    request<HistoryResponse>("/api/v1/climate/history", { ...coords(p), days }).then(historyView),
  series: (p: Location, startYear: number, endYear: number, month: number, metric: string) =>
    request<ClimateSeries>("/api/v1/climate/series", {
      ...coords(p),
      start_year: startYear,
      end_year: endYear,
      ...(month ? { month } : {}),
      metric,
      group_by: "month",
    }),
  forecast: (p: Location) =>
    request<ForecastResponse>("/api/v1/weather/forecast", coords(p)).then(forecastView),
  risks: (p: Location, cropId?: string) =>
    request<RisksResponse>("/api/v1/risks", {
      ...coords(p),
      ...(cropId ? { crop_id: cropId } : {}),
    }).then(risksView),
  soil: (p: Location) => request<SoilResponse>("/api/v1/soil", coords(p)).then(soilView),
  terrain: (p: Location) =>
    request<TerrainResponse>("/api/v1/terrain", coords(p)).then(terrainView),
  crops: () => request<Crop[]>("/api/v1/crops"),
  suitability: (body: FarmRequest) =>
    request<SuitabilityResponse>("/api/v1/crops/suitability", undefined, planting(body)).then(
      suitabilityView,
    ),
  rotation: (body: FarmRequest) =>
    request<RotationResponse>("/api/v1/crops/rotation", undefined, {
      ...planting(body),
      previous_crop_name: body.previous_crop_name,
      objective: body.priority,
      previous_planting_date: body.previous_planting_date || undefined,
    }).then(rotationView),
  chat: (body: AIChatRequest) =>
    request<ChatResponse>("/api/v1/ai/chat", undefined, {
      message:
        body.selected_crop && body.message.length + body.selected_crop.length + 20 <= 2000
          ? `Cultura em foco: ${body.selected_crop}.\n\n${body.message}`
          : body.message,
      location: coords(body.location),
      history: body.history.slice(-8).map(({ role, content }) => ({ role, content })),
    }).then(chatView),
};

const normalize = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();

export async function geocode(query: string): Promise<Location[]> {
  const match = query.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)$/);
  if (match) return [{ lat: Number(match[1]), lon: Number(match[2]), name: query }];
  const name = normalize(query)
    .replace(/,\s*sp$/, "")
    .trim();
  if (!name) return [];
  const matches = municipalities.filter(([city]) => normalize(String(city)).includes(name));
  const exact = matches.find(([city]) => normalize(String(city)) === name);
  if (exact || matches.length) {
    return (exact ? [exact] : matches.slice(0, 5)).map(([city, lat, lon]) => ({
      lat: Number(lat),
      lon: Number(lon),
      name: `${city}, SP`,
    }));
  }

  const base = import.meta.env["VITE_GEOCODING_URL"];
  if (!base) return [];
  const url = new URL(base);
  for (const [key, value] of Object.entries({
    format: "json",
    addressdetails: "1",
    limit: "5",
    countrycodes: "br",
    q: query,
  }))
    url.searchParams.set(key, value);
  const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error("Não foi possível buscar o endereço.");
  const rows = (await response.json()) as { lat: string; lon: string; display_name: string }[];
  return rows.map((row) => ({
    lat: Number(row.lat),
    lon: Number(row.lon),
    name: row.display_name,
  }));
}
