import { useEffect, useState } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import type { Bounds } from '../map/geo.ts'
import { useMission } from '../mission/mission.ts'
import { usePeople } from '../people/people.ts'
import { useSearchArea } from '../searchArea/searchArea.ts'
import { commandPost } from '../waypoints/waypointWords.ts'
import { useWaypoints } from '../waypoints/waypoints.ts'
import { loadPacks, type Box, type InstalledPack } from './packs.ts'

// The setup of a mission in planning: four steps, each done when the mission's own data
// says so, in whatever order things were done. Nothing here blocks anything.

// One step. red: it has been checked and something is missing, which only the Offline
// Maps step shows. missing: what is still needed, one line each.
export type SetupStep = {
    id: 'area' | 'maps' | 'post' | 'people'
    label: string
    done: boolean
    red: boolean
    missing: string[]
}

// The installed packs, or how reading them went.
export type PacksRead = InstalledPack[] | 'reading' | 'failed'

// What the steps are worked out from.
export type SetupFacts = {
    area: Bounds | null  // the search area; none: not drawn yet
    packs: PacksRead
    hasPost: boolean     // a command post is placed
    checkedIn: number    // how many people are checked in
}

// Whether the boxes, taken together, cover the whole rectangle. The edges of the boxes cut
// the rectangle into a grid of cells, each of which lies wholly inside or wholly outside
// every box, so it is enough to ask about the middle of each cell.
export function covers(area: Bounds, boxes: Box[]): boolean {
    const lons = cuts(area.min_lon, area.max_lon, boxes.flatMap(([west, , east]) => [west, east]))
    const lats = cuts(area.min_lat, area.max_lat, boxes.flatMap(([, south, , north]) => [south, north]))
    for (let column = 0; column < lons.length - 1; column += 1) {
        for (let row = 0; row < lats.length - 1; row += 1) {
            const lon = (lons[column] + lons[column + 1]) / 2
            const lat = (lats[row] + lats[row + 1]) / 2
            if (!boxes.some(([west, south, east, north]) => west <= lon && lon <= east && south <= lat && lat <= north)) return false
        }
    }
    return true
}

// The two ends of a span and every edge that falls between them, in order.
function cuts(from: number, to: number, edges: number[]): number[] {
    const inside = edges.filter((edge) => from < edge && edge < to)
    return [...new Set([from, ...inside, to])].sort((a, b) => a - b)
}

// What the Offline Maps step still needs: nothing when a state pack and a mission pack both
// cover the search area. A state pack is a basemap and a terrain pack, and both must cover
// it. Only complete packs count.
function mapsMissing(area: Bounds, packs: InstalledPack[]): string[] {
    const boxesOf = (kind: InstalledPack['kind'], contents: InstalledPack['contents']) => packs
        .filter((pack) => pack.status === 'complete' && pack.kind === kind && pack.contents === contents)
        .flatMap((pack) => pack.area)
    const state = covers(area, boxesOf('state', 'basemap')) && covers(area, boxesOf('state', 'terrain'))
    const mission = covers(area, boxesOf('mission', 'terrain'))
    if (!state && !mission) return ['No maps are installed for this area.']
    if (!state) return ['No state pack covers the search area.']
    if (!mission) return ['No mission pack covers the search area.']
    return []
}

function mapsStep(area: Bounds | null, packs: PacksRead): SetupStep {
    const step = { id: 'maps' as const, label: 'Offline Maps' }
    // With no search area there is nothing to check the packs against.
    if (!area || packs === 'reading') return { ...step, done: false, red: false, missing: [] }
    const missing = packs === 'failed' ? ['The installed maps could not be read.'] : mapsMissing(area, packs)
    return { ...step, done: missing.length === 0, red: missing.length > 0, missing }
}

// The four steps, in the order the bar shows them.
export function setupSteps({ area, packs, hasPost, checkedIn }: SetupFacts): SetupStep[] {
    const plain = (id: SetupStep['id'], label: string, done: boolean, needs: string): SetupStep =>
        ({ id, label, done, red: false, missing: done ? [] : [needs] })
    return [
        plain('area', 'Search Area', area !== null, 'No search area.'),
        mapsStep(area, packs),
        plain('post', 'Mark CP', hasPost, 'Command post not placed.'),
        plain('people', 'Check In People', checkedIn > 0, 'Nobody is checked in.'),
    ]
}

// The open mission's setup steps while it is in planning; none otherwise. The installed
// packs are read once when a mission in planning comes on screen.
export function useSetupSteps(): SetupStep[] | null {
    const planning = useMission().mission?.status === 'planning'
    const { area } = useSearchArea()
    const { waypoints } = useWaypoints()
    const { people } = usePeople()
    const [packs, setPacks] = useState<PacksRead>('reading')

    useEffect(() => {
        if (!planning) return
        let gone = false  // the mission left planning before the answer arrived
        loadPacks().then((list) => {
            if (!gone) setPacks(Array.isArray(list) ? list : 'failed')
        }).catch((error) => {
            sendError('mission', error)
            if (!gone) setPacks('failed')
        })
        return () => { gone = true }
    }, [planning])

    if (!planning) return null
    return setupSteps({
        area, packs,
        hasPost: commandPost(waypoints) !== undefined,
        checkedIn: people.filter((person) => person.checked_in).length,
    })
}
