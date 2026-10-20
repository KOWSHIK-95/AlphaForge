import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#090b0f",
        sidebar: "#0c0f14",
        panel: "#10141a",
        line: "#202731",
        signal: "#76d6a1",
        danger: "#e98282",
        muted: "#82909f",
      },
    },
  },
  plugins: [],
};

export default config;
