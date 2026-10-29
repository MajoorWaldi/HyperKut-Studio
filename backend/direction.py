"""One local vocabulary for optional creative choices and prepared-brief reuse."""
import hashlib
import json
from .creative_controls import canonical

FIELDS = {
    'look': ('Style visuel','Visual style', [
        ('natural','Naturel','Natural','natural observational imagery'),
        ('collage','Collage papier','Paper collage','tactile paper collage with editorial cutouts; preserve subject identity and outfit'),
        ('raw','Brut / grain','Raw / grain','raw tactile textures and restrained analog grain'),
        ('graphic','Graphique','Graphic','deliberate geometric composition and editorial graphic layers'),
        ('noir','Noir contrasté','High-contrast noir','high-contrast monochrome imagery')]),
    'mood': ('Ambiance','Mood',[
        ('calm','Calme','Calm','calm, spacious visual pacing'),
        ('confident','Assurée','Confident','confident presence and deliberate visual rhythm'),
        ('dreamy','Onirique','Dreamlike','dreamlike atmosphere and fluid visual rhythm'),
        ('intense','Intense','Intense','intense visual energy with brief bursts and breathing room')]),
    'camera': ('Caméra','Camera',[
        ('steady','Stable','Steady','stable framing and simple readable camera moves'),
        ('handheld','Portée','Handheld','subtle handheld documentary movement'),
        ('tracking','En mouvement','Tracking','controlled tracking that follows the subject')]),
    'light': ('Lumière','Light',[
        ('natural','Naturelle','Natural','natural light shaped by the actual setting'),
        ('golden','Dorée','Golden','warm low-angle golden light'),
        ('hard','Franche','Hard','hard directional light with defined shadows'),
        ('night','Nocturne','Night','nighttime practical lighting with readable subject detail')]),
}


def catalog():
    return [{'key':k,'fr':v[0],'en':v[1],'choices':[{'value':c[0],'fr':c[1],'en':c[2]} for c in v[2]]} for k,v in FIELDS.items()]


def validate_direction(value):
    for key,choice in value.items():
        if key not in FIELDS or choice not in ['auto',*[c[0] for c in FIELDS[key][2]]]:
            raise ValueError('Unsupported artistic direction choice')
    return {k:v for k,v in value.items() if v!='auto'}


def direction_text(settings):
    lines=[next(c[3] for c in FIELDS[k][2] if c[0]==v) for k,v in validate_direction(settings.art_direction).items()]
    return ('Selected artistic direction: '+ '; '.join(lines)+'. These are deliberate user choices, not a fixed house style; preserve references and all explicit exclusions.') if lines else ''


def resolved_brief(settings):
    if settings.approved_brief.strip():
        return settings.approved_brief.strip()
    return '\n\n'.join(s for s in [settings.prompt.strip(),direction_text(settings)] if s)


def brief_context(request, *, legacy=False):
    data=request.model_dump();s=data['settings']
    for key in ('approved_brief','approved_brief_context','seed'):s.pop(key,None)
    if s.get('music_edit_mode') == 'legacy':
        for key in ('music_edit_mode', 'music_cut_variation', 'music_cut_sync'):
            s.pop(key, None)
    if request.mode in ('text','music') and not legacy:
        for key in ('structure','creativity'):s[key]=canonical(s[key])
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def validate_prepared(request):
    if request.settings.approved_brief and request.settings.approved_brief_context not in (brief_context(request),brief_context(request,legacy=True)):
        raise ValueError('The prepared direction is outdated. Prepare it again after changing the request or references.')


def use_prepared_brief(graph, text):
    """Keep output index zero, bypass only the enrichment LLM after explicit approval."""
    if not text.strip():return
    for node in graph.values():
        link=node['inputs'].get('system_prompt')
        if node['class_type']=='TextGenerate' and isinstance(link,list):
            source=graph.get(str(link[0]),{})
            if source.get('class_type')=='MajoorEditSkills' and source['inputs'].get('skill')=='prompt_enhancer':
                node['class_type']='PrimitiveStringMultiline';node['inputs']={'value':text}


def normalize_media_roles(graph):
    """A removed optional picture batch must not leave the node's default phantom picture."""
    for node in graph.values():
        if node['class_type']=='MajoorEditSkills' and 'images' not in node['inputs']:
            node['inputs']['n_pictures']=0
