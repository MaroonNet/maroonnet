import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useRef } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { ask, useMission } from '../mission/mission.ts'

// The open mission's search area, as the backend answers it (backend/search_area/routes.py):
// the rectangle's south-west and north-east corners, in degrees.
export type SearchArea = {
    min_lat: number
    min_lon: number
    max_lat: number
    max_lon: number
}

// None: the mission has no search area yet.
export const loadSearchArea = () => ask<SearchArea | null>('/api/mission/search-area')

// Space, in pixels, left between the search area and the map's edges.
const EDGE = 40
// A panel covers this much of the map's left side (--spacing-panel in index.css).
const PANEL_WIDTH = 300

// Moves the map over the open mission's search area: once when the page opens with a
// mission open, and again each time another mission is opened. A mission with no search
// area leaves the map where it was. panelOpen: a panel is covering the map's left side.
export function useMapOverSearchArea(map: MapLibreMap | null, panelOpen: boolean) {
    const missionId = useMission().mission?.id
    // Kept in a ref (a box whose contents can change without redrawing) so that opening or
    // closing a panel does not move the map; only opening a mission does.
    const panelIsOpen = useRef(panelOpen)
    useEffect(() => { panelIsOpen.current = panelOpen }, [panelOpen])

    useEffect(() => {
        if (!map || !missionId) return
        let overtaken = false  // another mission was opened before this answer arrived
        loadSearchArea().then((area) => {
            if (!area || overtaken) return
            const left = panelIsOpen.current ? PANEL_WIDTH + EDGE : EDGE
            map.fitBounds([[area.min_lon, area.min_lat], [area.max_lon, area.max_lat]], {
                padding: { top: EDGE, bottom: EDGE, right: EDGE, left },
                duration: 0,  // jump there: gliding across states would load every tile on the way
            })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [map, missionId])
}
