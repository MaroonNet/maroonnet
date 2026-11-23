import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.tsx'

// The real map needs the backend and a real browser, so the tests draw an empty box in its place.
vi.mock('./map/MissionMap.tsx', () => ({ default: () => <div /> }))

afterEach(cleanup)  // clear the page between tests

test('the rail shows the Mission block, the nine buttons and Settings', () => {
    render(<App />)
    const labels = ['Groups & Teams', 'People', 'Sectors', 'Area', 'Alerts', 'Mesh', 'Layers', 'Maps', 'AAR']
    for (const label of labels) {
        expect(screen.getByRole('button', { name: label })).toBeTruthy()
    }
    expect(screen.getByRole('button', { name: /Mission/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeTruthy()
})

test('pressing Layers opens a panel titled "Map Layers"', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    expect(screen.getByRole('heading', { name: 'Map Layers' })).toBeTruthy()
})

test('pressing Layers again closes the panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    expect(screen.queryByRole('heading', { name: 'Map Layers' })).toBeNull()
})

test('the × button closes the panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(screen.queryByRole('heading', { name: 'Map Layers' })).toBeNull()
})

test('a greyed button opens nothing and says "Not available yet"', () => {
    render(<App />)
    const people = screen.getByRole('button', { name: 'People' })
    expect(people.title).toBe('Not available yet')
    expect(people.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(people)
    expect(screen.queryByRole('heading')).toBeNull()
})
