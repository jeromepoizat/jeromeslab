import { useEffect, useState } from 'react'
import './App.css'

type ApiState = 'checking' | 'available' | 'unavailable'
type Theme = 'dark' | 'light'
type SetupStatus = 'loading' | 'needs_workspace' | 'configured' | 'unavailable'

type WorkspaceSetup = {
  recommended_workspace_path: string
  setup_token: string
  workspace_path: string | null
}

const apiStateLabels: Record<ApiState, string> = {
  checking: 'Checking connection',
  available: 'Connected',
  unavailable: 'Not connected',
}

const healthCheckIntervalMs = 3_000

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
  const [setupStatus, setSetupStatus] = useState<SetupStatus>('loading')
  const [workspaceSetup, setWorkspaceSetup] = useState<WorkspaceSetup | null>(null)
  const [workspacePath, setWorkspacePath] = useState('')
  const [setupError, setSetupError] = useState<string | null>(null)
  const [needsNonemptyConfirmation, setNeedsNonemptyConfirmation] = useState(false)
  const [isSelectingFolder, setIsSelectingFolder] = useState(false)
  const [isConfiguringWorkspace, setIsConfiguringWorkspace] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    let controller: AbortController | null = null
    let disposed = false

    const checkHealth = async () => {
      controller?.abort()
      controller = new AbortController()

      try {
        const response = await fetch('/api/health', { signal: controller.signal })
        if (!response.ok) {
          throw new Error(`Health request failed: ${response.status}`)
        }

        if (!disposed) {
          setApiState('available')
        }
      } catch (error: unknown) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }

        if (!disposed) {
          setApiState('unavailable')
        }
      }
    }

    const checkWhenVisible = () => {
      if (document.visibilityState === 'visible') {
        void checkHealth()
      }
    }

    void checkHealth()
    const intervalId = window.setInterval(() => {
      void checkHealth()
    }, healthCheckIntervalMs)

    document.addEventListener('visibilitychange', checkWhenVisible)
    window.addEventListener('focus', checkWhenVisible)

    return () => {
      disposed = true
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', checkWhenVisible)
      window.removeEventListener('focus', checkWhenVisible)
      controller?.abort()
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/setup', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error('The local setup service is unavailable.')
        }
        return (await response.json()) as WorkspaceSetup & { configured: boolean }
      })
      .then((setup) => {
        setWorkspaceSetup(setup)
        setWorkspacePath(setup.workspace_path ?? setup.recommended_workspace_path)
        setSetupStatus(setup.configured ? 'configured' : 'needs_workspace')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setSetupStatus('unavailable')
      })

    return () => controller.abort()
  }, [])

  const readApiError = async (response: Response) => {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    return body?.detail ?? 'The request could not be completed. Try again.'
  }

  const selectFolder = async () => {
    if (workspaceSetup === null) {
      return
    }

    setIsSelectingFolder(true)
    setSetupError(null)
    try {
      const response = await fetch('/api/setup/select-folder', {
        method: 'POST',
        headers: { 'X-Jeromes-Lab-Setup-Token': workspaceSetup.setup_token },
      })
      if (!response.ok) {
        throw new Error(await readApiError(response))
      }
      const result = (await response.json()) as { path: string | null }
      if (result.path !== null) {
        setWorkspacePath(result.path)
        setNeedsNonemptyConfirmation(false)
      }
    } catch (error: unknown) {
      setSetupError(error instanceof Error ? error.message : 'The folder picker could not be opened.')
    } finally {
      setIsSelectingFolder(false)
    }
  }

  const configureWorkspace = async (confirmNonempty: boolean) => {
    if (workspaceSetup === null) {
      return
    }

    setIsConfiguringWorkspace(true)
    setSetupError(null)
    try {
      const response = await fetch('/api/setup/workspace', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Jeromes-Lab-Setup-Token': workspaceSetup.setup_token,
        },
        body: JSON.stringify({ path: workspacePath, confirm_nonempty: confirmNonempty }),
      })
      if (!response.ok) {
        const message = await readApiError(response)
        if (!confirmNonempty && message.includes('already contains files')) {
          setNeedsNonemptyConfirmation(true)
          setSetupError(message)
          return
        }
        throw new Error(message)
      }
      const result = (await response.json()) as { workspace_path: string }
      setWorkspaceSetup({ ...workspaceSetup, workspace_path: result.workspace_path })
      setWorkspacePath(result.workspace_path)
      setSetupStatus('configured')
      setNeedsNonemptyConfirmation(false)
    } catch (error: unknown) {
      setSetupError(error instanceof Error ? error.message : 'The workspace could not be created.')
    } finally {
      setIsConfiguringWorkspace(false)
    }
  }

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
        {setupStatus === 'loading' && (
          <section className="foundation-card" aria-live="polite">
            <p className="step-label">Preparing workspace</p>
            <h2>Checking local setup</h2>
            <p>Jerome&apos;s Laboratory is checking its local configuration.</p>
          </section>
        )}

        {setupStatus === 'needs_workspace' && (
          <section className="foundation-card workspace-setup" aria-labelledby="workspace-title">
            <p className="step-label">First-run setup</p>
            <h2 id="workspace-title">Choose your research workspace</h2>
            <p>
              Your projects, local database, artifacts, exports, and backups stay together in
              this folder. You can paste a path or select a folder from your computer.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void configureWorkspace(false)
              }}
            >
              <label htmlFor="workspace-path">Workspace folder</label>
              <div className="workspace-path-controls">
                <input
                  id="workspace-path"
                  value={workspacePath}
                  onChange={(event) => {
                    setWorkspacePath(event.target.value)
                    setNeedsNonemptyConfirmation(false)
                  }}
                  placeholder="C:\\Users\\you\\Documents\\Jerome's Laboratory"
                  required
                />
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void selectFolder()}
                  disabled={isSelectingFolder || isConfiguringWorkspace}
                >
                  {isSelectingFolder ? 'Opening…' : 'Select folder'}
                </button>
              </div>
              {setupError !== null && <p className="setup-error" role="alert">{setupError}</p>}
              {needsNonemptyConfirmation && (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void configureWorkspace(true)}
                  disabled={isConfiguringWorkspace}
                >
                  Use this folder anyway
                </button>
              )}
              <button className="primary-button" type="submit" disabled={isConfiguringWorkspace}>
                {isConfiguringWorkspace ? 'Preparing workspace…' : 'Continue'}
              </button>
            </form>
          </section>
        )}

        {setupStatus === 'configured' && (
          <section className="foundation-card" aria-labelledby="foundation-title">
            <p className="step-label">Local workspace ready</p>
            <h2 id="foundation-title">Application foundation</h2>
            <p>
              Your workspace is ready at <code>{workspacePath}</code>. Project and scientific
              workflow features will be added incrementally with provenance preserved from the
              start.
            </p>
          </section>
        )}

        {setupStatus === 'unavailable' && (
          <section className="foundation-card" aria-labelledby="unavailable-title">
            <p className="step-label">Local setup unavailable</p>
            <h2 id="unavailable-title">Reconnect the local application</h2>
            <p>Start Jerome&apos;s Laboratory again, then refresh this page.</p>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
