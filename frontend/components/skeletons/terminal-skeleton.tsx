import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function TerminalSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "border-border bg-background z-0 h-full max-h-[400px] w-full max-w-lg rounded-xl border p-4",
        className
      )}
    >
      <div className="flex flex-col gap-y-2 border-b border-border pb-4 mb-4">
        <div className="flex flex-row gap-x-2">
          <div className="h-2 w-2 rounded-full bg-red-500 opacity-50"></div>
          <div className="h-2 w-2 rounded-full bg-yellow-500 opacity-50"></div>
          <div className="h-2 w-2 rounded-full bg-green-500 opacity-50"></div>
        </div>
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/4 bg-neutral-800/50" />
        <Skeleton className="h-4 w-1/2 bg-neutral-800/50" />
        <Skeleton className="h-4 w-5/6 bg-neutral-800/50" />
      </div>
    </div>
  );
}
