import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
    look?: 'dark' | 'plain'  // dark: the main action. plain: any other
    wide?: boolean           // as wide as the box it is in
}

const LOOKS = {
    dark: 'border border-ink bg-ink text-panel',
    plain: 'border border-ink',
}
const HOVERS = { dark: 'hover:bg-ink/85', plain: 'hover:bg-strip' }

// A button with words on it, as used in panels, cards and boxes.
function Button({ look = 'plain', wide = false, disabled, className = '', ...rest }: Props) {
    const state = disabled ? 'opacity-40' : `cursor-pointer ${HOVERS[look]}`
    return (
        <button
            type="button"
            disabled={disabled}
            className={`h-control flex-none rounded-control px-3 font-semibold ${LOOKS[look]} ${state} ${wide ? 'w-full' : ''} ${className}`}
            {...rest}
        />
    )
}

export default Button
