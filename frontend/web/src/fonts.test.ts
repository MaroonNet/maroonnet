import { expect, test } from 'vitest'

// The rule for the two fonts (index.css): the mono font draws only the small capital labels
// (text-label), such as section headings and table headers. Figures, such as positions,
// sizes, times and counts, are in the text font, so every zero and every digit looks alike.

// Every component's source, as text; the tests are left out.
const sources = import.meta.glob(['./**/*.{ts,tsx}', '!./**/*.test.{ts,tsx}'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>

test('the mono font draws only the small capital labels', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(50)  // the sources were found
    const monoFigures = Object.entries(sources).flatMap(([file, text]) => text.split('\n').flatMap((line, index) =>
        line.includes('font-mono') && !line.includes('text-label') ? [`${file}:${index + 1}`] : []))
    expect(monoFigures).toEqual([])
})
