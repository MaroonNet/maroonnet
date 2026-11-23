import { IconX } from '@tabler/icons-react'
import type { ReactNode } from 'react'

type Props = {
    title: string
    onClose?: () => void    // given: the card has a close button
    children?: ReactNode    // the card's contents, under the title strip
}

// The box at the top right of the map. It shows what is selected, or the form for something
// being made. Its contents scroll when they are taller than the map.
function Card({ title, onClose, children }: Props) {
    return (
        <section className="absolute top-3.5 right-3.5 z-10 flex max-h-[calc(100%-28px)] w-card flex-col overflow-hidden rounded-box border border-ink bg-panel shadow-[0_2px_10px_rgb(32_30_24/0.22)]">
            <div className="flex h-6.5 flex-none items-center border-b border-ink bg-strip pr-1 pl-2.5">
                <h2 className="flex-1 font-mono text-label tracking-widest uppercase">{title}</h2>
                {onClose && (
                    <button
                        type="button"
                        aria-label="Close card"
                        title="Close card"
                        onClick={onClose}
                        className="flex size-5 cursor-pointer items-center justify-center rounded-control hover:bg-panel"
                    >
                        <IconX size={14} stroke={1.75} aria-hidden />
                    </button>
                )}
            </div>
            <div className="min-h-0 flex-1 overflow-auto px-2.5 pt-2.5 pb-3">{children}</div>
        </section>
    )
}

export default Card
