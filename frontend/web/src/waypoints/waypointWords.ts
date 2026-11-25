import { COMMAND_POST, kindOf } from './kinds.ts'
import type { Waypoint } from './waypoints.ts'

// The database's limits on a waypoint's words. They are counted in bytes, since a waypoint
// is sized to fit a radio packet.
export const NAME_BYTES = 30
export const DESCRIPTION_BYTES = 100

// How many bytes a text takes when sent: one for a plain letter, two for an accented one.
export const bytes = (text: string) => new TextEncoder().encode(text).length

// The name a new waypoint starts with: its kind and a number, "Hazard 2". The number is one
// more than the count of that kind on the map, and goes up past any name already there.
// There is one command post at a time, so its name has no number.
export function startingName(kind: string, waypoints: Waypoint[]): string {
    const { label } = kindOf(kind)
    if (kind === COMMAND_POST) return label
    const names = new Set(waypoints.map((waypoint) => waypoint.name))
    let number = waypoints.filter((waypoint) => waypoint.kind === kind).length + 1
    while (names.has(`${label} ${number}`)) number += 1
    return `${label} ${number}`
}

// Any command post waypoint is the command post. The backend keeps one on the map at a time.
export const commandPost = (waypoints: Waypoint[]) => waypoints.find((waypoint) => waypoint.kind === COMMAND_POST)
