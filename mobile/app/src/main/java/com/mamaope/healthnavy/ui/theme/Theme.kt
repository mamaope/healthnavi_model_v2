package com.mamaope.healthnavy.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = PrimaryBlueLight, // #2E66FF - lighter blue for dark theme
    secondary = AccentCoralLight, // #FB923C
    tertiary = SuccessGreen, // #22C55E
    background = Color(0xFF1A1816), // Dark background matching frontend
    surface = Color(0xFF252220), // Dark surface matching frontend
    surfaceVariant = Color(0xFF322F2C), // Dark tertiary matching frontend
    onPrimary = Neutral0,
    onSecondary = Neutral0,
    onTertiary = Neutral0,
    onBackground = Color(0xFFFAFAF9), // Light text on dark background
    onSurface = Color(0xFFFAFAF9),
    onSurfaceVariant = Color(0xFFD6D3D1), // Secondary text
    error = ErrorRed,
    onError = Neutral0,
    errorContainer = Color(0x26EF4444), // Error with opacity
    onErrorContainer = ErrorRedLight
)

private val LightColorScheme = lightColorScheme(
    primary = PrimaryBlue, // #1A4275 - Medical Blue
    secondary = AccentCoral, // #F97316 - Warm Coral
    tertiary = SuccessGreen, // #22C55E - Soft Green
    background = Neutral0, // #FFFFFF - White
    surface = Neutral50, // #FAFAF9 - Light gray
    surfaceVariant = Neutral100, // #F5F5F4 - Slightly darker gray
    onPrimary = Neutral0, // White text on primary
    onSecondary = Neutral0, // White text on secondary
    onTertiary = Neutral0, // White text on tertiary
    onBackground = Neutral900, // #1C1917 - Dark text
    onSurface = Neutral900, // #1C1917 - Dark text
    onSurfaceVariant = Neutral600, // #57534E - Medium gray text
    error = ErrorRed, // #EF4444
    onError = Neutral0,
    errorContainer = Color(0x1AEF4444), // Error with opacity
    onErrorContainer = ErrorRedDark
)

@Composable
fun HealthNavyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Dynamic color disabled to use custom HealthNavy theme
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = HealthNavyTypography,
        content = content
    )
}