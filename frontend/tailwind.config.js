/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f8fafc",
        surface: "#ffffff",
        primary: "#0f172a",
        muted: "#64748b",
        "market-up": "#00D09C",
        "market-down": "#EB5B3C",
        borders: "#e2e8f0",
      },
    },
  },
  plugins: [],
}

