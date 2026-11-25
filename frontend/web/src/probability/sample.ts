import type { ModelStatus, Overlay, ProbabilityBoard } from './probability.ts'

// Pieces the tests build probability maps and a probability board from.

// A map made at this time of 2026-11-25 (UTC), for a hiker, over the ground around Arizona07.
export function overlay(time: string): Overlay {
    const id = `20261125-${time}_hiker`
    return {
        id,
        image: `/api/spm/predictions/${id}/overlay.png`,
        coordinates: [[-110.808, 31.619], [-110.544, 31.619], [-110.544, 31.393], [-110.808, 31.393]],
    }
}

// The model as the demo laptop has it: two fitted models, each drawing hikers only.
export const READY: ModelStatus = { available: true, detail: 'ok', models: { hybrid: ['hiker'], model_a: ['hiker'] } }

// A board holding this map, or none, whose make does nothing and answers that it failed
// unless a test gives its own.
export function board(newest: Overlay | null, make: ProbabilityBoard['make'] = async () => 'Not in this test.'): ProbabilityBoard {
    return { newest, make }
}