def apply_plan_contract(graph, settings, reference_count=None, mode=None):
    """Pass literal UI constraints to the planner, not to the brief enhancer."""
    contract = {
        'duration_seconds': settings.duration,
        'fps': 24,
        'target_frames': round(settings.duration * 24),
        'cut_density': settings.cut_density,
        'shot_count_policy': 'Respect explicitly requested generated takes; otherwise choose useful takes adaptively. A requested number of edit cuts is not a required number of generations.',
        'text_enabled': settings.text,
        'approved_text': [settings.text_allowed.strip()] if settings.text and settings.text_allowed.strip() else [],
    }
    rules = (
        '\nFINAL PLAN INPUT CONTRACT (literal settings, not a style example):\n' + json.dumps(contract, ensure_ascii=False) +
        '\nThe requested total duration overrides example durations. Use the existing planner schema. '
        'Omit optional fields that are unused; do not emit empty sub_cuts arrays. '
        'approved_text is exhaustive: place that exact whole string once, either in text or in motion, never both; '
        'do not paraphrase it or add headings. An empty array means no readable overlays, including motion text. '
        'Use supplied references only; if none exist, describe a coherent subject from the brief without claiming an unseen Picture 1.'
        ' Preserve explicit shot/cut counts and their distinction. Twenty independently filmed viewpoints may require twenty takes; twenty excerpts/crops may reuse fewer. '
        'No fixed one-shot-per-1.2s or one-take-per-3s limit. Keep fast inserts feasible and essential actions readable. '
        'MUSIC TIMING GUIDE is advisory: choose your own generated shot count and ids, preserving the requested total and using measured grid timing where it serves the edit.'
    )
    music_grids = {key for key,node in graph.items() if node.get('class_type')=='MajoorCreateTimeline' and node['inputs'].get('source')=='music'}
    music_targets = [
        node for node in graph.values()
        if node.get('class_type') == 'MajoorCreateTimeline'
        and node['inputs'].get('source') == 'json' and 'music' in node['inputs']
    ]
    remix_targets = [
        node for node in graph.values()
        if node.get('class_type') == 'MajoorShotAssemble' and 'music' in node['inputs']
    ] if mode == 'remix' and settings.audio == 'new' else []
    dialogue_present = settings.audio == 'voice' or bool(settings.dialogue.strip())
    music_policy = bool(music_targets or remix_targets) and (settings.music_edit_mode != 'legacy' or dialogue_present)
    music_options = dict(
        music_edit_mode=settings.music_edit_mode,
        music_cut_density=settings.cut_density,
        music_cut_variation=settings.music_cut_variation,
        music_cut_sync=settings.music_cut_sync,
        music_cut_seed=settings.seed % (1 << 64),
        music_cut_every=settings.cut_every,
        music_cut_mood=settings.art_direction.get('mood', 'auto'),
    )
    if dialogue_present:
        for node in graph.values():
            if node.get('class_type') == 'MajoorShotAssemble':
                node['inputs']['preserve_dialogue'] = True
        rules += (
            '\nDIALOGUE SAFETY: mark every speaking shot story.protect_action=true. '
            'Do not split, accelerate or repeat a spoken phrase for musical rhythm. '
            'Allow enough take duration for the full sentence and its natural ending. '
            'Keep the full requested line even if its specified end crosses the shot boundary.'
        )
    if music_policy:
        rules += (
            '\nMUSIC CUT POLICY: ' + ('free (dialogue protection)' if dialogue_present else settings.music_edit_mode) +
            f'; density={settings.cut_density}; variation={settings.music_cut_variation}; sync={settings.music_cut_sync}. '
            'Do not cut on every beat. Choose useful generated takes, not one generation per beat. '
            'Adaptive: longer quiet holds and shorter energetic passages; random: varied musical intervals; '
            'regular: the requested grid; free: narrative timing without beat snapping. '
            'Acoustic energy is not an emotion classifier; respect the selected artistic mood and the brief. '
            'For adaptive/random/regular the renderer selects exact timing from measured music and may add sub-cuts '
            'within existing takes. Avoid extra invented sub-cuts; provide deliberate visual changes for musical accents.'
        )
    for key in music_grids:
        graph[key]['inputs']['rhythm_reference_only'] = True
    for node in graph.values():
        if node.get('class_type')=='MajoorCreateTimeline':
            link=node['inputs'].get('skeleton_json')
            if isinstance(link,list) and str(link[0]) in music_grids:
                node['inputs'].pop('skeleton_json')
                node['inputs']['source.duration'] = settings.duration
    if music_policy:
        for node in music_targets:
            node['inputs'].update(music_options)
            if dialogue_present:
                node['inputs']['music_edit_mode'] = 'free'
            node['inputs']['source.cut_snap'] = 'off'
            link = node['inputs'].get('source.plan_json')
            guard = graph.get(str(link[0]), {}) if isinstance(link, list) else {}
            if guard.get('class_type') == 'MajoorEnsureBurst':
                node['inputs']['source.plan_json'] = guard['inputs']['plan_json']
        for node in remix_targets:
            node['inputs'].update(music_options)
            if dialogue_present:
                node['inputs']['music_edit_mode'] = 'free'
    # Music previously bypassed the same deterministic density guard used by Text.
    if music_grids and not music_policy and not dialogue_present:
        for key,node in list(graph.items()):
            link=node['inputs'].get('source.plan_json') if node.get('class_type')=='MajoorCreateTimeline' else None
            if isinstance(link,list) and graph.get(str(link[0]),{}).get('class_type')=='TextGenerate':
                guard=key+'_edit_density'
                graph[guard]={'class_type':'MajoorEnsureBurst','inputs':{'plan_json':link,'density':settings.cut_density,'enabled':settings.effects,'text_on':False,'text_allowed':''}}
                node['inputs']['source.plan_json']=[guard,0]
    for node in graph.values():
        if node.get('class_type') != 'MajoorEditSkills':
            continue
        inputs = node['inputs']
        if reference_count is not None:
            inputs['n_pictures'] = reference_count
        if inputs.get('skill') == 'timeline_planner':
            inputs['extra_instructions'] = inputs.get('extra_instructions', '') + rules
