interface OrionLogoProps {
  size?: number;
  className?: string;
}

export function OrionLogo({ size = 36, className }: OrionLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="ORION logo"
    >
      {/* Orbit ellipse */}
      <ellipse
        cx="40"
        cy="44"
        rx="36"
        ry="18"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeOpacity="0.55"
        fill="none"
        transform="rotate(-22 40 44)"
      />

      {/* Constellation connecting lines — blue dashed */}
      <g stroke="#A8C9E3" strokeWidth="1.1" strokeDasharray="2.5 2.5" strokeLinecap="round">
        {/* top → upper-left */}
        <line x1="42" y1="8"  x2="24" y2="26" />
        {/* top → upper-right */}
        <line x1="42" y1="8"  x2="56" y2="24" />
        {/* upper-right → far-right */}
        <line x1="56" y1="24" x2="68" y2="20" />
        {/* upper-left → belt-left */}
        <line x1="24" y1="26" x2="30" y2="50" />
        {/* upper-center to belt-right */}
        <line x1="56" y1="24" x2="54" y2="50" />
        {/* belt-left → belt-right */}
        <line x1="30" y1="50" x2="54" y2="50" />
        {/* belt-left → foot-left */}
        <line x1="30" y1="50" x2="22" y2="70" />
        {/* belt-right → foot-right */}
        <line x1="54" y1="50" x2="62" y2="68" />
      </g>

      {/* Stars — gold fill */}
      <g fill="#E5C38E">
        {/* top */}
        <polygon points="42,4 43.4,7.2 46.8,7.2 44.2,9.3 45.2,12.6 42,10.6 38.8,12.6 39.8,9.3 37.2,7.2 40.6,7.2" />
        {/* upper-left */}
        <polygon points="24,22 25,24.5 27.8,24.5 25.7,26.2 26.5,28.8 24,27.2 21.5,28.8 22.3,26.2 20.2,24.5 23,24.5" />
        {/* upper-right */}
        <polygon points="56,20 57,22.5 59.8,22.5 57.7,24.2 58.5,26.8 56,25.2 53.5,26.8 54.3,24.2 52.2,22.5 55,22.5" />
        {/* far-right */}
        <polygon points="68,16 68.8,18.2 71.2,18.2 69.4,19.6 70.1,21.8 68,20.5 65.9,21.8 66.6,19.6 64.8,18.2 67.2,18.2" />
        {/* belt-left */}
        <polygon points="30,46 31,48.5 33.8,48.5 31.7,50.2 32.5,52.8 30,51.2 27.5,52.8 28.3,50.2 26.2,48.5 29,48.5" />
        {/* belt-right */}
        <polygon points="54,46 55,48.5 57.8,48.5 55.7,50.2 56.5,52.8 54,51.2 51.5,52.8 52.3,50.2 50.2,48.5 53,48.5" />
        {/* foot-left */}
        <polygon points="22,66 23,68.5 25.8,68.5 23.7,70.2 24.5,72.8 22,71.2 19.5,72.8 20.3,70.2 18.2,68.5 21,68.5" />
        {/* foot-right */}
        <polygon points="62,64 63,66.5 65.8,66.5 63.7,68.2 64.5,70.8 62,69.2 59.5,70.8 60.3,68.2 58.2,66.5 61,66.5" />
      </g>
    </svg>
  );
}
