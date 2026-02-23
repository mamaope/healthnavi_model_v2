# Mobile App Session & Auth Handling — Diagnosis & Implementation

## Current Session Flow

### 1. App Start (LoadingScreen)
- **AuthViewModel.init** → `authRepository.initialize()` restores token from DataStore
- **AuthRepository.currentUser** flow emits user (or null)
- **LoadingScreen** waits for `isInitialized`; then navigates to Chat (if authenticated) or Login
- **Timeout** (15s): if init doesn’t complete (e.g. network down), redirect to Login with “Connection timed out”

### 2. Login Flow
- **LoginScreen** → email/password or Google Sign-In
- On success → `isAuthenticated` becomes true → `onLoginSuccess()` → navigate to Chat
- On failure → show user-friendly error (see Error Messages below)

### 3. Protected Screens
- **Chat, Sessions, Profile, Settings, Pilot, SurveyForm** require auth
- **Global auth guard** in NavGraph: when `isAuthenticated` becomes false while on a protected route → redirect to Login (clear back stack)
- Covers: explicit logout, token expiry (401), session invalidated

### 4. Session Expiry (401)
- **ChatViewModel** detects auth errors from API: “not authenticated”, 401, “unauthorized”
- Sets `authExpired = true` instead of showing an error
- **ChatScreen** observes `authExpired` → calls `onSessionExpired()` → logout + redirect to Login
- User is redirected to Login instead of seeing an error message

---

## Data Layer Requirement

**AuthRepository** must clear the token when the API returns 401/403:

```kotlin
// In your OkHttp interceptor or API client:
// When response is 401 or 403:
// 1. Clear token from DataStore
// 2. Emit null to currentUser flow
// This causes isAuthenticated to become false → auth guard redirects
```

If the data layer does not clear the token on 401, the app will still redirect via ChatViewModel’s `authExpired` path, but the token will remain in storage until the next explicit logout.

---

## Edge Cases Handled

| Edge Case | Handling |
|-----------|----------|
| Token expired (401) | Redirect to Login, no error message |
| Network timeout on init | Show “Connection timed out” + “Continue to Sign In” |
| Init throws | Set `isInitialized = true`, `isAuthenticated = false` → redirect to Login |
| User logs out while on Chat | `onLogout` → logout + navigate to Login |
| User logs out while on Profile/Settings | Auth guard sees `isAuthenticated = false` → redirect to Login |
| Deep link to protected route when not logged in | Start at Loading → Login (no way to reach protected routes without auth) |
| Auth flow collector throws | Set `isAuthenticated = false` → redirect to Login |
| Session load fails with 401 | Set `authExpired` → redirect to Login |
| Send message fails with 401 | Set `authExpired` → redirect to Login |
| Feedback submit fails with 401 | Set `authExpired` → redirect to Login |

---

## Error Messages (User-Friendly)

### Login
- Invalid credentials → “Invalid email or password. Please try again.”
- Network error → “Network error. Please check your connection and try again.”
- Timeout → “Connection timed out. Please try again.”
- Generic → “Unable to sign in. Please try again.”

### Registration
- Email exists → “This email is already registered. Please sign in instead.”
- Network error → “Network error. Please check your connection and try again.”
- Generic → “Unable to create account. Please try again.”

### Google Sign-In
- Network error → “Network error. Please check your connection and try again.”
- Account disabled → “Google Sign-In is not available for this account.”
- Generic → “Google Sign-In failed. Please try again.”

---

## Files Modified

- **NavGraph.kt** — Global auth guard, `PROTECTED_ROUTES`, `onSessionExpired` for Chat
- **ChatScreen.kt** — `onSessionExpired` callback, `LaunchedEffect(uiState.authExpired)`
- **ChatViewModel.kt** — `authExpired` in state, auth error handling in all API calls, `clearAuthExpired()`
- **LoadingScreen.kt** — Timeout (15s), fallback UI when timed out
- **AuthViewModel.kt** — Init error handling, user-friendly error messages for login/register/Google
