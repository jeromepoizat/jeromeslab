import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { readApiError } from './apiClient'
import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'
import type { LLMSettings } from './LLMConfiguration'
import { ChangeModelIcon, EditableField, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'
import { promptVersionNumber } from './promptVersion'

export type CharterProject = {
  id: string
  research_charter_prompt: string
  research_charter_prompt_version: string
  research_charter_prompt_is_editable: boolean
}

type Props = {
  project: CharterProject
  jobs: Job[]
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  onProjectUpdated: (project: CharterProject) => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'

function CharterProvenance({ job }: { job: Job }) {
  return <div className="output-provenance">
    <span>{providerName(job.provider)} · {job.model}</span>
    <span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · Cost unavailable</span>
  </div>
}

function CharterOutput({ job, readOnly = false, setupToken, onJobsChanged, onEditingChange }: {
  job: Job
  readOnly?: boolean
  setupToken: string
  onJobsChanged: () => Promise<void>
  onEditingChange?: (editing: boolean) => void
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedMarkdown, setEditedMarkdown] = useState('')
  const [baseVersion, setBaseVersion] = useState<number | null>(null)
  const [isShowingOriginal, setIsShowingOriginal] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isApproving, setIsApproving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canEdit = !readOnly && job.charter_is_editable
  const isApproved = job.charter_approved_at !== null
  const usesPeptideDiscoveryLanguage = promptVersionNumber(job.prompt_template_version) >= 2

  const endEditing = () => {
    setIsEditing(false)
    onEditingChange?.(false)
  }

  const save = async () => {
    if (baseVersion === null || !canEdit) return
    setIsSaving(true)
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/research-charter-output`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ markdown: editedMarkdown, base_version: baseVersion }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
      endEditing()
      setIsShowingOriginal(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The charter could not be saved.')
    } finally { setIsSaving(false) }
  }

  const approve = async () => {
    if (job.effective_output_version === null || !canEdit) return
    setIsApproving(true)
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/research-charter-approval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ base_version: job.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (approvalError: unknown) {
      setError(approvalError instanceof Error ? approvalError.message : 'The charter could not be approved.')
    } finally { setIsApproving(false) }
  }

  return <>
    <EditableField
      variant="multiline"
      isEditing={isEditing && canEdit}
      canEdit={canEdit && !isShowingOriginal && !isApproving}
      display={<div className="markdown-output"><ReactMarkdown>{(isShowingOriginal ? job.original_output_markdown : job.effective_output_markdown) ?? ''}</ReactMarkdown></div>}
      editor={<textarea value={editedMarkdown} onChange={event => setEditedMarkdown(event.target.value)} aria-label={usesPeptideDiscoveryLanguage ? 'Peptide-discovery charter Markdown' : 'Research charter Markdown'} disabled={isSaving} />}
      onEdit={() => {
        setEditedMarkdown(job.effective_output_markdown ?? '')
        setBaseVersion(job.effective_output_version)
        setIsEditing(true)
        onEditingChange?.(true)
        setError(null)
      }}
      editLabel={usesPeptideDiscoveryLanguage ? 'Edit peptide-discovery charter' : 'Edit research charter'}
      sideActions={job.output_was_edited ? <button className="version-toggle-button" type="button" disabled={isApproving} onClick={() => setIsShowingOriginal(!isShowingOriginal)}>{isShowingOriginal ? 'Show edited version' : 'Show original output'}</button> : null}
      footer={<CharterProvenance job={job} />}
      actions={<>
        <button className="primary-button" type="button" disabled={isSaving || !editedMarkdown.trim()} onClick={() => void save()}>{isSaving ? 'Saving…' : 'Save edited version'}</button>
        <button className="text-button" type="button" disabled={isSaving} onClick={endEditing}>Cancel</button>
      </>}
    />
    {!readOnly && <div className="charter-approval">
      {isApproved && !isEditing ? <div><strong className="charter-approved">Charter approved</strong><p>Scientific-source investigation strategy is the next planned stage.</p></div> : <div><strong>Draft — review before approval</strong><p>{isEditing && isApproved ? 'Saving changes will require approval again.' : `Check that the charter reflects your intended ${usesPeptideDiscoveryLanguage ? 'peptide-discovery' : 'research'} investigation, then approve the version to use for the next stage.`}</p></div>}
      {!isApproved && canEdit && <button className="primary-button" type="button" disabled={isEditing || isShowingOriginal || isApproving} onClick={() => void approve()}>{isApproving ? 'Approving…' : 'Approve charter'}</button>}
    </div>}
    {isShowingOriginal && job.output_was_edited && <p className="charter-view-notice">Showing the original provider output. The edited version is the version used for approval.</p>}
    {readOnly && <details className="charter-used-prompt"><summary>Prompt used for this historical attempt</summary><pre className="question-detailing-prompt">{job.prompt_snapshot}</pre></details>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </>
}

export function ResearchCharterStage({ project, jobs, setupToken, llmSettings, nowMilliseconds, onProjectUpdated, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [isEditingOutput, setIsEditingOutput] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const orderedJobs = [...jobs].sort((left, right) => right.created_at.localeCompare(left.created_at))
  const job = orderedJobs[0] ?? null
  const completedJob = orderedJobs.find(attempt => attempt.status === 'completed') ?? null
  const previousAttempts = orderedJobs.filter(attempt => attempt.id !== job?.id && attempt.id !== completedJob?.id)
  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const canEditPrompt = project.research_charter_prompt_is_editable && job === null
  const promptVersion = promptVersionNumber(job?.prompt_template_version ?? project.research_charter_prompt_version)
  const usesPeptideDiscoveryLanguage = promptVersion >= 2

  const savePrompt = async () => {
    setIsSavingPrompt(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/research-charter-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated(await response.json() as CharterProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The charter prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/research-charter/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify(job?.status === 'completed' ? { previous_job_id: job.id, base_version: job.effective_output_version } : {}),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setIsConfirmingJob(false)
      setIsEditingPrompt(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Charter generation could not be queued.')
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

  return <>
    <section className="project-section">
      <SectionTitle help={usesPeptideDiscoveryLanguage ? 'Turn the original question and confirmed framing into a concise charter for this peptide-discovery evidence investigation. It preserves fixed premises, evidence objectives, accepted unknowns, and deferred design decisions.' : 'Consolidate your original question and confirmed framing into a concise charter for this research investigation. Review, edit if needed, and approve the draft before downstream work uses it.'}>{usesPeptideDiscoveryLanguage ? 'Peptide-discovery charter' : 'Research charter'}</SectionTitle>
      <div id={job === null ? undefined : `job-card-${job.id}`} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' && !isConfirmingJob ? <>
          <div className="completed-job-card"><span>{usesPeptideDiscoveryLanguage ? 'Peptide-discovery charter' : 'Charter generation'}</span><JobStatusLabel status="completed" /></div>
        </> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span>{activeJob === null && <button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button>}</div>
            {activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}
          </div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt || isEditingOutput} onClick={() => setIsConfirmingJob(true)}>{job === null ? usesPeptideDiscoveryLanguage ? 'Generate peptide-discovery charter' : 'Generate research charter' : 'Retry charter generation'}</button>}
          {isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>{completedJob === null ? 'This uses your exact confirmed framing, prompt, provider, and model to generate a draft for review.' : 'This makes a new provider call and creates a new draft for review and approval. Earlier attempts remain available below.'} The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured || isEditingPrompt || isEditingOutput} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
          {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>{usesPeptideDiscoveryLanguage ? 'Peptide-discovery charter job' : 'Research-charter job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      <JobPromptDisclosure
        visible={isPromptVisible} isEditing={isEditingPrompt} canEdit={canEditPrompt}
        prompt={job?.prompt_snapshot ?? project.research_charter_prompt} editedPrompt={editedPrompt}
        isSaving={isSavingPrompt} ariaLabel="Research-charter prompt"
        editLabel="Edit research-charter prompt"
        onEditedPromptChange={setEditedPrompt}
        onEdit={() => { setEditedPrompt(project.research_charter_prompt); setIsEditingPrompt(true) }}
        onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()}
      />
      {canStart && job !== null && <p className={job.error ? 'setup-error' : 'charter-view-notice'}>{job.error ? `Previous attempt: ${job.error}` : 'The previous attempt was cancelled.'}</p>}
      {error !== null && <p className="setup-error" role="alert">{error}</p>}
    </section>

    {completedJob !== null && <section id={`job-output-${completedJob.id}`} className="job-output-section charter-output-section">
      {activeJob !== null && <p className="charter-view-notice">Previous charter — a new draft is being generated.</p>}
      <CharterOutput key={completedJob.id} job={completedJob} setupToken={setupToken} onJobsChanged={onJobsChanged} onEditingChange={setIsEditingOutput} />
    </section>}

    {previousAttempts.length > 0 && <details className="charter-history">
      <summary>Previous charter attempts ({previousAttempts.length})</summary>
      {previousAttempts.map((attempt, index) => <details className="charter-attempt" key={attempt.id} id={`job-card-${attempt.id}`}>
        <summary><span>Attempt {orderedJobs.length - (orderedJobs.indexOf(attempt))} · {providerName(attempt.provider)} · {attempt.model}</span><JobStatusLabel status={attempt.status} /><JobElapsedTime job={attempt} nowMilliseconds={nowMilliseconds} /></summary>
        {attempt.status === 'completed' ? <section id={`job-output-${attempt.id}`} className="job-output-section">
          <p className="charter-view-notice">Previous attempt — read only. {attempt.charter_approved_at !== null ? 'This version was approved before it was superseded.' : 'Only the current charter can be approved.'}</p>
          <CharterOutput key={`${attempt.id}:${index}`} job={attempt} readOnly setupToken={setupToken} onJobsChanged={onJobsChanged} />
        </section> : <><p className={attempt.error ? 'setup-error' : 'charter-view-notice'}>{attempt.error ?? 'This attempt produced no charter.'}</p><details className="charter-used-prompt"><summary>Prompt used for this attempt</summary><pre className="question-detailing-prompt">{attempt.prompt_snapshot}</pre></details></>}
      </details>)}
    </details>}
  </>
}
