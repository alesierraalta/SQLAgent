"use client";

import { useEffect, useState } from "react";

import { fetchStats } from "@/lib/api";

export default function StatsPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats(7)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Stats</h1>
        <p className="text-sm text-neutral-300">Métricas agregadas y performance.</p>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/40 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {!data ? <div className="text-sm text-neutral-300">Cargando...</div> : null}

      {data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {(() => {
              const stats = (data.stats ?? {}) as Record<string, unknown>;
              const cards: Array<{ label: string; value: string }> = [
                { label: "Total queries", value: String(stats.total_queries ?? "—") },
                { label: "Success rate", value: stats.success_rate != null ? `${Number(stats.success_rate).toFixed(1)}%` : "—" },
                {
                  label: "Avg time",
                  value: stats.avg_execution_time != null ? `${Number(stats.avg_execution_time).toFixed(2)}s` : "—"
                },
                { label: "Cache hit rate", value: stats.cache_hit_rate != null ? `${Number(stats.cache_hit_rate).toFixed(1)}%` : "—" }
              ];
              return cards.map((card) => (
                <div key={card.label} className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
                  <div className="text-xs text-neutral-400">{card.label}</div>
                  <div className="mt-1 text-lg font-semibold text-white">{card.value}</div>
                </div>
              ));
            })()}
          </div>

          <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
            <h2 className="text-sm font-medium text-neutral-200">Top slow queries</h2>
            <pre className="overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
              {JSON.stringify(data.slow_queries ?? [], null, 2)}
            </pre>
          </div>

          <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
            <h2 className="text-sm font-medium text-neutral-200">Failed queries</h2>
            <pre className="overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
              {JSON.stringify(data.failed_queries ?? [], null, 2)}
            </pre>
          </div>

          <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
            <h2 className="text-sm font-medium text-neutral-200">Patterns</h2>
            <pre className="overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
              {JSON.stringify(data.patterns ?? [], null, 2)}
            </pre>
          </div>
        </>
      ) : null}
    </div>
  );
}
