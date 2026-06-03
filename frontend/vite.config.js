import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base: './' so the static build works from any path (GH Pages / CF / Vercel).
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', sourcemap: false },
});
