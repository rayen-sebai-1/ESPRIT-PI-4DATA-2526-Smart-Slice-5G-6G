import logoNormal from "@/assets/logoNormal.png";
import logoNoir from "@/assets/logoNoir.png";
import logoGrey from "@/assets/logoGrey.png";

import { cn } from "@/lib/cn";

export { logoNormal, logoNoir, logoGrey };

interface OrionLogoProps {
  size?: number;
  className?: string;
  /**
   * auto  — dark mode → full-color logo, light mode → black logo (default)
   * normal — full-color original, intended for dark backgrounds
   * noir   — black version, intended for light backgrounds
   * grey   — greyscale version, for neutral/muted contexts
   */
  variant?: "auto" | "normal" | "noir" | "grey";
}

export function OrionLogo({ size = 36, className, variant = "auto" }: OrionLogoProps) {
  const imgProps = {
    alt: "ORION",
    draggable: false as const,
    style: { height: size },
    className: cn("w-auto object-contain select-none", className),
  };

  if (variant === "auto") {
    return (
      <>
        {/* dark theme — full-color original */}
        <img {...imgProps} src={logoNormal} className={cn(imgProps.className, "hidden dark:block")} />
        {/* light theme — black version */}
        <img {...imgProps} src={logoNoir} className={cn(imgProps.className, "block dark:hidden")} />
      </>
    );
  }

  const src = variant === "normal" ? logoNormal : variant === "noir" ? logoNoir : logoGrey;
  return <img {...imgProps} src={src} />;
}
