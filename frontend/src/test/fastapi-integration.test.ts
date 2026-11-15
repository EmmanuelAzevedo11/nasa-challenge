import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, geocode } from "@/services/api";

const place = { lat: -23.5886, lon: -48.0483, name: "Itapetininga" };
const location = { latitude: place.lat, longitude: place.lon };
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8000");
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("FastAPI client integration", () => {
  it("uses FastAPI coordinates and reads NASA POWER daily values", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        source: "NASA POWER",
        last_available_date: "2026-05-01",
        daily: [
          {
            date: "2026-05-01",
            temperature: 22,
            precipitation: 10,
            relative_humidity: 65,
            wind_speed: 3,
          },
        ],
      }),
    );

    const history = await api.history(place, 90);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://127.0.0.1:8000/api/v1/climate/history?latitude=-23.5886&longitude=-48.0483&days=90",
    );
    expect(history.days[0]).toMatchObject({ humidity: 65, wind: 3, precipitation: 10 });
    expect(history.reference_date).toBe("2026-05-01");
  });

  it("sends the full planting date and the typed culture for rotation", async () => {
    fetchMock.mockResolvedValue(Response.json({ strategies: [], limitations: [] }));
    await api.rotation({
      location: place,
      planting_date: "2026-11-25",
      previous_crop_name: "Feijão",
      priority: "soil_conservation",
      previous_planting_date: "2025-10-10",
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      location,
      planting_month: 11,
      planting_year: 2026,
      planting_day: 25,
      previous_crop_name: "Feijão",
      objective: "soil_conservation",
      previous_planting_date: "2025-10-10",
    });
  });

  it("sends at most eight chat messages without UI metadata", async () => {
    const metadata = { answer: "663 metros", sources: [], kind: "observed" as const };
    fetchMock.mockResolvedValue(
      Response.json({
        status: "available",
        answer: metadata.answer,
        limitations: [],
        sources: [{ title: "NASA SRTM", url: "https://www.opentopodata.org/" }],
      }),
    );
    const answer = await api.chat({
      message: "Qual é a altitude?",
      location: place,
      history: Array.from({ length: 10 }, (_, i) => ({
        role: "assistant",
        content: String(i),
        metadata,
      })),
    });

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body.location).toEqual(location);
    expect(body.history).toHaveLength(8);
    expect(body.history[0]).toEqual({ role: "assistant", content: "2" });
    expect(answer).toMatchObject({ answer: "663 metros", sources: ["NASA SRTM"] });
  });

  it("finds municipalities by name without an external geocoder", async () => {
    const results = await geocode("Sao Paulo, SP");
    expect(results).toHaveLength(1);
    expect(results[0]?.name).toBe("São Paulo, SP");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
