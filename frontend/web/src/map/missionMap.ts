import type { Map as MapLibreMap } from 'maplibre-gl'
import { useMap } from 'react-map-gl/maplibre'

// The name the map goes by on the map library's shared board (MapProvider, in main.tsx).
export const MAP_ID = 'mission'

// What a component calls to reach the MapLibre map, wherever it is drawn: a piece drawn
// inside the map reads it as "current", and a piece outside reads it by its name.
// None: the map does not exist yet.
export function useMissionMap(): MapLibreMap | null {
    const maps = useMap()
    return (maps.current ?? maps[MAP_ID])?.getMap() ?? null
}
