package ai.empirico.app.navigation

import android.app.Activity
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.ui.screen.ChatScreen
import ai.empirico.app.util.GoogleSignInHelper
import ai.empirico.app.ui.screen.LoadingScreen
import ai.empirico.app.ui.screen.LoginScreen
import ai.empirico.app.ui.screen.RegisterScreen
import ai.empirico.app.ui.screen.SessionsScreen
import ai.empirico.app.ui.screen.ForgotPasswordScreen
import ai.empirico.app.ui.screen.ResetPasswordScreen
import ai.empirico.app.ui.screen.ProfileScreen
import ai.empirico.app.ui.screen.SettingsScreen
import ai.empirico.app.ui.screen.SettingsBillingScreen
import ai.empirico.app.ui.screen.SettingsPrivacyScreen
import ai.empirico.app.ui.screen.SettingsCloseAccountScreen
import ai.empirico.app.ui.screen.PilotScreen
import ai.empirico.app.ui.screen.SurveyFormScreen
import ai.empirico.app.ui.viewmodel.AuthViewModel
import ai.empirico.app.ui.viewmodel.ChatViewModel

sealed class Screen(val route: String) {
    object Loading : Screen("loading")
    object Login : Screen("login")
    object Register : Screen("register")
    object ForgotPassword : Screen("forgot_password")
    object ResetPassword : Screen("reset_password/{token}") {
        fun createRoute(token: String) = "reset_password/$token"
    }
    object Chat : Screen("chat")
    object Sessions : Screen("sessions")
    object Profile : Screen("profile")
    object Settings : Screen("settings")
    object SettingsBilling : Screen("settings/billing")
    object SettingsPrivacy : Screen("settings/privacy")
    object SettingsCloseAccount : Screen("settings/close_account")
    object Pilot : Screen("pilot")
    object SurveyForm : Screen("pilot/survey/{surveyType}") {
        fun createRoute(surveyType: String) = "pilot/survey/$surveyType"
    }
}

// Routes that require authentication - redirect to Login if user becomes unauthenticated
private val PROTECTED_ROUTES = setOf(
    Screen.Chat.route,
    Screen.Sessions.route,
    Screen.Profile.route,
    Screen.Settings.route,
    Screen.SettingsBilling.route,
    Screen.SettingsPrivacy.route,
    Screen.SettingsCloseAccount.route,
    Screen.Pilot.route,
    "pilot/survey" // SurveyForm.route prefix
)

