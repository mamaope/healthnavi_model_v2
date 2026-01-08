package com.mamaope.healthnavy.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mamaope.healthnavy.ui.screen.ChatScreen
import com.mamaope.healthnavy.ui.screen.LoginScreen
import com.mamaope.healthnavy.ui.screen.RegisterScreen
import com.mamaope.healthnavy.ui.screen.SessionsScreen
import com.mamaope.healthnavy.ui.screen.ForgotPasswordScreen
import com.mamaope.healthnavy.ui.screen.ResetPasswordScreen
import com.mamaope.healthnavy.ui.viewmodel.AuthViewModel
import com.mamaope.healthnavy.ui.viewmodel.ChatViewModel

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Register : Screen("register")
    object ForgotPassword : Screen("forgot_password")
    object ResetPassword : Screen("reset_password/{token}") {
        fun createRoute(token: String) = "reset_password/$token"
    }
    object Chat : Screen("chat")
    object Sessions : Screen("sessions")
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
                onNavigateToSessions = {
                    navController.navigate(Screen.Sessions.route)
                },
                chatViewModel = chatViewModel
            )
        }
        
        composable(Screen.Sessions.route) {
            SessionsScreen(
                onSessionSelected = { session ->
                    // Load session - this will update the shared ViewModel state
                    chatViewModel.loadSession(session.id)
                    // Navigate back to ChatScreen
                    // The messages will load asynchronously and appear in ChatScreen
                    navController.popBackStack()
                },
                onNewSession = {
                    chatViewModel.startNewChat()
                    chatViewModel.createSession()
                    navController.popBackStack()
                },
                onBack = {
                    navController.popBackStack()
                },
                viewModel = chatViewModel
            )
        }
    }
}

