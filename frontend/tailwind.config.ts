import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // PickReceipts — The Agate Page.
        // Newsprint ground, ink, one press red. W/L is carried by filled vs
        // hollow marks and by the letter itself, never by color.
        news: {
          DEFAULT: "#E7E4DC",
          2: "#F0EEE8",
          3: "#DAD6CC",
        },
        ink: {
          DEFAULT: "#121212",
          2: "#3A3835",
          3: "#625F59",
        },
        rule: {
          DEFAULT: "#B5B1A7",
        },
        press: {
          DEFAULT: "#C8102E",
          dim: "rgba(200, 16, 46, 0.10)",
        },
      },
      fontFamily: {
        display: ["var(--font-oswald)", "Oswald", "Arial Narrow", "sans-serif"],
        sans: ["var(--font-archivo)", "Archivo Narrow", "Arial Narrow", "sans-serif"],
      },
      transitionDuration: {
        120: "120ms",
      },
    },
  },
  plugins: [],
};

export default config;
