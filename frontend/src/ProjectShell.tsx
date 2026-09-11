import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { readApiError } from './apiClient'
import { IntentClarificationStage } from './IntentClarificationStage'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'
import { ChangeModelIcon, EditableField, SectionTitle } from './ProjectElements'
import { ScopeClarificationStage } from './ScopeClarificationStage'
import { ScopeReadinessStage } from './ScopeReadinessStage'

type Project = {
  id: string
  tag: string
  scientific_question: string
  question_is_editable: boolean
  question_detailing_prompt: string
  question_detailing_prompt_version: string
  question_detailing_prompt_is_editable: boolean
  intent_clarification_prompt: string
  intent_clarification_prompt_version: string
  intent_clarification_prompt_is_editable: boolean
  scope_clarification_prompt: string
  scope_clarification_prompt_version: string
  scope_clarification_prompt_is_editable: boolean
  scope_readiness_prompt: string
  scope_readiness_prompt_version: string
  scope_readiness_prompt_is_editable: boolean
}

type ClientState = { selected_project_id: string | null; scroll_top: number }

type Props = {
  setupToken: string
  llmSettings: LLMSettings
  jobs: Job[]
  nowMilliseconds: number
  jobNavigation: { projectId: string; jobId: string; requestId: number; target: 'job' | 'output' } | null
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

export function ProjectShell({ setupToken, llmSettings, jobs, nowMilliseconds, jobNavigation, onJobsChanged, onOpenSettings }: Props) {
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
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [isEditingOutput, setIsEditingOutput] = useState(false)
  const [editedOutput, setEditedOutput] = useState('')
  const [isSavingOutput, setIsSavingOutput] = useState(false)
  const [isShowingOriginalOutput, setIsShowingOriginalOutput] = useState(false)
  const restoredScrollTop = useRef(0)
  const saveTimer = useRef<number | null>(null)
  const jobCard = useRef<HTMLDivElement | null>(null)
  const jobOutput = useRef<HTMLElement | null>(null)
  const scopeJobCard = useRef<HTMLDivElement | null>(null)
  const scopeJobOutput = useRef<HTMLElement | null>(null)
  const readinessJobCard = useRef<HTMLDivElement | null>(null)
  const readinessJobOutput = useRef<HTMLElement | null>(null)

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
    if (jobNavigation === null) return
    let scrollTimer: number | null = null
    const selectionTimer = window.setTimeout(() => {
      restoredScrollTop.current = 0
      setSelectedProjectId(jobNavigation.projectId)
      setIsEditingQuestion(false)
      setIsEditingPrompt(false)
      setIsEditingOutput(false)
      setIsShowingOriginalOutput(false)
      setIsConfirmingJob(false)
      setError(null)
      saveClientState({ selected_project_id: jobNavigation.projectId, scroll_top: 0 })
      scrollTimer = window.setTimeout(() => {
        const target = document.getElementById(`${jobNavigation.target === 'output' ? 'job-output' : 'job-card'}-${jobNavigation.jobId}`)
          ?? (jobNavigation.target === 'output' ? jobOutput.current : jobCard.current)
        target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 50)
    }, 0)
    return () => {
      window.clearTimeout(selectionTimer)
      if (scrollTimer !== null) window.clearTimeout(scrollTimer)
    }
  }, [jobNavigation, saveClientState])

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
    setIsEditingOutput(false)
    setIsShowingOriginalOutput(false)
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

  const startQuestionDetailing = async (projectId: string) => {
    setIsStartingJob(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/question-detailing/jobs`, {
        method: 'POST',
        headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setProjects(previous => previous.map(project => project.id === projectId
        ? { ...project, question_is_editable: false, question_detailing_prompt_is_editable: false }
        : project))
      setIsEditingQuestion(false)
      setIsEditingPrompt(false)
      setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Question detailing could not be queued.')
    } finally {
      setIsStartingJob(false)
    }
  }

  const cancelQuestionDetailing = async (jobId: string) => {
    setError(null)
    const response = await fetch(`/api/jobs/${jobId}/cancel`, {
      method: 'POST',
      headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
    })
    if (!response.ok) setError(await readApiError(response))
    await onJobsChanged()
  }

  const saveDetailedQuestion = async (job: Job) => {
    if (job.effective_output_version === null) return
    setIsSavingOutput(true)
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/question-detailing-output`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ markdown: editedOutput, base_version: job.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
      setIsEditingOutput(false)
      setIsShowingOriginalOutput(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The detailed question could not be saved.')
    } finally {
      setIsSavingOutput(false)
    }
  }

  const selectedProject = projects.find(project => project.id === selectedProjectId) ?? null
  const legacyJob = selectedProject === null
    ? null
    : jobs.find(job => job.project_id === selectedProject.id && job.kind === 'question_detailing') ?? null
  const intentJob = selectedProject === null
    ? null
    : jobs.find(job => job.project_id === selectedProject.id && job.kind === 'intent_clarification') ?? null
  const scopeJob = selectedProject === null
    ? null
    : jobs.find(job => job.project_id === selectedProject.id && job.kind === 'scope_clarification_round_1') ?? null
  const readinessJob = selectedProject === null
    ? null
    : jobs.find(job => job.project_id === selectedProject.id && job.kind === 'scope_readiness') ?? null
  const selectedJob = legacyJob
  const activeJob = legacyJob !== null && (legacyJob.status === 'pending' || legacyJob.status === 'awaiting_response') ? legacyJob : null
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
          {legacyJob === null ? <><IntentClarificationStage
            key={`${selectedProject.id}:${intentJob?.id ?? 'new'}:${intentJob?.intent_selection === null ? 'open' : 'selected'}`}
            project={selectedProject}
            job={intentJob}
            setupToken={setupToken}
            llmSettings={llmSettings}
            nowMilliseconds={nowMilliseconds}
            jobCardRef={jobCard}
            outputRef={jobOutput}
            onProjectUpdated={updated => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, ...updated } : project))}
            onProjectLocked={() => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, question_is_editable: false, intent_clarification_prompt_is_editable: false } : project))}
            onJobsChanged={onJobsChanged}
            onOpenSettings={onOpenSettings}
          />
          {intentJob?.intent_selection !== null && intentJob?.intent_selection !== undefined && <ScopeClarificationStage
            key={`${selectedProject.id}:${scopeJob?.id ?? 'new'}:${scopeJob?.scope_answers_version ?? 'open'}`}
            project={selectedProject}
            job={scopeJob}
            setupToken={setupToken}
            llmSettings={llmSettings}
            nowMilliseconds={nowMilliseconds}
            jobCardRef={scopeJobCard}
            outputRef={scopeJobOutput}
            onProjectUpdated={updated => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, ...updated } : project))}
            onProjectLocked={() => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, scope_clarification_prompt_is_editable: false } : project))}
            onJobsChanged={onJobsChanged}
            onOpenSettings={onOpenSettings}
          />}
          {scopeJob?.scope_answers !== null && scopeJob?.scope_answers !== undefined && <ScopeReadinessStage
            key={`${selectedProject.id}:${readinessJob?.id ?? 'new'}:${readinessJob?.scope_follow_up_answers_version ?? 'open'}`}
            project={selectedProject}
            job={readinessJob}
            setupToken={setupToken}
            llmSettings={llmSettings}
            nowMilliseconds={nowMilliseconds}
            jobCardRef={readinessJobCard}
            outputRef={readinessJobOutput}
            onProjectUpdated={updated => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, ...updated } : project))}
            onProjectLocked={() => setProjects(previous => previous.map(project => project.id === selectedProject.id ? { ...project, scope_readiness_prompt_is_editable: false } : project))}
            onJobsChanged={onJobsChanged}
            onOpenSettings={onOpenSettings}
          />}</> : <>
          <section className="project-section">
            <SectionTitle help="Instructions used to turn this question into a structured research plan for later literature searches.">Question-detailing prompt</SectionTitle>
            <EditableField
              variant="multiline"
              isEditing={isEditingPrompt}
              canEdit={selectedProject.question_detailing_prompt_is_editable}
              display={<pre className="question-detailing-prompt">{selectedProject.question_detailing_prompt}</pre>}
              editor={<textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Question-detailing prompt" />}
              onEdit={() => { setEditedPrompt(selectedProject.question_detailing_prompt); setIsEditingPrompt(true) }}
              editLabel="Edit question-detailing prompt"
              actions={<><button className="primary-button" type="button" onClick={() => void saveQuestionDetailingPrompt(selectedProject.id)} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></>}
            />
            <div id={selectedJob === null ? undefined : `job-card-${selectedJob.id}`} ref={jobCard} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
              {selectedJob?.status === 'completed' ? <div className="completed-job-card"><span>Question detailing</span><JobStatusLabel status="completed" /></div> : <>
                <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label={llmSettings.configured ? 'Change model for future jobs' : 'Configure a model'}><ChangeModelIcon /></button></div>{activeJob !== null
                  ? <strong>{activeJob.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {activeJob.model}</strong>
                  : llmSettings.configured
                    ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong>
                    : <strong>Not configured</strong>}</div>
                {(selectedJob === null || selectedJob.status === 'failed' || selectedJob.status === 'cancelled') && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt || isEditingQuestion} onClick={() => setIsConfirmingJob(true)}>Start question detailing</button>}
                {(selectedJob === null || selectedJob.status === 'failed' || selectedJob.status === 'cancelled') && isConfirmingJob && <div className="job-confirmation job-confirmation--inline">
                  <p>This locks the exact scientific question, prompt, provider, and model shown here. The job can be cancelled only while it remains queued.</p>
                  <div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startQuestionDetailing(selectedProject.id)}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div>
                </div>}
                {activeJob !== null && <div className="active-job-summary">
                  <div className="active-job-heading"><strong>Question-detailing job</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>
                  {activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelQuestionDetailing(activeJob.id)}>Cancel queued job</button>}
                  {activeJob.status === 'awaiting_response' && <p>The request may already have reached {activeJob.provider === 'openai' ? 'OpenAI' : 'Anthropic'}, so cancellation is disabled.</p>}
                  {activeJob.error && <p className="setup-error">{activeJob.error}</p>}
                </div>}
              </>}
            </div>
            {(selectedJob === null || selectedJob.status === 'failed' || selectedJob.status === 'cancelled') && selectedJob?.error && <div className="job-start-area">
              {selectedJob?.error && <p className="setup-error">Previous attempt: {selectedJob.error}</p>}
            </div>}
          </section>
          {selectedJob?.status === 'completed' && selectedJob.original_output_markdown !== null && selectedJob.effective_output_markdown !== null && <section id={`job-output-${selectedJob.id}`} ref={jobOutput} className="project-section job-output-section">
            <SectionTitle help="The exact Markdown returned by the configured model and preserved as an immutable, hash-addressed artifact.">Detailed scientific question</SectionTitle>
            <EditableField
              variant="multiline"
              isEditing={isEditingOutput}
              canEdit={!isShowingOriginalOutput}
              display={<div className="markdown-output"><ReactMarkdown>{isShowingOriginalOutput ? selectedJob.original_output_markdown : selectedJob.effective_output_markdown}</ReactMarkdown></div>}
              editor={<textarea value={editedOutput} onChange={event => setEditedOutput(event.target.value)} aria-label="Detailed scientific question Markdown" />}
              onEdit={() => { setEditedOutput(selectedJob.effective_output_markdown ?? ''); setIsEditingOutput(true) }}
              editLabel="Edit detailed scientific question"
              sideActions={selectedJob.output_was_edited ? <button className="version-toggle-button" type="button" onClick={() => setIsShowingOriginalOutput(!isShowingOriginalOutput)}>{isShowingOriginalOutput ? 'Show edited version' : 'Show original output'}</button> : null}
              footer={<div className="output-provenance"><span>{selectedJob.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {selectedJob.model}</span><span>{selectedJob.total_tokens !== null ? `${selectedJob.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {selectedJob.duration_ms !== null ? `${(selectedJob.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span></div>}
              actions={<><button className="primary-button" type="button" onClick={() => void saveDetailedQuestion(selectedJob)} disabled={isSavingOutput}>{isSavingOutput ? 'Saving…' : 'Save edited version'}</button><button className="text-button" type="button" onClick={() => setIsEditingOutput(false)} disabled={isSavingOutput}>Cancel</button></>}
            />
          </section>}
          </>}
          {error !== null && <p className="setup-error" role="alert">{error}</p>}
        </article>}
      </section>
    </div>
  )
}
