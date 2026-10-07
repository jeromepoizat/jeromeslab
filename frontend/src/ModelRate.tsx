import { shortRate, usd, type ModelRate } from './modelRateFormat'

export function ModelRateLine({ rate }: { rate: ModelRate | undefined }) {
  if (!rate) return <small className="model-rate">Rate unavailable for this exact model</small>
  return <small className="model-rate">
    Standard rate · {shortRate(rate)} · {usd(rate.cached_input_per_million_usd)} cached input
    {' · '}<a href={rate.source_url} target="_blank" rel="noreferrer" title={`Rate captured ${rate.captured_on}; actual pricing may differ`}>Pricing source</a>
  </small>
}
