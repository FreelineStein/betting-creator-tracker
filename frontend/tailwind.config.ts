import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // PickReceipts — Stadium Card palette (light-first).
        // Warm paper surfaces, ink ramp, amber signal, cobalt institutional.
        // No red/green; W/L is conveyed by filled-vs-hollow + amber-vs-stone.
        paper: {
          DEFAULT: "#F5F2EC",
          2: "#FBFAF6",
          3: "#ECE7DC",
        },
        ink: {
          DEFAULT: "#14130F",
          700: "#2B2823",
          500: "#6B645A",
          300: "#A8A096",
        },
        rule: {
          DEFAULT: "#D9D3C5",
          soft: "rgba(20, 19, 15, 0.08)",
        },
        amber: {
          DEFAULT: "#FFB347",
          deep: "#C77A1F",
          dim: "rgba(255, 179, 71, 0.16)",
          glow: "rgba(255, 179, 71, 0.42)",
        },
        cobalt: {
          DEFAULT: "#1F3A8A",
          deep: "#15275C",
          dim: "rgba(31, 58, 138, 0.10)",
        },
        stone: {
          DEFAULT: "#7A6B4F",
          dim: "rgba(122, 107, 79, 0.14)",
        },
        // Warm white for text on dark banner gradients.
        moon: "#F5F2EC",
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "system-ui", "sans-serif"],
        display: ["var(--font-manrope)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        display: "-0.025em",
        tight: "-0.015em",
        label: "0.10em",
        "label-x": "0.14em",
      },
      borderRadius: {
        card: "18px",
      },
      boxShadow: {
        card: "0 1px 0 rgba(20,19,15,0.04), 0 1px 2px rgba(20,19,15,0.06)",
        lift: "0 6px 24px rgba(20,19,15,0.08)",
        focus: "0 0 0 3px rgba(255,179,71,0.42)",
        avatar: "0 2px 8px rgba(0,0,0,0.25)",
      },
    },
  },
  plugins: [],
};

export default config;
