import { useTheme } from '../../providers/ThemeProvider'

interface ThemeToggleProps {
  ariaLabel?: string
  variant?: 'default' | 'header'
}

export function ThemeToggle({ ariaLabel = 'Toggle theme', variant = 'default' }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme()

  const iconClass =
    theme === 'light'
      ? 'fas fa-sun'
      : 'fas fa-moon'

  const buttonClass =
    variant === 'header' ? 'theme-toggle header-theme-toggle' : 'theme-toggle'

  return (
    <button
      className={buttonClass}
      onClick={toggleTheme}
      aria-label={ariaLabel}
      title={ariaLabel}
    >
      <div className="theme-toggle-slider">
        <i className={iconClass} />
      </div>
    </button>
  )
}

