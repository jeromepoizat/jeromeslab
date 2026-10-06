import { useState } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type ScopeAnswer } from './JobQueue'
import { jobCostLabel } from './jobCost'
import { ChangeModelIcon, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'
import { ScopeQuestionnaire } from './ScopeQuestionnaire'

export type EvidenceScopeProject = {
  id: string
  evidence_scope_prompt: string
  evidence_scope_prompt_version: string
  evidence_scope_prompt_is_editable: boolean
}

type Props = {
  project: EvidenceScopeProject
  job: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  onProjectUpdated: (project: EvidenceScopeProject) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'

export function EvidenceScopeStage({ project, job, setupToken, llmSettings, nowMilliseconds, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'

  const savePrompt = async () => {
    setIsSavingPrompt(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/evidence-scope-prompt`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated((await response.json()) as EvidenceScopeProject)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/evidence-scope/jobs`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked(); setIsEditingPrompt(false); setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'The scientific-source scope questionnaire could not be queued.')
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
    if (job === null || (isEditing && job.evidence_scope_answers_version === null)) return
    const response = await fetch(`/api/jobs/${job.id}/evidence-scope-answers`, {
      method: isEditing ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
      body: JSON.stringify({ answers, ...(isEditing ? { base_version: job.evidence_scope_answers_version } : {}) }),
    })
    if (!response.ok) throw new Error(await readApiError(response))
    await onJobsChanged()
  }

  return <section className="project-section">
    <SectionTitle help="The approved charter already fixes the investigation goals. This step maps those goals to mandatory evidence themes and asks only about retrieval and screening boundaries that still need your decision. It does not generate database queries yet.">Define the scientific-source scope</SectionTitle>
    <div id={job === null ? undefined : `job-card-${job.id}`} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
      {job?.status === 'completed' ? <div className="completed-job-card"><span>Scientific-source scope</span><JobStatusLabel status="completed" /></div> : <>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button></div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
        {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>Generate source-scope questionnaire</button>}
        {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the exact approved charter, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
        {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>Source-scope questionnaire job</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
      </>}
      <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
    </div>
    <JobPromptDisclosure
      visible={isPromptVisible} isEditing={isEditingPrompt}
      canEdit={project.evidence_scope_prompt_is_editable && job === null}
      prompt={job?.prompt_snapshot ?? project.evidence_scope_prompt} editedPrompt={editedPrompt}
      isSaving={isSavingPrompt} ariaLabel="Scientific-source scope prompt"
      editLabel="Edit scientific-source scope prompt"
      onEditedPromptChange={setEditedPrompt}
      onEdit={() => { setEditedPrompt(project.evidence_scope_prompt); setIsEditingPrompt(true) }}
      onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()}
    />
    {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    {job?.status === 'completed' && job.evidence_scope_questions !== null && <section id={`job-output-${job.id}`} aria-label="Scientific-source scope output" className="scope-section job-output-section workflow-stage-output">
      <p className="scope-introduction">{job.evidence_scope_questions.introduction}</p>
      <div className="evidence-themes" aria-label="Included evidence themes">
        <p className="step-label">Included from the approved charter</p>
        <p className="evidence-themes-helper">These themes are required to answer the current investigation and are not optional search filters.</p>
        {job.evidence_scope_questions.charter_evidence_themes.map(theme => <article className="evidence-theme" key={theme.id}><h3>{theme.label}</h3><p>{theme.purpose}</p><div className="evidence-domain-list">{theme.evidence_domains.map(domain => <span key={domain}>{domain}</span>)}</div>{theme.negative_evidence_required && <small>Includes relevant negative, null, contradictory, failed, or adverse evidence.</small>}</article>)}
      </div>
      {job.evidence_scope_questions.questions.length === 0 ? <div className="confirmed-intent confirmed-scope"><p className="step-label">No additional decision needed</p><p>The approved charter provides enough information to prepare the scientific-source investigation plan without adding retrieval restrictions.</p></div> : <>
        <p className="step-label evidence-decisions-label">Decisions for you</p>
        <ScopeQuestionnaire
          key={`${job.id}:${job.evidence_scope_answers_version ?? 'open'}`}
          questions={job.evidence_scope_questions.questions}
          savedAnswers={job.evidence_scope_answers}
          canEdit={job.evidence_scope_answers_is_editable}
          confirmLabel="Confirm source-scope answers"
          editLabel="Edit source-scope answers"
          idPrefix={`evidence-scope-${job.id}`}
          onSave={saveAnswers}
        />
      </>}
      <div className="output-provenance intent-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(job)}</span></div>
    </section>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </section>
}
