"use client";

import { useEffect, useState } from "react";

import { clearHistory, fetchHistory, type HistoryResponse } from "@/lib/api";

export default function HistoryPage() {
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetchHistory(50, 0);
      setData(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">History</h1>
          <p className="text-sm text-neutral-300">Historial local (archivo).</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={load}
            className="rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-800"
          >
            {loading ? "..." : "Refrescar"}
          </button>
          <button
            onClick={async () => {
              try {
                if (!confirm("¿Limpiar historial local?")) return;
                await clearHistory();
                await load();
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e));
              }
            }}
            className="rounded-lg border border-red-900/40 bg-red-950/40 px-3 py-2 text-sm text-red-200 hover:bg-red-950/60"
          >
            Clear
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/40 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {!data ? <div className="text-sm text-neutral-300">Cargando...</div> : null}

      {data ? (
        <div className="space-y-3">
          {data.items.map((item) => (
            <div key={`${item.timestamp}-${item.question}`} className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm font-medium text-white">{item.question}</div>
                <div className="text-xs text-neutral-400">{item.timestamp}</div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-neutral-300">
                {item.cache_hit_type ? (
                  <span className="rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1">
                    cache: {item.cache_hit_type}
                  </span>
                ) : null}
                {item.model_used ? (
                  <span className="rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1">
                    model: {item.model_used}
                  </span>
                ) : null}
                <span
                  className={`rounded-md border px-2 py-1 ${
                    item.success
                      ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-200"
                      : "border-red-900/40 bg-red-950/30 text-red-200"
                  }`}
                >
                  {item.success ? "success" : "failed"}
                </span>
              </div>
              {item.sql ? (
                <pre className="mt-2 overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
                  {item.sql}
                </pre>
              ) : null}
              {item.response_preview ? (
                <p className="mt-2 text-xs text-neutral-300">{item.response_preview}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
