import { IconX } from '@tabler/icons-react'
import type { ReactNode } from 'react'

type Props = {
    title: string
    onClose: () => void
    children?: ReactNode    // the panel's contents, under the header
}

// The box that opens beside the rail, over the left of the map: a header with the title and
// a close button, then the contents, which scroll when they are taller than the screen.
function Panel({ title, onClose, children }: Props) {
    return (
        <aside className="absolute top-0 bottom-0 left-rail z-10 flex w-panel flex-col border-r border-ink bg-panel shadow-[4px_0_16px_rgb(32_30_24/0.22)]">
            <div className="flex h-header flex-none items-center border-b border-ink pr-2 pl-4">
                <h2 className="flex-1 text-title font-bold">{title}</h2>
                <button
                    type="button"
                    aria-label="Close panel"
                    title="Close panel"
                    onClick={onClose}
                    className="flex h-control w-control cursor-pointer items-center justify-center rounded-control hover:bg-strip"
                >
                    <IconX size={18} stroke={1.75} aria-hidden />
                </button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">{children}</div>
        </aside>
    )
}

export default Panel
