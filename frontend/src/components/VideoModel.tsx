import { useEffect, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import type { Mode, Settings, VideoEstimate } from '../types'

interface Props { mode: Mode; settings: Settings; busy: boolean; refs: number; refVideo: boolean; music: boolean; onSettings: (changes: Partial<Settings>) => void }

const money = (value: number) => `$${value < 10 ? value.toFixed(2) : Math.round(value)}`

/** The price of a model for this edit, on its card: free here, an amount or a range of dollars, or the seconds it will ask for when the price is not known yet. */
export function priceLabel(model: VideoEstimate, fr: boolean): string {
  if (model.source === 'local') return fr ? 'Gratuit · sur cet ordinateur' : 'Free · runs here'
  if (model.usd_low !== null && model.usd_high !== null) return `≈ ${model.usd_low === model.usd_high ? money(model.usd_low) : `${money(model.usd_low)} – ${money(model.usd_high)}`}`
  if (model.seconds !== null) return fr ? `≈ ${Math.round(model.seconds)} s de vidéo · prix au plan` : `≈ ${Math.round(model.seconds)} s of video · price at the plan`
  return fr ? 'Payant à la prise' : 'Paid per take'
}

/** The video model, the first thing of the form: one card per model with what it costs for this edit, then what the chosen one spends (resolution, budgets). */
export function VideoModel({ mode, settings, busy, refs, refVideo, music, onSettings }: Props) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const [models, setModels] = useState<VideoEstimate[] | null>(null)
  useEffect(() => {
    let current = true
    const load = async (): Promise<VideoEstimate[]> => {
      try {
        const rows = await api.videoEstimate({ mode, seconds: settings.duration, ratio: settings.ratio, resolution: settings.api_resolution, refs, refVideo, music })
        if (Array.isArray(rows)) return rows
      } catch { /* the estimate is not there: the models are still offered, without a price */ }
      try {
        const list = await api.videoModels(mode)
        return Array.isArray(list) ? list.map(model => ({ ...model, seconds: null, usd_low: null, usd_high: null, text: '' })) : []
      } catch { return [] }
    }
    const wait = setTimeout(() => { load().then(rows => { if (current) setModels(rows) }) }, 250)  // a number being typed asks once
    return () => { current = false; clearTimeout(wait) }
  }, [mode, settings.duration, settings.ratio, settings.api_resolution, refs, refVideo, music])
  const rows = models ?? []
  const chosen = rows.find(model => model.id === settings.video_model)
  const paid = chosen ? chosen.source === 'api' : settings.video_model !== 'minimax_h3'
  const budget = settings.api_budget_seconds
  const asked = chosen ? (chosen.seconds_high ?? chosen.seconds) : null  // with a second take or a retry, the most a shot may ask
  const overSeconds = asked !== null && budget > 0 && asked > budget
  const overDollars = !!chosen && chosen.usd_high !== null && settings.api_budget_usd > 0 && chosen.usd_high > settings.api_budget_usd
  const number = (key: 'api_budget_seconds' | 'api_budget_usd', text: string, hint: string, step: number) => (
    <label className="field" title={hint}><span>{text}</span>
      <input type="number" min={0} step={step} value={settings[key]} disabled={busy}
        onChange={event => { if (event.target.value !== '' && Number.isFinite(Number(event.target.value)) && Number(event.target.value) >= 0) onSettings({ [key]: Number(event.target.value) }) }} />
    </label>
  )
  return (
    <section className="section model-picker" aria-label={fr ? 'Modèle vidéo' : 'Video model'}>
      <h3 className="section-head">{fr ? 'Modèle vidéo' : 'Video model'} <span className="hint">{fr ? `prix pour ${settings.duration} s` : `price for ${settings.duration} s`}</span></h3>
      <div className="model-cards" role="radiogroup" aria-label={fr ? 'Modèle vidéo' : 'Video model'} onKeyDown={event => {
        // a radio group is one stop of the Tab key; the arrows move the choice (WAI-ARIA radio group)
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
        if (!step || busy || !rows.length) return
        event.preventDefault()
        const at = rows.findIndex(model => model.id === settings.video_model)
        const next = rows[((at < 0 ? 0 : at + step) + rows.length) % rows.length]
        onSettings({ video_model: next.id })
        const cards = event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]')
        cards[rows.indexOf(next)]?.focus()
      }}>
        {models === null && <p className="tiny-label">{fr ? 'Chargement des modèles…' : 'Loading the models…'}</p>}
        {rows.map((model, index) => (
          <button type="button" key={model.id} role="radio" aria-checked={model.id === settings.video_model} disabled={busy}
            tabIndex={model.id === settings.video_model || (!chosen && index === 0) ? 0 : -1}
            className={`model-card ${model.id === settings.video_model ? 'on' : ''} ${model.source}`} onClick={() => onSettings({ video_model: model.id })}>
            <span className="model-name"><strong>{model.title.replace(/ \((API|local)\)$/i, '')}</strong><i className={`model-badge ${model.source}`}>{model.source === 'api' ? 'API' : (fr ? 'Local' : 'Local')}</i></span>
            <span className="model-price">{priceLabel(model, fr)}</span>
          </button>
        ))}
        {models !== null && !chosen && <button type="button" role="radio" aria-checked className="model-card on" disabled><span className="model-name"><strong>{settings.video_model}</strong></span></button>}
      </div>
      {paid && <div className="model-spend">
        <label className="field" title={fr ? 'Plus haute, plus chère.' : 'Higher costs more.'}><span>{fr ? 'Résolution API' : 'API resolution'}</span>
          <select value={settings.api_resolution} disabled={busy} onChange={event => onSettings({ api_resolution: event.target.value as Settings['api_resolution'] })}>
            {['480p', '720p', '1080p'].map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        {number('api_budget_seconds', fr ? 'Budget (secondes de vidéo)' : 'Budget (seconds of video)', fr ? 'Le plus de secondes qu’un lancement peut demander à l’API, refaits compris. 0 : sans limite.' : 'The most seconds one run may ask from the API, retries included. 0: no limit.', 10)}
        {number('api_budget_usd', fr ? 'Budget (dollars)' : 'Budget (dollars)', fr ? 'Le même plafond en dollars, d’après les prix affichés par les nœuds API. 0 : sans limite.' : 'The same cap in dollars, from the prices the API nodes show. 0: no limit.', 0.5)}
        {chosen && <p className={`model-estimate ${overSeconds || overDollars ? 'over' : ''}`} role="status">
          {fr ? `Estimation pour ${settings.duration} s : ` : `Estimate for ${settings.duration} s: `}<strong>{priceLabel(chosen, fr)}</strong>
          {overSeconds || overDollars
            ? (fr ? ' · au-dessus du budget : le lancement s’arrête avant la prise qui le dépasse, ou attend ta validation.' : ' · over the budget: the run stops before the take that passes it, or waits for your approval.')
            : (fr ? ' · dans le budget.' : ' · within the budget.')}
        </p>}
        {mode === 'remix' && <small className="video-model-note">{fr
          ? 'Remix : Seedance modifie le plan de la vidéo source (mode édition) : il garde sa durée et son format, tes images disent qui remplace qui. Garde H3 pour un plan de moins de deux secondes ou pour « Pose seule ».'
          : 'Remix: Seedance edits the shot of the source video (edit mode): it keeps its length and format, your pictures say who replaces whom. Keep H3 for a shot under two seconds or for “Pose only”.'}</small>}
        <small className="video-model-note">{fr
          ? 'Chaque prise dépense des crédits Comfy. Estimation sur des plans de 3 s en moyenne : le plan affiche le chiffre exact avant la génération, et un plan qui dépasse le budget attend ta validation. Garde « Refaire les mauvais plans » désactivé pendant les essais.'
          : 'Every take spends Comfy credits. The estimate counts shots of 3 s on average: the plan shows the exact figure before generating, and a plan over the budget waits for your approval. Keep “Retry bad takes” off while you try.'}</small>
      </div>}
    </section>
  )
}
