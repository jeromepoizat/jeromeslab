import type { Job } from './JobQueue'

export function jobCostLabel(job: Job): string {
  if (job.cost_status !== 'estimated' || job.estimated_cost === null) return 'Cost unavailable'
  const amount = Number(job.estimated_cost)
  if (!Number.isFinite(amount)) return 'Cost unavailable'
  if (amount > 0 && amount < 0.0001) return 'Est. <$0.0001'
  return `Est. $${amount < 0.01 ? amount.toFixed(4) : amount.toFixed(2)}`
}
