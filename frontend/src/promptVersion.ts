export function promptVersionNumber(value: string) {
  const match = value.match(/(?:^|:)(\d+)$/)
  return match === null ? 0 : Number.parseInt(match[1], 10)
}
