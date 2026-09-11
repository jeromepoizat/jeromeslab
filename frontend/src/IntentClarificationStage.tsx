import { useState, type RefObject } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'
import { ChangeModelIcon, EditableField, PromptToggleButton, SectionTitle } from './ProjectElements'

export type IntentProject = {
  id: string
  intent_clarification_prompt: string
  intent_clarification_prompt_version: string
  intent_clarification_prompt_is_editable: boolean
}

type Props = {
  project: IntentProject
  job: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  jobCardRef: RefObject<HTMLDivElement | null>
  outputRef: RefObject<HTMLElement | null>
  onProjectUpdated: (project: IntentProject) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

export function IntentClarificationStage({ project, job, setupToken, llmSettings, nowMilliseconds, jobCardRef, outputRef, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [primaryIntentId, setPrimaryIntentId] = useState('')
  const [secondaryIntentIds, setSecondaryIntentIds] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isEditingSelection, setIsEditingSelection] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const savePrompt = async () => {
    setIsSavingPrompt(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/intent-clarification-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated((await response.json()) as IntentProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The prompt could not be saved.')
    } finally {
      setIsSavingPrompt(false)
    }
  }

  const startJob = async () => {
    setIsStartingJob(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/intent-clarification/jobs`, {
        method: 'POST',
        headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked()
      setIsEditingPrompt(false)
      setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Research-direction clarification could not be queued.')
    } finally {
      setIsStartingJob(false)
    }
  }

  const cancelJob = async () => {
    if (job === null) return
    setError(null)
    const response = await fetch(`/api/jobs/${job.id}/cancel`, {
      method: 'POST',
      headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
    })
    if (!response.ok) setError(await readApiError(response))
    await onJobsChanged()
  }

  const submitSelection = async () => {
    if (job === null || primaryIntentId === '' || (isEditingSelection && job.intent_selection_version === null)) return
    setIsSubmitting(true)
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/intent-selection`, {
        method: isEditingSelection ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({
          primary_intent_id: primaryIntentId,
          secondary_intent_ids: secondaryIntentIds,
          note,
          ...(isEditingSelection ? { base_version: job.intent_selection_version } : {}),
        }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setIsEditingSelection(false)
      await onJobsChanged()
    } catch (submitError: unknown) {
      setError(submitError instanceof Error ? submitError.message : 'The research direction could not be saved.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'
  const usesEvidenceLedLanguage = job?.prompt_template_version === '2' || (job === null && project.intent_clarification_prompt_version === '2')
  const stageLabel = usesEvidenceLedLanguage ? 'Research direction' : 'Intent clarification'
  const primaryLabel = usesEvidenceLedLanguage ? 'Current objective' : 'Primary'
  const primaryControlLabel = usesEvidenceLedLanguage ? 'Current' : 'Primary'
  const secondaryLabel = usesEvidenceLedLanguage ? 'Later / parallel' : 'Also include'
  const confirmedSecondaryLabel = usesEvidenceLedLanguage ? 'Later or parallel goals' : 'Also included'
  const selectedPrimary = job?.intent_questions?.options.find(option => option.id === job.intent_selection?.primary_intent_id)
  const selectedSecondary = job?.intent_questions?.options.filter(option => job.intent_selection?.secondary_intent_ids.includes(option.id)) ?? []

  return <>
    <section className="project-section">
      <SectionTitle help={usesEvidenceLedLanguage ? 'Advanced instructions used to identify a current research objective and relevant later or parallel goals from the original question.' : 'Advanced instructions used to identify distinct research purposes that could be intended by the original question.'}>{usesEvidenceLedLanguage ? 'Research-direction prompt' : 'Intent-clarification prompt'}</SectionTitle>
      {isPromptVisible && <div className="job-prompt-disclosure">
        <EditableField
          variant="multiline"
          isEditing={isEditingPrompt}
          canEdit={project.intent_clarification_prompt_is_editable}
          display={<pre className="question-detailing-prompt">{project.intent_clarification_prompt}</pre>}
          editor={<textarea value={editedPrompt} onChange={event => setEditedPrompt(event.target.value)} aria-label="Intent-clarification prompt" />}
          onEdit={() => { setEditedPrompt(project.intent_clarification_prompt); setIsEditingPrompt(true) }}
          editLabel="Edit intent-clarification prompt"
          actions={<><button className="primary-button" type="button" onClick={() => void savePrompt()} disabled={isSavingPrompt}>{isSavingPrompt ? 'Saving…' : 'Save prompt'}</button><button className="text-button" type="button" onClick={() => setIsEditingPrompt(false)} disabled={isSavingPrompt}>Cancel</button></>}
        />
      </div>}
      <div id={job === null ? undefined : `job-card-${job.id}`} ref={jobCardRef} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' ? <div className="completed-job-card"><span>{stageLabel}</span><JobStatusLabel status="completed" /></div> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label={llmSettings.configured ? 'Change model for future jobs' : 'Configure a model'}><ChangeModelIcon /></button></div>{activeJob !== null
            ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong>
            : llmSettings.configured
              ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong>
              : <strong>Not configured</strong>}</div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{usesEvidenceLedLanguage ? 'Clarify research direction' : 'Start intent clarification'}</button>}
          {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline">
            <p>This locks the exact scientific question, prompt, provider, and model shown here. The job can be cancelled only while it remains queued.</p>
            <div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div>
          </div>}
          {activeJob !== null && <div className="active-job-summary">
            <div className="active-job-heading"><strong>{usesEvidenceLedLanguage ? 'Research-direction job' : 'Intent-clarification job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>
            {activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}
            {activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}
          </div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    </section>

    {job?.status === 'completed' && job.intent_questions !== null && <section id={`job-output-${job.id}`} ref={outputRef} className="project-section intent-section job-output-section">
      <SectionTitle help={usesEvidenceLedLanguage ? 'Choose what the next research cycle should accomplish now, retain any later or parallel goals, and add context the generated choices do not capture.' : 'Choose one primary purpose, optionally retain related secondary purposes, and add any qualification the generated choices do not capture.'}>{usesEvidenceLedLanguage ? 'Research direction' : 'Research intent'}</SectionTitle>
      <div className="intent-introduction"><h3>{job.intent_questions.question}</h3><p>{job.intent_questions.explanation}</p></div>
      {job.intent_selection === null || isEditingSelection ? <form className="intent-form" onSubmit={event => { event.preventDefault(); void submitSelection() }}>
        <div className="intent-choice-headings" aria-hidden="true"><span>Research direction</span><span>{primaryLabel}</span><span>{secondaryLabel}</span></div>
        <div className="intent-options">
          {job.intent_questions.options.map(option => <div className={`intent-option ${primaryIntentId === option.id ? 'intent-option--primary' : ''}`} key={option.id}>
            <label className="intent-option-copy" htmlFor={`primary-${option.id}`}><strong>{option.label}</strong><span>{option.description}</span></label>
            <label className="intent-control"><input id={`primary-${option.id}`} type="radio" name="primary-intent" checked={primaryIntentId === option.id} onChange={() => { setPrimaryIntentId(option.id); setSecondaryIntentIds(current => current.filter(id => id !== option.id)) }} /><span>{primaryControlLabel}</span></label>
            <label className="intent-control"><input type="checkbox" checked={secondaryIntentIds.includes(option.id)} disabled={primaryIntentId === option.id} onChange={event => setSecondaryIntentIds(current => event.target.checked ? [...current, option.id] : current.filter(id => id !== option.id))} /><span>{secondaryLabel}</span></label>
          </div>)}
        </div>
        <label className="intent-note"><span>Optional note or custom qualification</span><textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add context that the suggested choices do not fully capture…" /></label>
        <div className="intent-submit"><button className="primary-button" type="submit" disabled={primaryIntentId === '' || isSubmitting}>{isSubmitting ? 'Saving…' : isEditingSelection ? (usesEvidenceLedLanguage ? 'Save edited direction' : 'Save edited intent') : (usesEvidenceLedLanguage ? 'Confirm research direction' : 'Confirm research intent')}</button>{isEditingSelection && <button className="text-button" type="button" disabled={isSubmitting} onClick={() => setIsEditingSelection(false)}>Cancel</button>}<span>{isEditingSelection ? 'The previous confirmation remains preserved in history.' : 'Your confirmed decision will be preserved as workflow input.'}</span></div>
      </form> : <div className="confirmed-intent">
        {job.intent_selection_is_editable && <button className="intent-edit-button" type="button" title={usesEvidenceLedLanguage ? 'Edit research direction' : 'Edit research intent'} aria-label={usesEvidenceLedLanguage ? 'Edit research direction' : 'Edit research intent'} onClick={() => { setPrimaryIntentId(job.intent_selection?.primary_intent_id ?? ''); setSecondaryIntentIds(job.intent_selection?.secondary_intent_ids ?? []); setNote(job.intent_selection?.note ?? ''); setIsEditingSelection(true) }}>✎</button>}
        <p className="step-label">{primaryLabel}</p>
        <h3>{selectedPrimary?.label ?? job.intent_selection.primary_intent_id}</h3>
        {selectedPrimary && <p>{selectedPrimary.description}</p>}
        {selectedSecondary.length > 0 && <><p className="step-label confirmed-intent-secondary-label">{confirmedSecondaryLabel}</p><ul>{selectedSecondary.map(option => <li key={option.id}><strong>{option.label}</strong> — {option.description}</li>)}</ul></>}
        {job.intent_selection.note && <><p className="step-label confirmed-intent-secondary-label">User note</p><p className="intent-saved-note">{job.intent_selection.note}</p></>}
        <div className="intent-next-step"><JobStatusLabel status="completed" /></div>
      </div>}
      <div className="output-provenance intent-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span></div>
    </section>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </>
}
