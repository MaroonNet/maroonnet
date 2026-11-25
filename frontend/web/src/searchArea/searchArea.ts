import { createContext, useContext, useEffect, useRef } from 'react'
import type { Bounds } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { ask } from '../mission/mission.ts'

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

// Moves the map over the open mission's search area: once when the page opens with a
// mission open, and again each time another mission is opened. A mission with no search
// area leaves the map where it was, and so does saving a new area: the user has just
// drawn it, so it is already on screen. panelOpen: a panel is covering the map's left side.
export function useMapOverSearchArea(panelOpen: boolean) {
    const map = useMissionMap()
    const { area, loadedFor } = useSearchArea()
    // Kept in refs (boxes whose contents can change without redrawing) so that opening or
    // closing a panel, or saving a new area, does not move the map; only opening a mission does.
    const panelIsOpen = useRef(panelOpen)
    const areaNow = useRef(area)
    useEffect(() => {
        panelIsOpen.current = panelOpen
        areaNow.current = area
    }, [panelOpen, area])

    useEffect(() => {
        const box = areaNow.current
        if (!map || !loadedFor || !box) return
        const left = panelIsOpen.current ? PANEL_WIDTH + EDGE : EDGE
        map.fitBounds([[box.min_lon, box.min_lat], [box.max_lon, box.max_lat]], {
            padding: { top: EDGE, bottom: EDGE, right: EDGE, left },
            duration: 0,  // jump there: gliding across states would load every tile on the way
        })
    }, [map, loadedFor])
}
