import { useTheme } from "@/lib/theme";
import logoNormal from "@/images/logoNormal.png";
import logoGrey from "@/images/logoGrey.png";
import logoNoir from "@/images/logoNoir.png";

interface OrionLogoProps {
  size?: number;
  className?: string;
  /** "auto" picks normal in dark mode, grey in light mode */
  variant?: "normal" | "grey" | "noir" | "auto";
}

export function OrionLogo({ size = 36, className, variant = "auto" }: OrionLogoProps) {
  const { theme } = useTheme();

  const src =
    variant === "auto"
      ? theme === "dark"
        ? logoNormal
        : logoGrey
      : variant === "normal"
        ? logoNormal
        : variant === "grey"
          ? logoGrey
          : logoNoir;

  return (
    <img
      src={src}
      alt="ORION logo"
      width={size}
      height={size}
      className={className}
      style={{ objectFit: "contain", display: "block" }}
    />
  );
}
