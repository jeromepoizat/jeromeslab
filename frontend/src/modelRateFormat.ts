export type ModelRate = {
  input_per_million_usd: number
  cached_input_per_million_usd: number
  output_per_million_usd: number
  source_url: string
  captured_on: string
}

export function usd(value: number) {
  return `$${value.toFixed(2).replace(/\.00$/, '')}`
}

export function shortRate(rate: ModelRate | undefined) {
  return rate
    ? `${usd(rate.input_per_million_usd)} input / ${usd(rate.output_per_million_usd)} output per 1M tokens`
    : 'Rate unavailable for this exact model'
}
