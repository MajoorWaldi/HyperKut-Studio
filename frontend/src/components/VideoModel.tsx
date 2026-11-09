import { useEffect, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import type { Mode, Settings, VideoModel as Model } from '../types'

/** The video model of Text and Music: H3 on this computer, or an API model that is paid per take, with what a run may spend. */
export function VideoModel({ mode, settings, busy, onSettings }: { mode: Mode; settings: Settings; busy: boolean; onSettings: (changes: Partial<Settings>) => void }) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const [models, setModels] = useState<Model[] | null>(null)
  useEffect(() => { api.videoModels(mode).then(setModels).catch(() => setModels([])) }, [mode])
  const chosen = models?.find(model => model.id === settings.video_model)
  const paid = chosen ? chosen.source === 'api' : settings.video_model !== 'minimax_h3'
  const number = (key: 'api_budget_seconds' | 'api_budget_usd', text: string, hint: string, step: number) => (
    <label className="field" title={hint}><span>{text}</span>
      <input type="number" min={0} step={step} value={settings[key]} disabled={busy}
        onChange={event => { if (event.target.value !== '' && Number.isFinite(Number(event.target.value)) && Number(event.target.value) >= 0) onSettings({ [key]: Number(event.target.value) }) }} />
    </label>
  )
  return (
    <div className="video-model" role="group" aria-label={fr ? 'Modèle vidéo' : 'Video model'}>
      <label className="field" title={fr ? 'H3 tourne sur cet ordinateur. Les modèles API (Seedance, Wan, LTX) passent par ton compte Comfy et se paient à chaque prise.' : 'H3 runs on this computer. API models (Seedance, Wan, LTX) go through your Comfy account and are paid for every take.'}>
        <span>{fr ? 'Modèle vidéo' : 'Video model'}</span>
        <select value={settings.video_model} disabled={busy || models === null} onChange={event => onSettings({ video_model: event.target.value })}>
          {(models ?? []).map(model => <option key={model.id} value={model.id}>{model.title}{model.source === 'api' ? ' · API' : ''}</option>)}
          {models !== null && !chosen && <option value={settings.video_model}>{settings.video_model}</option>}
          {models === null && <option value={settings.video_model}>{settings.video_model}</option>}
        </select>
      </label>
      {paid && <>
        <label className="field" title={fr ? 'Plus haute, plus chère.' : 'Higher costs more.'}><span>{fr ? 'Résolution API' : 'API resolution'}</span>
          <select value={settings.api_resolution} disabled={busy} onChange={event => onSettings({ api_resolution: event.target.value as Settings['api_resolution'] })}>
            {['480p', '720p', '1080p'].map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        {number('api_budget_seconds', fr ? 'Budget (secondes de vidéo)' : 'Budget (seconds of video)', fr ? 'Le plus de secondes qu’un lancement peut demander à l’API, refaits compris. 0 : sans limite.' : 'The most seconds one run may ask from the API, retries included. 0: no limit.', 10)}
        {number('api_budget_usd', fr ? 'Budget (dollars)' : 'Budget (dollars)', fr ? 'Le même plafond en dollars, d’après les prix affichés par les nœuds API. 0 : sans limite.' : 'The same cap in dollars, from the prices the API nodes show. 0: no limit.', 0.5)}
        {mode === 'remix' && <small className="video-model-note">{fr
          ? 'Remix : Seedance modifie le plan de la vidéo source (mode édition) : il garde sa durée et son format, tes images disent qui remplace qui. Garde H3 pour un plan de moins de deux secondes ou pour « Pose seule ».'
          : 'Remix: Seedance edits the shot of the source video (edit mode): it keeps its length and format, your pictures say who replaces whom. Keep H3 for a shot under two seconds or for “Pose only”.'}</small>}
        <small className="video-model-note">{fr
          ? 'Chaque prise dépense des crédits Comfy. Le plan affiche l’estimation avant la génération ; un plan qui dépasse le budget attend ta validation. Garde « Refaire les mauvais plans » désactivé pendant les essais.'
          : 'Every take spends Comfy credits. The plan shows the estimate before generating; a plan over the budget waits for your approval. Keep “Retry bad takes” off while you try.'}</small>
      </>}
    </div>
  )
}
