import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job, type SourceQuery } from './JobQueue'
import { jobCostLabel } from './jobCost'
import { ChangeModelIcon, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'
import { RetrievalSummary, type RetrievalSummaryData } from './RetrievalSummary'

type Project = {
  id: string
  source_queries_prompt: string
  source_queries_prompt_version: string
  source_queries_prompt_is_editable: boolean
}

type Props = {
  project: Project
  job: Job | null
  retrievalJob: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  onProjectUpdated: (project: Project) => void
  onProjectLocked: () => void
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

const providerName = (provider: Job['provider']) => provider === 'openai' ? 'OpenAI' : 'Anthropic'

export function SourceQueriesStage({ project, job, retrievalJob, setupToken, llmSettings, nowMilliseconds, onProjectUpdated, onProjectLocked, onJobsChanged, onOpenSettings }: Props) {
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingPrompt, setIsEditingPrompt] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isSavingPrompt, setIsSavingPrompt] = useState(false)
  const [note, setNote] = useState('')
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [isStartingJob, setIsStartingJob] = useState(false)
  const [draft, setDraft] = useState<SourceQuery[]>(() => job?.source_queries?.queries ?? [])
  const [expandedIds, setExpandedIds] = useState<string[]>([])
  const [isShowingOriginal, setIsShowingOriginal] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isApproving, setIsApproving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retrievalSummary, setRetrievalSummary] = useState<RetrievalSummaryData | null>(null)
  const pollTick = Math.floor(nowMilliseconds / 3000)
  const retrievalJobId = retrievalJob?.id
  const retrievalStatus = retrievalJob?.status
  const retrievalPollTick = retrievalStatus === 'completed' ? 0 : pollTick

  useEffect(() => {
    if (!retrievalJobId) return
    const controller = new AbortController()
    void fetch(`/api/jobs/${retrievalJobId}/retrieval-summary`, { signal: controller.signal })
      .then(response => response.ok ? response.json() as Promise<RetrievalSummaryData> : Promise.reject(new Error('Search progress unavailable.')))
      .then(setRetrievalSummary)
      .catch(() => { /* Queue polling will retry; do not obscure saved results. */ })
    return () => controller.abort()
  }, [retrievalJobId, retrievalStatus, retrievalPollTick])

  const activeJob = job !== null && (job.status === 'pending' || job.status === 'awaiting_response') ? job : null
  const canStart = job === null || job.status === 'failed' || job.status === 'cancelled'
  const canEdit = job?.status === 'completed' && job.source_queries_is_editable && !isShowingOriginal
  const saved = job?.source_queries?.queries ?? []
  const isDirty = JSON.stringify(draft) !== JSON.stringify(saved)
  const displayed = isShowingOriginal ? job?.original_source_queries?.queries ?? [] : draft
  const requiredThemes = new Set(saved.flatMap(query => query.theme_ids))
  const includedThemes = new Set(draft.filter(query => query.included).flatMap(query => query.theme_ids))
  const coverageComplete = requiredThemes.size > 0 && [...requiredThemes].every(theme => includedThemes.has(theme))
  const isApproved = job?.source_queries_approved_at != null
  let savedNote = ''
  try {
    if (job?.workflow_input_snapshot_json) savedNote = (JSON.parse(job.workflow_input_snapshot_json) as { user_note?: string }).user_note ?? ''
  } catch { /* A malformed historical snapshot must not break the page. */ }

  const requestHeaders = { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken }

  const savePrompt = async () => {
    setIsSavingPrompt(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/source-queries-prompt`, {
        method: 'PATCH', headers: requestHeaders, body: JSON.stringify({ prompt: editedPrompt }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectUpdated(await response.json() as Project)
      setIsEditingPrompt(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The query prompt could not be saved.')
    } finally { setIsSavingPrompt(false) }
  }

  const startJob = async () => {
    setIsStartingJob(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${project.id}/source-queries/jobs`, {
        method: 'POST', headers: requestHeaders, body: JSON.stringify({ note: job === null ? note : savedNote }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      onProjectLocked(); setIsEditingPrompt(false); setIsConfirmingJob(false)
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'The query job could not be queued.')
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

  const updateQuery = (id: string, update: Partial<SourceQuery>) => {
    setDraft(previous => previous.map(query => query.id === id ? { ...query, ...update } : query))
  }

  const saveQueries = async () => {
    if (job?.effective_output_version == null) return
    setIsSaving(true); setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/source-queries`, {
        method: 'PATCH', headers: requestHeaders,
        body: JSON.stringify({ queries: draft, base_version: job.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The query edits could not be saved.')
    } finally { setIsSaving(false) }
  }

  const approve = async () => {
    if (job?.effective_output_version == null) return
    setIsApproving(true); setError(null)
    try {
      const response = await fetch(`/api/jobs/${job.id}/source-queries-approval`, {
        method: 'POST', headers: requestHeaders,
        body: JSON.stringify({ base_version: job.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (approvalError: unknown) {
      setError(approvalError instanceof Error ? approvalError.message : 'The queries could not be approved and queued.')
    } finally { setIsApproving(false) }
  }

  const retryRetrieval = async () => {
    if (retrievalJob === null) return
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${retrievalJob.id}/search-runs/retry`, {
        method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken },
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (retryError: unknown) {
      setError(retryError instanceof Error ? retryError.message : 'The search could not be retried.')
    }
  }

  return <>
  <section className="project-section">
    <SectionTitle help="Draft purpose-labelled Europe PMC publication queries from the approved investigation plan. Review, edit, include, or exclude each suggestion. Approval locks the exact selected version and queues its retrieval; drafting alone never searches.">Scientific-source queries</SectionTitle>
    {job === null && <label className="intent-note query-generation-note"><span>Optional note for query generation</span><textarea value={note} onChange={event => setNote(event.target.value)} maxLength={10000} placeholder="Add a specific concept to include or exclude, without changing the approved investigation scope." disabled={isStartingJob} /></label>}
    {job !== null && savedNote && <div className="query-saved-note"><strong>Note used for generation</strong><p>{savedNote}</p>{canStart && <small>A retry reuses this exact note and the original input snapshot.</small>}</div>}
    <div id={job === null ? undefined : `job-card-${job.id}`} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${activeJob !== null ? 'llm-job-provider--active' : ''}`}>
      {job?.status === 'completed' ? <div className="completed-job-card"><span>Europe PMC query drafting</span><JobStatusLabel status="completed" /></div> : <>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span>{activeJob === null && <button className="model-change-button" type="button" onClick={onOpenSettings} title="Change model" aria-label="Change model for future jobs"><ChangeModelIcon /></button>}</div>{activeJob !== null ? <strong>{providerName(activeJob.provider)} · {activeJob.model}</strong> : llmSettings.configured ? <strong>{llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · {llmSettings.selected_model}</strong> : <strong>Not configured</strong>}</div>
        {canStart && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!llmSettings.configured || isEditingPrompt} onClick={() => setIsConfirmingJob(true)}>{job === null ? 'Draft Europe PMC queries' : 'Retry query drafting'}</button>}
        {canStart && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the approved charter, scope, strategy, your note, prompt, provider, and model. It generates proposed queries only; it will not run a search.</p><div><button className="primary-button" type="button" disabled={isStartingJob || !llmSettings.configured} onClick={() => void startJob()}>{isStartingJob ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" disabled={isStartingJob} onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
        {activeJob !== null && <div className="active-job-summary"><div className="active-job-heading"><strong>Query-drafting job</strong><div><JobStatusLabel status={activeJob.status} /><JobElapsedTime job={activeJob} nowMilliseconds={nowMilliseconds} /></div></div>{activeJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelJob()}>Cancel queued job</button>}{activeJob.status === 'awaiting_response' && <p>The request may already have reached {providerName(activeJob.provider)}, so cancellation is disabled.</p>}</div>}
      </>}
      <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingPrompt(false); setIsPromptVisible(!isPromptVisible) }} />
    </div>
    <JobPromptDisclosure visible={isPromptVisible} isEditing={isEditingPrompt} canEdit={project.source_queries_prompt_is_editable && job === null} prompt={job?.prompt_snapshot ?? project.source_queries_prompt} editedPrompt={editedPrompt} isSaving={isSavingPrompt} ariaLabel="Europe PMC query-drafting prompt" editLabel="Edit query-drafting prompt" onEditedPromptChange={setEditedPrompt} onEdit={() => { setEditedPrompt(project.source_queries_prompt); setIsEditingPrompt(true) }} onCancel={() => setIsEditingPrompt(false)} onSave={() => void savePrompt()} />
    {canStart && job?.error && <p className="setup-error">Previous attempt: {job.error}</p>}
    {job?.status === 'completed' && <div id={`job-output-${job.id}`} className="job-output-section query-output-section">
      <p className="evidence-themes-helper">Review these untested query drafts before searching. Uncheck suggestions you do not want to run. Changes are saved as a new version.</p>
      {job.output_was_edited && <button className="text-button" type="button" onClick={() => setIsShowingOriginal(!isShowingOriginal)}>{isShowingOriginal ? 'Show edited version' : 'Show original suggestions'}</button>}
      <div className="query-cards">{displayed.map(query => <article className={`query-card ${query.included ? '' : 'query-card--excluded'}`} key={query.id}>
        <div className="query-card-heading"><label><input type="checkbox" checked={query.included} disabled={!canEdit || isSaving || isApproving} onChange={event => updateQuery(query.id, { included: event.target.checked })} aria-label={`Include ${query.title} in the run`} /><span><strong>{query.title}</strong><small>{query.description}</small></span></label><button className="text-button" type="button" aria-expanded={expandedIds.includes(query.id)} onClick={() => setExpandedIds(previous => previous.includes(query.id) ? previous.filter(id => id !== query.id) : [...previous, query.id])}>{expandedIds.includes(query.id) ? 'Hide query' : 'View / edit query'}</button></div>
        {expandedIds.includes(query.id) && <div className="query-card-detail"><label>Title<input type="text" value={query.title} maxLength={160} disabled={!canEdit} onChange={event => updateQuery(query.id, { title: event.target.value })} /></label><label>Short description<textarea value={query.description} maxLength={600} disabled={!canEdit} onChange={event => updateQuery(query.id, { description: event.target.value })} /></label><label>Europe PMC query<textarea className="query-text" value={query.query_text} maxLength={8000} spellCheck={false} disabled={!canEdit} onChange={event => updateQuery(query.id, { query_text: event.target.value })} /></label><small>Addresses themes: {query.theme_ids.join(', ')}. Syntax and results have not been tested yet.</small></div>}
      </article>)}</div>
      {!coverageComplete && !isShowingOriginal && <p className="setup-error" role="status">The included queries do not cover every mandatory theme. Restore coverage before approval.</p>}
      <div className="output-provenance"><span>{providerName(job.provider)} · {job.model}</span><span>{job.total_tokens !== null ? `${job.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {job.duration_ms !== null ? `${(job.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(job)}</span></div>
      {isDirty && !isShowingOriginal && <div className="query-actions"><button className="primary-button" type="button" disabled={!canEdit || isSaving} onClick={() => void saveQueries()}>{isSaving ? 'Saving…' : 'Save edited version'}</button><button className="text-button" type="button" disabled={isSaving} onClick={() => setDraft(saved)}>Discard unsaved changes</button></div>}
      <div className="charter-approval">{isApproved && retrievalJob !== null && !isDirty ? <div><strong className="charter-approved">Queries approved</strong><p>The exact approved version was queued for Europe PMC retrieval.</p></div> : <div><strong>Draft — review before retrieval</strong><p>Check wording, included queries, and coverage. Approval immediately queues the selected searches; source requests begin when the job reaches the front of the queue.</p></div>}{retrievalJob === null && <button className="primary-button" type="button" disabled={!canEdit || isDirty || !coverageComplete || isApproving} onClick={() => void approve()}>{isApproving ? 'Approving and queueing…' : 'Approve queries and run them'}</button>}</div>
    </div>}
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </section>
  {retrievalJob !== null && <section id={`job-output-${retrievalJob.id}`} className="project-section">
    <SectionTitle help="Summarizes the saved Europe PMC search results. Counts describe query hits, saved records, and source IDs; they are not yet screened evidence or a count of unique publications.">Retrieval overview</SectionTitle>
    <RetrievalSummary job={retrievalJob} summary={retrievalSummary} expectedQueries={saved.filter(query => query.included).length} nowMilliseconds={nowMilliseconds} onRetry={() => void retryRetrieval()} />
  </section>}
  </>
}
