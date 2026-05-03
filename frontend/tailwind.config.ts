import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#fafafa",
          subtle: "#f4f4f5",
          panel: "#ffffff",
        },
        border: {
          DEFAULT: "#e4e4e7",
          subtle: "#f4f4f5",
        },
        text: {
          DEFAULT: "#0a0a0a",
          muted: "#71717a",
          subtle: "#a1a1aa",
        },
        accent: {
          DEFAULT: "#2563eb",
          hover: "#1d4ed8",
          subtle: "#dbeafe",
        },
        success: { DEFAULT: "#16a34a", subtle: "#dcfce7" },
        warn: { DEFAULT: "#d97706", subtle: "#fef3c7" },
        danger: { DEFAULT: "#dc2626", subtle: "#fee2e2" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.05), 0 1px 3px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
} satisfies Config;
