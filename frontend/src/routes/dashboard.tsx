import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { usePlatform } from "@/components/PlatformContext";
import { PageTitle } from "@/components/PlatformHeader";
import { DataState } from "@/components/DataState";
import { ClimateSeriesChart } from "@/components/ClimateSeriesChart";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { pageHead } from "@/lib/metadata";
export const Route = createFileRoute("/dashboard")({
  head: () =>
    pageHead(
      "Monitoramento ambiental",
      "Histórico climático, previsão e riscos agroambientais da localização selecionada.",
    ),
  component: Dashboard,
});
function Dashboard() {
  const { place } = usePlatform();
  const [days, setDays] = useState(90);
  const [riskCrop, setRiskCrop] = useState("");
  const history = useQuery({
    queryKey: ["history", place, days],
    queryFn: () => api.history(place, days),
    retry: false,
  });
  const forecast = useQuery({
    queryKey: ["forecast", place],
    queryFn: () => api.forecast(place),
    retry: false,
  });
  const crops = useQuery({
    queryKey: ["crops"],
    queryFn: () => api.crops(),
    retry: false,
  });
  const risks = useQuery({
    queryKey: ["risks", place, riskCrop || undefined],
    queryFn: () => api.risks(place, riskCrop || undefined),
    retry: false,
  });
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-7 md:px-8">
      <PageTitle
        title="Monitoramento ambiental"
        subtitle="Histórico climático, previsão meteorológica e riscos agroambientais da região selecionada."
      />
      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Histórico climático</h2>
          <div className="flex gap-1">
            {[30, 90, 180, 365].map((d) => (
              <Button
                key={d}
                size="sm"
                variant={days === d ? "default" : "outline"}
                onClick={() => setDays(d)}
              >
                {d} dias
              </Button>
            ))}
          </div>
        </div>
        {history.isPending ? (
          <DataState loading />
        ) : history.error ? (
          <DataState error={history.error.message} retry={() => history.refetch()} />
        ) : !history.data?.days.length ? (
          <DataState />
        ) : (
          <>
            <p className="mb-4 text-xs text-muted-foreground">
              Fonte: {history.data.source} · Referência:{" "}
              {history.data.reference_date ?? "Não informada"}
            </p>
            <div className="grid gap-6 lg:grid-cols-2">
              {(
                [
                  ["temperature", "Temperatura (°C)", "var(--chart-5)"],
                  ["precipitation", "Precipitação (mm)", "var(--water)"],
                  ["humidity", "Umidade relativa (%)", "var(--agriculture)"],
                  ["wind", "Vento (m/s)", "var(--primary)"],
                ] as const
              ).map(([key, title, color]) => (
                <section key={key} className="min-w-0 border-b border-border pb-4">
                  <h3 className="mb-3 text-sm font-medium">{title}</h3>
                  <ResponsiveContainer width="100%" height={230}>
                    {key === "precipitation" ? (
                      <BarChart data={history.data?.days}>
                        <CartesianGrid stroke="var(--border)" vertical={false} />
                        <XAxis dataKey="date" fontSize={10} tickFormatter={(d) => d.slice(5)} />
                        <YAxis fontSize={10} />
                        <Tooltip />
                        <Bar isAnimationActive={false} dataKey={key} fill={color} />
                      </BarChart>
                    ) : (
                      <LineChart data={history.data?.days}>
                        <CartesianGrid stroke="var(--border)" vertical={false} />
                        <XAxis dataKey="date" fontSize={10} tickFormatter={(d) => d.slice(5)} />
                        <YAxis fontSize={10} />
                        <Tooltip />
                        <Line
                          isAnimationActive={false}
                          dataKey={key}
                          stroke={color}
                          dot={false}
                          connectNulls={false}
                        />
                      </LineChart>
                    )}
                  </ResponsiveContainer>
                </section>
              ))}
            </div>
          </>
        )}
      </section>
      <ClimateSeriesChart place={place} />
      <section className="mt-8 border-t border-border pt-6">
        <h2 className="mb-4 text-lg font-semibold">Previsão meteorológica</h2>
        {forecast.isPending ? (
          <DataState loading />
        ) : forecast.error ? (
          <DataState error={forecast.error.message} retry={() => forecast.refetch()} />
        ) : !forecast.data?.length ? (
          <DataState />
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            {forecast.data.map((d) => (
              <article key={d.date} className="rounded-lg border border-border p-3">
                <h3 className="text-sm font-medium">
                  {d.date.slice(5).split("-").reverse().join("/")}
                </h3>
                <p className="my-2 font-mono text-xl">{d.temperature ?? "—"} °C</p>
                <p className="text-xs text-water">
                  {d.precipitation ?? "—"} mm · {d.rain_probability ?? "—"}%
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Vento {d.wind ?? "—"} km/h</p>
                <p className="mt-1 text-xs text-muted-foreground">Umidade {d.humidity ?? "—"}%</p>
                <p className="mt-3 text-[10px] text-muted-foreground">
                  {d.source} · {d.reference_date ?? "Sem data de referência"}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="mt-8 border-t border-border pt-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Riscos agroambientais</h2>
          <label className="flex items-center gap-2 text-sm">
            Cultura para avaliar calor
            <select
              className="rounded border border-input bg-background p-2"
              value={riskCrop}
              onChange={(event) => setRiskCrop(event.target.value)}
            >
              <option value="">Selecione uma cultura</option>
              {crops.data?.map((crop) => (
                <option key={crop.id} value={crop.id}>
                  {crop.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {risks.isPending ? (
          <DataState loading />
        ) : risks.error ? (
          <DataState error={risks.error.message} retry={() => risks.refetch()} />
        ) : !risks.data?.length ? (
          <DataState />
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {risks.data.map((r) => (
              <article key={r.id} className="rounded-lg border border-border p-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-medium">{r.name}</h3>
                  <span
                    className={`rounded px-2 py-1 text-xs ${r.level === "Alto" ? "bg-destructive/10 text-destructive" : r.level === "Moderado" ? "bg-warning/15 text-foreground" : "bg-muted text-muted-foreground"}`}
                  >
                    {r.level}
                  </span>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">{r.explanation}</p>
                <p className="mt-3 text-[11px] text-muted-foreground">
                  {r.period} · {r.source ?? "Fonte indisponível"}
                </p>
                {r.criteria_url && (
                  <a
                    href={r.criteria_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-block text-xs text-muted-foreground underline underline-offset-4"
                  >
                    Referência do critério
                  </a>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
