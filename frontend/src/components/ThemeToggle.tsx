import { useTheme } from '../lib/theme'

export function ThemeToggle({ className = 'icon-button' }: { className?: string }) {
  const { theme, toggle } = useTheme()
  return (
    <button type="button" className={className} onClick={toggle} aria-pressed={theme === 'dark'}>
      {theme === 'dark' ? 'Light' : 'Dark'}
      <span className="visually-hidden"> mode</span>
    </button>
  )
}
