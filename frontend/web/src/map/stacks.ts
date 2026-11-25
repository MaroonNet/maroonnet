import type { Map as MapLibreMap } from 'maplibre-gl'

// How near markers are on screen, in pixels, for them to be grouped. Markers closer than
// CLICK_DISTANCE cover each other, so they are one stack: one click target with one count.
// A marker closer than LABEL_DISTANCE to another would run into its pill or name (a pill
// reaches about 65 px right of its dot), so it shows none.
export const CLICK_DISTANCE = 25
export const LABEL_DISTANCE = 75

// What one click on the map's markers picked: the teams (by radio) and the waypoints on
// that spot. Often one thing; several when they sit on the same spot.
export type Stack = { teams: number[], waypoints: number[] }

// How a stack of several is counted: "6 teams · 2 waypoints", "2 waypoints", "1 team · 1 waypoint".
export function stackWords(teams: number, waypoints: number): string {
    const count = (many: number, word: string) => many === 0 ? [] : [`${many} ${word}${many === 1 ? '' : 's'}`]
    return [...count(teams, 'team'), ...count(waypoints, 'waypoint')].join(' · ')
}

// Markers sorted into stacks: markers whose places are less than distance apart on screen.
// Each marker in turn joins every stack with a marker near it, and those stacks become one,
// so a row of close markers is one stack. The markers keep the order they were given in,
// within a stack and between stacks, so the last of a stack is drawn on top. How close two
// places are on screen depends on the zoom, so the stacks are worked out again when the map
// zooms.
export function stacksOf<Placed extends { lat: number, lon: number }>(placed: Placed[], map: MapLibreMap, distance: number): Placed[][] {
    const points = placed.map((one) => map.project([one.lon, one.lat]))
    const near = (a: number, b: number) => Math.hypot(points[a].x - points[b].x, points[a].y - points[b].y) < distance
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
