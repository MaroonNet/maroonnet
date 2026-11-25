import type { Map as MapLibreMap } from 'maplibre-gl'

// Markers whose places are closer than this on screen, in pixels, are one stack. A team's
// pill reaches about 65 px right of its dot and a waypoint's name further, so markers this
// near would run into each other's.
export const STACK_DISTANCE = 50

// What one click on the map's markers picked: the teams (by radio) and the waypoints on
// that spot. Often one thing; several when they sit on the same spot.
export type Stack = { teams: number[], waypoints: number[] }

// How a stack of several is counted: "6 teams · 2 waypoints", "2 waypoints", "1 team · 1 waypoint".
export function stackWords(teams: number, waypoints: number): string {
    const count = (many: number, word: string) => many === 0 ? [] : [`${many} ${word}${many === 1 ? '' : 's'}`]
    return [...count(teams, 'team'), ...count(waypoints, 'waypoint')].join(' · ')
}

// Markers sorted into stacks. Each marker in turn joins every stack with a marker near it,
// and those stacks become one, so a row of close markers is one stack. The markers keep the
// order they were given in, within a stack and between stacks, so the last of a stack is
// drawn on top. How close two places are on screen depends on the zoom, so the stacks are
// worked out again when the map zooms.
export function stacksOf<Placed extends { lat: number, lon: number }>(placed: Placed[], map: MapLibreMap): Placed[][] {
    const points = placed.map((one) => map.project([one.lon, one.lat]))
    const near = (a: number, b: number) => Math.hypot(points[a].x - points[b].x, points[a].y - points[b].y) < STACK_DISTANCE
    let stacks: number[][] = []  // each stack as the numbers of its markers in placed
    placed.forEach((_, one) => {
        const joined = stacks.filter((stack) => stack.some((member) => near(member, one)))
        stacks = [...stacks.filter((stack) => !joined.includes(stack)), [...joined.flat(), one]]
    })
    return stacks
        .map((stack) => stack.sort((a, b) => a - b))
        .sort((a, b) => a[0] - b[0])
        .map((stack) => stack.map((member) => placed[member]))
}
