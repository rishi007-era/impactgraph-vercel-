import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// base "./" makes the build work on Vercel, GitHub Pages (project sites), Firebase Hosting, Cloud Run and AI Studio.
export default defineConfig({ plugins: [react()], base: "./" });
