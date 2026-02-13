import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '');
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8000';
  const codespaceName = process.env.CODESPACE_NAME;
  const codespaceHost = codespaceName
    ? `${codespaceName}-8080.app.github.dev`
    : undefined;
  
  console.log('🔧 Vite proxy target:', backendUrl);

  return {
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
      hmr: {
        overlay: false,
        ...(codespaceHost
          ? {
              protocol: "wss",
              host: codespaceHost,
              clientPort: 443,
            }
          : {}),
      },
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          secure: false,
          followRedirects: false,
          configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log('→ Proxying:', req.method, req.url, 'to', options.target);
            });
            proxy.on('error', (err, req, res) => {
              console.error('✗ Proxy error:', err.message);
            });
          },
        },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});