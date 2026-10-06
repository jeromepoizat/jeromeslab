import { useState, type RefObject } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type ScopeAnswer } from './JobQueue'
import { jobCostLabel } from './jobCost'
import { ChangeModelIcon, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'
import { promptVersionNumber } from './promptVersion'
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
  const [isReviewExpanded, setIsReviewExpanded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'
  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const promptVersion = promptVersionNumber(job?.prompt_template_version ?? project.scope_readiness_prompt_version)
  const usesPeptideDiscoveryLanguage = promptVersion >= 5
  const usesFramingLanguage = promptVersion >= 3

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
      setError(startError instanceof Error ? startError.message : 'The framing check could not be queued.')
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
  const followUpIsConfirmed = review?.ready_for_charter === false && job?.scope_follow_up_answers !== null
  const framingIsComplete = review?.ready_for_charter === true || followUpIsConfirmed
  const followUpNeedsAnswers = review?.ready_for_charter === false && !followUpIsConfirmed
  const showReviewDetails = followUpNeedsAnswers || isReviewExpanded
  return <>
    <section className="project-section">
      <SectionTitle help={usesPeptideDiscoveryLanguage ? 'Check once for a material contradiction or missing user-controlled decision. Broad exploration, scientific unknowns, and deferred peptide-design choices do not block the charter.' : usesFramingLanguage ? 'Determine once whether the next research investigation is framed well enough for a charter. Show prompt opens the advanced instructions; scientific unknowns and later search decisions do not block readiness.' : 'Determine whether the confirmed scope is explicit enough for a charter and, if necessary, generate the only follow-up round.'}>{usesPeptideDiscoveryLanguage ? 'Framing check' : usesFramingLanguage ? 'Framing readiness review' : 'Scope readiness review'}</SectionTitle>
      <div id={job === null ? undefined : `job-card-${job.id}`} ref={jobCardRef} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' ? <div className="completed-job-card"><span>{usesPeptideDiscoveryLanguage ? 'Framing check' : usesFramingLanguage ? 'Framing readiness review' : 'Scope readiness review'}</span><JobStatusLabel status="completed" /></div> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button></div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{usesPeptideDiscoveryLanguage ? 'Check the framing' : usesFramingLanguage ? 'Review framing readiness' : 'Start scope readiness review'}</button>}
          {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This locks the exact first-round {usesFramingLanguage ? 'framing' : 'scope'} answer version, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
          {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>{usesPeptideDiscoveryLanguage ? 'Framing-check job' : usesFramingLanguage ? 'Framing-readiness job' : 'Scope-readiness job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      <JobPromptDisclosure
        visible={isPromptVisible} isEditing={isEditingPrompt}
        canEdit={project.scope_readiness_prompt_is_editable && job === null}
        prompt={job?.prompt_snapshot ?? project.scope_readiness_prompt} editedPrompt={editedPrompt}
        isSaving={isSavingPrompt} ariaLabel="Scope-readiness prompt"
        editLabel="Edit scope-readiness prompt"
        onEditedPromptChange={setEditedPrompt}
        onEdit={() => { setEditedPrompt(project.scope_readiness_prompt); setIsEditingPrompt(true) }}
        onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()}
      />
      {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
      {job?.status === 'completed' && review !== null && review !== undefined && <section id={`job-output-${job.id}`} ref={outputRef} aria-label="Framing-readiness output" className="job-output-section readiness-section workflow-stage-output">
      <div className={`readiness-card ${framingIsComplete ? 'readiness-card--complete' : 'readiness-card--action-required'}`}>
        {framingIsComplete ? <button className="readiness-card-toggle" type="button" aria-expanded={showReviewDetails} onClick={() => setIsReviewExpanded(!isReviewExpanded)}>
          <span className="readiness-card-indicator" aria-hidden="true" />
          <strong>{followUpIsConfirmed ? 'Final framing answers confirmed' : 'Framing is sufficient'} <span>— Ready to create the {usesPeptideDiscoveryLanguage ? 'peptide-discovery charter' : 'research charter'}</span></strong>
          <svg className="readiness-card-chevron" aria-hidden="true" viewBox="0 0 16 10"><path d={showReviewDetails ? 'M2 8 8 2l6 6' : 'm2 2 6 6 6-6'} /></svg>
        </button> : <div className="readiness-card-heading">
          <span className="readiness-card-indicator" aria-hidden="true" />
          <strong>{usesFramingLanguage ? 'One final framing round is needed' : 'One final scope-clarification round is needed'}</strong>
        </div>}
        {showReviewDetails && <div className="readiness-card-details">
          <div className="readiness-assessment">
            <p className="step-label">{followUpIsConfirmed ? 'Original readiness assessment' : 'Readiness assessment'}</p>
            <p>{review.assessment}</p>
          </div>
          {review.remaining_uncertainties.length > 0 && <div className="readiness-carry-forward"><p className="step-label">{framingIsComplete ? 'Questions carried into the charter' : 'Questions to resolve or carry forward'}</p><ul>{review.remaining_uncertainties.map(value => <li key={value}>{value}</li>)}</ul></div>}
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
          <div className="output-provenance readiness-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(job)}</span></div>
        </div>}
      </div>
      </section>}
      {error !== null && <p className="setup-error" role="alert">{error}</p>}
    </section>
  </>
}
