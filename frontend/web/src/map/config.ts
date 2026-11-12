import type { ViewState } from 'react-map-gl/maplibre'

// The map style, served by the backend (backend/maps/style.py). Drawing from local packs only.
export const MAP_STYLE_URL = '/maps/style.json'

// Placeholder center (Denver) until the search region is picked.
export const INITIAL_VIEW: Pick<ViewState, 'longitude' | 'latitude' | 'zoom'> = {
    longitude: -105.0,
    latitude: 39.74,
    zoom: 11
}