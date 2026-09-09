export async function readApiError(response: Response) {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null
  return body?.detail ?? 'The request could not be completed. Try again.'
}
