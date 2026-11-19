import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f7ff",
          100: "#e0effe",
          200: "#b9ddfd",
          300: "#7cc0fb",
          400: "#36a0f6",
          500: "#0c82ea",
          600: "#0265c7",
          700: "#0350a1",
          800: "#074485",
          900: "#0c3a6e",
          950: "#082549",
        },
        surface: {
          50: "#0b0f19",
          100: "#111827",
          200: "#1f2937",
          300: "#374151",
          400: "#4b5563",
          500: "#6b7280",
          800: "#151c2d",
          900: "#0d131f",
        },
      },
    },
  },
  plugins: [],
};

export default config;
