# Google Sign-In for Release Builds

Google Sign-In works in **debug** but does nothing (or fails silently) after selecting an account in **release** when the **release signing certificate’s SHA-1** is not registered in Google Cloud.

## Why release behaves differently

- **Debug** builds are signed with the debug keystore (`~/.android/debug.keystore`). That certificate’s SHA-1 is often already added in Google Cloud / Firebase.
- **Release** builds are signed with your **release keystore**. Google only returns an ID token to an app if the APK’s signing certificate SHA-1 is registered for that OAuth client. If the release SHA-1 is missing, account selection completes but the app never receives an ID token, so login appears to do nothing.

## Fix: Add your release SHA-1 in Google Cloud

1. **Get the SHA-1 of your release keystore**

   If you use a release keystore (e.g. `release.keystore` or the one used by your CI):

   ```bash
   keytool -list -v -keystore /path/to/your/release.keystore -alias your_key_alias
   ```

   Under “Certificate fingerprints” copy the **SHA-1** line (e.g. `AA:BB:CC:...`).

   If you build release without a custom keystore (e.g. `assembleRelease` with no `signingConfigs`), the build may still use the debug keystore; in that case use the debug SHA-1:

   ```bash
   keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android -keypass android
   ```

2. **Register the SHA-1 in Google Cloud Console**

   - Open [Google Cloud Console](https://console.cloud.google.com/) → your project.
   - Go to **APIs & Services** → **Credentials**.
   - Under **OAuth 2.0 Client IDs**, open your **Android** client (or create one with application ID `ai.empirico.app`).
   - Add the **SHA-1** from step 1 to that Android client and save.

3. **Use the same Web Client ID for backend**

   The app uses the **Web application** client ID for `requestIdToken()` (see `BuildConfig.GOOGLE_WEB_CLIENT_ID` in `app/build.gradle.kts`). Your backend’s `GOOGLE_CLIENT_ID` (or equivalent) must match this Web client ID. The Android OAuth client (where you added the SHA-1) is separate; it identifies the app, while the Web client ID is what you pass to `requestIdToken()` and what the backend uses to verify the token.

4. **Rebuild and test**

   Build a new release APK, install it, and try Google Sign-In again. After the SHA-1 is registered, the release build should receive the ID token and complete login.

## Summary

| Build   | Signing key      | What to add in Google Cloud     |
|---------|------------------|----------------------------------|
| Debug   | Debug keystore   | Debug keystore SHA-1 (often done) |
| Release | Release keystore | **Release keystore SHA-1**      |

Without the release SHA-1, Google Sign-In after account selection will not work in release builds.
