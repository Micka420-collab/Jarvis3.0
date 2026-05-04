import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      strategies: "generateSW",
      // injecte le handler push dans le SW généré
      injectManifest: { swSrc: undefined },
      includeAssets: ["favicon.svg", "robots.txt", "apple-touch-icon.png", "sw-push.js"],
      manifest: {
        name: "Jarvis 3.0",
        short_name: "Jarvis",
        description: "Assistant domotique auto-hébergé",
        theme_color: "#0a0e14",
        background_color: "#0a0e14",
        display: "standalone",
        orientation: "any",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // Pas de cache des appels /api ni /ws (toujours réseau)
        navigateFallbackDenylist: [/^\/api/, /^\/ws/],
        // ajoute le handler push dans le SW
        importScripts: ["sw-push.js"],
        runtimeCaching: [
          {
            urlPattern: /\/models\/.*\.glb$/,
            handler: "CacheFirst",
            options: {
              cacheName: "avatar-glb",
              expiration: { maxEntries: 4, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /\/icons\/.*\.png$/,
            handler: "CacheFirst",
            options: { cacheName: "pwa-icons" },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
