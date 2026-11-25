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

test('pressing A, or the tool itself, picks the Draw Search Area tool', () => {
    const onPick = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} />)
    fireEvent.keyDown(document.body, { key: 'a' })
    fireEvent.click(screen.getByRole('button', { name: 'Draw Search Area' }))
    expect(onPick.mock.calls).toEqual([['search-area'], ['search-area']])
})

test('pressing M, or the tool itself, picks the Measure tool', () => {
    const onPick = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} />)
    fireEvent.keyDown(document.body, { key: 'm' })
    fireEvent.click(screen.getByRole('button', { name: 'Measure' }))
    expect(onPick.mock.calls).toEqual([['measure'], ['measure']])
})

test('pressing D, or the tool itself, picks the Draw Sector tool', () => {
    const onPick = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} />)
    fireEvent.keyDown(document.body, { key: 'd' })
    fireEvent.click(screen.getByRole('button', { name: 'Draw Sector' }))
    expect(onPick.mock.calls).toEqual([['sector'], ['sector']])
})

test('the tools run Select, Draw Sector, Draw Search Area, Measure', () => {
    render(<Toolbar tool="select" onPick={() => {}} />)
    expect(screen.getAllByRole('button').map((button) => button.getAttribute('aria-label')))
        .toEqual(['Select', 'Draw Sector', 'Draw Search Area', 'Measure'])
})

test("the Draw Sector tool's tooltip says a right-click offers the shapes", () => {
    render(<Toolbar tool="select" onPick={() => {}} />)
    fireEvent.mouseEnter(screen.getByRole('button', { name: 'Draw Sector' }))
    expect(screen.getByRole('tooltip').textContent).toBe('Draw SectorD · right-click for shapes')
})

test('a right-click on Draw Sector opens the shape menu, with the picked shape ticked', () => {
    render(<Toolbar tool="select" onPick={() => {}} sectorShape="rectangle" onPickShape={() => {}} />)
    fireEvent.contextMenu(screen.getByRole('button', { name: 'Draw Sector' }))
    const items = screen.getAllByRole('menuitemradio')
    expect(items.map((item) => [item.textContent, item.getAttribute('aria-checked')]))
        .toEqual([['Rectangle', 'true'], ['Custom shape', 'false']])
})

test('picking Custom shape from the menu picks that shape and the tool, and closes the menu', () => {
    const onPick = vi.fn(), onPickShape = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} sectorShape="rectangle" onPickShape={onPickShape} />)
    fireEvent.contextMenu(screen.getByRole('button', { name: 'Draw Sector' }))

    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Custom shape' }))

    expect(onPickShape).toHaveBeenCalledWith('custom')
    expect(onPick).toHaveBeenCalledWith('sector')
    expect(screen.queryByRole('menu')).toBeNull()
})

test('Escape, or a press anywhere else, closes the shape menu', () => {
    render(<Toolbar tool="select" onPick={() => {}} sectorShape="rectangle" onPickShape={() => {}} />)
    const tool = screen.getByRole('button', { name: 'Draw Sector' })
    fireEvent.contextMenu(tool)
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()

    fireEvent.contextMenu(tool)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
})

test('a right-click on a greyed Draw Sector opens no menu', () => {
    render(<Toolbar tool="select" onPick={() => {}} greyed={{ sector: 'Draw a search area first' }} sectorShape="rectangle" onPickShape={() => {}} />)
    fireEvent.contextMenu(screen.getByRole('button', { name: 'Draw Sector' }))
    expect(screen.queryByRole('menu')).toBeNull()
})

test('a greyed tool is not picked by a press or by its key, and its tooltip says why', () => {
    const onPick = vi.fn()
    render(<Toolbar tool="select" onPick={onPick} greyed={{ 'search-area': 'Open a mission first' }} />)
    const tool = screen.getByRole('button', { name: 'Draw Search Area' })
    expect(tool.getAttribute('aria-disabled')).toBe('true')

    fireEvent.click(tool)
    fireEvent.keyDown(document.body, { key: 'a' })
    expect(onPick).not.toHaveBeenCalled()

    fireEvent.mouseEnter(tool)
    expect(screen.getByRole('tooltip').textContent).toBe('Draw Search AreaOpen a mission first')
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