@Composable
fun NavGraph(
    navController: NavHostController
) {
    val logTag = "NavGraph"
    val authViewModel: AuthViewModel = viewModel()
    val authState by authViewModel.uiState.collectAsState()
    val context = LocalContext.current

    // Google Sign-In launcher at NavGraph level so the result is always received even if the
    // activity was recreated (e.g. returning from account picker) and we're on Loading or Login.
    val googleSignInLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        Log.d(logTag, "Google Sign-In activity resultCode=${result.resultCode}, hasData=${result.data != null}")
        // Some devices / Google Play Services versions return RESULT_CANCELED even when the Intent contains
        // failure details (ApiException status codes). Parse whenever data is present so we can surface the
        // real reason (e.g. status=10 for misconfiguration / missing release SHA-1).
        if (result.data != null) {
            authViewModel.handleGoogleSignInResult(result.resultCode, result.data)
        } else {
            authViewModel.setError("Google Sign-In was cancelled or failed")
        }
    }

    fun launchGoogleSignIn() {
        val signInIntent = GoogleSignInHelper.getGoogleSignInClient(context).signInIntent
        googleSignInLauncher.launch(signInIntent)
    }

    // Create a shared ChatViewModel at the NavGraph level (before auth effect so we can clear authExpired)
    val chatViewModel: ChatViewModel = viewModel()

    // When auth becomes true while on Login or Loading, navigate to Chat immediately.
    // Clear ChatViewModel.authExpired first: ChatViewModel is created on app start and its init
    // calls loadSessions() with no token, which can set authExpired = true; without clearing it,
    // ChatScreen would immediately call onSessionExpired() and send the user back to Login.
    LaunchedEffect(authState.isAuthenticated) {
        if (!authState.isAuthenticated) return@LaunchedEffect
        val currentRoute = navController.currentBackStackEntry?.destination?.route ?: return@LaunchedEffect
        when (currentRoute) {
            Screen.Login.route -> {
                chatViewModel.clearAuthExpired()
                navController.navigate(Screen.Chat.route) {
                    popUpTo(Screen.Login.route) { inclusive = true }
                }
            }
            Screen.Loading.route -> {
                chatViewModel.clearAuthExpired()
                navController.navigate(Screen.Chat.route) {
                    popUpTo(Screen.Loading.route) { inclusive = true }
                }
            }
            else -> { }
        }
    }

    // Global auth guard: redirect to Login when user becomes unauthenticated while on protected route
    // Handles: explicit logout, token expiry (401), session invalidated
    LaunchedEffect(authState.isAuthenticated, authState.isInitialized) {
        if (!authState.isInitialized) return@LaunchedEffect
        if (authState.isAuthenticated) return@LaunchedEffect
        val currentRoute = navController.currentBackStackEntry?.destination?.route ?: return@LaunchedEffect
        val isProtectedRoute = PROTECTED_ROUTES.any { currentRoute == it || currentRoute.startsWith(it) }
        if (isProtectedRoute) {
            navController.navigate(Screen.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }
    
    NavHost(
        navController = navController,
        startDestination = Screen.Loading.route
    ) {
        composable(Screen.Loading.route) {
            LoadingScreen(
                authViewModel = authViewModel,
                onNavigateToLogin = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Loading.route) { inclusive = true }
                    }
                },
                onNavigateToChat = {
                    navController.navigate(Screen.Chat.route) {
                        popUpTo(Screen.Loading.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Screen.Chat.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onNavigateToRegister = {
                    navController.navigate(Screen.Register.route)
                },
                onNavigateToForgotPassword = {
                    navController.navigate(Screen.ForgotPassword.route)
                },
                onGoogleSignInRequested = { launchGoogleSignIn() },
                viewModel = authViewModel
            )
        }
        
        composable(Screen.Register.route) {
            RegisterScreen(
                onRegisterSuccess = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Register.route) { inclusive = true }
                    }
                },
                onNavigateToLogin = {
                    navController.popBackStack()
                },
                viewModel = authViewModel
            )
        }
        
        composable(Screen.ForgotPassword.route) {
            ForgotPasswordScreen(
                onBack = {
                    navController.popBackStack()
                },
                onSuccess = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.ForgotPassword.route) { inclusive = true }
                    }
                },
                viewModel = authViewModel
            )
        }
        
        composable(
            route = Screen.ResetPassword.route,
            arguments = listOf(
                navArgument("token") {
                    type = NavType.StringType
                    defaultValue = ""
                }
            )
        ) { backStackEntry ->
            val token = backStackEntry.arguments?.getString("token") ?: ""
            ResetPasswordScreen(
                token = if (token.isBlank()) null else token,
                onBack = {
                    navController.popBackStack()
                },
                onSuccess = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.ResetPassword.route) { inclusive = true }
                    }
                },
                viewModel = authViewModel
            )
        }
        
        composable(Screen.Chat.route) {
            ChatScreen(
                onLogout = {
                    authViewModel.logout()
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onSessionExpired = {
                    chatViewModel.clearAuthExpired()
                    authViewModel.logout()
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onNavigateToSessions = { navController.navigate(Screen.Sessions.route) },
                onNavigateToProfile = { navController.navigate(Screen.Profile.route) },
                onNavigateToSettings = { navController.navigate(Screen.Settings.route) },
                onNavigateToPilot = { navController.navigate(Screen.Pilot.route) },
                chatViewModel = chatViewModel
            )
        }
        
        composable(Screen.Sessions.route) {
            SessionsScreen(
                onSessionSelected = { session ->
                    chatViewModel.loadSession(session.id)
                    navController.popBackStack()
                },
                onNewSession = {
                    chatViewModel.startNewChat()
                    chatViewModel.createSession()
                    navController.popBackStack()
                },
                onBack = { navController.popBackStack() },
                viewModel = chatViewModel
            )
        }

        composable(Screen.Profile.route) {
            ProfileScreen(onBack = { navController.popBackStack() }, viewModel = authViewModel)
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onProfile = { navController.navigate(Screen.Profile.route) },
                onBilling = { navController.navigate(Screen.SettingsBilling.route) },
                onPrivacy = { navController.navigate(Screen.SettingsPrivacy.route) },
                onCloseAccount = { navController.navigate(Screen.SettingsCloseAccount.route) }
            )
        }

        composable(Screen.SettingsBilling.route) {
            SettingsBillingScreen(onBack = { navController.popBackStack() })
        }

        composable(Screen.SettingsPrivacy.route) {
            SettingsPrivacyScreen(
                onBack = { navController.popBackStack() },
                onCloseAccount = { navController.navigate(Screen.SettingsCloseAccount.route) }
            )
        }

        composable(Screen.SettingsCloseAccount.route) {
            SettingsCloseAccountScreen(onBack = { navController.popBackStack() }, viewModel = authViewModel)
        }

        composable(Screen.Pilot.route) {
            PilotScreen(
                onBack = { navController.popBackStack() },
                onSurveyClick = { st -> navController.navigate(Screen.SurveyForm.createRoute(st)) }
            )
        }

        composable(
            route = Screen.SurveyForm.route,
            arguments = listOf(navArgument("surveyType") { type = NavType.StringType })
        ) { backStackEntry ->
            val st = backStackEntry.arguments?.getString("surveyType") ?: ""
            SurveyFormScreen(
                surveyType = st,
                onBack = { navController.popBackStack() },
                onSuccess = { navController.popBackStack() }
            )
        }
    }
}

