import { useEffect, useId, useState } from 'react'
import { controlCopy, levelValue, poseStrength } from '../creativeControls'
import { useI18n } from '../i18n'
import { Dropdown } from './Dropdown'
import { Icon } from './Icon'
import type { Mode, Quality, Ratio, Settings } from '../types'

interface Props { mode: Mode; settings: Settings; busy: boolean; hasReferences?: boolean; onSettings: (changes: Partial<Settings>) => void }

const RATIOS: Ratio[] = ['9:16', '16:9', '1:1', '3:4']
const QUALITIES: Quality[] = ['draft', 'standard', 'max', 'xhigh']
const DURATIONS = [10, 15, 20, 30]
const MIN_SECONDS = 2
const MAX_SECONDS = 120

/** The length in seconds, typed: it is kept while the field is edited and set (between 2 and 120) when the field is left or Enter is pressed. */
function SecondsField({ value, disabled, label, onCommit }: { value: number; disabled: boolean; label: string; onCommit: (seconds: number) => void }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  const commit = () => {
    const seconds = Math.min(MAX_SECONDS, Math.max(MIN_SECONDS, Math.round(Number(text))))
    if (Number.isFinite(seconds) && text.trim() !== '') onCommit(seconds)
    else setText(String(value))
  }
  return <input className="seconds-field" type="number" inputMode="numeric" min={MIN_SECONDS} max={MAX_SECONDS} step={1} value={text} disabled={disabled} aria-label={label} title={label}
    onChange={e => setText(e.target.value)} onBlur={commit} onKeyDown={e => { if (e.key === 'Enter') commit() }} />
}

export function Toolbar({ mode, settings, busy, hasReferences = true, onSettings }: Props) {
  const { t, lang } = useI18n()
  const copy = controlCopy(lang === 'fr'), fidelityId = useId(), freedomId = useId(), scopeId = useId()
  const poseLabel = poseStrength(settings.structure).toFixed(2).replace('.', lang === 'fr' ? ',' : '.')
  const qualityName = { draft: t.draft, standard: t.standard, max: t.max, xhigh: t.xhigh }
  return (
    <div className="toolbar">
      {mode !== 'remix' && (
        <div className="tool" title={t.tip.duration}><label>{t.duration}</label>
          <div className="duration-row"><Dropdown compact align="left" label={t.duration} icon={<Icon name="clock" size={14} />} value={settings.duration} disabled={busy} choices={(DURATIONS.includes(settings.duration) ? DURATIONS : [...DURATIONS, settings.duration].sort((a, b) => a - b)).map(d => ({ value: d, label: `${d} ${t.seconds}` }))} onChange={duration => onSettings({ duration })} />
          <SecondsField value={settings.duration} disabled={busy} label={t.durationManual} onCommit={duration => onSettings({ duration })} /></div>
        </div>
      )}
      {mode !== 'remix' && (
        <div className="tool" title={t.tip.format}><label>{t.format}</label>
          <div className="toggle-row">{RATIOS.map(r => <button key={r} type="button" disabled={busy} className={`mini-toggle ${settings.ratio === r ? 'selected' : ''}`} onClick={() => onSettings({ ratio: r })}>{r}</button>)}</div></div>
      )}
      <div className="tool" title={t.tip.quality}><label>{t.quality}</label>
        <div className="toggle-row">{QUALITIES.map(q => <button key={q} type="button" disabled={busy} title={t.qualityHint[q]} className={`mini-toggle ${settings.quality === q ? 'selected' : ''}`} onClick={() => onSettings({ quality: q })}>{qualityName[q]}</button>)}</div></div>
      {mode === 'remix' ? <div className="tool range" title={copy.poseHint}>
        <label htmlFor={fidelityId}>{copy.pose} · {poseLabel}</label>
        <input id={fidelityId} type="range" min={0.4} max={1} step={0.01} value={poseStrength(settings.structure)} aria-describedby={scopeId} aria-valuetext={`${copy.pose}: ${poseLabel} (${lang==='fr'?'0,40–1,00':'0.40–1.00'})`} disabled={busy} onChange={e => onSettings({structure:Math.max(0,Math.min(100,Math.round((Number(e.target.value)-.4)/.6*100)))})}/>
      </div> : <>
        <div className="tool creative-control" title={hasReferences ? copy.fidelityHint : copy.noRefs}>
          <label htmlFor={fidelityId}>{copy.fidelity}</label>
          <select id={fidelityId} value={levelValue(settings.structure)} disabled={busy || !hasReferences} aria-describedby={scopeId} onChange={e=>onSettings({structure:Number(e.target.value)})}>{[0,50,85].map((value,i)=><option key={value} value={value}>{copy.fidelityLevels[i]}</option>)}</select>
        </div>
        <div className="tool creative-control" title={copy.freedomHint}>
          <label htmlFor={freedomId}>{copy.freedom}</label>
          <select id={freedomId} value={levelValue(settings.creativity)} disabled={busy} aria-describedby={scopeId} onChange={e=>onSettings({creativity:Number(e.target.value)})}>{[0,50,85].map((value,i)=><option key={value} value={value}>{copy.freedomLevels[i]}</option>)}</select>
        </div>
      </>}
      <small id={scopeId} className="creative-control-scope">{copy.scope}{mode !== 'remix' && !hasReferences ? ` ${copy.noRefs}` : ''}</small>
    </div>
  )
}
