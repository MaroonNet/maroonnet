import type { Feature, LineString } from 'geojson'
import { Layer, Source } from 'react-map-gl/maplibre'
import { useSearchArea, type SearchArea } from './searchArea.ts'

// The line's look. The numbers of line-dasharray are a dash and a gap, in line widths.
const DASHED = { 'line-color': '#201e18', 'line-width': 2, 'line-dasharray': [4, 3] }

// The saved search area on the map: a dashed line around it. It is drawn inside the map
// (a child of MissionMap), and the map library adds it, redraws it when the area changes,
// and takes it away when there is none.
function SearchAreaOutline() {
    const { area } = useSearchArea()
    if (!area) return null
    return (
        <Source id="search-area" type="geojson" data={outline(area)}>
            <Layer id="search-area-line" type="line" paint={DASHED} />
        </Source>
    )
}

// The rectangle as a line the map can draw: its four corners, west and south first, and
// back to the start. The map takes longitude before latitude.
function outline(area: SearchArea): Feature<LineString> {
    const { min_lat: south, min_lon: west, max_lat: north, max_lon: east } = area
    return {
        type: 'Feature',
        properties: {},
        geometry: { type: 'LineString', coordinates: [[west, south], [east, south], [east, north], [west, north], [west, south]] },
    }
}

export default SearchAreaOutline
