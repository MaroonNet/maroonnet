import { IconCheck, IconMapPinPlus, IconMarquee2, IconPointer, IconPolygon, IconRuler2, type Icon } from '@tabler/icons-react'
import { useEffect, useState, type ReactNode } from 'react'
import type { SectorShape } from '../map/drawSector.ts'

// The tools of the toolbar. One is picked at a time.
export type ToolId = 'select' | 'sector' | 'search-area' | 'measure' | 'waypoint'

// key: the keyboard key that picks the tool. tip: what its tooltip shows beside the name,
// when that is more than the key.
const TOOLS: { id: ToolId, label: string, key: string, tip?: string, icon: Icon }[] = [
    { id: 'select', label: 'Select', key: 'V', icon: IconPointer },
    { id: 'sector', label: 'Draw Sector', key: 'D', tip: 'D · right-click for shapes', icon: IconPolygon },
    { id: 'search-area', label: 'Draw Search Area', key: 'A', icon: IconMarquee2 },
    { id: 'measure', label: 'Measure', key: 'M', icon: IconRuler2 },
    { id: 'waypoint', label: 'Drop Waypoint', key: 'W', icon: IconMapPinPlus },
]

// The shapes the Draw Sector tool draws, in its right-click menu.
const SHAPES: { id: SectorShape, label: string }[] = [
    { id: 'rectangle', label: 'Rectangle' },
    { id: 'custom', label: 'Custom shape' },
]

type Props = {
    tool: ToolId                    // the picked tool
    onPick: (id: ToolId) => void
    // The tools that cannot be picked now, each with the reason its tooltip gives.
    greyed?: Partial<Record<ToolId, string>>
    sectorShape?: SectorShape                   // the shape Draw Sector draws
    onPickShape?: (shape: SectorShape) => void  // a shape was picked from its menu
    children?: ReactNode    // drawn at the end of the row: a tool's own buttons, such as Undo
}

const NONE_GREYED = {}

// The row of map tools at the top left of the map. Each tool shows a tooltip with its name
// and key while the pointer is over it or the keyboard focus is on it. A right-click on
// Draw Sector opens a small menu of the shapes it draws.
function Toolbar({ tool, onPick, greyed = NONE_GREYED, sectorShape = 'rectangle', onPickShape, children }: Props) {
    const [tipFor, setTipFor] = useState<ToolId | null>(null)  // the tool whose tooltip shows
    const [menuOpen, setMenuOpen] = useState(false)  // Draw Sector's shape menu

    // A tool's key picks it from anywhere on the page. The listener is added when the toolbar
    // appears and taken away when it goes.
    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.ctrlKey || event.metaKey || event.altKey) return  // a shortcut such as paste
            if (isTextBox(event.target)) return  // the key is being typed
            const picked = TOOLS.find((t) => t.key.toLowerCase() === event.key.toLowerCase())
            if (picked && !greyed[picked.id]) onPick(picked.id)
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [onPick, greyed])

    // While the shape menu is open, Escape or a press anywhere outside it closes it.
    useEffect(() => {
        if (!menuOpen) return
        const close = () => setMenuOpen(false)
        const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
        window.addEventListener('pointerdown', close)
        window.addEventListener('keydown', onKeyDown)
        return () => {
            window.removeEventListener('pointerdown', close)
            window.removeEventListener('keydown', onKeyDown)
        }
    }, [menuOpen])

    function pickShape(shape: SectorShape) {
        setMenuOpen(false)
        onPickShape?.(shape)
        onPick('sector')
    }

    return (
        <div className="flex items-center gap-0.5 rounded-box bg-panel p-1 shadow-[0_1px_6px_rgb(32_30_24/0.25)]">
            {TOOLS.map(({ id, label, key, tip, icon: ToolIcon }) => (
                <div key={id} className="relative">
                    <button
                        type="button"
                        aria-label={label}
                        aria-pressed={tool === id}
                        aria-keyshortcuts={key}
                        aria-disabled={greyed[id] ? true : undefined}
                        onClick={greyed[id] ? undefined : () => onPick(id)}
                        onContextMenu={id === 'sector' ? (event) => {
                            event.preventDefault()  // no browser menu
                            if (!greyed[id]) {
                                setTipFor(null)
                                setMenuOpen(true)
                            }
                        } : undefined}
                        onMouseEnter={() => setTipFor(id)}
                        onMouseLeave={() => setTipFor(null)}
                        onFocus={() => setTipFor(id)}
                        onBlur={() => setTipFor(null)}
                        className={`flex h-control w-control items-center justify-center rounded-control ${greyed[id] ? 'opacity-40' : tool === id ? 'cursor-pointer bg-strip' : 'cursor-pointer hover:bg-strip'}`}
                    >
                        <ToolIcon size={18} stroke={1.75} aria-hidden />
                    </button>
                    {tipFor === id && !(id === 'sector' && menuOpen) && (
                        <div
                            role="tooltip"
                            className="pointer-events-none absolute top-full left-0 z-10 mt-2.5 flex items-baseline gap-2 rounded-control bg-ink px-2.5 py-1.5 whitespace-nowrap text-panel shadow-[0_2px_8px_rgb(32_30_24/0.25)]"
                        >
                            {label}
                            <span className="font-mono text-label font-medium opacity-70">{greyed[id] ?? tip ?? key}</span>
                        </div>
                    )}
                    {id === 'sector' && menuOpen && (
                        // A press inside the menu is kept from the window, so it does not close it first.
                        <div
                            role="menu"
                            aria-label="Sector shape"
                            onPointerDown={(event) => event.stopPropagation()}
                            className="absolute top-full left-0 z-20 mt-2.5 flex w-40 flex-col rounded-box border border-ink bg-panel p-1 shadow-[0_2px_10px_rgb(32_30_24/0.22)]"
                        >
                            {SHAPES.map((shape) => (
                                <button
                                    key={shape.id}
                                    type="button"
                                    role="menuitemradio"
                                    aria-checked={sectorShape === shape.id}
                                    onClick={() => pickShape(shape.id)}
                                    className={`flex h-control cursor-pointer items-center gap-2 rounded-control px-2 text-left ${sectorShape === shape.id ? 'bg-strip' : 'hover:bg-strip'}`}
                                >
                                    <span className="w-4">{sectorShape === shape.id && <IconCheck size={14} stroke={2} aria-hidden />}</span>
                                    {shape.label}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            ))}
            {children}
        </div>
    )
}

// Whether a key pressed here is text being typed: a text input, a text area, a drop-down,
// or any element the user can edit. A checkbox or a slider is not.
function isTextBox(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    if (target.isContentEditable) return true
    if (target instanceof HTMLInputElement) return !['checkbox', 'radio', 'range', 'button'].includes(target.type)
    return target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement
}

export default Toolbar
