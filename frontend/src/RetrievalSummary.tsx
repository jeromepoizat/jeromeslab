import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'

export type SearchRun = {
  query_id: string
  query_title: string
  status: string
  total_hits: number | null
  retrieved_count: number
  unique_to_query: number
  truncated: boolean
  error: string | null
}

export type RetrievalSummaryData = {
  runs: SearchRun[]
  reported_hits: number
  raw_saved_records: number
  distinct_source_records: number
  repeat_discoveries: number
  records_in_multiple_queries: number
  distinct_records_with_abstract: number
  provisional_record_groups: number | null
  additional_source_ids_grouped: number | null
  groups_with_metadata_differences: number | null
  sources: { source: string; unique_records: number; raw_records: number }[]
}

type Props = {
  job: Job
  summary: RetrievalSummaryData | null
  expectedQueries: number
  nowMilliseconds: number
  onRetry: () => void
}

const number = (value: number) => value.toLocaleString()

// Europe PMC's source codes: https://europepmc.org/help
const sourceDescriptions: Record<string, string> = {
  AGR: 'AGR — Agricola: agricultural literature citations.',
  CBA: 'CBA — Chinese Biological Abstracts: biological-science citations.',
  CTX: 'CTX — CiteXplore: manually submitted or additional Europe PMC records.',
  ETH: 'ETH — EThOS Theses: doctoral theses from the British Library.',
  HIR: 'HIR — NHS Evidence: UK clinical guidelines.',
  MED: 'MED — PubMed/MEDLINE: biomedical literature citations from the US National Library of Medicine.',
  NBK: 'NBK — Europe PMC Bookshelf metadata.',
  PAT: 'PAT — Biological Patents: patent records.',
  PMC: 'PMC — PubMed Central: biomedical and life-sciences full-text archive records.',
  PPR: 'PPR — Preprints: manuscripts posted before peer review.',
}

