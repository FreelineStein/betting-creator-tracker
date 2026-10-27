import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // PickReceipts — the receipt logo's palette on a near-black app shell.
        // Lime is the logo's check, orange its cross. W/L always carries its
        // letter as well as its color.
        ground: "#0C0F0D",
        panel: {
          DEFAULT: "#151A17",
          2: "#1C221E",
          3: "#232A25",
        },
        line: {
          DEFAULT: "#262D28",
          2: "#3A443D",
        },
        fg: {
          DEFAULT: "#EEF1EC",
          2: "#A9B0A6",
          3: "#848C81",
        },
        win: {
          DEFAULT: "#A8F55C",
          dim: "rgba(168, 245, 92, 0.14)",
        },
        loss: {
          DEFAULT: "#FF6A3D",
          dim: "rgba(255, 106, 61, 0.15)",
        },
      },
      fontFamily: {
        display: ["var(--font-barlow-condensed)", "Barlow Condensed", "Arial Narrow", "sans-serif"],
        sans: ["var(--font-barlow)", "Barlow", "Arial", "sans-serif"],
      },
      borderRadius: {
        chip: "7px",
        control: "10px",
        card: "14px",
      },
    },
  },
  plugins: [],
};

export default config;
