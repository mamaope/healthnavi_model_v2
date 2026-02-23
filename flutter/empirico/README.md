# Empirico (Flutter WebView)

Android and iOS app that loads the Empirico web platform in a WebView.

## Setup

1. Install [Flutter](https://docs.flutter.dev/get-started/install).
2. From this directory run:
   ```bash
   flutter pub get
   ```

## Change the URL

Edit `lib/main.dart` and set `kPlatformUrl` to your web app URL (default: `https://empirico.ai`).

## Run

- **Android:** `flutter run` or open in Android Studio and run.
- **iOS:** `flutter run` (on macOS with Xcode) or open `ios/Runner.xcworkspace` in Xcode and run.

## Build

- **Android APK:** `flutter build apk`
- **iOS:** `flutter build ios` (then archive in Xcode for distribution)

## Requirements

- **Android:** minSdk from Flutter SDK (typically 21+). INTERNET permission is included.
- **iOS:** iOS 12+. `NSAppTransportSecurity` allows HTTPS and web content; change in `ios/Runner/Info.plist` if you need different domains.
