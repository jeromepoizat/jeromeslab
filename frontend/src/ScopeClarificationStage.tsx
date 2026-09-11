import { useState, type RefObject } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type ScopeAnswer } from './JobQueue'
import { ChangeModelIcon, EditableField, PromptToggleButton, SectionTitle } from './ProjectElements'
import { ScopeQuestionnaire } from './ScopeQuestionnaire'

export type ScopeProject = {
  id: string
  scope_clarification_prompt: string
  scope_clarification_prompt_version: string
  scope_clarification_prompt_is_editable: boolean
}

type Props = {
  project: ScopeProject
  job: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  jobCardRef: RefObject<HTMLDivElement | null>
  outputRef: RefObject<HTMLElement | null>
  onProjectUpdated: (project: ScopeProject) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

export function ScopeClarificationStage({ project, job, setupToken, llmSettings, nowMilliseconds, jobCardRef, outputRef, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'
  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const usesProjectFramingLanguage = Number.parseInt(job?.prompt_template_version ?? project.scope_clarification_prompt_version, 10) >= 3

  const savePrompt = async () => {
    setIsSavingPrompt(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/scope-clarification-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated((await response.json()) as ScopeProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/scope-clarification/jobs`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked(); setIsEditingPrompt(false); setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Project framing could not be queued.')
    } finally { setIsStartingJob(false) }
  }

  const cancelJob = async () => {
    if (job === null) return
    setError(null)
    const response = await fetch(`/api/jobs/${job.id}/cancel`, { method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken } })
    if (!response.ok) setError(await readApiError(response))
    await onJobsChanged()
  }

  const saveAnswers = async (answers: ScopeAnswer[], isEditing: boolean) => {
    if (job === null || (isEditing && job.scope_answers_version === null)) return
    const response = await fetch(`/api/jobs/${job.id}/scope-answers`, {
      method: isEditing ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
      body: JSON.stringify({ answers, ...(isEditing ? { base_version: job.scope_answers_version } : {}) }),
    })
    if (!response.ok) throw new Error(await readApiError(response))
    await onJobsChanged()
  }

  return <>
    <section className="project-section">
      <SectionTitle help={usesProjectFramingLanguage ? 'Advanced instructions used to ask only the project-level decisions needed to frame the next research cycle. Literature search and screening scope are decided later.' : 'Advanced instructions used to turn the confirmed research intent into a small set of material scope decisions.'}>{usesProjectFramingLanguage ? 'Project-framing prompt' : 'Scope-clarification prompt'}</SectionTitle>
      {isPromptVisible && <div className="job-prompt-disclosure"><EditableField
        variant="multiline" isEditing={isEditingPrompt} canEdit={project.scope_clarification_prompt_is_editable}
        display={<pre className="question-detailing-prompt">{project.scope_clarification_prompt}</pre>}
        editor={<textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Scope-clarification prompt" />}
        onEdit={() => { setEditedPrompt(project.scope_clarification_prompt); setIsEditingPrompt(true) }} editLabel="Edit scope-clarification prompt"
        actions={<><button className="primary-button" type="button" onClick={() => void savePrompt()} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></>}
      /></div>}
      <div id={job === null ? undefined : `job-card-${job.id}`} ref={jobCardRef} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' ? <div className="completed-job-card"><span>{usesProjectFramingLanguage ? 'Project framing' : 'Scope clarification'}</span><JobStatusLabel status="completed" /></div> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button></div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{usesProjectFramingLanguage ? 'Frame this research cycle' : 'Start scope clarification'}</button>}
          {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the original question, effective {usesProjectFramingLanguage ? 'research direction' : 'research intent'}, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
          {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>{usesProjectFramingLanguage ? 'Project-framing job' : 'Scope-clarification job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    </section>

    {job?.status === 'completed' && job.scope_questions !== null && <section id={`job-output-${job.id}`} ref={outputRef} className="project-section scope-section job-output-section">
      <SectionTitle help={usesProjectFramingLanguage ? 'Answer only project-level decisions needed for the next cycle. Scientific unknowns can remain investigation objectives, while literature inclusion and exclusion rules are decided later.' : 'Resolve each material boundary using suggested choices, your own note, or Not sure. Notes may replace the suggested choices.'}>{usesProjectFramingLanguage ? 'Frame the research cycle' : 'Clarify the research scope'}</SectionTitle>
      <p className="scope-introduction">{job.scope_questions.introduction}</p>
      <ScopeQuestionnaire
        key={`${job.id}:${job.scope_answers_version ?? 'open'}`}
        questions={job.scope_questions.questions}
        savedAnswers={job.scope_answers}
        canEdit={job.scope_answers_is_editable}
        confirmLabel={usesProjectFramingLanguage ? 'Confirm framing answers' : 'Confirm scope answers'}
        editLabel={usesProjectFramingLanguage ? 'Edit framing answers' : 'Edit scope answers'}
        idPrefix={`scope-${job.id}`}
        onSave={saveAnswers}
      />
      <div className="output-provenance intent-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span></div>
    </section>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </>
}
