import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-2xl font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" && "h-9 px-3 text-xs",
        size === "md" && "h-11 px-4 text-sm",
        size === "lg" && "h-12 px-5 text-sm",
        size === "icon" && "h-11 w-11",
        variant === "primary" &&
          "bg-accent text-slate-950 shadow-glow hover:-translate-y-0.5 hover:bg-sky-300",
        variant === "secondary" &&
          "border border-border bg-cardAlt text-ink hover:border-accent/40 hover:bg-card",
        variant === "ghost" && "text-slate-300 hover:bg-white/5 hover:text-white",
        variant === "danger" && "bg-red-700 text-white hover:bg-red-600",
        className,
      )}
      {...props}
    />
  );
}
