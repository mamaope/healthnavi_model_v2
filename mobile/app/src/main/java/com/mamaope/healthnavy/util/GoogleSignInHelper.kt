package com.mamaope.healthnavy.util

import android.content.Context
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions

object GoogleSignInHelper {
    
    // Web client ID from Google Cloud Console (OAuth 2.0 Client ID for Web application)
    private const val DEFAULT_WEB_CLIENT_ID = "132524488069-ektp8kh37ei9bhoa58f4qqhp3dr2ahsk.apps.googleusercontent.com"
    
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

