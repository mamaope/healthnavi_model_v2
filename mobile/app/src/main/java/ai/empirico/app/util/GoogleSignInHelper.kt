package ai.empirico.app.util

import ai.empirico.app.BuildConfig
import android.content.Context
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions

object GoogleSignInHelper {
    
    // Web client ID from Google Cloud Console (OAuth 2.0 Client ID for Web application)
    // IMPORTANT: This must be a WEB client ID, not the Android client ID
    // The Android client ID is used automatically by Google Play Services
    // Uses BuildConfig to get the appropriate client ID for debug vs release builds
    // Release client ID must match backend GOOGLE_CLIENT_ID in .env
    private val DEFAULT_WEB_CLIENT_ID: String = BuildConfig.GOOGLE_WEB_CLIENT_ID
    
    fun getGoogleSignInClient(context: Context, webClientId: String = DEFAULT_WEB_CLIENT_ID): GoogleSignInClient {
        val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestIdToken(webClientId) // Request ID token for backend verification
            .requestEmail()
            .requestProfile()
            .build()
        
        return GoogleSignIn.getClient(context, gso)
    }
    
    fun getLastSignedInAccount(context: Context): GoogleSignInAccount? {
        return GoogleSignIn.getLastSignedInAccount(context)
    }
    
    fun signOut(context: Context, webClientId: String = DEFAULT_WEB_CLIENT_ID) {
        val signInClient = getGoogleSignInClient(context, webClientId)
        signInClient.signOut()
    }
}

