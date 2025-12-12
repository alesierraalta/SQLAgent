import React from "react";

import { cn } from "@/lib/utils";

interface PulsatingButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  pulseColor?: string;
  duration?: string;
}

export const PulsatingButton = React.forwardRef<HTMLButtonElement, PulsatingButtonProps>(
  ({ className, children, pulseColor = "#808080", duration = "1.5s", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "relative flex cursor-pointer items-center justify-center rounded-lg bg-white px-4 py-2 text-center text-sm font-medium text-neutral-950",
          "transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-60",
          className
        )}
        style={
          {
            ["--pulse-color" as string]: pulseColor,
            ["--duration" as string]: duration
          } as React.CSSProperties
        }
        {...props}
      >
        <div className="relative z-10">{children}</div>
        <div
          className="absolute left-1/2 top-1/2 size-full -translate-x-1/2 -translate-y-1/2 animate-pulse rounded-lg opacity-30"
          style={
            {
              backgroundColor: "var(--pulse-color)",
              animationDuration: "var(--duration)"
            } as React.CSSProperties
          }
        />
      </button>
    );
  }
);

PulsatingButton.displayName = "PulsatingButton";

