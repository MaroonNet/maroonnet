import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { TRACKS } from './sample.ts'
import { groupColor, NO_GROUP_COLOR } from './teamWords.ts'
import { TracksContext, type Track } from './tracks.ts'
import TracksOnMap from './TracksOnMap.tsx'

// The map library's two pieces for drawing a line, as boxes that print what they were given.
vi.mock('react-map-gl/maplibre', () => ({
    Source: ({ data, children }: { data: unknown, children: unknown }) => <div data-testid="source">{JSON.stringify(data)}{children as never}</div>,
    Layer: ({ id, paint, layout }: { id: string, paint: unknown, layout: unknown }) => (
        <div data-testid="layer">{id} {JSON.stringify(paint)} {JSON.stringify(layout)}</div>
    ),
}))

afterEach(cleanup)

type Line = { properties: { radio: number, color: string }, geometry: { type: string, coordinates: number[][] } }

function draw(tracks: Track[], selected: number | null = null): Line[] {
    render(<TracksContext value={tracks}><TracksOnMap selected={selected} /></TracksContext>)
    return JSON.parse(screen.getByTestId('source').firstChild!.textContent!).features
}

const layer = () => screen.getByTestId('layer').textContent!

test("each piece of a track is a line in the color of the group the radio was in, grey for none", () => {
    const lines = draw(TRACKS)
    expect(lines.map((line) => line.properties)).toEqual([
        { radio: 1, color: groupColor(1) },
        { radio: 1, color: groupColor(3) },
        { radio: 4, color: groupColor(2) },
        { radio: 4, color: NO_GROUP_COLOR },
    ])
    expect(layer()).toContain('"line-color":["get","color"]')
})

test('a line goes through its points in order, as the backend sent them', () => {
    const lines = draw(TRACKS)
    expect(lines[0].geometry).toEqual({ type: 'LineString', coordinates: [[-110.677, 31.506], [-110.675, 31.508], [-110.673, 31.509]] })
})

test('a piece of one point is no line, so it is left off', () => {
    const lines = draw([{ radio_id: 2, pieces: [{ group_id: null, points: [[-110.677, 31.506]] }] }])
    expect(lines).toEqual([])
})

test('with no team selected every track is drawn alike', () => {
    draw(TRACKS)
    expect(layer()).toContain('"line-opacity":0.85')
})

test("the selected team's track is drawn stronger and on top, and the rest fade", () => {
    draw(TRACKS, 4)
    const isSelected = '["==",["get","radio"],4]'
    expect(layer()).toContain(`"line-width":["case",${isSelected},4.5,2.5]`)
    expect(layer()).toContain(`"line-opacity":["case",${isSelected},1,0.25]`)
    expect(layer()).toContain(`"line-sort-key":["case",${isSelected},1,0]`)
})
