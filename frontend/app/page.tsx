"use client";

import { useMemo, useRef, useState } from "react";

import { PulsatingButton } from "@/components/magicui/pulsating-button";
import { QueryResultTable } from "@/components/query-result-table";
import { queryApi, type QueryResponse } from "@/lib/api";
import { startQueryStream } from "@/lib/sse";

export default function Page() {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState<number | "">("");
  const [explain, setExplain] = useState(false);
  const [streaming, setStreaming] = useState(false);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [sql, setSql] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<{ close: () => void } | null>(null);

  const canRun = useMemo(() => question.trim().length > 0 && !loading, [question, loading]);

  const reset = () => {
    setResult(null);
    setSql(null);
    setLogs([]);
    setError(null);
  };

  const stopStream = () => {
    streamRef.current?.close();
    streamRef.current = null;
    setLoading(false);
  };

  const run = async () => {
    reset();
    const questionClean = question.trim();
    if (!questionClean) {
      setError("La pregunta no puede estar vacía.");
      return;
    }

    setLoading(true);

    try {
      if (streaming) {
        streamRef.current = startQueryStream(
          {
            question: questionClean,
            limit: typeof limit === "number" ? limit : null,
            explain
          },
          {
            onSql: (sqlText) => setSql(sqlText),
            onAnalysis: (text) => setLogs((prev) => [...prev, text]),
            onExecution: (text) => setLogs((prev) => [...prev, text]),
            onError: (err) => {
              setError(`${err.message} (fallback a single-shot)`);
              stopStream();
              void (async () => {
                setLoading(true);
                try {
                  const response = await queryApi({
                    question: questionClean,
                    limit: typeof limit === "number" ? limit : null,
                    explain,
                    stream: false
                  });
                  setResult(response);
                  setSql(response.sql_generated ?? sql ?? null);
                  if (!response.success) {
                    setError(response.error?.message ?? "Error al ejecutar la query.");
                  }
                } catch (e) {
                  setError(e instanceof Error ? e.message : String(e));
                } finally {
                  setLoading(false);
                }
              })();
            },
            onDone: (finalResult) => {
              setResult(finalResult);
              setSql(finalResult.sql_generated ?? sql ?? null);
              stopStream();
            }
          }
        );
        return;
      }

      const response = await queryApi({
        question: questionClean,
        limit: typeof limit === "number" ? limit : null,
        explain,
        stream: false
      });

      setResult(response);
      setSql(response.sql_generated ?? null);
      if (!response.success) {
        setError(response.error?.message ?? "Error al ejecutar la query.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!streaming) setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Consultas</h1>
        <p className="text-sm text-neutral-300">
          Escribe una pregunta en lenguaje natural y revisa resultados + SQL generado.
        </p>
      </div>

      <div className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
        <label className="block text-sm font-medium text-neutral-200">Pregunta</label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder='Ej: "Top 10 productos por ventas"'
          className="h-28 w-full rounded-md border border-neutral-800 bg-neutral-900 p-3 text-sm text-white outline-none focus:border-neutral-600"
        />

        <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-200">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={explain}
              onChange={(e) => setExplain(e.target.checked)}
              className="accent-white"
            />
            Explain
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={streaming}
              onChange={(e) => setStreaming(e.target.checked)}
              className="accent-white"
            />
            Streaming (SSE)
          </label>
          <label className="flex items-center gap-2">
            Limit
            <input
              type="number"
              min={1}
              max={10000}
              value={limit}
              onChange={(e) => setLimit(e.target.value ? Number(e.target.value) : "")}
              className="w-24 rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm text-white outline-none focus:border-neutral-600"
            />
          </label>

          <div className="ml-auto flex items-center gap-2">
            {streaming && loading ? (
              <button
                onClick={stopStream}
                className="rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-800"
              >
                Detener
              </button>
            ) : null}
            <PulsatingButton disabled={!canRun} onClick={run}>
              {loading ? "Ejecutando..." : "Ejecutar"}
            </PulsatingButton>
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/40 p-4 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {sql ? (
        <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-neutral-200">SQL generado</h2>
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(sql);
                } catch {
                  setError("No se pudo copiar al portapapeles.");
                }
              }}
              className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800"
            >
              Copiar
            </button>
          </div>
          <pre className="overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
            {sql}
          </pre>
        </div>
      ) : null}

      {logs.length > 0 ? (
        <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
          <h2 className="text-sm font-medium text-neutral-200">Streaming log</h2>
          <div className="max-h-64 space-y-2 overflow-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
            {logs.map((line, idx) => (
              <pre key={idx} className="whitespace-pre-wrap">
                {line}
              </pre>
            ))}
          </div>
        </div>
      ) : null}

      {result?.rows ? <QueryResultTable columns={result.columns} rows={result.rows} /> : null}

      {result?.response ? (
        <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
          <h2 className="text-sm font-medium text-neutral-200">Respuesta</h2>
          <pre className="whitespace-pre-wrap rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
            {result.response}
          </pre>
        </div>
      ) : null}

      {result?.explanation ? (
        <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-950 p-4">
          <h2 className="text-sm font-medium text-neutral-200">Explain</h2>
          <pre className="whitespace-pre-wrap rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
            {result.explanation}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
