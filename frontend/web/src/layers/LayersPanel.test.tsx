import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import LayersPanel from './LayersPanel.tsx'
import { AS_OPENED, type MissionLayerChoices } from './missionLayers.ts'

afterEach(cleanup)

// The panel with one basemap group, and the mission layers as given. Answers with the
// function the panel calls to change the mission layers.
function show(missionLayers: MissionLayerChoices = AS_OPENED) {
    const setMissionLayers = vi.fn()
    render(
        <LayersPanel
            groups={[{ id: 'contours', label: 'Contours' }]}
            hidden={[]}
            setHidden={() => {}}
            trailUses={[]}
            pickedUses={[]}
            setPickedUses={() => {}}
            missionLayers={missionLayers}
            setMissionLayers={setMissionLayers}
        />,
    )
    return setMissionLayers
}

const box = (name: string) => screen.getByRole('checkbox', { name }) as HTMLInputElement

test('the mission layers are listed above the basemap rows: four ticked, the heatmap not', () => {
    show()
    expect(screen.getAllByRole('heading').map((heading) => heading.textContent)).toEqual(['Mission', 'Basemap'])
    const rows = screen.getAllByRole('checkbox').map((one) => [one.parentElement!.textContent, (one as HTMLInputElement).checked])
    expect(rows).toEqual([
        ['Sectors', true], ['Team positions', true], ['Tracks walked', true], ['Waypoints', true],
        ['Probability heatmap', false], ['Contours', true],
    ])
})

test('unticking a mission layer hides that layer and leaves the rest', () => {
    const setMissionLayers = show()
    fireEvent.click(box('Tracks walked'))
    expect(setMissionLayers).toHaveBeenCalledWith({ ...AS_OPENED, tracks: { shown: false, opacity: 1 } })
})

test('ticking the heatmap shows it', () => {
    const setMissionLayers = show()
    fireEvent.click(box('Probability heatmap'))
    expect(setMissionLayers).toHaveBeenCalledWith({ ...AS_OPENED, heatmap: { shown: true, opacity: 1 } })
})

test("a row's arrow opens its opacity slider, which reads the layer's opacity", () => {
    show({ ...AS_OPENED, sectors: { shown: true, opacity: 0.4 } })
    expect(screen.queryByRole('slider')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Opacity of Sectors' }))
    expect((screen.getByRole('slider', { name: 'Opacity of Sectors' }) as HTMLInputElement).value).toBe('40')
    expect(screen.getByText('40%')).toBeTruthy()
})

test('moving the slider changes that layer\'s opacity and nothing else', () => {
    const setMissionLayers = show()
    fireEvent.click(screen.getByRole('button', { name: 'Opacity of Probability heatmap' }))
    fireEvent.change(screen.getByRole('slider'), { target: { value: '65' } })
    expect(setMissionLayers).toHaveBeenCalledWith({ ...AS_OPENED, heatmap: { shown: false, opacity: 0.65 } })
})

test('one slider is open at a time, and pressing the open row\'s arrow closes it', () => {
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Opacity of Sectors' }))
    fireEvent.click(screen.getByRole('button', { name: 'Opacity of Waypoints' }))
    expect(screen.getAllByRole('slider').map((one) => one.getAttribute('aria-label'))).toEqual(['Opacity of Waypoints'])
    fireEvent.click(screen.getByRole('button', { name: 'Opacity of Waypoints' }))
    expect(screen.queryByRole('slider')).toBeNull()
})

test('the basemap rows have a checkbox only', () => {
    show()
    expect(screen.queryByRole('button', { name: 'Opacity of Contours' })).toBeNull()
})
