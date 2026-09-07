import { useCallback, useEffect, useRef, useState } from 'react'

type Project = {
  id: string
  tag: string
  scientific_question: string
  question_is_editable: boolean
  question_detailing_prompt: string
  question_detailing_prompt_version: string
}

type ClientState = { selected_project_id: string | null; scroll_top: number }

type Props = { setupToken: string }

async function readApiError(response: Response) {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null
  return body?.detail ?? 'The request could not be completed. Try again.'
}

export function ProjectShell({ setupToken }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [editingTagId, setEditingTagId] = useState<string | null>(null)
  const [editingTag, setEditingTag] = useState('')
  const [isEditingQuestion, setIsEditingQuestion] = useState(false)
  const [editedQuestion, setEditedQuestion] = useState('')
  const [isSavingQuestion, setIsSavingQuestion] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const restoredScrollTop = useRef(0)
  const saveTimer = useRef<number | null>(null)

  const saveClientState = useCallback((state: ClientState) => {
    void fetch('/api/client-state', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
      body: JSON.stringify(state),
    })
  }, [setupToken])

  useEffect(() => {
    let disposed = false
    Promise.all([fetch('/api/projects'), fetch('/api/client-state')])
      .then(async ([projectsResponse, stateResponse]) => {
        if (!projectsResponse.ok) throw new Error(await readApiError(projectsResponse))
        const loadedProjects = (await projectsResponse.json()) as Project[]
        const state = stateResponse.ok
          ? ((await stateResponse.json()) as ClientState)
          : { selected_project_id: null, scroll_top: 0 }
        if (disposed) return
        setProjects(loadedProjects)
        const savedProjectExists = loadedProjects.some(project => project.id === state.selected_project_id)
        setSelectedProjectId(savedProjectExists ? state.selected_project_id : null)
        restoredScrollTop.current = savedProjectExists ? state.scroll_top : 0
      })
      .catch((loadError: unknown) => {
        if (!disposed) setError(loadError instanceof Error ? loadError.message : 'Projects could not be loaded.')
      })
    return () => { disposed = true }
  }, [])

  useEffect(() => {
    if (selectedProjectId === null) return
    window.setTimeout(() => window.scrollTo({ top: restoredScrollTop.current }), 0)
  }, [selectedProjectId])

  useEffect(() => {
    const onScroll = () => {
      if (saveTimer.current !== null) window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(() => {
        saveClientState({ selected_project_id: selectedProjectId, scroll_top: Math.round(window.scrollY) })
      }, 350)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (saveTimer.current !== null) window.clearTimeout(saveTimer.current)
    }
  }, [saveClientState, selectedProjectId])

  const selectProject = (projectId: string | null) => {
    restoredScrollTop.current = 0
    setSelectedProjectId(projectId)
    setError(null)
    saveClientState({ selected_project_id: projectId, scroll_top: 0 })
  }

  const createProject = async () => {
    setIsCreating(true)
    setError(null)
    try {
      const response = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ scientific_question: question }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const project = (await response.json()) as Project
      setProjects(previous => [...previous, project])
      setQuestion('')
      selectProject(project.id)
    } catch (createError: unknown) {
      setError(createError instanceof Error ? createError.message : 'The project could not be created.')
    } finally {
      setIsCreating(false)
    }
  }

  const renameProject = async (projectId: string) => {
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/tag`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ tag: editingTag }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const updated = (await response.json()) as Project
      setProjects(previous => previous.map(project => project.id === updated.id ? updated : project))
      setEditingTagId(null)
    } catch (renameError: unknown) {
      setError(renameError instanceof Error ? renameError.message : 'The project tag could not be changed.')
    }
  }

  const saveScientificQuestion = async (projectId: string) => {
    setIsSavingQuestion(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/scientific-question`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ scientific_question: editedQuestion }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const updated = (await response.json()) as Project
      setProjects(previous => previous.map(project => project.id === updated.id ? updated : project))
      setIsEditingQuestion(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The scientific question could not be saved.')
    } finally {
      setIsSavingQuestion(false)
    }
  }

  const saveQuestionDetailingPrompt = async (projectId: string) => {
    setIsSavingPrompt(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/question-detailing-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      const updated = (await response.json()) as Project
      setProjects(previous => previous.map(project => project.id === updated.id ? updated : project))
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The prompt could not be saved.')
    } finally {
      setIsSavingPrompt(false)
    }
  }

  const selectedProject = projects.find(project => project.id === selectedProjectId) ?? null
  return (
    <div className={`project-layout ${isCollapsed ? 'project-layout--collapsed' : ''}`}>
      <aside className="project-sidebar" aria-label="Projects">
        <div className="project-sidebar-header">
          {!isCollapsed && <p className="step-label">Projects</p>}
          <button className="sidebar-toggle" type="button" onClick={() => setIsCollapsed(!isCollapsed)} aria-label={isCollapsed ? 'Expand projects' : 'Collapse projects'}>{isCollapsed ? '›' : '‹'}</button>
        </div>
        {!isCollapsed && <>
          <button className="new-project-button" type="button" onClick={() => selectProject(null)}>+ New project</button>
          <nav className="project-list" aria-label="Project list">
            {projects.map(project => <div className="project-list-row" key={project.id}>
              {editingTagId === project.id ? <form onSubmit={event => { event.preventDefault(); void renameProject(project.id) }}><input autoFocus value={editingTag} onChange={event => setEditingTag(event.target.value)} onBlur={() => setEditingTagId(null)} aria-label="Project tag" /></form> : <button className={`project-list-item ${project.id === selectedProjectId ? 'project-list-item--selected' : ''}`} type="button" onClick={() => selectProject(project.id)} onDoubleClick={() => { setEditingTagId(project.id); setEditingTag(project.tag) }}>{project.tag}</button>}
              {editingTagId !== project.id && <button className="rename-project" type="button" title={`Rename ${project.tag}`} aria-label={`Rename ${project.tag}`} onClick={() => { setEditingTagId(project.id); setEditingTag(project.tag) }}>✎</button>}
            </div>)}
          </nav>
        </>}
      </aside>
      <section className="project-content">
        {selectedProject === null ? <div className="new-project-card">
          <p className="step-label">New project</p>
          <h2>What scientific question do you want to investigate?</h2>
          <input value={question} onChange={event => setQuestion(event.target.value)} placeholder="Enter the exact scientific question…" aria-label="Scientific question" />
          {error !== null && <p className="setup-error" role="alert">{error}</p>}
          <button className="primary-button" type="button" onClick={() => void createProject()} disabled={isCreating}>{isCreating ? 'Starting…' : 'Start'}</button>
        </div> : <article className="project-view">
          <p className="step-label">{selectedProject.tag}</p>
          <div className="project-section-heading"><h2>Scientific question</h2>{selectedProject.question_is_editable && <button className="edit-icon" type="button" title="Edit scientific question" aria-label="Edit scientific question" onClick={() => { setEditedQuestion(selectedProject.scientific_question); setIsEditingQuestion(true) }}>✎</button>}</div>
          {isEditingQuestion ? <div className="question-editor">
            <input value={editedQuestion} onChange={event => setEditedQuestion(event.target.value)} aria-label="Scientific question" />
            <div>
              <button className="primary-button" type="button" onClick={() => void saveScientificQuestion(selectedProject.id)} disabled={isSavingQuestion}>{isSavingQuestion ? 'Saving…' : 'Save question'}</button>
              <button className="text-button" type="button" onClick={() => setIsEditingQuestion(false)} disabled={isSavingQuestion}>Cancel</button>
            </div>
          </div> : <>
            <p className="scientific-question">{selectedProject.scientific_question}</p>
          </>}
          <p className="project-input-note">This exact question is the input to later workflow steps. It can only be edited before a workflow job uses it.</p>
          <section className="project-section">
            <div className="project-section-heading"><h2>Question-detailing prompt</h2><button className="edit-icon" type="button" title="Edit question-detailing prompt" aria-label="Edit question-detailing prompt" onClick={() => { setEditedPrompt(selectedProject.question_detailing_prompt); setIsEditingPrompt(true) }}>✎</button></div>
            {isEditingPrompt ? <div className="prompt-editor"><textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Question-detailing prompt" /><div><button className="primary-button" type="button" onClick={() => void saveQuestionDetailingPrompt(selectedProject.id)} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></div></div> : <pre className="question-detailing-prompt">{selectedProject.question_detailing_prompt}</pre>}
          </section>
          {error !== null && <p className="setup-error" role="alert">{error}</p>}
        </article>}
      </section>
    </div>
  )
}

export function ProjectShellBootstrap() {
  const [setupToken, setSetupToken] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const loadSetup = () => fetch('/api/setup', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) return null
        return (await response.json()) as { configured: boolean; setup_token: string }
      })
      .then(setup => {
        if (setup?.configured) setSetupToken(setup.setup_token)
      })
      .catch(() => undefined)
    void loadSetup()
    const intervalId = window.setInterval(() => {
      if (setupToken === null) void loadSetup()
    }, 1_000)
    return () => { controller.abort(); window.clearInterval(intervalId) }
  }, [setupToken])

  return setupToken === null ? null : <ProjectShell setupToken={setupToken} />
}
