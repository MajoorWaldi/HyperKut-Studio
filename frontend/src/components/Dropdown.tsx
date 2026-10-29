import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Icon } from './Icon'

export interface Choice<T> { value: T; label: string; short?: string }

interface Props<T> {
  value: T
  choices: Choice<T>[]
  onChange: (value: T) => void
  /** What the list is for, said to a screen reader. */
  label: string
  title?: string
  icon?: ReactNode
  align?: 'left' | 'right'
  compact?: boolean
  disabled?: boolean
}

/** A list of choices that opens under a button, in the style of the app: an icon, the current choice, a caret that turns, and a menu with the chosen one marked. Arrow keys, Enter and Escape work. */
export function Dropdown<T extends string | number>({ value, choices, onChange, label, title, icon, align = 'right', compact, disabled }: Props<T>) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLUListElement>(null)
  const menuId = useId()
  const selected = choices.find(choice => choice.value === value)

  useEffect(() => { if (open) menu.current?.focus() }, [open])
  useEffect(() => { if (disabled || !choices.length) setOpen(false) }, [disabled, choices.length])

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])

  const show = () => { if (disabled || !choices.length) return; setActive(Math.max(0, choices.findIndex(choice => choice.value === value))); setOpen(true) }
  const close = () => { setOpen(false); trigger.current?.focus() }
  const pick = (choice: Choice<T>) => { if (disabled) return; onChange(choice.value); close() }
  const keys = (event: KeyboardEvent) => {
    if (event.key === 'Escape') { event.stopPropagation(); close(); return }
    if (event.key === 'Tab') { setOpen(false); trigger.current?.focus(); return }
    if (open && (event.key === 'Home' || event.key === 'End')) {
      event.preventDefault(); setActive(event.key === 'Home' ? 0 : choices.length - 1); return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) { show(); return }
      setActive(current => (current + (event.key === 'ArrowDown' ? 1 : -1) + choices.length) % choices.length)
    } else if ((event.key === 'Enter' || event.key === ' ') && open) {
      event.preventDefault()
      if (choices[active]) pick(choices[active])
    }
  }

  return (
    <div className={`dropdown ${compact ? 'compact' : ''} ${open ? 'open' : ''}`} ref={root}>
      <button ref={trigger} type="button" className="dropdown-button" aria-haspopup="listbox" aria-controls={open ? menuId : undefined} aria-expanded={open} aria-label={`${label}: ${selected?.label ?? ''}`} title={title} disabled={disabled || !choices.length} onClick={() => (open ? close() : show())} onKeyDown={keys}>
        {icon && <span className="dd-icon" aria-hidden>{icon}</span>}
        <span className="dd-value">{selected?.short ?? selected?.label}</span>
        <span className="dd-caret" aria-hidden><Icon name="chevron-down" size={12} /></span>
      </button>
      {open && (
        <ul ref={menu} id={menuId} tabIndex={-1} className={`dd-menu ${align}`} role="listbox" aria-label={label} aria-activedescendant={`${menuId}-${active}`} onKeyDown={keys}>
          {choices.map((choice, i) => (
            <li id={`${menuId}-${i}`} key={String(choice.value)} role="option" aria-selected={choice.value === value} className={`${choice.value === value ? 'chosen' : ''} ${i === active ? 'active' : ''}`} onMouseEnter={() => setActive(i)} onClick={() => pick(choice)}>
              <span className="dd-check" aria-hidden>{choice.value === value && <Icon name="check" size={13} />}</span>{choice.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
