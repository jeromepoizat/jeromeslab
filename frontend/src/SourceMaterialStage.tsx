import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import { SectionTitle } from './ProjectElements'

type Resource = {
  kind: string; status: string; error: string | null; raw_byte_size: number | null
  details: { recovery_provider?: string; provider?: string; format?: string; license_statements?: string[]; file_count?: number; reported_count?: number; inventory_partial?: boolean
    files: { name: string; bytes: number }[]; links: { Target?: { Title?: string; Identifier?: { ID?: string } } }[] }
}
type CollectionRun = {
  id: string; status: string; stop_requested: boolean; total: number; processed: number; abstract_only: number; retrying: boolean; remaining_resources: number; full_text_saved: number; fallback_eligible: number
  created_at: string; completed_at: string | null; counts: Record<string, number>; offset: number; phase?: string | null
  jobs: { id: string; status: string; error: string | null }[]
  records: { id: string; title: string; source: string; source_record_id: string; resources: Resource[] }[]
}
type CollectionState = { run: CollectionRun | null; selection_sha256: string }
const labels: Record<string, string> = { metadata: 'Metadata', full_text: 'Europe PMC full text', full_text_fallback: 'Fallback full text', supplements: 'Supplements', data_links: 'Linked-data inventory' }
const statuses: Record<string, string> = { saved: 'Saved', recovered: 'Full text recovered through fallback · No primary retry needed', failed: 'Failed · Retryable', blocked: 'Waiting on prerequisite', unavailable: 'Unavailable through this route · Not retried', unsupported: 'No supported route · Availability unknown', needs_review: 'Needs review · Not confirmed unavailable', skipped_limit: 'Size limit · Unresolved', not_applicable: 'Not applicable', pending: 'Waiting' }
const outcomes = [
  { status: 'recovered', title: 'Primary failures covered by saved fallback text', help: 'Verified full text is already available. The primary failure stays in history, but is not retried or counted as missing text.' },
  { status: 'failed', title: 'Retryable failures', help: 'Network, rate-limit or server errors. Retrying may succeed; these are not confirmed unavailable.' },
  { status: 'unavailable', title: 'Unavailable through checked routes', help: 'The enabled source reports no access or no text. These resources are skipped on retry, not declared unavailable everywhere.' },
  { status: 'unsupported', title: 'No supported route', help: 'No enabled adapter or usable identifier. Availability elsewhere is unknown; repeating the same request cannot help.' },
  { status: 'needs_review', title: 'Needs review', help: 'Identity, format or version could not be verified. Not silently discarded, not confirmed unavailable, and not blindly retried.' },
  { status: 'blocked', title: 'Waiting on prerequisite', help: 'Another resource must succeed first. Retried with unfinished work, not counted as an unavailable download.' },
  { status: 'skipped_limit', title: 'Size-limited resources', help: 'Not downloaded under the current safety limit. Unresolved, not unavailable; the same-limit retry is skipped.' },
]

