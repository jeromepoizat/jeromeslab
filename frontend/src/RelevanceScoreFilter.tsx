import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import { HelpTooltip, SectionTitle } from './ProjectElements'
import { relevanceScoreLabels } from './relevanceScoreLabels'
import { ScoreThresholdControl } from './ScoreThresholdControl'

type Selection = {
  minimum_score: number
  include_not_assessable: boolean
  included_count: number
  excluded_count: number
  validated_at: string
}
type FilterState = {
  scored_count: number
  counts: Record<string, number>
  confirmation_sha256: string
  selection: Selection | null
}

const selectionWarning = 'After validation, records excluded at this step cannot be included in later steps of this project. Their original records and scores remain saved.'

/** A local selection of an immutable scored pool, not another LLM job. */
export function RelevanceScoreFilter({ projectId, runId, setupToken }: {
  projectId: string; runId: string; setupToken: string
}) {
  const [data, setData] = useState<FilterState | null>(null)
  const [minimum, setMinimum] = useState(0)
  const [includeUnassessable, setIncludeUnassessable] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const path = `/api/projects/${projectId}/relevance/scoring/runs/${runId}/filter`

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await fetch(path, { signal: controller.signal })
        if (!response.ok) throw new Error(await readApiError(response))
        const result = await response.json() as FilterState
        if (!controller.signal.aborted) setData(result)
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load scored records.')
      }
    }
    void load()
    return () => controller.abort()
  }, [path])

  const threshold = data?.selection?.minimum_score ?? minimum
  const includeNA = data?.selection?.include_not_assessable ?? includeUnassessable
  const locked = Boolean(data?.selection) || confirming || saving
  const included = data ? relevanceScoreLabels.reduce((total, [score]) => total + (
    (score === 'not_assessable' ? includeNA : Number(score) >= threshold) ? data.counts[score] ?? 0 : 0
  ), 0) : 0
  const excluded = (data?.scored_count ?? 0) - included

  async function validate() {
    if (!data) return
    setSaving(true)
    setError('')
    try {
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ minimum_score: threshold, include_not_assessable: includeNA,
          expected_confirmation_sha256: data.confirmation_sha256 }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setData({ ...data, selection: await response.json() as Selection })
      setConfirming(false)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not validate the filter.') }
    finally { setSaving(false) }
  }

  return <section className="project-section relevance-score-filter">
    <SectionTitle help="Choose which validated relevance scores to carry into further work. The slider sets the minimum included score: higher scores are also included. Not assessable is a separate choice, not a low score. Counts refer only to the validated scored pool, not unscored retrieval records. This filter does not assess study quality or delete excluded records.">Select records by relevance score</SectionTitle>
    {!data && !error && <p className="evidence-themes-helper">Loading scored records…</p>}
    {data && <>
      <div className="score-filter-summary" aria-live="polite" aria-atomic="true">
        <div><strong>{included.toLocaleString()}</strong><span>Records included</span></div>
        <div><strong>{excluded.toLocaleString()}</strong><span>Records excluded</span></div>
      </div>
      <div className="score-filter-card">
        <div className="score-filter-threshold"><strong>Minimum inclusion score: {threshold}</strong><HelpTooltip label="Minimum score help">The numbered arrow marks the minimum included score. Green points above it are included; lower points are excluded. Click a point or row, drag the arrow, or use the arrow keys to change the threshold.</HelpTooltip></div>
        <div className="score-filter-scale">
          <ScoreThresholdControl value={threshold} disabled={locked} onChange={setMinimum} />
          <div className="score-filter-levels">{relevanceScoreLabels.filter(([score]) => score !== 'not_assessable').map(([score, label]) => <button className={`score-filter-level ${Number(score) >= threshold ? 'score-filter-level--included' : ''}`} type="button" key={score} disabled={locked} onClick={() => setMinimum(Number(score))} aria-label={`Set minimum score to ${score}: ${data.counts[score].toLocaleString()} records`}><span>{label}</span><strong>{data.counts[score].toLocaleString()}</strong><small>{Number(score) >= threshold ? 'Included' : 'Excluded'}</small></button>)}</div>
        </div>
        <label className={`score-filter-unassessable ${includeNA ? 'score-filter-unassessable--included' : ''}`}><input type="checkbox" checked={includeNA} disabled={locked} onChange={event => setIncludeUnassessable(event.target.checked)} /><span>Include not assessable</span><strong>{data.counts.not_assessable.toLocaleString()}</strong><HelpTooltip label="Not assessable help">The saved metadata was insufficient to assign a relevance score. Keep these records for further review if you do not want to exclude them on missing information alone.</HelpTooltip></label>
      </div>
      {data.selection ? <p className="score-filter-validation" role="status">Selection validated · {data.selection.included_count.toLocaleString()} records saved for further work</p> : confirming ? <div className="score-filter-confirmation">
        <p>Include {included.toLocaleString()} records and exclude {excluded.toLocaleString()} from further work? This saves and locks this selection; original scores and excluded records remain preserved.</p>
        <div className="query-actions"><button className="primary-button" type="button" disabled={saving} onClick={() => void validate()}>{saving ? 'Validating…' : 'Confirm selection'}</button><HelpTooltip label="Relevance selection validation warning" variant="warning">{selectionWarning}</HelpTooltip><button className="text-button" type="button" disabled={saving} onClick={() => setConfirming(false)}>Cancel</button></div>
      </div> : <div className="relevance-confirm-card"><button className="primary-button" type="button" disabled={included === 0} onClick={() => setConfirming(true)}>Validate selection</button><HelpTooltip label="Relevance selection validation warning" variant="warning">{selectionWarning}</HelpTooltip></div>}
      {!data.selection && included === 0 && <p className="evidence-themes-helper">Include at least one record to continue.</p>}
    </>}
    {error && <p className="setup-error" role="alert">{error}</p>}
  </section>
}
