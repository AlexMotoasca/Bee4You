# Bee4You — mobile app

Expo SDK 58 (React Native 0.88) **development build**. Expo Go does not work (PowerSync's SQLite is native code).
Rules and contracts: [FrontendArchitect.md](FrontendArchitect.md).

## 1. One-time setup on your PC (Windows, PowerShell)

1. Fill in `frontend/.env` (copy of `.env.example`):
   - `EXPO_PUBLIC_SUPABASE_KEY` — Supabase → Project Settings → API keys → **publishable** key
   - `EXPO_PUBLIC_POWERSYNC_URL` — PowerSync dashboard → your instance URL
2. Point the tools at Android Studio's Java and the Android SDK (each new PowerShell window, or set them permanently in *Environment Variables*):

   ```powershell
   $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
   $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
   $env:Path += ";$env:ANDROID_HOME\platform-tools"
   ```
3. `cd frontend` and `npm install`.

## 2. Prepare the Galaxy S24 (once)

1. **Settings → About phone → Software information** → tap **Build number** 7 times.
2. **Settings → Developer options** → turn on **USB debugging**.
3. Plug in the USB cable → on the phone tap **Allow** (tick *Always allow from this computer*). If nothing pops up: pull down the notification shade → USB → **File transfer**.
4. Check: `adb devices` must list the phone as `device` (not `unauthorized`).

## 3. Install the app on the phone

```powershell
npx expo run:android --device
```

Pick the S24 from the list. This builds the app (the **first build takes 10–20 minutes**), installs it, and starts the dev server. The app opens on the phone.

Already have a built APK? Install it instead of rebuilding:

```powershell
adb install -r android\app\build\outputs\apk\debug\app-debug.apk
```

## 4. Every day after that

```powershell
npx expo start
```

Open **Bee4You** on the phone. Code changes show up instantly. With the USB cable connected run `adb reverse tcp:8081 tcp:8081` once so the phone reaches the dev server; on the same Wi-Fi it also works without the cable.

Rebuild (step 3) only after adding a library with native code or changing `app.json`.

## Checks before committing

```powershell
npx tsc --noEmit
npx expo lint
npx jest
```

## Troubleshooting

- **"Missing EXPO_PUBLIC_…" on launch** → `.env` is incomplete; fix it, then reload (shake the phone → Reload).
- **Gradle complains about the Java version** → install **JDK 17** (e.g. Microsoft Build of OpenJDK 17) and set `JAVA_HOME` to it.
- **`adb devices` shows `unauthorized`** → unplug/replug and accept the prompt on the phone.
