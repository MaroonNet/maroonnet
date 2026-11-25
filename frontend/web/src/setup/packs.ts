import { ask } from '../mission/mission.ts'

// One box of ground: [west, south, east, north], in degrees.
export type Box = [number, number, number, number]

// An installed map pack, as the backend lists it (backend/maps/routes.py). A state pack is
// two of these, its basemap and its terrain; a mission pack is terrain only.
export type InstalledPack = {
    id: string                      // "state/AZ/terrain", "mission/arizona07"
    kind: 'state' | 'mission'
    contents: 'basemap' | 'terrain'
    name: string
    area: Box[]                     // the ground it covers
    min_zoom: number
    max_zoom: number
    data_date: string | null        // how old the map data is; none when unknown
    downloaded: string
    bytes: number
    status: 'complete' | 'partial'  // a partial pack serves no tiles
}

export const loadPacks = () => ask<InstalledPack[]>('/api/maps/packs')
