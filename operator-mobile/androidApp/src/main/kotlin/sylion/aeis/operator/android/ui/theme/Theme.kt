package sylion.aeis.operator.android.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val AEISDarkColorScheme = darkColorScheme(
    primary = Primary80,
    onPrimary = OnPrimary20,
    primaryContainer = PrimaryContainer30,
    onPrimaryContainer = OnPrimaryContainer90,
    secondary = Secondary80,
    onSecondary = OnSecondary20,
    secondaryContainer = SecondaryContainer30,
    tertiary = Tertiary80,
    onTertiary = OnTertiary20,
    tertiaryContainer = TertiaryContainer30,
    background = Background10,
    onBackground = OnBackground90,
    surface = Surface10,
    onSurface = OnSurface90,
    surfaceVariant = SurfaceVariant30,
    onSurfaceVariant = OnSurfaceVariant60,
    error = Error80,
    onError = OnError20,
    errorContainer = ErrorContainer30,
    outline = Outline50,
)

@Composable
fun AEISOperatorTheme(
    content: @Composable () -> Unit,
) {
    val colorScheme = AEISDarkColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AEISTypography,
        content = content,
    )
}