export function RetrievalSummary({ job, summary, expectedQueries, nowMilliseconds, onRetry }: Props) {
  const runs = summary?.runs ?? []
  const completed = runs.filter(run => run.status === 'completed').length
  const partial = runs.filter(run => run.truncated).length
  const maxHits = Math.max(1, ...runs.map(run => run.total_hits ?? run.retrieved_count))
  const abstractShare = summary && summary.distinct_source_records > 0
    ? Math.round(100 * summary.distinct_records_with_abstract / summary.distinct_source_records) : 0

  return <div className="retrieval-dashboard" aria-label="Europe PMC retrieval results">
    <div className="retrieval-dashboard-header">
      <div><p className="step-label">Search results · Europe PMC</p><p className="retrieval-dashboard-subtitle">What the approved queries found and what was saved locally.</p></div>
      <div className="retrieval-dashboard-status">{job.status !== 'completed' && <JobStatusLabel status={job.status} sourceRetrieval />}{job.status === 'completed' ? <strong><JobElapsedTime job={job} nowMilliseconds={nowMilliseconds} /></strong> : <JobElapsedTime job={job} nowMilliseconds={nowMilliseconds} />}</div>
    </div>
    {summary === null ? <p className="retrieval-dashboard-empty">Loading saved search counts…</p> : <>
      <div className="retrieval-metrics">
        <div className="retrieval-metric"><span>Reported hits</span><strong>{number(summary.reported_hits)}</strong><small>{completed < expectedQueries ? 'From queries with results so far' : 'Across all queries'}</small></div>
        <div className="retrieval-metric retrieval-metric--accent"><span>Raw records saved</span><strong>{number(summary.raw_saved_records)}</strong><small>Every query-to-record match</small></div>
        <div className="retrieval-metric"><span>Distinct source records</span><strong>{number(summary.distinct_source_records)}</strong><small>Same source ID counted once</small></div>
        <div className="retrieval-metric"><span>Found by multiple queries</span><strong>{number(summary.records_in_multiple_queries)}</strong><small>Overlapping query coverage</small></div>
      </div>
      <p className="retrieval-identity-note">A record can appear in more than one query result. Of the {number(summary.raw_saved_records)} saved results, {number(summary.repeat_discoveries)} are repeat appearances of a Europe PMC record ID, leaving {number(summary.distinct_source_records)} different source IDs. The same-article check below looks for overlap between those different IDs.</p>
      <div className="retrieval-detail-grid">
        <div className="retrieval-panel">
          <div className="retrieval-panel-heading"><h4>Queries</h4><span>{completed} of {expectedQueries} completed{partial > 0 ? ` · ${partial} partial` : ''}</span></div>
          <div className="retrieval-chart-explainer"><div className="retrieval-chart-legend"><span><span className="retrieval-legend-dot retrieval-legend-dot--hits" />Reported hits</span><span><span className="retrieval-legend-dot retrieval-legend-dot--saved" />Saved locally</span><span><span className="retrieval-legend-dot retrieval-legend-dot--unique" />Unique to query</span></div><p>Bar length compares query size, not relevance.</p></div>
          {runs.length === 0 ? <p className="retrieval-dashboard-empty">Searches have not begun yet.</p> : <div className="retrieval-query-list">{runs.map((run, index) => {
            const hits = run.total_hits ?? run.retrieved_count
            const uniqueDescription = `${number(run.unique_to_query)} distinct source ${run.unique_to_query === 1 ? 'record' : 'records'} saved only by this query in this retrieval. Different source IDs may still describe the same article.`
            const barDescription = run.total_hits === null
              ? `${number(run.retrieved_count)} records saved so far; total hits are not yet reported. ${uniqueDescription}`
              : `${number(run.total_hits)} hits reported by Europe PMC; ${number(run.retrieved_count)} records saved locally. ${uniqueDescription} Bar length is relative to the largest query, not a quality score.`
            return <div className="retrieval-query" key={run.query_id}>
              <div className="retrieval-query-line"><span className="retrieval-query-index">{String(index + 1).padStart(2, '0')}</span><strong>{run.query_title}</strong><span className={`retrieval-query-state ${run.truncated ? 'retrieval-query-state--partial' : ''}`}>{run.status === 'failed' ? 'Failed' : run.truncated ? 'Partial' : run.status === 'completed' ? 'Saved' : 'Running'}</span></div>
              <div className="retrieval-query-bottom"><div className="retrieval-query-track retrieval-tooltip-target" tabIndex={0} aria-label={barDescription}><span className="retrieval-query-hit" style={{ width: `${100 * hits / maxHits}%` }} /><span className="retrieval-query-saved" style={{ width: `${100 * run.retrieved_count / maxHits}%` }} /><span className="retrieval-query-unique" style={{ width: `${100 * run.unique_to_query / maxHits}%` }} /><span className="retrieval-data-tooltip" role="tooltip">{barDescription}</span></div><span>{number(run.retrieved_count)} saved <span className="retrieval-query-muted">· {number(run.unique_to_query)} unique / {run.total_hits === null ? 'hits pending' : `${number(run.total_hits)} hits`}</span></span></div>
              {run.error && <small className="setup-error">{run.error}</small>}
            </div>
          })}</div>}
        </div>
        <div className="retrieval-side-panels">
          <div className="retrieval-panel"><div className="retrieval-panel-heading"><h4>Abstract coverage</h4></div><strong className="retrieval-coverage-number">{abstractShare}%</strong><p>{number(summary.distinct_records_with_abstract)} of {number(summary.distinct_source_records)} distinct source records have an abstract.</p><div className="retrieval-coverage-track" aria-hidden="true"><span style={{ width: `${abstractShare}%` }} /></div><small>Availability is metadata, not a relevance judgment.</small></div>
          <div className="retrieval-panel"><div className="retrieval-panel-heading"><h4>Source collections</h4></div>{summary.sources.length === 0 ? <p>No source records yet.</p> : <div className="retrieval-source-list">{summary.sources.map(source => {
            const description = sourceDescriptions[source.source] ?? `${source.source} — Europe PMC source collection.`
            return <div key={source.source}><span className="retrieval-source-code retrieval-tooltip-target" tabIndex={0} aria-label={description}>{source.source}<span className="retrieval-data-tooltip" role="tooltip">{description}</span></span><div className="retrieval-source-track" aria-hidden="true"><span style={{ width: `${100 * source.unique_records / Math.max(1, summary.distinct_source_records)}%` }} /></div><strong>{number(source.unique_records)}</strong></div>
          })}</div>}</div>
        </div>
      </div>
      {summary.provisional_record_groups === null || summary.additional_source_ids_grouped === null || summary.groups_with_metadata_differences === null
        ? <p className="retrieval-identity-note">The same-article check will run when all queries finish.</p>
        : <div className="retrieval-article-check">
          <div><p className="step-label">Same-article check</p><strong>{number(summary.provisional_record_groups)}</strong><span>provisional record groups</span></div>
          <div className="retrieval-article-check-details"><p><strong>{number(summary.additional_source_ids_grouped)}</strong> additional source IDs matched to another record by DOI, PMID, PMCID, or the same normalized title.</p><p><strong>{number(summary.groups_with_metadata_differences)}</strong> groups have differing identifiers, authors, years, or journals and need review.</p></div>
          <p className="retrieval-article-check-note">No source records were removed. Patents are not grouped by title alone because different filings may share a title. All matches are provisional; this is not yet a verified count of distinct papers or studies.</p>
        </div>}
    </>}
    {job.error && <p className="setup-error">{job.error}</p>}
    {(job.status === 'failed' || job.status === 'cancelled') && <button className="primary-button" type="button" onClick={onRetry}>Retry retrieval from the same approved queries</button>}
  </div>
}
