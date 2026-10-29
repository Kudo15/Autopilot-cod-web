import { defineConfig } from 'vite';

const backendPort = Number(process.env.VITE_BACKEND_PORT || 8000);

export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist'
  }
});
