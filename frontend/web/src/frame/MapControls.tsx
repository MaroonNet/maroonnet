import { IconMinus, IconPlus, type Icon } from '@tabler/icons-react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import { useMissionMap } from '../map/missionMap.ts'
import { useSettings, type Units } from '../settings/settings.ts'
import CenterOnCommandPost from '../waypoints/CenterOnCommandPost.tsx'
import Legend, { BOX } from './Legend.tsx'
import { metersPerPixel, scaleBar } from './scaleBar.ts'

const SCALE_MAX = 170  // the widest the scale bar is drawn, in pixels

// The controls at the bottom right of the map. They show once the map exists.
function MapControls() {
    const map = useMissionMap()
    return map && <Controls map={map} />
}

// The controls, raised to sit above the map's credits line in the corner. The stack itself
// lets the pointer through to the map; only the boxes in it take presses.
function Controls({ map }: { map: MapLibreMap }) {
    // Where the map is now. It is read again each time the map moves, so the zoom buttons
    // and the scale bar follow it.
    const [view, setView] = useState(() => readView(map))
    const { settings } = useSettings()

    useEffect(() => {
        function onMove() {
            setView(readView(map))
        }
        map.on('move', onMove)
        return () => { map.off('move', onMove) }
    }, [map])

    return (
        <div className="pointer-events-none absolute right-3.5 bottom-11 z-10 flex flex-col items-end gap-2.5">
            <CenterOnCommandPost map={map} />
            <div className={`flex w-11 flex-col divide-y divide-ink overflow-hidden rounded-box ${BOX}`}>
                <ZoomButton label="Zoom in" icon={IconPlus} atLimit={view.zoom >= map.getMaxZoom()} onPress={() => map.zoomIn()} />
                <ZoomButton label="Zoom out" icon={IconMinus} atLimit={view.zoom <= map.getMinZoom()} onPress={() => map.zoomOut()} />
            </div>
            <div className="flex items-end gap-2.5">
                <ScaleBar groundPerPixel={metersPerPixel(view.latitude, view.zoom)} units={settings.units} />
                <Legend />
            </div>
        </div>
    )
}

function readView(map: MapLibreMap): { zoom: number, latitude: number } {
    return { zoom: map.getZoom(), latitude: map.getCenter().lat }
}

type ZoomButtonProps = {
    label: string
    icon: Icon
    atLimit: boolean        // the map cannot zoom further this way
    onPress: () => void
}

// One zoom button. At its limit it is greyed out and a press does nothing.
function ZoomButton({ label, icon: ButtonIcon, atLimit, onPress }: ZoomButtonProps) {
    return (
        <button
            type="button"
            aria-label={label}
            aria-disabled={atLimit}
            title={label}
            onClick={atLimit ? undefined : onPress}
            className={`flex h-10.5 items-center justify-center ${atLimit ? 'opacity-40' : 'cursor-pointer hover:bg-strip'}`}
        >
            <ButtonIcon size={18} stroke={1.75} aria-hidden />
        </button>
    )
}

// A bar as wide as a round distance on the ground, with that distance written in it, in the
// units the Units setting names. groundPerPixel is how many meters of ground one screen
// pixel covers.
function ScaleBar({ groundPerPixel, units }: { groundPerPixel: number, units: Units }) {
    const { label, width } = scaleBar(groundPerPixel, SCALE_MAX, units)
    return (
        <div
            title="Map scale"
            style={{ width }}
            className="mb-1 flex h-6 items-center border-x-[3px] border-b-[3px] border-ink bg-panel/85 px-2 text-input font-medium whitespace-nowrap"
        >
            {label}
        </div>
    )
}

export default MapControls
