import { useTheme } from "@/lib/theme";
import logoNormal from "@/images/logoNormal.png";
import logoNoir from "@/images/logoNoir.png";

interface OrionLogoProps {
  /** Controls the outer frame width, e.g. "w-36", "w-52" */
  className?: string;
  /** Explicit override — defaults to auto (Normal on dark, Noir on light) */
  variant?: "normal" | "noir";
}

// Logos are landscape 16:9 with solid backgrounds (black/white).
// The frame provides rounded corners + a bordered ring that integrates cleanly.
export function OrionLogo({ className, variant }: OrionLogoProps) {
  const { theme } = useTheme();
  const resolvedVariant = variant ?? (theme === "dark" ? "normal" : "noir");
  const src = resolvedVariant === "normal" ? logoNormal : logoNoir;

  return (
    <div
      className={className}
      style={{
        overflow: "hidden",
        borderRadius: "12px",
        border: theme === "dark"
          ? "1px solid rgba(255,255,255,0.10)"
          : "1px solid rgba(0,0,0,0.10)",
        boxShadow: theme === "dark"
          ? "0 0 0 1px rgba(229,195,142,0.08), 0 4px 16px rgba(0,0,0,0.40)"
          : "0 0 0 1px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.10)",
      }}
    >
      <img
        src={src}
        alt="ORION"
        style={{ display: "block", width: "100%", height: "auto" }}
      />
    </div>
  );
}
