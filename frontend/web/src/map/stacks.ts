import type { Map as MapLibreMap } from 'maplibre-gl'

// Two markers this close on screen, in pixels, cover each other: a team's circle is 30
// across, a waypoint's pin 24.
export const SAME_SPOT = 20

// What one click on the map's markers picked: the teams (by radio) and the waypoints on
// that spot. Often one thing; several when they sit on the same spot.
export type Stack = { teams: number[], waypoints: number[] }

// How a stack of several is counted: "6 teams · 2 waypoints", "2 waypoints", "1 team · 1 waypoint".
export function stackWords(teams: number, waypoints: number): string {
    const count = (many: number, word: string) => many === 0 ? [] : [`${many} ${word}${many === 1 ? '' : 's'}`]
    return [...count(teams, 'team'), ...count(waypoints, 'waypoint')].join(' · ')
}

// Markers sorted into stacks: each joins the first stack whose first marker is on the same
// spot of the screen, or starts a stack of its own. How close two places are on screen
// depends on the zoom, so the stacks are worked out again when the map zooms.
export function stacksOf<Placed extends { lat: number, lon: number }>(placed: Placed[], map: MapLibreMap): Placed[][] {
    const stacks: { x: number, y: number, members: Placed[] }[] = []
    for (const one of placed) {
        const { x, y } = map.project([one.lon, one.lat])
        const near = stacks.find((stack) => Math.hypot(stack.x - x, stack.y - y) < SAME_SPOT)
        if (near) near.members.push(one)
        else stacks.push({ x, y, members: [one] })
    }
    return stacks.map((stack) => stack.members)
}
