import type { ViewState } from 'react-map-gl/maplibre'

// The map style, served by the backend (backend/maps/style.py). Drawing from local packs only.
export const MAP_STYLE_URL = '/maps/style.json'

// The deepest zoom a user can reach. Past a pack's last zoom there is no new detail, so MapLibre
// enlarges the last tiles instead. The basemap (built to 14) stays sharp for about 3 zooms of
// enlarging, and the most detailed terrain (a mission pack) stops at 16, so going past 17 would
// only make the map blurrier.
export const MAX_ZOOM = 17

// Placeholder center (Denver) until the search region is picked.
export const INITIAL_VIEW: Pick<ViewState, 'longitude' | 'latitude' | 'zoom'> = {
    longitude: -105.0,
    latitude: 39.74,
    zoom: 11
}