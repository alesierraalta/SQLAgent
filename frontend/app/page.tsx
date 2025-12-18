"use client";

import { Terminal, AnimatedSpan } from "@/components/magicui/terminal";
import { BentoGrid } from "@/components/magicui/bento-grid";
import { DotPattern } from "@/components/magicui/dot-pattern";
import { TerminalSkeleton } from "@/components/skeletons/terminal-skeleton";
import { TableSkeleton } from "@/components/skeletons/table-skeleton";
import { QueryResultTable } from "@/components/query-result-table";
import { ChatInput } from "@/components/chat-input";
import { useSettingsStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { CopyButton } from "@/components/magicui/copy-button";
import { useChatQuery } from "@/hooks/use-chat-query";

export default function Page() {
  const settings = useSettingsStore();
  
  const { 
    result, 
    loading, 
    logs, 
    error, 
    sql,
    isExecutingStream, 
    runQuery, 
    stopStream 
  } = useChatQuery();

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
          {/* Input Area - Isolated Component */}
          <ChatInput 
            onRun={runQuery} 
            loading={loading} 
            onStop={stopStream} 
            isStreaming={isExecutingStream} 
          />

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