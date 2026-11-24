// The one place that turns a saved time into the text shown on screen. Times are saved in
// UTC, and are shown in the mission's time zone, not the laptop's, so a mission reads the
// same on every laptop that opens it.

// The zones the New Mission form offers. A zone's name carries its own daylight saving
// rule, so there is one entry for each zone and no separate summer entry.
export const TIME_ZONES: { name: string, label: string }[] = [
    { name: 'America/New_York', label: 'Eastern' },
    { name: 'America/Chicago', label: 'Central' },
    { name: 'America/Denver', label: 'Mountain' },
    { name: 'America/Phoenix', label: 'Arizona' },
    { name: 'America/Los_Angeles', label: 'Pacific' },
    { name: 'America/Anchorage', label: 'Alaska' },
    { name: 'Pacific/Honolulu', label: 'Hawaii' },
]

// A zone's plain name. A zone that is not on the list is shown by its own name.
export function zoneLabel(zone: string): string {
    return TIME_ZONES.find((listed) => listed.name === zone)?.label ?? zone
}

// The pieces of a moment as a clock and calendar in this zone show them.
function pieces(time: Date, zone: string, options: Intl.DateTimeFormatOptions): Record<string, string> {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: zone, ...options }).formatToParts(time)
    return Object.fromEntries(parts.map((part) => [part.type, part.value]))
}

// A time of day: "8:30 pm".
export function formatTime(utc: string, zone: string): string {
    const { hour, minute, dayPeriod } = pieces(new Date(utc), zone, { hour: 'numeric', minute: '2-digit', hour12: true })
    return `${hour}:${minute} ${dayPeriod.toLowerCase()}`
}

// A date and a time of day: "Apr 13, 2025, 8:30 pm".
export function formatDateTime(utc: string, zone: string): string {
    const { month, day, year } = pieces(new Date(utc), zone, { month: 'short', day: 'numeric', year: 'numeric' })
    return `${month} ${day}, ${year}, ${formatTime(utc, zone)}`
}

// The calendar date of a moment in this zone, as a count of days.
function dateCount(utc: string, zone: string): number {
    const { year, month, day } = pieces(new Date(utc), zone, { year: 'numeric', month: 'numeric', day: 'numeric' })
    return Date.UTC(Number(year), Number(month) - 1, Number(day)) / 86_400_000
}

// Which day of the mission its latest session is on, from the start time of every session so
// far: the number of different dates they started on. Two sessions on one date are the same
// day, and a session on a later date is the next day.
export function dayNumber(starts: string[], zone: string): number {
    return new Set(starts.map((start) => dateCount(start, zone))).size
}

// How long something has been going, from milliseconds: "7:50:00".
export function formatElapsed(milliseconds: number): string {
    const seconds = Math.max(0, Math.floor(milliseconds / 1000))
    const two = (n: number) => String(n).padStart(2, '0')
    return `${Math.floor(seconds / 3600)}:${two(Math.floor(seconds / 60) % 60)}:${two(seconds % 60)}`
}

// How many minutes a zone is from UTC at a moment: -420 for Arizona.
function offsetMinutes(zone: string, at: Date): number {
    const { timeZoneName } = pieces(at, zone, { timeZoneName: 'longOffset' })  // "GMT-07:00", or "GMT"
    const match = /([+-])(\d\d):(\d\d)/.exec(timeZoneName)
    if (!match) return 0
    return (match[1] === '-' ? -1 : 1) * (Number(match[2]) * 60 + Number(match[3]))
}

// The listed zone that keeps the same time as this one: the zone itself when it is listed,
// otherwise the listed zone the same distance from UTC in both winter and summer. With no
// match, the first on the list.
export function listedZoneFor(zone: string): string {
    if (TIME_ZONES.some((listed) => listed.name === zone)) return zone
    const year = new Date().getFullYear()
    const seasons = [new Date(Date.UTC(year, 0, 15)), new Date(Date.UTC(year, 6, 15))]
    const same = TIME_ZONES.find((listed) =>
        seasons.every((day) => offsetMinutes(listed.name, day) === offsetMinutes(zone, day)))
    return (same ?? TIME_ZONES[0]).name
}

// The listed zone for the zone this laptop is set to. The New Mission form starts on it.
export function laptopZone(): string {
    return listedZoneFor(Intl.DateTimeFormat().resolvedOptions().timeZone)
}
