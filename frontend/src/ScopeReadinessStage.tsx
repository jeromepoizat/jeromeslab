import { useState, type RefObject } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type ScopeAnswer } from './JobQueue'
import { ChangeModelIcon, EditableField, PromptToggleButton, SectionTitle } from './ProjectElements'
import { ScopeQuestionnaire } from './ScopeQuestionnaire'

export type ReadinessProject = {
  id: string
  scope_readiness_prompt: string
  scope_readiness_prompt_version: string
  scope_readiness_prompt_is_editable: boolean
}

type Props = {
  project: ReadinessProject
  job: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  jobCardRef: RefObject<HTMLDivElement | null>
  outputRef: RefObject<HTMLElement | null>
  onProjectUpdated: (project: ReadinessProject) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

export function ScopeReadinessStage({ project, job, setupToken, llmSettings, nowMilliseconds, jobCardRef, outputRef, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
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
  const usesFramingLanguage = Number.parseInt(job?.prompt_template_version ?? project.scope_readiness_prompt_version, 10) >= 3

  const savePrompt = async () => {
    setIsSavingPrompt(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/scope-readiness-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated((await response.json()) as ReadinessProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/scope-readiness/jobs`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked(); setIsEditingPrompt(false); setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Framing readiness could not be queued.')
    } finally { setIsStartingJob(false) }
  }

  const cancelJob = async () => {
    if (job === null) return
    setError(null)
    const response = await fetch(`/api/jobs/${job.id}/cancel`, { method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken } })
    if (!response.ok) setError(await readApiError(response))
    await onJobsChanged()
  }

  const saveFollowUp = async (answers: ScopeAnswer[], isEditing: boolean) => {
    if (job === null || (isEditing && job.scope_follow_up_answers_version === null)) return
    const response = await fetch(`/api/jobs/${job.id}/scope-follow-up-answers`, {
      method: isEditing ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
      body: JSON.stringify({ answers, ...(isEditing ? { base_version: job.scope_follow_up_answers_version } : {}) }),
    })
    if (!response.ok) throw new Error(await readApiError(response))
    await onJobsChanged()
  }

  const review = job?.scope_readiness_review
  return <>
    <section className="project-section">
      <SectionTitle help={usesFramingLanguage ? 'Advanced instructions used once to determine whether the next research cycle is framed well enough for a charter. Scientific unknowns and later literature-search decisions do not block readiness.' : 'Advanced instructions used once to determine whether the confirmed scope is explicit enough for a research charter and, if necessary, generate the only follow-up round.'}>{usesFramingLanguage ? 'Framing-readiness prompt' : 'Scope-readiness prompt'}</SectionTitle>
      {isPromptVisible && <div className="job-prompt-disclosure"><EditableField
        variant="multiline" isEditing={isEditingPrompt} canEdit={project.scope_readiness_prompt_is_editable}
        display={<pre className="question-detailing-prompt">{project.scope_readiness_prompt}</pre>}
        editor={<textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Scope-readiness prompt" />}
        onEdit={() => { setEditedPrompt(project.scope_readiness_prompt); setIsEditingPrompt(true) }} editLabel="Edit scope-readiness prompt"
        actions={<><button className="primary-button" type="button" onClick={() => void savePrompt()} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></>}
      /></div>}
      <div id={job === null ? undefined : `job-card-${job.id}`} ref={jobCardRef} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' ? <div className="completed-job-card"><span>{usesFramingLanguage ? 'Framing readiness review' : 'Scope readiness review'}</span><JobStatusLabel status="completed" /></div> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button></div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{usesFramingLanguage ? 'Review framing readiness' : 'Start scope readiness review'}</button>}
          {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This locks the exact first-round {usesFramingLanguage ? 'framing' : 'scope'} answer version, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
          {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>{usesFramingLanguage ? 'Framing-readiness job' : 'Scope-readiness job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    </section>

    {job?.status === 'completed' && review !== null && review !== undefined && <section id={`job-output-${job.id}`} ref={outputRef} className="project-section job-output-section readiness-section">
      <SectionTitle help={usesFramingLanguage ? 'This review checks only whether the next cycle has an understandable purpose and conceptual envelope. It does not require scientific unknowns or later search criteria to be settled.' : 'This review checks only whether the scope is operationally explicit enough for the research charter. It does not judge scientific truth or feasibility.'}>{usesFramingLanguage ? 'Framing readiness' : 'Scope readiness'}</SectionTitle>
      <div className={`readiness-summary ${review.ready_for_charter ? 'readiness-summary--ready' : ''}`}><div><p className="step-label">{review.ready_for_charter ? (usesFramingLanguage ? 'Ready for current-cycle charter' : 'Ready for research charter') : (usesFramingLanguage ? 'One final framing round' : 'One final clarification round')}</p><p>{review.assessment}</p></div><JobStatusLabel status="completed" /></div>
      {review.remaining_uncertainties.length > 0 && <div className="readiness-uncertainties"><p className="step-label">Remaining or accepted uncertainties</p><ul>{review.remaining_uncertainties.map(value => <li key={value}>{value}</li>)}</ul></div>}
      {!review.ready_for_charter && <ScopeQuestionnaire
        key={`${job.id}:${job.scope_follow_up_answers_version ?? 'open'}`}
        questions={review.follow_up_questions}
        savedAnswers={job.scope_follow_up_answers}
        canEdit={job.scope_follow_up_answers_is_editable}
        confirmLabel={usesFramingLanguage ? 'Confirm final framing answers' : 'Confirm final scope answers'}
        editLabel={usesFramingLanguage ? 'Edit final framing answers' : 'Edit final scope answers'}
        idPrefix={`follow-up-${job.id}`}
        onSave={saveFollowUp}
      />}
      {(review.ready_for_charter || job.scope_follow_up_answers !== null) && <p className="readiness-next">{usesFramingLanguage ? 'Project framing is complete. Current-cycle charter generation is the next workflow stage.' : 'Scope clarification is complete. Research-charter generation is the next workflow stage.'}</p>}
      <div className="output-provenance intent-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span></div>
    </section>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </>
}
