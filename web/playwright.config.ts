import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 0,
  use: {
    // Em dev e o Vite (5173) com proxy; TC_WEB_URL aponta a suite para o
    // build servido pelo FastAPI (8765) ou para o shell que vier depois.
    baseURL: process.env.TC_WEB_URL ?? "http://127.0.0.1:5173",
    headless: true,
  },
});
