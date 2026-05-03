export default {
    darkMode: "class",
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                background: "var(--bg)",
                surface: "var(--surface)",
                card: "var(--card)",
                cardAlt: "var(--card-alt)",
                border: "var(--border)",
                accent: "var(--accent)",
                accentSoft: "var(--accent-soft)",
                accentBlue: "var(--accent-blue)",
                accentBlueSoft: "var(--accent-blue-soft)",
                ink: "var(--ink)",
                inkSecondary: "var(--ink-secondary)",
                mutedText: "var(--muted)",
                success: "#22c55e",
                warning: "#f59e0b",
                danger: "#ef4444",
                critical: "#991b1b",
            },
            boxShadow: {
                glow: "0 0 32px rgba(229,195,142,0.22), 0 8px 24px rgba(0,0,0,0.28)",
                panel: "0 2px 24px rgba(0,0,0,0.12)",
                "panel-light": "0 2px 16px rgba(0,0,0,0.08)",
            },
            backgroundImage: {
                "network-grid": "radial-gradient(circle at 1px 1px, rgba(229,195,142,0.10) 1px, transparent 0)",
                "network-glow-dark": "radial-gradient(circle at 15% 20%, rgba(168,201,227,0.07), transparent 35%), radial-gradient(circle at 85% 80%, rgba(229,195,142,0.06), transparent 35%)",
                "network-glow-light": "radial-gradient(circle at 10% 15%, rgba(168,201,227,0.22), transparent 40%), radial-gradient(circle at 90% 85%, rgba(229,195,142,0.18), transparent 40%)",
            },
        },
    },
    plugins: [],
};
