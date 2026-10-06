import { useState, type RefObject } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type ScopeAnswer } from './JobQueue'
import { jobCostLabel } from './jobCost'
import { ChangeModelIcon, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'
import { promptVersionNumber } from './promptVersion'
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
  const promptVersion = promptVersionNumber(job?.prompt_template_version ?? project.scope_clarification_prompt_version)
  const usesPeptideDiscoveryLanguage = promptVersion >= 5
  const usesProjectFramingLanguage = promptVersion >= 3

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
      <SectionTitle help={usesPeptideDiscoveryLanguage ? 'The AI checks whether it still needs any decisions from you before writing the investigation charter—for example, whether a named target, peptide, application, or constraint is fixed or should remain open to evidence. It asks up to five questions only when necessary. Scientific unknowns and search or screening rules are handled later.' : usesProjectFramingLanguage ? 'Answer the project-level decisions needed for the next investigation. Show prompt opens the advanced generation instructions; literature search and screening scope are decided later.' : 'Resolve the material project boundaries. Show prompt opens the advanced instructions used to generate the questions.'}>{usesPeptideDiscoveryLanguage ? 'Clarify assumptions and boundaries' : usesProjectFramingLanguage ? 'Frame the research investigation' : 'Clarify the research scope'}</SectionTitle>
      <div id={job === null ? undefined : `job-card-${job.id}`} ref={jobCardRef} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
        {job?.status === 'completed' ? <div className="completed-job-card"><span>{usesPeptideDiscoveryLanguage ? 'Assumptions and boundaries' : usesProjectFramingLanguage ? 'Project framing' : 'Scope clarification'}</span><JobStatusLabel status="completed" /></div> : <>
          <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title={llmSettings.configured ? 'Change model' : 'Configure model'} aria-label="Change model for future jobs"><ChangeModelIcon /></button></div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
          {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{usesPeptideDiscoveryLanguage ? 'Check for needed clarifications' : usesProjectFramingLanguage ? 'Frame this research investigation' : 'Start scope clarification'}</button>}
          {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the original question, effective {usesPeptideDiscoveryLanguage ? 'research goal' : usesProjectFramingLanguage ? 'research direction' : 'research intent'}, prompt, provider, and model. The job can be cancelled only while queued.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
          {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>{usesPeptideDiscoveryLanguage ? 'Clarification-question job' : usesProjectFramingLanguage ? 'Project-framing job' : 'Scope-clarification job'}</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
        </>}
        <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
      </div>
      <JobPromptDisclosure
        visible={isPromptVisible} isEditing={isEditingPrompt}
        canEdit={project.scope_clarification_prompt_is_editable && job === null}
        prompt={job?.prompt_snapshot ?? project.scope_clarification_prompt} editedPrompt={editedPrompt}
        isSaving={isSavingPrompt} ariaLabel="Scope-clarification prompt"
        editLabel="Edit scope-clarification prompt"
        onEditedPromptChange={setEditedPrompt}
        onEdit={() => { setEditedPrompt(project.scope_clarification_prompt); setIsEditingPrompt(true) }}
        onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()}
      />
      {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
      {job?.status === 'completed' && job.scope_questions !== null && <section id={`job-output-${job.id}`} ref={outputRef} aria-label="Project-framing output" className="scope-section job-output-section workflow-stage-output">
      <p className="scope-introduction">{job.scope_questions.introduction}</p>
      {job.scope_questions.questions.length === 0 ? <div className="confirmed-intent confirmed-scope"><p className="step-label">No clarification needed</p><p>Your research goal already provides enough information to write the investigation charter. No additional assumptions or boundaries need your decision.</p></div> : <ScopeQuestionnaire
        key={`${job.id}:${job.scope_answers_version ?? 'open'}`}
        questions={job.scope_questions.questions}
        savedAnswers={job.scope_answers}
        canEdit={job.scope_answers_is_editable}
        confirmLabel={usesPeptideDiscoveryLanguage ? 'Confirm clarification answers' : usesProjectFramingLanguage ? 'Confirm framing answers' : 'Confirm scope answers'}
        editLabel={usesPeptideDiscoveryLanguage ? 'Edit clarification answers' : usesProjectFramingLanguage ? 'Edit framing answers' : 'Edit scope answers'}
        idPrefix={`scope-${job.id}`}
        onSave={saveAnswers}
      />}
      <div className="output-provenance intent-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(job)}</span></div>
      </section>}
      {error !== null && <p className="setup-error" role="alert">{error}</p>}
    </section>
  </>
}
