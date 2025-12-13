package com.mamaope.healthnavy.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mamaope.healthnavy.ui.screen.ChatScreen
import com.mamaope.healthnavy.ui.screen.LoginScreen
import com.mamaope.healthnavy.ui.screen.RegisterScreen
import com.mamaope.healthnavy.ui.screen.SessionsScreen
import com.mamaope.healthnavy.ui.viewmodel.AuthViewModel
import com.mamaope.healthnavy.ui.viewmodel.ChatViewModel

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Register : Screen("register")
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
        
        composable(Screen.Chat.route) {
            val chatViewModel: ChatViewModel = viewModel()
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
            val chatViewModel: ChatViewModel = viewModel()
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
                onBack = {
                    navController.popBackStack()
                },
                viewModel = chatViewModel
            )
        }
    }
}

