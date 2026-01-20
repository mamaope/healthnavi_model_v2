package ai.empirico.app.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.ui.screen.ChatScreen
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

@Composable
fun NavGraph(
    navController: NavHostController
) {
    val authViewModel: AuthViewModel = viewModel()
    val uiState by authViewModel.uiState.collectAsState()
    val isAuthenticated = uiState.isAuthenticated
    
    // Create a shared ChatViewModel at the NavGraph level
    // This ensures the same instance is used across Chat and Sessions screens
    val chatViewModel: ChatViewModel = viewModel()
    
    NavHost(
        navController = navController,
        startDestination = if (isAuthenticated) Screen.Chat.route else Screen.Login.route
    ) {
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
                viewModel = authViewModel
            )
        }
        
        composable(Screen.Register.route) {
            RegisterScreen(
                onRegisterSuccess = {
                    navController.navigate(Screen.Chat.route) {
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
                        popUpTo(Screen.Chat.route) { inclusive = true }
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

