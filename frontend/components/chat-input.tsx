"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { ViewSettings } from "@/components/view-settings";

interface ChatInputProps {
  onRun: (params: { question: string; limit: number | null; explain: boolean; streaming: boolean }) => void;
  loading: boolean;
  onStop: () => void;
  isStreaming: boolean;
}

export function ChatInput({ onRun, loading, onStop, isStreaming }: ChatInputProps) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState<number | "">("");
  const [explain, setExplain] = useState(false);
  const [streaming, setStreaming] = useState(false);

  const canRun = useMemo(() => question.trim().length > 0 && !loading, [question, loading]);

  const handleRun = () => {
    if (!question.trim()) {
      toast.error("La pregunta no puede estar vacía");
      return;
    }
    if (loading) return;
    
    onRun({
      question: question.trim(),
      limit: typeof limit === "number" ? limit : null,
      explain,
      streaming
    });
  };

  return (
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
          {isStreaming && loading ? (
            <button
              onClick={onStop}
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
            onClick={handleRun}
          >
            <span className="relative z-10 text-sm font-medium">
              {loading ? "Ejecutando..." : "Ejecutar"}
            </span>
          </ShimmerButton>
        </div>
      </div>
    </div>
  );
}
