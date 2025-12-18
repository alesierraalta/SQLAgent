import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function TableSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4 rounded-xl border border-neutral-800 bg-neutral-950 p-4", className)}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-32 bg-neutral-800/50" />
      </div>
      <div className="space-y-2">
        {/* Header */}
        <div className="flex gap-2">
          <Skeleton className="h-8 w-1/4 bg-neutral-800/60" />
          <Skeleton className="h-8 w-1/4 bg-neutral-800/60" />
          <Skeleton className="h-8 w-1/4 bg-neutral-800/60" />
          <Skeleton className="h-8 w-1/4 bg-neutral-800/60" />
        </div>
        {/* Rows */}
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-2">
            <Skeleton className="h-6 w-1/4 bg-neutral-800/40" />
            <Skeleton className="h-6 w-1/4 bg-neutral-800/40" />
            <Skeleton className="h-6 w-1/4 bg-neutral-800/40" />
            <Skeleton className="h-6 w-1/4 bg-neutral-800/40" />
          </div>
        ))}
      </div>
    </div>
  );
}
