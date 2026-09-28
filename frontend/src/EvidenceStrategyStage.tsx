import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'
import { ChangeModelIcon, EditableField, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'

export type EvidenceStrategyProject = {
  id: string
  evidence_strategy_prompt: string
  evidence_strategy_prompt_version: string
  evidence_strategy_prompt_is_editable: boolean
}

type Props = {
  project: EvidenceStrategyProject
  job: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  onProjectUpdated: (project: EvidenceStrategyProject) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'

export function EvidenceStrategyStage({ project, job, setupToken, llmSettings, nowMilliseconds, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [isEditingOutput, setIsEditingOutput] = useState(false)
  const [editedMarkdown, setEditedMarkdown] = useState('')
  const [baseVersion, setBaseVersion] = useState<number | null>(null)
  const [isShowingOriginal, setIsShowingOriginal] = useState(false)
  const [isSavingOutput, setIsSavingOutput] = useState(false)
  const [isApproving, setIsApproving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const canEditOutput = job?.status === 'completed' && job.evidence_strategy_is_editable
  const isApproved = job?.evidence_strategy_approved_at !== null && job?.evidence_strategy_approved_at !== undefined

  const savePrompt = async () => {
    setIsSavingPrompt(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/evidence-strategy-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated(await response.json() as EvidenceStrategyProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The strategy prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/evidence-strategy/jobs`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked(); setIsEditingPrompt(false); setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'The strategy job could not be queued.')
    } finally { setIsStartingJob(false) }
  }

  const cancelJob = async () => {
    if (activeJob === null) return
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${activeJob.id}/cancel`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (cancelError: unknown) {
      setError(cancelError instanceof Error ? cancelError.message : 'The queued job could not be cancelled.')
    }
  }

  const saveOutput = async () => {
    if (job === null || baseVersion === null || !canEditOutput) return
    setIsSavingOutput(true); setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/evidence-strategy-output`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ markdown: editedMarkdown, base_version: baseVersion }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
      setIsEditingOutput(false); setIsShowingOriginal(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The edited strategy could not be saved.')
    } finally { setIsSavingOutput(false) }
  }

  const approve = async () => {
    if (job === null || job.effective_output_version === null || !canEditOutput) return
    setIsApproving(true); setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/evidence-strategy-approval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ base_version: job.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (approvalError: unknown) {
      setError(approvalError instanceof Error ? approvalError.message : 'The strategy could not be approved.')
    } finally { setIsApproving(false) }
  }

  return <section className="project-section">
    <SectionTitle help="Turn the approved charter, required evidence themes, and your confirmed search-scope answers into a reviewable investigation plan. It organizes evidence workstreams, source categories, and screening principles before source-specific queries are written.">Evidence-investigation strategy</SectionTitle>
    <div id={job === null ? undefined : `job-card-${job.id}`} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
      {job?.status === 'completed' ? <div className="completed-job-card"><span>Strategy generation</span><JobStatusLabel status="completed" /></div> : <>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span>{activeJob === null && <button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button>}</div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
        {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{job === null ? 'Generate evidence strategy' : 'Retry strategy generation'}</button>}
        {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the approved charter, required evidence themes, confirmed scope answers, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
        {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>Evidence-strategy job</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
      </>}
      <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
    </div>
    <JobPromptDisclosure
      visible={isPromptVisible} isEditing={isEditingPrompt}
      canEdit={project.evidence_strategy_prompt_is_editable && job === null}
      prompt={job?.prompt_snapshot ?? project.evidence_strategy_prompt} editedPrompt={editedPrompt}
      isSaving={isSavingPrompt} ariaLabel="Evidence-strategy prompt"
      editLabel="Edit evidence-strategy prompt"
      onEditedPromptChange={setEditedPrompt}
      onEdit={() => { setEditedPrompt(project.evidence_strategy_prompt); setIsEditingPrompt(true) }}
      onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()}
    />
    {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    {job?.status === 'completed' && <div id={`job-output-${job.id}`} className="job-output-section charter-output-section">
      <p className="evidence-themes-helper">Review the plan against every required evidence theme above and check that indirect findings stay labelled.</p>
      <EditableField
        variant="multiline" isEditing={isEditingOutput && canEditOutput}
        canEdit={canEditOutput && !isShowingOriginal && !isApproving}
        display={<div className="markdown-output"><ReactMarkdown>{(isShowingOriginal ? job.original_output_markdown : job.effective_output_markdown) ?? ''}</ReactMarkdown></div>}
        editor={<textarea value={editedMarkdown} onChange={event => setEditedMarkdown(event.target.value)} aria-label="Evidence strategy Markdown" disabled={isSavingOutput} />}
        onEdit={() => { setEditedMarkdown(job.effective_output_markdown ?? ''); setBaseVersion(job.effective_output_version); setIsEditingOutput(true); setError(null) }}
        editLabel="Edit evidence strategy"
        sideActions={job.output_was_edited ? <button className="version-toggle-button" type="button" disabled={isApproving} onClick={() => setIsShowingOriginal(!isShowingOriginal)}>{isShowingOriginal ? 'Show edited version' : 'Show original output'}</button> : null}
        footer={<div className="output-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span></div>}
        actions={<><button className="primary-button" type="button" disabled={isSavingOutput || !editedMarkdown.trim()} onClick={() => void saveOutput()}>{isSavingOutput ? 'Saving…' : 'Save edited version'}</button><button className="text-button" type="button" disabled={isSavingOutput} onClick={() => setIsEditingOutput(false)}>Cancel</button></>}
      />
      <div className="charter-approval">
        {isApproved && !isEditingOutput ? <div><strong className="charter-approved">Strategy approved</strong><p>This version is ready for later source-specific query planning.</p></div> : <div><strong>Draft — review before approval</strong><p>{isEditingOutput && isApproved ? 'Saving changes will require approval again.' : 'Check that the plan covers the charter themes and follows your confirmed scope answers, then approve the version to use next.'}</p></div>}
        {!isApproved && canEditOutput && <button className="primary-button" type="button" disabled={isEditingOutput || isShowingOriginal || isApproving} onClick={() => void approve()}>{isApproving ? 'Approving…' : 'Approve strategy'}</button>}
      </div>
      {isShowingOriginal && job.output_was_edited && <p className="charter-view-notice">Showing the original provider output. The edited version is the version used for approval.</p>}
    </div>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </section>
}
