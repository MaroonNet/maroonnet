import { createContext, useContext, useEffect, useRef } from 'react'
import type { Bounds, Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { ask } from '../mission/mission.ts'
import { useSectors, type Sector } from '../sectors/sectors.ts'
import { commandPost } from '../waypoints/waypointWords.ts'
import { useWaypoints } from '../waypoints/waypoints.ts'

// The open mission's search area, as the backend answers it (backend/search_area/routes.py):
// the rectangle's south-west and north-east corners, in degrees.
export type SearchArea = Bounds

// None: the mission has no search area yet.
export const loadSearchArea = () => ask<SearchArea | null>('/api/mission/search-area')
// Sets the search area, in place of the one that was there. Answers with it as saved.
export const saveSearchArea = (area: SearchArea) => ask<SearchArea>('/api/mission/search-area', 'PUT', area)

// The board: the open mission's search area, kept in one place that any component can read.
export type SearchAreaBoard = {
    area: SearchArea | null     // none: no mission is open, or it has no search area yet
    loadedFor: string | null    // the id of the mission the area was read for; none until it is read
    // Saves a new search area. The answer is empty when it worked, and the reason when it
    // did not; the board changes only when it worked, so the screen always shows what is saved.
    save: (area: SearchArea) => Promise<string>
}

// A component drawn with no SearchAreaProvider above it, as in a test of one component,
// reads this board: no search area, and none can be saved.
export const SearchAreaContext = createContext<SearchAreaBoard>({
    area: null,
    loadedFor: null,
    save: async () => 'There is no search area board.',
})

// What a component calls to read the board.
export function useSearchArea(): SearchAreaBoard {
    return useContext(SearchAreaContext)
}

// Space, in pixels, left between the search area and the map's edges.
const EDGE = 40
// A panel covers this much of the map's left side (--spacing-panel in index.css).
const PANEL_WIDTH = 300

// The box the map is fitted to when a mission is opened. With a command post, the box is
// centered on it and reaches far enough every way to show every sector, or the whole
// search area when there are no sectors. Without one, it is the search area. None: there is
// no search area, so the map stays where it was.
function openingBox(area: SearchArea | null, post: Position | undefined, sectors: Sector[]): Bounds | null {
    if (!area) return null
    if (!post) return area
    const corners = sectors.length > 0
        ? sectors.flatMap((sector) => sector.corners)
        : [{ lat: area.min_lat, lon: area.min_lon }, { lat: area.max_lat, lon: area.max_lon }]
    const across = Math.max(...corners.map((corner) => Math.abs(corner.lon - post.lon)))
    const up = Math.max(...corners.map((corner) => Math.abs(corner.lat - post.lat)))
    return { min_lat: post.lat - up, min_lon: post.lon - across, max_lat: post.lat + up, max_lon: post.lon + across }
}

// Moves the map to the opening box above: once when the page opens with a mission open, and
// again each time another mission is opened. It waits until the search area, the waypoints
// and the sectors have all been read for that mission. Changes after that, such as a new
// search area the user has just drawn, leave the map where it is. panelOpen: a panel is
// covering the map's left side.
export function useOpeningView(panelOpen: boolean) {
    const map = useMissionMap()
    const { area, loadedFor: areaFor } = useSearchArea()
    const { waypoints, loadedFor: waypointsFor } = useWaypoints()
    const { sectors, loadedFor: sectorsFor } = useSectors()
    // The mission all three were read for, once they agree.
    const readFor = areaFor !== null && areaFor === waypointsFor && areaFor === sectorsFor ? areaFor : null
    // Kept in refs (boxes whose contents can change without redrawing) so that opening or
    // closing a panel, or a change to the mission, does not move the map; only opening a
    // mission does.
    const panelIsOpen = useRef(panelOpen)
    const box = useRef<Bounds | null>(null)
    useEffect(() => {
        panelIsOpen.current = panelOpen
        box.current = openingBox(area, commandPost(waypoints), sectors)
    }, [panelOpen, area, waypoints, sectors])

    useEffect(() => {
        const fit = box.current
        if (!map || !readFor || !fit) return
        const left = panelIsOpen.current ? PANEL_WIDTH + EDGE : EDGE
        map.fitBounds([[fit.min_lon, fit.min_lat], [fit.max_lon, fit.max_lat]], {
            padding: { top: EDGE, bottom: EDGE, right: EDGE, left },
            duration: 0,  // jump there: gliding across states would load every tile on the way
        })
    }, [map, readFor])
}
