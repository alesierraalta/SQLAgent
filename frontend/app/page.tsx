"use client";

import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Terminal, AnimatedSpan } from "@/components/magicui/terminal";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { CopyButton } from "@/components/magicui/copy-button";
import { BentoGrid } from "@/components/magicui/bento-grid";
import { DotPattern } from "@/components/magicui/dot-pattern";
import { TerminalSkeleton } from "@/components/skeletons/terminal-skeleton";
import { TableSkeleton } from "@/components/skeletons/table-skeleton";
import { QueryResultTable } from "@/components/query-result-table";
import { ViewSettings } from "@/components/view-settings";
import { queryApi, type QueryResponse } from "@/lib/api";
import { startQueryStream } from "@/lib/sse";
import { useSettingsStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export default function Page() {
  const settings = useSettingsStore();
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
      toast.error("La pregunta no puede estar vacía");
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
              const msg = `${err.message} (fallback a single-shot)`;
              setError(msg);
              toast.error("Error en streaming, reintentando...", { description: msg });
              stopStream();
              
              // Fallback
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
                    const errMsg = response.error?.message ?? "Error al ejecutar la query.";
                    setError(errMsg);
                    toast.error("Error", { description: errMsg });
                  }
                } catch (e) {
                  const errMsg = e instanceof Error ? e.message : String(e);
                  setError(errMsg);
                  toast.error("Error crítico", { description: errMsg });
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
        const errMsg = response.error?.message ?? "Error al ejecutar la query.";
        setError(errMsg);
        toast.error("Error", { description: errMsg });
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      setError(errMsg);
      toast.error("Error crítico", { description: errMsg });
    } finally {
      if (!streaming) setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full space-y-6">
      {/* Background */}
      <DotPattern
        width={20}
        height={20}
        cx={1}
        cy={1}
        cr={1}
        className={cn(
          "[mask-image:radial-gradient(300px_circle_at_center,white,transparent)]",
          "inset-x-0 inset-y-[-30%] h-[200%] w-full skew-y-12"
        )}
      />
      
      <div className="relative z-10 space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Consultas</h1>
          <p className="text-sm text-neutral-300">
            Escribe una pregunta en lenguaje natural y revisa resultados + SQL generado.
          </p>
        </div>

        <BentoGrid className="auto-rows-min grid-cols-1 md:grid-cols-3 md:auto-rows-auto">
          {/* Input Area - Full Width */}
          <div className="col-span-1 md:col-span-3 space-y-3 rounded-xl border border-neutral-800 bg-neutral-950 p-4 shadow-sm">
            <label className="block text-sm font-medium text-neutral-200">Pregunta</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder='Ej: "Top 10 productos por ventas"'
              className="h-28 w-full rounded-md border border-neutral-800 bg-neutral-900 p-3 text-sm text-white outline-none focus:border-neutral-600 transition-colors"
            />

            <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-200">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={explain}
                  onChange={(e) => setExplain(e.target.checked)}
                  className="accent-white"
                />
                Explain
              </label>
              <label className="flex items-center gap-2 cursor-pointer select-none">
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
                <ViewSettings />
                {streaming && loading ? (
                  <button
                    onClick={stopStream}
                    className="rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-800 transition-colors"
                  >
                    Detener
                  </button>
                ) : null}
                <ShimmerButton 
                  className="h-9 px-6" 
                  background="#000000"
                  shimmerColor="#ffffff"
                  disabled={!canRun} 
                  onClick={run}
                >
                  <span className="relative z-10 text-sm font-medium">
                    {loading ? "Ejecutando..." : "Ejecutar"}
                  </span>
                </ShimmerButton>
              </div>
            </div>
          </div>

          {error ? (
            <div className="col-span-1 md:col-span-3 rounded-lg border border-red-900/40 bg-red-950/40 p-4 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          {/* Left Column: Logs & SQL */}
          <div className="col-span-1 md:col-span-1 flex flex-col gap-4">
            {/* Show SQL if exists AND enabled */}
            {!settings.simpleMode && settings.showSQL && sql && (
              <div className="space-y-2 rounded-xl border border-neutral-800 bg-neutral-950 p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-medium text-neutral-200">SQL generado</h2>
                  <CopyButton text={sql} />
                </div>
                <pre className="overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100 scrollbar-thin scrollbar-thumb-neutral-700">
                  {sql}
                </pre>
              </div>
            )}

            {/* Terminal: Show if logs exist AND enabled */}
            {!settings.simpleMode && settings.showThinking && (logs.length > 0 || loading) && (
               <div className="w-full">
                  {loading && logs.length === 0 ? (
                    <TerminalSkeleton className="min-h-[200px]" />
                  ) : (
                    <Terminal className="min-h-[200px] w-full max-w-none bg-neutral-950 border-neutral-800 shadow-sm">
                      {logs.map((line, idx) => (
                        <AnimatedSpan key={idx} delay={0} className="text-neutral-300">
                          <span>{"> "}{line}</span>
                        </AnimatedSpan>
                      ))}
                    </Terminal>
                  )}
               </div>
            )}
          </div>

          {/* Right Column: Results */}
          <div className="col-span-1 md:col-span-2 flex flex-col gap-4">
            {loading && !result ? (
              <TableSkeleton />
            ) : (
              <>
                {settings.showData && result?.rows && <QueryResultTable columns={result.columns} rows={result.rows} />}

                {result?.response && (
                  <div className="space-y-2 rounded-xl border border-neutral-800 bg-neutral-950 p-4 shadow-sm">
                    <h2 className="text-sm font-medium text-neutral-200">Respuesta</h2>
                    <pre className="whitespace-pre-wrap rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
                      {result.response}
                    </pre>
                  </div>
                )}

                {!settings.simpleMode && settings.showThinking && result?.explanation && (
                  <div className="space-y-2 rounded-xl border border-neutral-800 bg-neutral-950 p-4 shadow-sm">
                    <h2 className="text-sm font-medium text-neutral-200">Explain</h2>
                    <pre className="whitespace-pre-wrap rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
                      {result.explanation}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </BentoGrid>
      </div>
    </div>
  );
}
