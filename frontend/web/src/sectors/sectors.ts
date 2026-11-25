import { createContext, useContext } from 'react'
import type { Position } from '../map/geo.ts'
import { ask } from '../mission/mission.ts'

// A sector as the backend answers it (backend/sectors/routes.py).
export type Sector = {
    id: number
    name: string                // S and its number: "S4"
    status: 'drawn' | 'searching' | 'partial' | 'completed'
    corners: Position[]         // in order; the last joins back to the first
    group_id: number | null     // the group that holds it now, or none
    can_edit: boolean           // its shape can be changed and it can be deleted
    created_time: string        // UTC
    completed_time: string | null
}

export const loadSectors = () => ask<Sector[]>('/api/mission/sectors')
// Saves a new sector, drawn and with no group. Answers with it as saved, with its number.
export const addSector = (corners: Position[]) => ask<Sector>('/api/mission/sectors', 'POST', { corners })
// Gives a never-assigned sector a new shape. Answers with it as saved.
export const changeSectorShape = (id: number, corners: Position[]) => ask<Sector>(`/api/mission/sectors/${id}/corners`, 'PUT', { corners })
// Deletes a never-assigned sector.
export const deleteSector = (id: number) => ask<null>(`/api/mission/sectors/${id}`, 'DELETE')

// The board: the open mission's sectors, kept in one place that any component can read.
// Each change answers with nothing when it worked, and with the reason when it did not; the
// board changes only when it worked, so the screen always shows what is saved.
export type SectorsBoard = {
    sectors: Sector[]           // in number order; none while no mission is open
    loadedFor: string | null    // the id of the mission the sectors were read for; none until read
    add: (corners: Position[]) => Promise<string>                       // a new sector
    changeShape: (id: number, corners: Position[]) => Promise<string>   // Edit Shape's Done
    remove: (id: number) => Promise<string>                             // Delete
}

// A component drawn with no SectorsProvider above it, as in a test of one component, reads
// this board: no sectors, and nothing can be saved.
const NO_BOARD = 'There is no sectors board.'
export const SectorsContext = createContext<SectorsBoard>({
    sectors: [],
    loadedFor: null,
    add: async () => NO_BOARD,
    changeShape: async () => NO_BOARD,
    remove: async () => NO_BOARD,
})

// What a component calls to read the board.
export function useSectors(): SectorsBoard {
    return useContext(SectorsContext)
}
