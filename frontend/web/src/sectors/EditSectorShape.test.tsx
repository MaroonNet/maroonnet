import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Bounds, Position } from '../map/geo.ts'
import { SearchAreaContext } from '../searchArea/searchArea.ts'
import { SettingsContext } from '../settings/settings.ts'
import EditSectorShape from './EditSectorShape.tsx'
import { NEVER_HELD, NO_LIFE } from './sample.ts'
import { SectorsContext, type Sector } from './sectors.ts'

// The real drawing needs a real map. This stand-in keeps what the tool handed it, so a test
// can play the user: change(...) is a corner dragged or added, full() a 25th corner refused.
type Listeners = { change: (corners: Position[]) => void, full: () => void }
const drawing = vi.hoisted(() => ({
    on: null as unknown as Listeners,
    area: null as unknown,
    shape: '',
    discard: vi.fn(), stop: vi.fn(), edit: vi.fn(),
    map: {},
}))
vi.mock('../map/drawSector.ts', () => ({
    drawSector: (_map: unknown, area: unknown, shape: string, on: Listeners) => {
        drawing.on = on
        drawing.area = area
        drawing.shape = shape
        return { discard: drawing.discard, stop: drawing.stop, edit: drawing.edit }
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => drawing.map }))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
})

const ARIZONA07_AREA: Bounds = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }
const S7_CORNERS: Position[] = [[31.510046, -110.679325], [31.513835, -110.679272], [31.515188, -110.676638], [31.515278, -110.672002],
    [31.513925, -110.668209], [31.510948, -110.667893], [31.509280, -110.671791], [31.510633, -110.675585], [31.510588, -110.677481]]
    .map(([lat, lon]) => ({ lat, lon }))
const S7: Sector = {
    id: 7, name: 'S7', status: 'drawn', group_id: null, can_edit: true, corners: S7_CORNERS,
    created_time: '2025-04-14T08:02:00Z', completed_time: null, ...NEVER_HELD,
}

function editTool(changeShape = vi.fn(async (_id: number, _corners: Position[]) => '')) {
    const onClose = vi.fn()
    function Screen() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)
        return (
            <SettingsContext value={{ settings: { units: 'metric' }, loadFailed: false, change: async () => false }}>
                <SearchAreaContext value={{ area: ARIZONA07_AREA, loadedFor: 'az07', save: async () => '' }}>
                    <SectorsContext value={{ sectors: [S7], loadedFor: 'az07', add: async () => '', changeShape, remove: async () => '', ...NO_LIFE }}>
                        <div ref={setHintSlot} />
                        <EditSectorShape id={7} hintSlot={hintSlot} onClose={onClose} />
                    </SectorsContext>
                </SearchAreaContext>
            </SettingsContext>
        )
    }
    render(<Screen />)
    return { changeShape, onClose }
}
const hint = () => screen.getByRole('status').textContent
const fact = (label: string) => screen.getByText(label).nextSibling?.textContent

test("the sector's shape is put on the map with its corners ready to drag, inside the search area", () => {
    editTool()
    expect(drawing.area).toEqual(ARIZONA07_AREA)
    expect(drawing.edit).toHaveBeenCalledWith(S7_CORNERS)
    expect(screen.getByRole('heading', { name: 'Edit Sector S7' })).toBeTruthy()
    expect(fact('Points')).toBe('9')
    expect(fact('Area')).toBe('0.55 km²')
    expect(hint()).toBe("0.55 km²Drag a corner to move it, or a side's middle to add a corner. Then press Done.")
})

test('dragging or adding a corner changes the figures', () => {
    editTool()
    act(() => drawing.on.change([...S7_CORNERS, { lat: 31.509, lon: -110.678 }]))
    expect(fact('Points')).toBe('10')
})

test('a 25th corner is refused, and the hint line says so', () => {
    editTool()
    act(() => drawing.on.full())
    expect(hint()).toBe('0.55 km²A sector has at most 24 corners.')
})

test('Done saves the new shape and the editing ends', async () => {
    const { changeShape, onClose } = editTool()
    const moved = [{ lat: 31.51, lon: -110.68 }, ...S7_CORNERS.slice(1)]
    act(() => drawing.on.change(moved))

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
    expect(changeShape).toHaveBeenCalledWith(7, moved)
})

test('a refused save keeps the editing, and the card says why', async () => {
    const { onClose } = editTool(vi.fn(async () => 'S7 has been assigned, so its shape cannot be changed.'))

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    expect((await screen.findByRole('alert')).textContent).toBe('S7 has been assigned, so its shape cannot be changed.')
    expect(onClose).not.toHaveBeenCalled()
})

test('Cancel, or Escape, ends the editing and saves nothing', () => {
    const { changeShape, onClose } = editTool()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(2)
    expect(changeShape).not.toHaveBeenCalled()
})

test('leaving the editing stops the drawing', () => {
    editTool()
    cleanup()
    expect(drawing.stop).toHaveBeenCalledOnce()
})
