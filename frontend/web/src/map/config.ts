import type { ViewState } from 'react-map-gl/maplibre'

// The map style, served by the backend (backend/maps/style.py). Drawing from local packs only.
export const MAP_STYLE_URL = '/maps/style.json'

// The deepest zoom a user can reach. Past a pack's last zoom there is no new detail, so MapLibre
// enlarges the last tiles instead: the basemap ends at 14 and the terrain at 16, so at 19 the
// hillshade is soft. 19 is deep enough to pull apart teams about 6 m apart, near the limit of
// what their radios' GPS can tell apart.
export const MAX_ZOOM = 19

// Placeholder center (Denver) until the search region is picked.
export const INITIAL_VIEW: Pick<ViewState, 'longitude' | 'latitude' | 'zoom'> = {
    longitude: -105.0,
    latitude: 39.74,
    zoom: 11
}