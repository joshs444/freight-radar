import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base: './' so the static build works from any path (GH Pages / CF / Vercel).
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,   // maplibre-gl is one ~1MB lib; intentionally its own chunk
    // Split the heavy map libraries into their own long-cached chunks so a data/app
    // change doesn't re-bust ~480KB-gz of vendor code, and they download in parallel.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('maplibre-gl')) return 'maplibre';
            if (id.includes('weatherlayers-gl') || id.includes('geotiff')) return 'weather';
            if (/[\\/](deck|luma|math|loaders|probe)\.gl[\\/]/.test(id) || id.includes('@deck.gl')) return 'deck';
            if (/[\\/]react(-dom)?[\\/]/.test(id) || id.includes('scheduler')) return 'react';
            return 'vendor';
          }
        },
      },
    },
    // Keep the lazy ambient-wind chunk (weatherlayers + geotiff worker) off the
    // critical-path modulepreload; the hero deck/maplibre stay preloaded.
    modulepreload: {
      resolveDependencies: (_file, deps) => deps.filter((d) => !/weather|geotiff/.test(d)),
    },
  },
});
