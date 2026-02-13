import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f7f8f4",
        ink: "#121519",
        accent: "#0b7a75",
        accentSoft: "#d8efed",
        border: "#d2d9d8"
      }
    }
  },
  plugins: []
};

export default config;
