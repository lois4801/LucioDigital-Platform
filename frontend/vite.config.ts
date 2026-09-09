import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// CRA-compatible: existing code reads process.env.REACT_APP_*, so those are injected at build time.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const define = Object.fromEntries(
    Object.keys(env)
      .filter((k) => k.startsWith("REACT_APP_"))
      .map((k) => [`process.env.${k}`, JSON.stringify(env[k])]),
  );

  return {
    plugins: [react()],
    define: { ...define, "process.env.NODE_ENV": JSON.stringify(mode) },
    envPrefix: ["REACT_APP_", "VITE_"],
    resolve: {
      alias: { "@": path.resolve(__dirname, "src") },
    },
    server: {
      host: "0.0.0.0",
      port: Number(process.env.PORT) || 3000,
      strictPort: true,
      allowedHosts: true,
      hmr: { clientPort: 443, protocol: "wss" },
      watch: { ignored: ["**/node_modules/**", "**/build/**", "**/.git/**"] },
    },
    preview: { host: "0.0.0.0", port: 3000, allowedHosts: true },
    build: { outDir: "build", sourcemap: false },
  };
});
