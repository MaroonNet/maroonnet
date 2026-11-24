import { useId, type ReactNode } from 'react'
import Button from './Button.tsx'

export type Choice = {
    label: string
    onPress: () => void
    main?: boolean  // drawn dark: the choice the box is about
}

type Props = {
    title: string
    children?: ReactNode   // what the box says, under the title
    choices: Choice[]
    stacked?: boolean      // the choices one under another, for long labels
}

// A box in the middle of the screen that asks a question before something happens. The
// rest of the screen is dimmed and cannot be pressed until a choice is made.
function ConfirmBox({ title, children, choices, stacked = false }: Props) {
    const titleId = useId()  // ties the title to the box, so a screen reader announces it
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                className="w-85 rounded-box border border-ink bg-panel p-4 shadow-[0_2px_10px_rgb(32_30_24/0.22)]"
            >
                <h2 id={titleId} className="text-title font-bold">{title}</h2>
                <div className="mt-2 font-medium text-muted">{children}</div>
                <div className={`mt-4 flex gap-2 ${stacked ? 'flex-col' : 'justify-end'}`}>
                    {choices.map((choice) => (
                        <Button key={choice.label} look={choice.main ? 'dark' : 'plain'} wide={stacked} onClick={choice.onPress}>
                            {choice.label}
                        </Button>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default ConfirmBox