export function SourceMaterialStage({ projectId, filterRunId, setupToken }: {
  projectId: string; filterRunId: string; setupToken: string
}) {
  const [data, setData] = useState<CollectionState | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [offset, setOffset] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const path = `/api/projects/${projectId}/source-material`
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const response = await fetch(`${path}?filter_run_id=${filterRunId}&offset=${offset}`, {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        })
        if (!response.ok) throw new Error(await readApiError(response))
        const state = await response.json() as CollectionState
        if (!controller.signal.aborted) { setData(state); setError('') }
        if (!controller.signal.aborted && (state.run?.status === 'pending' || state.run?.status === 'running')) timer = setTimeout(() => void load(), 3000)
      } catch (cause) {
        if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : 'Could not load collection progress.'); timer = setTimeout(() => void load(), 5000) }
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [path, filterRunId, offset, refresh])
  const run = data?.run
  const active = run?.status === 'running' || run?.status === 'pending'
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [active])

  async function action(command?: string) {
    setWorking(true)
    setError('')
    try {
      const response = await fetch(command ? `${path}/${run?.id}/${command}` : path, {
        method: 'POST', signal: AbortSignal.timeout(20000),
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: command ? undefined : JSON.stringify({ filter_run_id: filterRunId, expected_selection_sha256: data?.selection_sha256 }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setData(await response.json() as CollectionState)
      setOffset(0)
      setRefresh(value => value + 1)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not update collection.') }
    finally { setWorking(false) }
  }
  const count = (kind: string, status = 'saved') => run?.counts[`${kind}:${status}`] ?? 0
  const failures = run ? Object.entries(run.counts).reduce((sum, [key, value]) => sum + (key.endsWith(':failed') ? value : 0), 0) : 0
  const blocked = run ? Object.entries(run.counts).reduce((sum, [key, value]) => sum + (key.endsWith(':blocked') ? value : 0), 0) : 0
  const remaining = run ? Object.entries(run.counts).reduce((sum, [key, value]) => sum + (key.endsWith(':pending') ? value : 0), 0) : 0
  const totalFor = (status: string) => run ? Object.entries(run.counts).reduce((sum, [key, value]) => sum + (key.endsWith(`:${status}`) ? value : 0), 0) : 0
  const unresolved = remaining + failures + blocked + totalFor('needs_review') + totalFor('skipped_limit')
  const elapsed = run ? Math.max(0, Math.floor(((run.completed_at ? Date.parse(run.completed_at) : now) - Date.parse(run.created_at)) / 1000)) : 0

  return <section className="project-section source-material-stage">
    <SectionTitle help="Collect available source material for the exact retained record list. Europe PMC metadata and available full-text XML are saved locally; missing text can use official PMC BioC or bioRxiv/medRxiv JATS fallbacks. Preprint versions must match the retained record. Declared Europe PMC supplements are downloaded as bounded ZIP archives. Linked-data entries are inventoried, not recursively downloaded. XML is capped at 20 MB, supplements at 50 MB compressed / 200 MB declared expanded size and 1,000 files, and metadata/link responses at 2 MB. No arbitrary publisher scraping, PDF download or paywall bypass is performed. Missing text does not exclude a record or establish that no full text exists elsewhere. No LLM call, quality assessment, or evidence extraction is performed here.">Collect source material</SectionTitle>
    {!data && !error && <p>Loading source collection…</p>}
    {data && !run && <div className="llm-job-provider source-material-job-card"><div><div className="llm-job-model-label"><span>SOURCE FOR THIS JOB</span></div><strong>Europe PMC · No LLM usage</strong></div><button className="primary-button" type="button" disabled={working} onClick={() => void action()}>Collect source material</button></div>}
    {run && <>
      {run.jobs.map(job => <span key={job.id} id={`job-output-${job.id}`}><span id={`job-card-${job.id}`} /></span>)}
      <div className="llm-job-provider source-material-job-card"><strong>Europe PMC source collection</strong><span className={`job-status job-status--${run.status === 'completed' && !unresolved ? 'completed' : 'pending'}`}><span aria-hidden="true" />{run.stop_requested && active ? 'Pausing after current request' : run.status === 'completed' ? `Collection finished${unresolved ? ' · Unresolved resources remain' : ''}` : run.status === 'paused' ? 'Paused' : run.status === 'pending' ? 'Queued' : 'Collecting'}</span><span title="Elapsed wall-clock time since collection was first queued, including pauses">{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</span></div>
      <div className="relevance-batch-status" role="status">{active && <span className="relevance-spinner" aria-hidden="true" />}{active && run.phase ? `${run.phase} · ` : active && run.retrying ? 'Retrying failed resources · ' : ''}{run.processed.toLocaleString()} of {run.total.toLocaleString()} records processed</div>
      <div className="relevance-progress-track" role="progressbar" aria-label="Source records processed" aria-valuemin={0} aria-valuemax={run.total} aria-valuenow={run.processed}><div style={{ width: `${100 * run.processed / Math.max(1, run.total)}%` }} /></div>
      <div className="source-material-overview">
        <div><strong>{(run.full_text_saved ?? count('full_text')).toLocaleString()}</strong><span>Full texts saved</span></div>
        <div><strong>{run.abstract_only.toLocaleString()}</strong><span>Abstract-only so far</span></div>
        <div><strong>{count('supplements').toLocaleString()}</strong><span>Supplement archives saved</span></div>
        <div><strong>{count('data_links').toLocaleString()}</strong><span>Linked-data inventories saved</span></div>
      </div>
      <div className="source-material-access-summary" aria-live="polite">
        {outcomes.map(outcome => <p key={outcome.status} className="evidence-themes-helper"><strong>{totalFor(outcome.status).toLocaleString()} · {outcome.title}</strong><br />{outcome.help}</p>)}
        {active && run.retrying && <p>{run.remaining_resources.toLocaleString()} resource checks remaining in this retry.</p>}
        <p className="evidence-themes-helper">Counts above refer to resources, not distinct papers. All retained records remain included. Finishing collection does not resolve retryable failures, review issues or size limits.</p>
      </div>
      {active && !run.stop_requested && <button type="button" className="text-button" disabled={working} onClick={() => void action('pause')}>Pause after current request</button>}
      {!active && (remaining > 0 || failures > 0 || blocked > 0) && <div className="relevance-confirm-card"><button type="button" className="primary-button" disabled={working} onClick={() => void action('resume')}>{remaining > 0 ? 'Resume collection' : 'Retry temporary failures'}</button></div>}
      {!active && run.fallback_eligible > 0 && <div className="relevance-confirm-card"><button type="button" className="text-button" disabled={working} onClick={() => void action('fallback')}>Try missing full text elsewhere</button></div>}
      {!active && run.jobs[0]?.error && <p className="setup-error">{run.jobs[0].error}</p>}
      <details className="source-material-records"><summary>Inspect collected material</summary>
        {run.records.map(record => <article key={record.id} className="source-material-record"><strong>{record.title}</strong><small>{record.source}:{record.source_record_id}</small>
          {record.resources.map(resource => <details key={resource.kind}><summary>{labels[resource.kind]} · {statuses[resource.status] ?? resource.status}{resource.raw_byte_size ? ` · ${(resource.raw_byte_size / 1000000).toFixed(2)} MB` : ''}</summary>
            {resource.details.recovery_provider && <p>Full text recovered via {resource.details.recovery_provider}. Earlier primary failures remain in history.</p>}
            {resource.error && <p>{resource.status === 'recovered' ? 'Primary route history: ' : ''}{resource.error}</p>}
            {resource.details.provider && <p>{resource.details.provider} · {resource.details.format}</p>}
            {resource.details.license_statements?.map((license, index) => <p key={index}>{license}</p>)}
            {resource.details.file_count !== undefined && <p>{resource.details.file_count} archived files; stored without executing or extracting them.</p>}
            {resource.details.files.length > 0 && <ul>{resource.details.files.map(file => <li key={file.name}>{file.name}</li>)}</ul>}
            {resource.details.reported_count !== undefined && <p>{resource.details.reported_count} reported links{resource.details.inventory_partial ? ' · Inventory is partial' : ''}. Links are not verified experimental evidence; linked content was not fetched.</p>}
            {resource.details.links.length > 0 && <ul>{resource.details.links.map((link, index) => <li key={index}>{link.Target?.Title || link.Target?.Identifier?.ID || 'Linked source entry'}</li>)}</ul>}
          </details>)}
        </article>)}
        <div className="query-actions"><button type="button" className="text-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous records</button><span>{offset + 1}–{Math.min(offset + 25, run.total)} / {run.total}</span><button type="button" className="text-button" disabled={offset + 25 >= run.total} onClick={() => setOffset(offset + 25)}>Next records</button></div>
        <p className="evidence-themes-helper">Previews show up to 10 files or links per resource. Complete responses and inventories are preserved locally.</p>
      </details>
    </>}
    {error && <div role="alert"><p className="setup-error">{error}</p><button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Retry status</button></div>}
  </section>
}
