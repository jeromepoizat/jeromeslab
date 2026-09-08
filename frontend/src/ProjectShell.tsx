import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { LLMSettings } from './LLMConfiguration'

type Project = {
  id: string
  tag: string
  scientific_question: string
  question_is_editable: boolean
  question_detailing_prompt: string
  question_detailing_prompt_version: string
}

type ClientState = { selected_project_id: string | null; scroll_top: number }

type Props = {
  setupToken: string
  llmSettings: LLMSettings
  onOpenSettings: () => void
}

type HelpProps = { children: string }

function HelpTooltip({ children }: HelpProps) {
  return <span className="section-help" tabIndex={0} aria-label="Section help">?<span className="section-help-tooltip" role="tooltip">{children}</span></span>
}

function SectionTitle({ children, help }: { children: string; help: string }) {
  return <div className="section-title"><h2>{children}</h2><HelpTooltip>{help}</HelpTooltip></div>
}

type EditableFieldProps = {
  variant: 'single-line' | 'multiline'
  isEditing: boolean
  canEdit?: boolean
  display: ReactNode
  editor: ReactNode
  actions: ReactNode
  onEdit: () => void
  editLabel: string
}

function EditableField({ variant, isEditing, canEdit = true, display, editor, actions, onEdit, editLabel }: EditableFieldProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  return <div className={`editable-field editable-field--${variant} ${isExpanded ? 'editable-field--expanded' : ''}`}>
    <div className="editable-box-row">
      <div className={`project-input-box ${isEditing ? 'project-input-box--editing' : ''}`}>
        {isEditing ? editor : display}
      </div>
      {!isEditing && canEdit && <button className="edit-icon" type="button" title={editLabel} aria-label={editLabel} onClick={onEdit}>✎</button>}
      {variant === 'multiline' && <button className="expand-handle" type="button" title={isExpanded ? 'Collapse input' : 'Expand input to show all content'} aria-label={isExpanded ? 'Collapse input' : 'Expand input to show all content'} aria-expanded={isExpanded} onClick={() => setIsExpanded(!isExpanded)}><svg aria-hidden="true" viewBox="0 0 16 10"><path d={isExpanded ? 'M2 8 8 2l6 6' : 'm2 2 6 6 6-6'} /></svg></button>}
    </div>
    <div className="edit-controls">{isEditing ? actions : null}</div>
  </div>
}

async function readApiError(response: Response) {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null
  return body?.detail ?? 'The request could not be completed. Try again.'
}

