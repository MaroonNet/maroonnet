import type { ExpressionSpecification } from 'maplibre-gl'
import type { Feature, FeatureCollection, Polygon } from 'geojson'
import { useEffect } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import { useMissionMap } from '../map/missionMap.ts'
import { lookOf, SECTOR_COLORS, STRIPES, stripesImage, type Look } from './looks.ts'
import { useSectors, type Sector } from './sectors.ts'

// Each look, as a choice the map makes for each sector from its "look" property.
const byLook = (values: Record<Look, string | number>): ExpressionSpecification =>
    ['match', ['get', 'look'], 'drawn', values.drawn, 'partial', values.partial, values.completed]

// The saved sectors on the map: an outline in the look's color, a light green fill for a
// completed sector, and orange stripes for a partial one. It is drawn inside the map (a
// child of MissionMap), above the search area line.
function SectorsOnMap() {
    const { sectors } = useSectors()
    useStripes()
    return (
        <Source id="sectors" type="geojson" data={sectorShapes(sectors)}>
            <Layer
                id="sectors-fill"
                type="fill"
                filter={['==', ['get', 'look'], 'completed']}
                paint={{ 'fill-color': SECTOR_COLORS.completed, 'fill-opacity': 0.18 }}
            />
            <Layer
                id="sectors-stripes"
                type="fill"
                filter={['==', ['get', 'look'], 'partial']}
                paint={{ 'fill-pattern': STRIPES }}
            />
            <Layer
                id="sectors-line"
                type="line"
                paint={{ 'line-color': byLook(SECTOR_COLORS), 'line-width': 2 }}
            />
        </Source>
    )
}

// The sectors as shapes the map can draw. The map takes longitude before latitude, and a
// shape's ring goes back to its first corner.
function sectorShapes(sectors: Sector[]): FeatureCollection<Polygon> {
    return {
        type: 'FeatureCollection',
        features: sectors.map((sector): Feature<Polygon> => {
            const ring = [...sector.corners, sector.corners[0]].map(({ lat, lon }) => [lon, lat])
            return {
                type: 'Feature',
                properties: { id: sector.id, name: sector.name, look: lookOf(sector) },
                geometry: { type: 'Polygon', coordinates: [ring] },
            }
        }),
    }
}

// Gives the map the stripe picture. A new map style drops pictures added by hand, and the
// map then asks for any it is missing ("styleimagemissing"), so it is given again then.
function useStripes() {
    const map = useMissionMap()
    useEffect(() => {
        if (!map) return
        const add = () => {
            if (!map.hasImage(STRIPES)) map.addImage(STRIPES, stripesImage(), { pixelRatio: 2 })
        }
        const onMissing = (event: { id: string }) => {
            if (event.id === STRIPES) add()
        }
        add()
        map.on('styleimagemissing', onMissing)
        return () => { map.off('styleimagemissing', onMissing) }
    }, [map])
}

export default SectorsOnMap
