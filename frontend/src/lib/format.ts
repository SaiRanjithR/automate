export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not stated'
  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null
  return Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000)
}

export function deadlineLabel(value: string | null | undefined): string {
  const days = daysUntil(value)
  if (days === null) return 'No deadline found'
  if (days < 0) return 'Deadline passed'
  if (days === 0) return 'Due today'
  return `${days} day${days === 1 ? '' : 's'} left`
}

export function inr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return 'Not stated'
  return `INR ${amount.toLocaleString('en-IN')}`
}
