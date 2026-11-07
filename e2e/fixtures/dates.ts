// The browser runs in UTC (see playwright.config.ts), matching the app's UTC "today".

/** `YYYY-MM-DD` for today plus `days`, in UTC. */
export function isoDaysFromToday(days: number): string {
  const date = new Date()
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function ordinal(day: number): string {
  if (day % 100 >= 11 && day % 100 <= 13) return `${day}th`
  return `${day}${{ 1: 'st', 2: 'nd', 3: 'rd' }[day % 10] ?? 'th'}`
}

/** react-day-picker's day button label (date-fns `PPPP`), e.g. "Friday, November 20th, 2026". */
export function dayButtonLabel(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`)
  const weekday = date.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' })
  const month = date.toLocaleDateString('en-US', { month: 'long', timeZone: 'UTC' })
  return `${weekday}, ${month} ${ordinal(date.getUTCDate())}, ${date.getUTCFullYear()}`
}

/** Whole calendar months from the current UTC month to the month of `iso`. */
export function monthsFromNow(iso: string): number {
  const now = new Date()
  const [year, month] = iso.split('-').map(Number) as [number, number]
  return (year - now.getUTCFullYear()) * 12 + (month - 1 - now.getUTCMonth())
}
