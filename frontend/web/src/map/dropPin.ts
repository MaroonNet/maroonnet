import { Marker, type Map as MapLibreMap, type MapMouseEvent } from 'maplibre-gl'
import type { Position } from './geo.ts'

// A pin being placed on the map.
export type Pin = {
    clear: () => void   // takes the pin off the map; the next click places it again
    stop: () => void    // ends the placing: the pin goes, and a click is an ordinary click again
}

type Listeners = {
    move: (position: Position) => void  // where the pin is now: after a click, and while it is dragged
}

// Lets the user place one pin: a click on the map puts it there, a click elsewhere moves
// it, and it can be dragged. element is what the pin looks like; the caller draws into it.
// The pin hangs from its bottom, so the tip of its point is the place.
// start: where the pin already is, when a saved waypoint is being moved.
export function dropPin(map: MapLibreMap, element: HTMLElement, on: Listeners, start?: Position): Pin {
    const marker = new Marker({ element, draggable: true, anchor: 'bottom' })
    const place = (position: Position) => marker.setLngLat([position.lon, position.lat]).addTo(map)
    const report = () => {
        const { lat, lng } = marker.getLngLat()
        on.move({ lat, lon: lng })
    }
    const onClick = (event: MapMouseEvent) => {
        place({ lat: event.lngLat.lat, lon: event.lngLat.lng })
        report()
    }

    // A click on the pin itself is not a click on the map, which would move the pin's
    // point to the pointer.
    const keepFromMap = (event: MouseEvent) => event.stopPropagation()

    if (start) place(start)
    marker.on('drag', report)
    map.on('click', onClick)
    element.addEventListener('click', keepFromMap)
    const canvas = map.getCanvas()
    canvas.style.cursor = 'crosshair'

    return {
        clear() {
            marker.remove()
        },
        stop() {
            marker.remove()
            map.off('click', onClick)
            element.removeEventListener('click', keepFromMap)
            canvas.style.cursor = ''
        },
    }
}
