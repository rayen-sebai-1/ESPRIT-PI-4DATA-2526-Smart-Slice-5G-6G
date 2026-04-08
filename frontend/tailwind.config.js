export default {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                background: "#07111f",
                surface: "#0d1726",
                card: "#111f33",
                cardAlt: "#16253d",
                border: "#23344f",
                accent: "#3fb8ff",
                accentSoft: "#13314a",
                success: "#22c55e",
                warning: "#f59e0b",
                danger: "#ef4444",
                critical: "#991b1b",
                mutedText: "#96a4ba",
            },
            boxShadow: {
                glow: "0 12px 40px rgba(15, 23, 42, 0.38)",
            },
            backgroundImage: {
                "network-grid": "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.12) 1px, transparent 0)"
            }
        },
    },
    plugins: [],
};
