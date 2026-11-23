import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Card from './Card.tsx'
import HintLine from './HintLine.tsx'
import Toolbar from './Toolbar.tsx'

afterEach(cleanup)  // clear the page between tests

test('pressing V picks the Select tool', () => {
    const onPick = vi.fn()  // a stand-in function that records how it was called
    render(<Toolbar tool="select" onPick={onPick} />)
    fireEvent.keyDown(document.body, { key: 'v' })
    expect(onPick).toHaveBeenCalledWith('select')
})

test('a V typed into a text box picks nothing', () => {
    const onPick = vi.fn()
    render(<><Toolbar tool="select" onPick={onPick} /><input aria-label="Name" /></>)
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Name' }), { key: 'v' })
    expect(onPick).not.toHaveBeenCalled()
})

test('V with Ctrl or Cmd held picks nothing, so pasting still works', () => {
    const onPick = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} />)
    fireEvent.keyDown(document.body, { key: 'v', ctrlKey: true })
    fireEvent.keyDown(document.body, { key: 'v', metaKey: true })
    expect(onPick).not.toHaveBeenCalled()
})

test('the card shows its title and its contents', () => {
    render(<Card title="New Sector"><p>4 points</p></Card>)
    expect(screen.getByRole('heading', { name: 'New Sector' })).toBeTruthy()
    expect(screen.getByText('4 points')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()  // no close button unless it is asked for
})

test('a card that can be closed has a close button', () => {
    const onClose = vi.fn()
    render(<Card title="Selected" onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Close card' }))
    expect(onClose).toHaveBeenCalledOnce()
})

test('the hint line says what to do next, with a running figure before it when there is one', () => {
    render(<HintLine text="Click the end point." figure="1.2 mi" />)
    expect(screen.getByRole('status').textContent).toBe('1.2 miClick the end point.')
    cleanup()
    render(<HintLine text="Click the start point." />)
    expect(screen.getByRole('status').textContent).toBe('Click the start point.')
})
