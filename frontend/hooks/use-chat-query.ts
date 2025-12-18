import { useRef, useState } from "react";
import { toast } from "sonner";
import { queryApi, type QueryResponse } from "@/lib/api";
import { startQueryStream } from "@/lib/sse";

export function useChatQuery() {
  const [loading, setLoading] = useState(false);
  const [isExecutingStream, setIsExecutingStream] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [sql, setSql] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<{ close: () => void } | null>(null);

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
    setIsExecutingStream(false);
  };

  const runQuery = async ({ 
    question, 
    limit, 
    explain, 
    streaming 
  }: { 
    question: string; 
    limit: number | null; 
    explain: boolean; 
    streaming: boolean 
  }) => {
    reset();
    setLoading(true);
    if (streaming) setIsExecutingStream(true);

    try {
      if (streaming) {
        streamRef.current = startQueryStream(
          {
            question,
            limit,
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
                setIsExecutingStream(false); // Fallback is not streaming
                try {
                  const response = await queryApi({
                    question,
                    limit,
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
        question,
        limit,
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
      if (!streaming) {
        setLoading(false);
      }
    }
  };

  return {
    loading,
    isExecutingStream,
    result,
    sql,
    logs,
    error,
    stopStream,
    runQuery
  };
}
