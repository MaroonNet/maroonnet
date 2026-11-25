import type { Sector, SectorsBoard } from './sectors.ts'

// Pieces the tests build a sector and a sectors board from.

// What a sector that no group holds or has held answers for its later life.
export const NEVER_HELD: Pick<Sector, 'assigned_time' | 'entered_time' | 'completed_by' | 'sends'> = {
    assigned_time: null, entered_time: null, completed_by: null, sends: [],
}

// A board's four changes to a sector's life, each doing nothing and answering that it worked.
export const NO_LIFE: Pick<SectorsBoard, 'assign' | 'release' | 'markEntered' | 'complete'> = {
    assign: async () => '', release: async () => '', markEntered: async () => '', complete: async () => '',
}

const SQUARE = [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }, { lat: 31.5, lon: -110.69 }]

// A sector drawn at 8:35 pm Arizona time. A completed one was completed at 1:21 am.
export function sector(id: number, status: Sector['status'], extra: Partial<Sector> = {}): Sector {
    return {
        id, name: `S${id}`, status, group_id: null, can_edit: false, corners: SQUARE, ...NEVER_HELD,
        created_time: '2025-04-14T03:35:00Z', completed_time: status === 'completed' ? '2025-04-14T08:21:45Z' : null, ...extra,
    }
}

// A sector a group holds, given to it at 8:50 pm.
export const held = (id: number, status: Sector['status'], group_id: number, extra: Partial<Sector> = {}) =>
    sector(id, status, { group_id, assigned_time: '2025-04-14T03:50:00Z', ...extra })
