import type { Bounds } from '../map/geo.ts'
import type { Box, InstalledPack } from './packs.ts'

// Pieces the setup tests build installed packs from.

// A complete pack. Its id says what it is: "state/AZ/terrain", "mission/arizona07".
export function pack(id: string, area: Box[]): InstalledPack {
    const [place, , last] = id.split('/')
    return {
        id, kind: place === 'state' ? 'state' : 'mission', contents: last === 'basemap' ? 'basemap' : 'terrain',
        name: id, area, min_zoom: 0, max_zoom: 12, data_date: null, downloaded: '2026-11-24', bytes: 1000, status: 'complete',
    }
}

// The Arizona state pack: its basemap and its terrain.
const ARIZONA_BOX: Box = [-114.82, 31.33, -109.04, 37.01]
export const ARIZONA: InstalledPack[] = [pack('state/AZ/basemap', [ARIZONA_BOX]), pack('state/AZ/terrain', [ARIZONA_BOX])]

// Arizona07's mission pack and its search area, which lies inside it.
export const ARIZONA07_PACK = pack('mission/arizona07', [[-110.9404, 31.2794, -110.4118, 31.7322]])
export const ARIZONA07_AREA: Bounds = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }
