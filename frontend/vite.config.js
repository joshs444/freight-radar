import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Strip the heavy, LAZY map-library chunks from the entry HTML's <link rel=modulepreload>.
// maplibre (~277KB gz), deck (~91KB gz) and the ambient-wind chunk are pulled by <Globe> /
// <Chat> through React.lazy — they are NOT in the boot graph (the entry imports only
// react + a small vendor util). Vite still hoists those async deps into the entry preload,
// and build.modulepreload.resolveDependencies only reaches the runtime __vitePreload, not
// these static HTML links — so first paint of the shell would race ~380KB gz of map code
// it doesn't execute yet. We remove those preload hints here; the chunks still load on the
// dynamic import, so the globe just streams in behind <Suspense> a beat later.
function deferHeavyModulepreload() {
  return {
    name: 'defer-heavy-modulepreload',
    transformIndexHtml(html) {
      return html.replace(
        /\s*<link rel="modulepreload"[^>]*(?:maplibre|deck|weather|geotiff)[^>]*>/g,
        ''
      );
    },
  };
}

// base: './' so the static build works from any path (GH Pages / CF / Vercel).
export default defineConfig({
  plugins: [react(), deferHeavyModulepreload()],
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200, // maplibre-gl is one ~1MB lib; intentionally its own chunk
    // Split the heavy map libraries into their own long-cached chunks so a data/app
    // change doesn't re-bust ~480KB-gz of vendor code, and they download in parallel.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('maplibre-gl')) return 'maplibre';
            if (id.includes('weatherlayers-gl') || id.includes('geotiff')) return 'weather';
            if (/[\\/](deck|luma|math|loaders|probe)\.gl[\\/]/.test(id) || id.includes('@deck.gl'))
              return 'deck';
            if (/[\\/]react(-dom)?[\\/]/.test(id) || id.includes('scheduler')) return 'react';
            return 'vendor';
          }
        },
      },
    },
    // Belt-and-suspenders for the runtime async preloads (the wind/geotiff chunk + deck);
    // the HTML-level strip above is what actually keeps maplibre off the boot critical path.
    modulepreload: {
      resolveDependencies: (_file, deps) =>
        deps.filter((d) => !/maplibre|deck|weather|geotiff/.test(d)),
    },
  },
});
