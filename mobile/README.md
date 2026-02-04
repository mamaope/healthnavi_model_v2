# Empirico Mobile App

Android mobile application for Empirico Clinical Decision Support System.

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

1. **Configure API URL** (required for **physical devices**; emulator can use the default):
   - **Default**: The app uses `https://empirico.ai/api/v2/` (production). No config needed.
   - **Android Emulator (local backend)**: Set `API_BASE_URL=http://10.0.2.2:8050/api/v2/`.
   - **Physical Device (local backend)**: Use your PC's LAN IP, e.g. `API_BASE_URL=http://192.168.1.XXX:8050/api/v2/`. Options:
     - **gradle.properties** (project root):  
       `API_BASE_URL=http://192.168.1.XXX:8050/api/v2/`  
       (replace `192.168.1.XXX` with your machine’s IP; ensure the trailing `/`.)
     - **local.properties** (project root, usually gitignored):  
       `api.base.url=http://192.168.1.XXX:8050/api/v2/`
     - **Command line**:  
       `./gradlew assembleDebug -PAPI_BASE_URL=http://192.168.1.XXX:8050/api/v2/`
   - Ensure the backend is running on that machine and port (default 8050). If the device and PC are on the same Wi‑Fi, allow cleartext in `network_security_config` if required.

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

The app connects to the Empirico backend API. Ensure the backend is running and accessible from your device/emulator.

## Notes

- The app uses cleartext traffic for localhost connections (development only)
- For production, configure HTTPS and update the network security config
- Google Sign-In can be added by configuring OAuth credentials





