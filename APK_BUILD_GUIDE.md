# FeedScroll - Android APK Setup Guide

This guide explains how to build your Netflix-style video app as a native Android APK using GitHub Actions and Capacitor.

## What's Included

### 1. GitHub Actions Workflow (`.github/workflows/android.yml`)
- **Triggers on**: Every push to `main`, pull requests, and manual workflow dispatch
- **Builds**: Debug APK automatically on every push
- **Builds**: Release APK (with signing) when pushed to `main`
- **Artifacts**: Uploads APK files as downloadable artifacts

### 2. Capacitor Config (`capacitor.config.ts`)
- App ID: `com.rayhandox.feedscroll`
- App Name: `FeedScroll`
- Background color: Netflix dark (`#141414`)
- HTTPS scheme for secure connections

### 3. Updated Package.json
- Capacitor dependencies added
- New scripts: `cap:sync`, `cap:open`

---

## Setup Instructions

### Step 1: Push to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Add Capacitor for Android APK build"

# Create repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/Feed.git
git branch -M main
git push -u origin main
```

### Step 2: Enable GitHub Actions

1. Go to your repository on GitHub
2. Navigate to **Settings → Actions → General**
3. Scroll to **Workflow permissions**
4. Select **Read and write permissions**
5. Click **Save**

### Step 3: First Build (Debug APK)

1. Go to **Actions** tab in your repository
2. You should see the "Build Android APK" workflow
3. Click **Run workflow** (optional, it runs automatically on push)
4. Wait for the build to complete (~3-5 minutes)
5. Download the APK from the workflow run artifacts

### Step 4: (Optional) Release APK with Signing

For a production-ready APK with your signing key:

#### Generate a Signing Key

```bash
keytool -genkey -v -keystore release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

#### Add GitHub Secrets

1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each:

| Secret Name | Value |
|------------|-------|
| `KEYSTORE_BASE64` | `base64 release.jks` (on your computer) |
| `KEY_ALIAS` | `upload` |
| `KEY_PASSWORD` | Your key password |
| `STORE_PASSWORD` | Your keystore password |

3. Push a commit to trigger release build:
```bash
git add .
git commit -m "Enable release signing"
git push
```

---

## Local Development (Optional)

If you want to run the app locally on your phone during development:

```bash
# Install Capacitor
pnpm add @capacitor/core @capacitor/cli @capacitor/android
npx cap init "FeedScroll" "com.rayhandox.feedscroll" --web-dir=dist

# After building web app
pnpm build:prod
npx cap sync android

# Open in Android Studio
npx cap open android
```

Or use `adb` to install directly:

```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

---

## Troubleshooting

### Workflow fails at build step
- Check the TypeScript compilation errors in the build log
- Ensure all dependencies are in `package.json`

### APK won't install
- Enable **Install unknown apps** in Android settings
- Check if you have enough storage space
- Ensure USB debugging is enabled (if installing via USB)

### Release APK rejected by Play Store
- The release APK needs proper signing and Play Store signing key
- Follow Play Store's signing process after uploading

---

## Workflow Summary

```
Push to main → GitHub Actions →
  ├─ npm install
  ├─ Type check
  ├─ Build web app
  ├─ Add Capacitor
  ├─ Sync to Android
  ├─ Build APK (Debug)
  └─ Upload artifact
```

Each push to `main` generates a fresh debug APK ready to install on any Android device! 🎬