export function ProjectShell({ setupToken, llmSettings, onOpenSettings }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isSidebarHovered, setIsSidebarHovered] = useState(false)
  const [suppressHoverExpansion, setSuppressHoverExpansion] = useState(false)
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
  const isSidebarExpanded = !isCollapsed || (isSidebarHovered && !suppressHoverExpansion)
  const toggleSidebar = () => {
    if (isCollapsed) {
      setIsCollapsed(false)
      setSuppressHoverExpansion(false)
      return
    }
    setIsCollapsed(true)
    setIsSidebarHovered(false)
    setSuppressHoverExpansion(true)
  }
  return (
    <div className={`project-layout ${isSidebarExpanded ? 'project-layout--expanded' : ''}`}>
      {selectedProject !== null && <div className="project-header-context"><strong>{selectedProject.tag}</strong><span>{selectedProject.scientific_question}</span></div>}
      <aside className="project-sidebar" aria-label="Projects" onMouseEnter={() => setIsSidebarHovered(true)} onMouseLeave={() => { setIsSidebarHovered(false); setSuppressHoverExpansion(false) }}>
        <div className="project-sidebar-header">
          <p className="step-label sidebar-content">Projects</p>
          <button className="sidebar-toggle" type="button" onClick={toggleSidebar} aria-label={isCollapsed ? 'Expand projects' : 'Collapse projects'}>{isCollapsed ? '›' : '‹'}</button>
        </div>
        <div className="sidebar-content">
          <button className="new-project-button" type="button" onClick={() => selectProject(null)}>+ New project</button>
          <nav className="project-list" aria-label="Project list">
            {projects.map(project => <div className="project-list-row" key={project.id}>
              {editingTagId === project.id ? <form onSubmit={event => { event.preventDefault(); void renameProject(project.id) }}><input autoFocus value={editingTag} onChange={event => setEditingTag(event.target.value)} onBlur={() => setEditingTagId(null)} aria-label="Project tag" /></form> : <button className={`project-list-item ${project.id === selectedProjectId ? 'project-list-item--selected' : ''}`} type="button" onClick={() => selectProject(project.id)} onDoubleClick={() => { setEditingTagId(project.id); setEditingTag(project.tag) }}>{project.tag}</button>}
              {editingTagId !== project.id && <button className="rename-project" type="button" title="Rename project tag" aria-label={`Rename project tag ${project.tag}`} onClick={() => { setEditingTagId(project.id); setEditingTag(project.tag) }}>✎</button>}
            </div>)}
          </nav>
        </div>
      </aside>
      <section className="project-content">
        {selectedProject === null ? <div className="new-project-card">
          <p className="step-label">New project</p>
          <SectionTitle help="Enter the exact scientific question that will define this project and its later research workflow.">What scientific question do you want to investigate?</SectionTitle>
          <input value={question} onChange={event => setQuestion(event.target.value)} placeholder="Enter the exact scientific question…" aria-label="Scientific question" />
          {error !== null && <p className="setup-error" role="alert">{error}</p>}
          <button className="primary-button" type="button" onClick={() => void createProject()} disabled={isCreating}>{isCreating ? 'Starting…' : 'Start'}</button>
        </div> : <article className="project-view">
          <p className="step-label">{selectedProject.tag}</p>
          <SectionTitle help="The exact question that defines this project and supplies later workflow steps.">Scientific question</SectionTitle>
          <EditableField
            variant="single-line"
            isEditing={isEditingQuestion}
            canEdit={selectedProject.question_is_editable}
            display={<p className="scientific-question">{selectedProject.scientific_question}</p>}
            editor={<input value={editedQuestion} onChange={event => setEditedQuestion(event.target.value)} aria-label="Scientific question" />}
            onEdit={() => { setEditedQuestion(selectedProject.scientific_question); setIsEditingQuestion(true) }}
            editLabel="Edit scientific question"
            actions={<>
              <button className="primary-button" type="button" onClick={() => void saveScientificQuestion(selectedProject.id)} disabled={isSavingQuestion}>{isSavingQuestion ? 'Saving…' : 'Save question'}</button>
              <button className="text-button" type="button" onClick={() => setIsEditingQuestion(false)} disabled={isSavingQuestion}>Cancel</button>
            </>}
          />
          <section className="project-section">
            <SectionTitle help="Instructions used to turn this question into a structured research plan for later literature searches.">Question-detailing prompt</SectionTitle>
            <EditableField
              variant="multiline"
              isEditing={isEditingPrompt}
              display={<pre className="question-detailing-prompt">{selectedProject.question_detailing_prompt}</pre>}
              editor={<textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Question-detailing prompt" />}
              onEdit={() => { setEditedPrompt(selectedProject.question_detailing_prompt); setIsEditingPrompt(true) }}
              editLabel="Edit question-detailing prompt"
              actions={<><button className="primary-button" type="button" onClick={() => void saveQuestionDetailingPrompt(selectedProject.id)} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></>}
            />
            <div className="llm-job-provider">
              <div><span>Model for this job</span>{llmSettings.configured
                ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong>
                : <strong>Not configured</strong>}</div>
              <button className="text-button" type="button" onClick={onOpenSettings}>{llmSettings.configured ? 'Change' : 'Configure provider'}</button>
            </div>
          </section>
          {error !== null && <p className="setup-error" role="alert">{error}</p>}
        </article>}
      </section>
    </div>
  )
}
