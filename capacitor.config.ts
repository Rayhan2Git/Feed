import { CapacitorConfig } from '@capacitor/cli/config';

const config: CapacitorConfig = {
  appId: 'com.rayhandox.feedscroll',
  appName: 'FeedScroll',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
  android: {
    backgroundColor: '#141414',
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#141414',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
    },
  },
};

export default config;