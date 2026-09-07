import { useEffect, useState } from 'react'
import './App.css'

type ApiState = 'checking' | 'available' | 'unavailable'
type Theme = 'dark' | 'light'

const apiStateLabels: Record<ApiState, string> = {
  checking: 'Checking connection',
  available: 'Connected',
  unavailable: 'Not connected',
}

function SunIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M20.4 15.3A9 9 0 0 1 8.7 3.6 9 9 0 1 0 20.4 15.3Z" />
    </svg>
  )
}

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [theme, setTheme] = useState<Theme>('dark')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Health request failed: ${response.status}`)
        }
        setApiState('available')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setApiState('unavailable')
      })

    return () => controller.abort()
  }, [])

  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  const themeToggleLabel = `Switch to ${nextTheme} mode`

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Local scientific workspace</p>
          <h1>Jerome's Laboratory</h1>
        </div>
        <div className="header-actions">
          <div
            className={`api-status api-status--${apiState}`}
            role="status"
            aria-label={apiStateLabels[apiState]}
            tabIndex={0}
          >
            <span className="api-status-dot" aria-hidden="true" />
            <span className="api-status-tooltip" role="tooltip">
              {apiStateLabels[apiState]}
            </span>
          </div>
          <button
            className="theme-toggle"
            type="button"
            aria-label={themeToggleLabel}
            title={themeToggleLabel}
            onClick={() => setTheme(nextTheme)}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <main>
        <section className="foundation-card" aria-labelledby="foundation-title">
          <p className="step-label">Milestone 0</p>
          <h2 id="foundation-title">Application foundation</h2>
          <p>
            The local React client and FastAPI service are connected. Project and
            scientific workflow features will be added incrementally with provenance
            preserved from the start.
          </p>
        </section>
      </main>
    </div>
  )
}

export default App
