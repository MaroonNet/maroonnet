import type { ExpressionSpecification, MapLayerMouseEvent } from 'maplibre-gl'
import type { Feature, FeatureCollection, Point, Polygon } from 'geojson'
import { useEffect } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import { polygonCenter } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { lookOf, SECTOR_COLORS, STRIPES, stripesImage, type Look } from './looks.ts'
import { useSectors, type Sector } from './sectors.ts'

// Each look, as a choice the map makes for each sector from its "look" property.
const byLook = (values: Record<Look, string | number>): ExpressionSpecification =>
    ['match', ['get', 'look'], 'drawn', values.drawn, 'partial', values.partial, values.completed]

type Props = {
    selected: number | null             // the id of the selected sector, drawn with a stronger outline
    onPick?: (id: number) => void       // given while a click on a sector picks it (the Select tool)
}

// The layer a click on a sector is read from: every sector, filled with nothing visible.
const HIT = 'sectors-hit'

// The saved sectors on the map: an outline in the look's color, a light green fill for a
// completed sector, orange stripes for a partial one, and the name in the middle. It is
// drawn inside the map (a child of MissionMap), above the search area line.
function SectorsOnMap({ selected, onPick }: Props) {
    const { sectors } = useSectors()
    useStripes()
    usePicking(onPick)
    const isSelected: ExpressionSpecification = ['==', ['get', 'id'], selected ?? -1]
    return (
        <Source id="sectors" type="geojson" data={sectorShapes(sectors)}>
            <Layer id={HIT} type="fill" paint={{ 'fill-color': '#000000', 'fill-opacity': 0 }} />
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
                paint={{ 'line-color': byLook(SECTOR_COLORS), 'line-width': ['case', isSelected, 4, 2] }}
            />
            <Layer
                id="sectors-label"
                type="symbol"
                filter={['==', ['geometry-type'], 'Point']}
                layout={{
                    'text-field': ['get', 'name'],
                    'text-font': ['Noto Sans Bold'],  // one of the map style's own fonts
                    'text-size': 13,
                    'text-allow-overlap': true,  // a sector's name always shows
                }}
                paint={{ 'text-color': byLook(SECTOR_COLORS), 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 }}
            />
        </Source>
    )
}

// While onPick is given, a click on a sector picks it, and the pointer shows a hand over one.
function usePicking(onPick: ((id: number) => void) | undefined) {
    const map = useMissionMap()
    useEffect(() => {
        if (!map || !onPick) return
        const pick = (event: MapLayerMouseEvent) => {
            const top = event.features?.[0]  // where sectors overlap, the one drawn on top comes first
            if (top) onPick(top.properties.id as number)
        }
        const enter = () => { map.getCanvas().style.cursor = 'pointer' }
        const leave = () => { map.getCanvas().style.cursor = '' }
        map.on('click', HIT, pick)
        map.on('mouseenter', HIT, enter)
        map.on('mouseleave', HIT, leave)
        return () => {
            map.off('click', HIT, pick)
            map.off('mouseenter', HIT, enter)
            map.off('mouseleave', HIT, leave)
            leave()
        }
    }, [map, onPick])
}

// The sectors as shapes the map can draw, and one point for each at the middle of its
// ground, where its name goes. A shape alone would be labeled once in every map tile it
// crosses. The map takes longitude before latitude, and a shape's ring goes back to its
// first corner.
function sectorShapes(sectors: Sector[]): FeatureCollection<Polygon | Point> {
    const shapes = sectors.map((sector): Feature<Polygon> => {
        const ring = [...sector.corners, sector.corners[0]].map(({ lat, lon }) => [lon, lat])
        return { type: 'Feature', properties: facts(sector), geometry: { type: 'Polygon', coordinates: [ring] } }
    })
    const labels = sectors.map((sector): Feature<Point> => {
        const { lat, lon } = polygonCenter(sector.corners)
        return { type: 'Feature', properties: facts(sector), geometry: { type: 'Point', coordinates: [lon, lat] } }
    })
    return { type: 'FeatureCollection', features: [...shapes, ...labels] }
}

const facts = (sector: Sector) => ({ id: sector.id, name: sector.name, look: lookOf(sector) })

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
