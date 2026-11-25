import type { ExpressionSpecification, MapLayerMouseEvent } from 'maplibre-gl'
import type { Feature, FeatureCollection, Point, Polygon } from 'geojson'
import { useEffect } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import { SHOWN, type LayerChoice } from '../layers/missionLayers.ts'
import { polygonCenter } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { lookOf, mapLabel, sectorColor, STRIPES, stripesImage } from './looks.ts'
import { useSectors, type Sector } from './sectors.ts'

// The map reads each sector's look, color and label from the facts sent with its shape.
const COLOR: ExpressionSpecification = ['get', 'color']

type Props = {
    selected: number | null             // the id of the selected sector, drawn with a stronger outline
    onPick?: (id: number) => void       // given while a click on a sector picks it (the Select tool)
    hidden?: number | null              // a sector whose shape is being edited, drawn by the editing instead
    layer?: LayerChoice                 // the Layers panel's choice for Sectors: shown or not, and how solid
}

// The layer a click on a sector is read from: every sector, filled with nothing visible.
const HIT = 'sectors-hit'

// The saved sectors on the map: an outline in the look's color, a light fill for a
// completed sector (green) and one being searched (its group's color), orange stripes for
// a partial one, and the name in the middle, with the group for a sector a group holds. It
// is drawn inside the map (a child of MissionMap), above the search area line. Unticked in
// the Layers panel, its layers stay on the map and are switched off, so they keep their
// place under the tracks; a layer switched off takes no clicks.
function SectorsOnMap({ selected, onPick, hidden = null, layer = SHOWN }: Props) {
    const { sectors } = useSectors()
    useStripes()
    usePicking(onPick)
    const isSelected: ExpressionSpecification = ['==', ['get', 'id'], selected ?? -1]
    const shown = sectors.filter((sector) => sector.id !== hidden)
    const { opacity } = layer
    const visibility = layer.shown ? 'visible' : 'none'
    return (
        <Source id="sectors" type="geojson" data={sectorShapes(shown)}>
            <Layer id={HIT} type="fill" layout={{ visibility }} paint={{ 'fill-color': '#000000', 'fill-opacity': 0 }} />
            <Layer
                id="sectors-fill"
                type="fill"
                filter={['in', ['get', 'look'], ['literal', ['completed', 'searching']]]}
                layout={{ visibility }}
                paint={{ 'fill-color': COLOR, 'fill-opacity': 0.18 * opacity }}
            />
            <Layer
                id="sectors-stripes"
                type="fill"
                filter={['==', ['get', 'look'], 'partial']}
                layout={{ visibility }}
                paint={{ 'fill-pattern': STRIPES, 'fill-opacity': opacity }}
            />
            <Layer
                id="sectors-line"
                type="line"
                layout={{ visibility }}
                paint={{ 'line-color': COLOR, 'line-width': ['case', isSelected, 4, 2], 'line-opacity': opacity }}
            />
            <Layer
                id="sectors-label"
                type="symbol"
                filter={['==', ['geometry-type'], 'Point']}
                layout={{
                    visibility,
                    'text-field': ['get', 'label'],
                    'text-font': ['Noto Sans Bold'],  // one of the map style's own fonts
                    'text-size': 13,
                    'text-allow-overlap': true,  // a sector's name always shows
                }}
                paint={{ 'text-color': COLOR, 'text-halo-color': '#ffffff', 'text-halo-width': 1.5, 'text-opacity': opacity }}
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

const facts = (sector: Sector) => ({
    id: sector.id, name: sector.name, look: lookOf(sector), color: sectorColor(sector), label: mapLabel(sector),
})

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
