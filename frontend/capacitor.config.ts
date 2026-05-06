/// <reference types="@capacitor/cli" />

import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Capacitor : enveloppe la PWA dans une app native Android / iOS.
 *
 * Build :
 *   npm i -D @capacitor/cli @capacitor/core @capacitor/android @capacitor/ios
 *   npm run build
 *   npx cap add android
 *   npx cap add ios
 *   npx cap copy
 *   npx cap open android   # → Android Studio
 *   npx cap open ios       # → Xcode
 *
 * En dev : pointe sur ton serveur Jarvis sur le LAN
 *   server.url = "https://jarvis.local"
 *   server.cleartext = false (TLS auto-signé accepté côté webview)
 *
 * En prod : webDir = "dist" (build statique embarqué dans l'app)
 */
const config: CapacitorConfig = {
  appId: "ai.jarvis.app",
  appName: "Jarvis",
  webDir: "dist",
  bundledWebRuntime: false,
  server: {
    androidScheme: "https",
    iosScheme: "https",
    // Pour pointer sur ton serveur LAN en dev, override avec une env var :
    //   CAP_SERVER_URL=https://jarvis.local npx cap copy
    url: process.env.CAP_SERVER_URL,
    cleartext: false,
  },
  ios: {
    contentInset: "always",
  },
  android: {
    allowMixedContent: false,
    backgroundColor: "#0a0e14",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 800,
      backgroundColor: "#0a0e14",
      androidSplashResourceName: "splash",
      showSpinner: false,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
};

export default config;
