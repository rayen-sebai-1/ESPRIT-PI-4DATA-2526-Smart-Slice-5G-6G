import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#07101c",
        surface: "#0c1726",
        card: "#101d31",
        cardAlt: "#16253b",
        border: "#223653",
        accent: "#4ec3ff",
        accentSoft: "#12334d",
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
        critical: "#991b1b",
        mutedText: "#94a8c4",
        ink: "#e5f0ff",
      },
      boxShadow: {
        glow: "0 22px 54px rgba(4, 10, 19, 0.42)",
        panel: "0 18px 46px rgba(6, 12, 23, 0.28)",
      },
      backgroundImage: {
        "network-grid":
          "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.14) 1px, transparent 0)",
        "network-glow":
          "radial-gradient(circle at top left, rgba(78,195,255,0.22), transparent 32%), radial-gradient(circle at bottom right, rgba(34,197,94,0.12), transparent 28%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
