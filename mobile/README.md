# HealthNavy Mobile App

Android mobile application for HealthNavy Clinical Decision Support System.

## Features

- **Authentication**: Email/password login and registration
- **Chat Interface**: Real-time clinical decision support chat
- **Session Management**: Create and manage multiple chat sessions
- **Message Feedback**: Provide feedback on AI responses (Helpful/Not Helpful)
- **Deep Search**: Toggle for enhanced search capabilities

## Architecture

The app follows MVVM (Model-View-ViewModel) architecture:

- **Data Layer**: 
  - Models (`data/model/`)
  - API Service (`data/api/`)
  - Repositories (`data/repository/`)

- **UI Layer**:
  - Screens (`ui/screen/`)
  - ViewModels (`ui/viewmodel/`)
  - Theme (`ui/theme/`)

- **Navigation**: Jetpack Compose Navigation

## Setup

1. **Configure API URL**: 
   Update `BASE_URL` in `RetrofitClient.kt`:
   - For Android Emulator: `http://10.0.2.2:8000/api/v2`
   - For Physical Device: Use your computer's IP address (e.g., `http://192.168.1.100:8000/api/v2`)

2. **Build the app**:
   ```bash
   ./gradlew assembleDebug
   ```

3. **Install on device**:
   ```bash
   ./gradlew installDebug
   ```

## Dependencies

- Jetpack Compose for UI
- Retrofit & OkHttp for networking
- Coroutines for async operations
- Navigation Compose for navigation
- Material 3 for design system

## API Integration

The app connects to the HealthNavy backend API. Ensure the backend is running and accessible from your device/emulator.

## Notes

- The app uses cleartext traffic for localhost connections (development only)
- For production, configure HTTPS and update the network security config
- Google Sign-In can be added by configuring OAuth credentials





