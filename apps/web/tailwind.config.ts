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
        devaura: {
          bg: "#0C0E10",
          surface: "#121518",
          raised: "#191D21",
          border: "#2A3036",
          text: "#EDF0F2",
          muted: "#9AA4AC",
          accent: "#9CE8CE",
          green: "#85D9AE",
          amber: "#E5BD7D",
          red: "#EE9393",
        },
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
          50: "#0C0E10",
          100: "#121518",
          200: "#191D21",
          300: "#2A3036",
          400: "#4b5563",
          500: "#6b7280",
          800: "#151c2d",
          900: "#0C0E10",
        },
      },
      borderRadius: {
        control: "4px",
        panel: "6px",
        overlay: "8px",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      transitionDuration: {
        120: "120ms",
        180: "180ms",
        240: "240ms",
      },
    },
  },
  plugins: [],
};

export default config;
