import type { ReactNode } from 'react'
import type { Lang } from '../i18n'
import { Icon } from './Icon'

export type ToastTone = 'success' | 'info' | 'warning' | 'error'

interface Props {
  tone: ToastTone
  lang: Lang
  children: ReactNode
  busy?: boolean
  action?: { label: string; run: () => void }
  onDismiss?: () => void
}

const titles = {
  en: { success: 'Success', info: 'Information', warning: 'Attention', error: 'Error' },
  fr: { success: 'Succès', info: 'Information', warning: 'Attention', error: 'Erreur' },
}

export function Toast({ tone, lang, children, busy, action, onDismiss }: Props) {
  return <div className={`toast toast-${tone}${busy ? ' is-busy' : ''}`} role={tone === 'error' ? 'alert' : 'status'} aria-atomic="true">
    <span className="toast-mark" aria-hidden="true">{busy ? <Icon name="refresh" size={20} /> : tone === 'success' ? <Icon name="check" size={21} /> : tone === 'info' ? 'i' : tone === 'warning' ? '!' : <Icon name="x" size={20} />}</span>
    <div className="toast-content"><strong>{titles[lang][tone]}</strong><span>{children}</span></div>
    {action && <button type="button" className="toast-action" onClick={action.run}>{action.label}</button>}
    {onDismiss && <button type="button" className="toast-close" aria-label={lang === 'fr' ? 'Fermer la notification' : 'Dismiss notification'} onClick={onDismiss}><Icon name="x" size={17} /></button>}
  </div>
}
