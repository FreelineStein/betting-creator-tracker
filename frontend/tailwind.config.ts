import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette — see brand guide v1.0
        signal: {
          DEFAULT: "#7AE53C", // primary accent · win · verified · CTAs
          dim: "rgba(122, 229, 60, 0.12)",
        },
        forest: "#3D8A12",   // green text on light backgrounds
        pitch: "#0A0A0A",    // primary BG · logo BG
        alert: {
          DEFAULT: "#E85D30", // loss · error · rejected
          dim: "rgba(232, 93, 48, 0.10)",
          deep: "#B84420",   // orange text on light/dim backgrounds
        },
        paper: "#F7F7F5",    // light page background
        ink: {
          100: "#F2F2F2",
          200: "#E0E0E0",
          400: "#A0A0A0",
          600: "#555555",
          800: "#222222",
        },
      },
      fontFamily: {
        sans: ["var(--font-barlow)", "system-ui", "sans-serif"],
        display: ["var(--font-barlow-condensed)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        // Brand calls for tight tracking on display + wide tracking on mono labels
        display: "-0.02em",
        label: "0.1em",
      },
    },
  },
  plugins: [],
};

export default config;
