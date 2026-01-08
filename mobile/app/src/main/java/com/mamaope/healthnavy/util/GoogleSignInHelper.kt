package com.mamaope.healthnavy.util

import android.content.Context
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions

object GoogleSignInHelper {
    
    // Web client ID from Google Cloud Console (OAuth 2.0 Client ID for Web application)
    // IMPORTANT: This must be a WEB client ID, not the Android client ID
    // The Android client ID is used automatically by Google Play Services
    private const val DEFAULT_WEB_CLIENT_ID = "1033520161890-o24gvc8ecog70fu0ekv9rrr3hobki87r.apps.googleusercontent.com"
    
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

