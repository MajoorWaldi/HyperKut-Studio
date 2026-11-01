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
export function SecondsField({ value, disabled, label, onCommit }: { value: number; disabled: boolean; label: string; onCommit: (seconds: number) => void }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  const commit = () => {
    const seconds = Math.min(MAX_SECONDS, Math.max(MIN_SECONDS, Math.round(Number(text))))
    if (Number.isFinite(seconds) && text.trim() !== '') { setText(String(seconds)); onCommit(seconds) }  // the field shows what was kept, even when it equals the current value
    else setText(String(value))
  }
  return <input className="seconds-field" type="number" inputMode="numeric" min={MIN_SECONDS} max={MAX_SECONDS} step={1} value={text} disabled={disabled} aria-label={label} title={label}
    onChange={e => setText(e.target.value)} onBlur={commit} onKeyDown={e => { if (e.key === 'Enter') commit() }} />
}

/** What a remix holds fixed. Empty leaves the pose slider alone. */
const STRATEGY_CHOICES = [['', 'Sliders only', 'Curseurs seuls'], ['preserve', 'Preserve the edit', 'Préserver le montage'], ['creative', 'Creative remix', 'Remix créatif'], ['transfer', 'Motion transfer', 'Transfert de mouvement']] as const
const STRATEGY_TIPS = {
  en: { sliders: 'The pose slider alone decides how close the remix stays.', preserve: 'Same cuts and durations as the source; only the look changes. A different cut structure is reported.', creative: 'The source is an inspiration: staging and cuts may change.', transfer: 'The motion of the source carries another subject.' },
  fr: { sliders: 'Le curseur de pose décide seul de la proximité du remix.', preserve: 'Mêmes coupes et mêmes durées que la source ; seul le style change. Une structure différente est signalée.', creative: 'La source est une inspiration : mise en scène et coupes peuvent changer.', transfer: 'Le mouvement de la source porte un autre sujet.' },
} as const

export function Toolbar({ mode, settings, busy, hasReferences = true, onSettings }: Props) {
  const { t, lang } = useI18n()
  const copy = controlCopy(lang === 'fr'), fidelityId = useId(), freedomId = useId(), scopeId = useId(), strategyId = useId()
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
      {mode === 'remix' ? <><div className="tool range" title={copy.poseHint}>
        <label htmlFor={fidelityId}>{copy.pose} · {poseLabel}</label>
        <input id={fidelityId} type="range" min={0.4} max={1} step={0.01} value={poseStrength(settings.structure)} aria-describedby={scopeId} aria-valuetext={`${copy.pose}: ${poseLabel} (${lang==='fr'?'0,40–1,00':'0.40–1.00'})`} disabled={busy} onChange={e => onSettings({structure:Math.max(0,Math.min(100,Math.round((Number(e.target.value)-.4)/.6*100)))})}/>
      </div>
        <div className="tool creative-control" title={STRATEGY_TIPS[lang === 'fr' ? 'fr' : 'en'][settings.remix_strategy || 'sliders']}>
          <label htmlFor={strategyId}>{lang === 'fr' ? 'Stratégie' : 'Strategy'}</label>
          <select id={strategyId} value={settings.remix_strategy} disabled={busy} onChange={e => onSettings({ remix_strategy: e.target.value as Settings['remix_strategy'] })}>
            {STRATEGY_CHOICES.map(([value, en, fr]) => <option key={value} value={value}>{lang === 'fr' ? fr : en}</option>)}
          </select>
        </div></> : <>
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
