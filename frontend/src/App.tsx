import { useEffect, useState } from 'react'
import './App.css'

type ApiState = 'checking' | 'available' | 'unavailable'

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Local scientific workspace</p>
          <h1>Jerome's Laboratory</h1>
        </div>
        <div className={`api-status api-status--${apiState}`} role="status">
          <span aria-hidden="true" />
          API {apiState}
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
