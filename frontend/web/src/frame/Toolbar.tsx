import { IconMarquee2, IconPointer, type Icon } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

// The tools of the toolbar. One is picked at a time.
export type ToolId = 'select' | 'search-area'

// key: the keyboard key that picks the tool, shown in its tooltip.
const TOOLS: { id: ToolId, label: string, key: string, icon: Icon }[] = [
    { id: 'select', label: 'Select', key: 'V', icon: IconPointer },
    { id: 'search-area', label: 'Draw Search Area', key: 'A', icon: IconMarquee2 },
]

type Props = {
    tool: ToolId                    // the picked tool
    onPick: (id: ToolId) => void
    // The tools that cannot be picked now, each with the reason its tooltip gives.
    greyed?: Partial<Record<ToolId, string>>
}

const NONE_GREYED = {}

// The row of map tools at the top left of the map. Each tool shows a tooltip with its name
// and key while the pointer is over it or the keyboard focus is on it.
function Toolbar({ tool, onPick, greyed = NONE_GREYED }: Props) {
    const [tipFor, setTipFor] = useState<ToolId | null>(null)  // the tool whose tooltip shows

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

    return (
        <div className="flex items-center gap-0.5 rounded-box bg-panel p-1 shadow-[0_1px_6px_rgb(32_30_24/0.25)]">
            {TOOLS.map(({ id, label, key, icon: ToolIcon }) => (
                <div key={id} className="relative">
                    <button
                        type="button"
                        aria-label={label}
                        aria-pressed={tool === id}
                        aria-keyshortcuts={key}
                        aria-disabled={greyed[id] ? true : undefined}
                        onClick={greyed[id] ? undefined : () => onPick(id)}
                        onMouseEnter={() => setTipFor(id)}
                        onMouseLeave={() => setTipFor(null)}
                        onFocus={() => setTipFor(id)}
                        onBlur={() => setTipFor(null)}
                        className={`flex h-control w-control items-center justify-center rounded-control ${greyed[id] ? 'opacity-40' : tool === id ? 'cursor-pointer bg-strip' : 'cursor-pointer hover:bg-strip'}`}
                    >
                        <ToolIcon size={18} stroke={1.75} aria-hidden />
                    </button>
                    {tipFor === id && (
                        <div
                            role="tooltip"
                            className="pointer-events-none absolute top-full left-0 z-10 mt-2.5 flex items-baseline gap-2 rounded-control bg-ink px-2.5 py-1.5 whitespace-nowrap text-panel shadow-[0_2px_8px_rgb(32_30_24/0.25)]"
                        >
                            {label}
                            <span className="font-mono text-label font-medium opacity-70">{greyed[id] ?? key}</span>
                        </div>
                    )}
                </div>
            ))}
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
