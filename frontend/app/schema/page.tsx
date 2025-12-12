"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchSchema, type SchemaResponse } from "@/lib/api";

export default function SchemaPage() {
  const [data, setData] = useState<SchemaResponse | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSchema(true)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const filteredTables = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    if (!q) return data.tables;
    return data.tables.filter((t) => {
      if (t.name.toLowerCase().includes(q)) return true;
      return t.columns.some((c) => c.name.toLowerCase().includes(q));
    });
  }, [data, query]);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Schema</h1>
        <p className="text-sm text-neutral-300">Tablas/columnas permitidas.</p>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Buscar por tabla/columna..."
        className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-white outline-none focus:border-neutral-600"
      />

      {error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/40 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {!data ? <div className="text-sm text-neutral-300">Cargando...</div> : null}

      {data ? (
        <div className="space-y-4">
          {filteredTables.map((table) => (
            <div key={table.name} className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm font-semibold text-white">{table.name}</h2>
                <span className="text-xs text-neutral-400">{table.columns.length} cols</span>
              </div>
              {table.description ? <p className="mt-1 text-xs text-neutral-300">{table.description}</p> : null}
              <div className="mt-3 flex flex-wrap gap-2">
                {table.columns.map((col) => (
                  <span
                    key={col.name}
                    className="rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1 text-xs text-neutral-200"
                  >
                    {col.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

