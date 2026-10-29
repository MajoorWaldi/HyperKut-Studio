// Export the API templates of a mode from its SECATOR graph. Run it in the page of ComfyUI (a console, or any tool that evaluates JavaScript in the page), with the graph in
// ComfyUI/user/default/workflows/: it defines window.secatorExport(mode) -> { stage1, shot, final, slots }.
// The three prompts of a mode are cut from the graph with graphToPrompt, the way the interface needs them to be run one after the other:
//   stage1  the plan: everything up to the shot list (Scene Detect for a remix, Create Timeline for a creation), then Save Project Info (the server reads it)
//   shot    one shot: the block of SHOT_001 up to Apply Shot Metadata, then Save Project Info (it makes ComfyUI run Apply, which registers the take)
//   final   the edit: everything up to the saved video, but with the shot list read back from the project (Load Shot List) instead of the chain of the shots
// slots: name -> [[node id, input], ...] where the interface puts a value. A prompt only carries the slots of the nodes it has.
(() => {
  const GRAPHS = { remix: 'SECATOR Remix', text: 'SECATOR Creative Text', music: 'SECATOR Creative Music' }
  const PLAN = { remix: 'MajoorSceneDetectSplit', text: 'MajoorCreateTimeline', music: 'MajoorCreateTimeline' }
  // slot name -> [title prefix of the node, its input]
  const CONTROLS = {
    idea: ['WHAT TO REPLACE', 'value'], brief: ['YOUR BRIEF', 'value'], idea_creative: ['YOUR IDEA', 'value'],
    length: ['EDIT LENGTH', 'value'], mood: ['SOUND MOOD', 'value'], bpm: ['BPM', 'value'], music_start: ['MUSIC START', 'value'],
    replace_sound: ['REPLACE THE SOUND', 'value'], voice_on: ['VOICE ON', 'value'], dialogue: ['DIALOGUE', 'value'],
    effects: ['EFFECTS', 'value'], text: ['TEXT (', 'value'], motion_on: ['MOTION GRAPHICS ON', 'value'], motion_layers: ['MOTION GRAPHICS (layers', 'value'], extra_layers: ['EXTRA MOTION GRAPHICS (layers', 'value'],
    sound_design: ['SOUND DESIGN', 'value'], sd_volume: ['SOUND OF THE SHOTS VOLUME', 'value'], sound_effects: ['SOUND EFFECTS', 'value'], music_sync: ['MUSIC SYNC', 'value'], retry_bad: ['RETRY BAD TAKES', 'value'],
    turbo: ['TURBO', 'value'], plates: ['PLACES', 'value'], camera: ['CAMERA LOOK', 'value'], pose_strength: ['POSE STRENGTH', 'value'], force_pose: ['POSE ONLY', 'value'],
    redraw_text: ['REDRAW THE TEXT', 'value'], subject_mask: ['SUBJECT MASK (for', 'value'], mask_n: ['SUBJECT MASK FRAMES', 'value'], quality_check: ['QUALITY CHECK', 'value'],
    reference_fidelity: ['Skill · timeline_planner', 'reference_fidelity'], creative_freedom: ['Skill · timeline_planner', 'creative_freedom'],
    style: ['Skill · timeline_planner', 'profile'], cut_density: ['Skill · timeline_planner', 'cut_density'], transition_intensity: ['Skill · timeline_planner', 'transition_intensity'], narrative_coherence: ['Skill · timeline_planner', 'narrative_coherence'], text_allowed: ['Skill · timeline_planner', 'text_allowed'],
    cut_every: ['RHYTHM ·', 'source.cut_every'], music_shots: ['RHYTHM ·', 'source.shots'],
    ref_video: ['REF', 'file'], voice: ['VOICE ·', 'audio'],
    ratio: ['FORMAT AND QUALITY', 'aspect_ratio'], megapixels_creative: ['FORMAT AND QUALITY', 'megapixels'], megapixels: ['QUALITY (megapixels', 'value'],
    source: ['VIDEO TO REMIX', 'file'], music: ['YOUR MUSIC', 'audio'],
    ref1: ['REF 1', 'image'], ref2: ['REF 2', 'image'], ref3: ['REF 3', 'image'], ref4: ['REF 4', 'image'], ref5: ['REF 5', 'image'],
  }

  const ancestors = (prompt, roots) => {
    const keep = new Set()
    const walk = id => { if (keep.has(id) || !prompt[id]) return; keep.add(id); for (const v of Object.values(prompt[id].inputs)) if (Array.isArray(v)) walk(String(v[0])) }
    roots.forEach(walk)
    return Object.fromEntries([...keep].map(id => [id, prompt[id]]))
  }
function upgradeMusicToYuE2(graph, slots) {
  for (const [id,node] of Object.entries(graph)) if (node.class_type === 'MajoorMusicFit' && !Array.isArray(node.inputs.energy_goal)) slots.music_energy = [[id,'energy_goal']];
  const entry = Object.entries(graph).find(([, n]) => n.class_type === 'TextEncodeAceStepAudio1.5')
  if (!entry) {
    const music = Object.entries(graph).find(([, node]) => node.class_type === 'YuE2GenerateMusic')
    if (music) {
      slots.music_seed = Object.entries(graph).filter(([, node]) =>
        ['YuE2GenerateABC', 'YuE2GenerateMusic'].includes(node.class_type) ||
        (node.class_type === 'KSampler' && node.inputs.positive?.[0] === music[0])
      ).map(([id]) => [id, 'seed'])
    }
    return
  }
  const [id, oldNode] = entry, old = oldNode.inputs
  const samplerEntry = Object.entries(graph).find(([, n]) => n.class_type === 'KSampler' && n.inputs.positive?.[0] === id)
  if (!samplerEntry) throw new Error('Cannot locate music sampler')
  const [samplerId, sampler] = samplerEntry
  const shiftId = sampler.inputs.model[0], modelId = graph[shiftId].inputs.model[0]
  const clipId = old.clip[0]
  const decodeEntry = Object.entries(graph).find(([, n]) => n.class_type === 'VAEDecodeAudio' && n.inputs.samples?.[0] === samplerId)
  if (!decodeEntry) throw new Error('Cannot locate music decoder')
  const vaeId = decodeEntry[1].inputs.vae[0], latentId = sampler.inputs.latent_image[0]
  const styleId = 'yue2_style', planId = 'yue2_plan', scoreId = 'yue2_score'
  graph[modelId] = { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: 'yue2_3b_int8_convrot.safetensors' }, _meta: { title: 'YuE2 · local music model' } }
  graph[styleId] = { class_type: 'MajoorYuE2Style', inputs: { prompt: old.tags, bpm: old.bpm, key: old.keyscale, lyrics: '' } }
  graph[planId] = { class_type: 'YuE2GenerateABC', inputs: { clip: [modelId, 1], style: [styleId, 0], lyrics: [styleId, 1], seed: old.seed, mode: 'full', max_abc_tokens: 8192, temperature: 0.7, top_p: 0.9, top_k: 30, repetition_penalty: 1.005, penalty_window: 100 } }
  graph[scoreId] = { class_type: 'MajoorYuE2Score', inputs: { abc: [planId, 0], instrumental: [styleId, 2] } }
  graph[id] = { class_type: 'YuE2GenerateMusic', inputs: { clip: [modelId, 1], style: [styleId, 0], lyrics: [styleId, 1], abc: [scoreId, 0], seed: old.seed, mode: 'full', max_duration: old.duration, temperature: 1, top_p: 0.95, top_k: 100, repetition_penalty: 1.2, cfg_scale: 1 } }
  graph[latentId] = { class_type: 'EmptyYuE2LatentAudio', inputs: { seconds: [id, 1], batch_size: 1 } }
  Object.assign(sampler.inputs, { model: [modelId, 0], steps: 32, cfg: 1, sampler_name: 'dpm_2', scheduler: 'sgm_uniform', denoise: 1 })
  if (sampler._meta) sampler._meta.title = 'YuE2 · sampler (32 steps)'
  decodeEntry[1].inputs.vae = [modelId, 2]
  if (decodeEntry[1]._meta) decodeEntry[1]._meta.title = 'YuE2 · decode'
  delete graph[shiftId]; delete graph[clipId]; delete graph[vaeId]
  for (const node of Object.values(graph)) {
    if (node.class_type === 'ComfyMathExpression' && node.inputs.expression === 'a + 80') node.inputs.expression = 'max(24, a + 8)'
  }
  for (const [key, pairs] of Object.entries(slots)) {
    const kept = pairs.filter(([node, field]) => graph[node] && field in graph[node].inputs)
    if (kept.length) slots[key] = kept
    else delete slots[key]
  }
  slots.music_seed = [[id, 'seed'], [planId, 'seed'], [samplerId, 'seed']]
}

  const retainRemixPrompts = graph => {
    const apply = Object.values(graph).find(n => n.class_type === 'MajoorApplyShotMetadata')
    if (!apply) throw new Error('Remix has no Apply Shot Metadata')
    const promptFor = link => {
      const [id] = link, node = graph[id]
      if (node.class_type === 'MajoorSelectShot') return ''
      if (node.class_type === 'ComfySwitchNode') {
        const key = `${id}_generation_prompt`
        graph[key] = { class_type: 'ComfySwitchNode', inputs: {
          switch: node.inputs.switch,
          on_false: promptFor(node.inputs.on_false),
          on_true: promptFor(node.inputs.on_true),
        }, _meta: { title: 'Prompt of the selected Remix take' } }
        return [key, 0]
      }
      // Follow the generated video's nearest H3, not an earlier take used by its judge.
      const queue = [String(id)], seen = new Set()
      while (queue.length) {
        const next = queue.shift()
        if (seen.has(next)) continue
        seen.add(next)
        const upstream = graph[next]
        if (upstream.class_type === 'MiniMaxH3ReferenceToVideo') return upstream.inputs.prompt
        for (const value of Object.values(upstream.inputs)) if (Array.isArray(value)) queue.push(String(value[0]))
      }
      throw new Error(`No H3 prompt for Remix video ${id}`)
    }
    apply.inputs.generation_prompt = promptFor(apply.inputs.video)
  }

  const titleOf = node => node._meta?.title ?? ''
  const slotsFor = prompt => {
    const slots = {}
    for (const [name, [title, input]] of Object.entries(CONTROLS)) {
      const hits = Object.entries(prompt).filter(([, n]) => titleOf(n).startsWith(title) && input in n.inputs)
      if (hits.length) slots[name] = hits.map(([id]) => [id, input])
    }
    return slots
  }

  // Pad only micro-shot references; keep the original timeline and normal refs.
  const padShortRemix = graph => {
    const short = Object.entries(graph).find(([, n]) => n.class_type === 'ComfyMathExpression' && n.inputs.expression?.replace(/\s/g, '') === 'a<5')
    const keep = short && Object.values(graph).find(n => n.class_type === 'ComfyMathExpression' && n.inputs['values.b']?.[0] === short[0] && n.inputs.expression?.replace(/\s/g, '') === 'max(a,b)>0')
    const reference = Object.values(graph).find(n => n.class_type === 'ComfySwitchNode' && titleOf(n).startsWith('SOURCE FRAMES as the H3 reference video'))
    if (!short || !keep || !reference) throw new Error('Cannot export Remix without its short-shot reference controls')
    const source = reference.inputs.on_true
    keep.inputs = { expression: 'a > 0', 'values.a': keep.inputs['values.a'] }
    keep._meta.title = 'KEEP THE SHOT? no subject to replace'
    graph.short_last = { class_type: 'ImageFromBatch', inputs: { image: source, batch_index: -1, length: 1 } }
    graph.short_tail = { class_type: 'RepeatImageBatch', inputs: { image: ['short_last', 0], amount: 4 } }
    graph.short_batch = { class_type: 'ImageBatch', inputs: { image1: source, image2: ['short_tail', 0] } }
    graph.short_reference = { class_type: 'ImageFromBatch', inputs: { image: ['short_batch', 0], batch_index: 0, length: 5 } }
    graph.short_reference_switch = { class_type: 'ComfySwitchNode', inputs: { switch: [short[0], 2], on_true: ['short_reference', 0], on_false: source } }
    reference.inputs.on_true = ['short_reference_switch', 0]
  }

  window.secatorExport = async mode => {
    const wf = await (await fetch('/api/userdata/' + encodeURIComponent(`workflows/${GRAPHS[mode]}.json`))).json()
    await app.loadGraphData(wf)
    await new Promise(r => setTimeout(r, 3000))
    for (const node of app.graph._nodes) {
      // the optional inputs are in the prompt, the server removes the ones that were not given (with the nodes that only they fed)
      if (/^(REF \d|REF VIDEO|REFERENCE VIDEO|VOICE ·)/.test(node.title ?? '')) node.mode = 0
      for (const w of node.widgets ?? []) if (w.name === 'control_after_generate') w.value = 'fixed'
    }
    for (const sg of app.graph.subgraphs.values()) for (const node of sg.nodes) for (const w of node.widgets ?? []) if (w.name === 'control_after_generate') w.value = 'fixed'
    const { output } = await app.graphToPrompt()
    // inputs that a saved graph does not have yet (a node was extended after it was built) come out empty: they get the default of the node
    for (const node of Object.values(output)) if (node.class_type === 'MajoorEditSkills') { node.inputs.shot_start ??= -1; node.inputs.shot_duration ??= 0 }
    // the cut density the user chose is kept even when the LLM wrote no burst: a node between the planner and the timeline adds one (Text only: in Music mode the cuts come from the grid of the music)
    const timelineNode = mode === 'text' ? Object.values(output).find(n => n.class_type === 'MajoorCreateTimeline' && titleOf(n).startsWith('CREATE TIMELINE')) : undefined
    if (timelineNode && Array.isArray(timelineNode.inputs['source.plan_json'])) {
      output.burst = { class_type: 'MajoorEnsureBurst', inputs: { plan_json: timelineNode.inputs['source.plan_json'], density: 'auto', enabled: true, text_allowed: '', text_on: true }, _meta: { title: 'Ensure Burst' } }
      timelineNode.inputs['source.plan_json'] = ['burst', 0]
    }
    const find = type => Object.entries(output).filter(([, n]) => n.class_type === type).map(([id]) => id)
    const [plan] = find(PLAN[mode]).filter(id => PLAN[mode] !== 'MajoorCreateTimeline' || titleOf(output[id]).startsWith('CREATE TIMELINE'))
    const save = find('SaveVideo')[0]

    const stage1 = ancestors(output, [plan])
    stage1.p1 = { class_type: 'MajoorSaveProjectInfo', inputs: { shot_list: [plan, 0], name: 'job' }, _meta: { title: 'Save Project Info' } }
    // the music of a Text or Music edit is kept as a file of the project: the shots and the edit read it, they do not ask the music models again (the music of a Remix is only made in its edit)
    const fit = mode === 'remix' ? undefined : find('MajoorMusicFit')[0]
    if (fit) stage1.p5 = { class_type: 'MajoorSaveProjectMusic', inputs: { shot_list: [plan, 0], music: [fit, 0], fork_project_id: '' }, _meta: { title: 'Save Project Music' } }
    const keptMusic = graph => {
      if (!fit) return
      graph.p6 = { class_type: 'MajoorLoadProjectMusic', inputs: { project_id: '' }, _meta: { title: 'Load Project Music' } }
      for (const node of Object.values(graph)) for (const [name, value] of Object.entries(node.inputs)) if (Array.isArray(value) && String(value[0]) === fit && value[1] === 0) node.inputs[name] = ['p6', 0]
    }

    // a shot reads its project from the disk (Load Shot List) instead of the plan of the first prompt: it can be run again, with the prompt that was edited, whatever ComfyUI kept in memory
    const apply = find('MajoorApplyShotMetadata').sort()[0]
    const shotGraph = structuredClone(output)
    shotGraph.p4 = { class_type: 'MajoorLoadShotList', inputs: { project_id: '' }, _meta: { title: 'Load Shot List' } }
    for (const node of Object.values(shotGraph)) for (const [name, value] of Object.entries(node.inputs)) if (Array.isArray(value) && String(value[0]) === plan) node.inputs[name] = ['p4', 0]
    keptMusic(shotGraph)
    const shot = ancestors(shotGraph, [apply])
    shot.p2 = { class_type: 'MajoorSaveProjectInfo', inputs: { shot_list: [apply, 0], name: 'shot' }, _meta: { title: 'Save Project Info (shot)' } }

    const assemble = find('MajoorShotAssemble')[0]
    const final = structuredClone(output)
    final.p3 = { class_type: 'MajoorLoadShotList', inputs: { project_id: '' }, _meta: { title: 'Load Shot List' } }
    final[assemble].inputs.shot_list = ['p3', 0]
    keptMusic(final)
    const energyReports = Object.entries(final).filter(([, n]) => n.class_type === 'MajoorEnergyReport').map(([id, n]) => { n.inputs.shot_list = ['p3', 0]; return id })
    const finalPrompt = ancestors(final, [save, ...energyReports])

    const slots = { stage1: slotsFor(stage1), shot: slotsFor(shot), final: slotsFor(finalPrompt) }
    slots.stage1.job_name = [['p1', 'name']]
    if (stage1.burst) { ;(slots.stage1.cut_density ??= []).push(['burst', 'density']); ;(slots.stage1.text_allowed ??= []).push(['burst', 'text_allowed']); ;(slots.stage1.text ??= []).push(['burst', 'text_on']); ;(slots.stage1.effects ??= []).push(['burst', 'enabled']) }
    slots.stage1.fork_project_id = [['p1', 'fork_project_id'], ...(fit ? [['p5', 'fork_project_id']] : [])]
    stage1.p1.inputs.fork_project_id = ''
    slots.final.project_id = [['p3', 'project_id'], ...(fit ? [['p6', 'project_id']] : [])]
    slots.final.save = [[save, 'filename_prefix']]
    // the style of the edit, set on the assembly itself: the edit can be made again with another style without making a shot again
    for (const [slot, input] of Object.entries({ edit_effects: 'effects', edit_text: 'text', edit_sub_cuts: 'sub_cuts', edit_music_volume: 'music_volume', edit_shot_volume: 'shot_volume', edit_duck: 'duck_music', edit_auto_sfx: 'auto_sfx' })) slots.final[slot] = [[assemble, input]]
    const select = Object.entries(shot).find(([, n]) => n.class_type === 'MajoorSelectShot')
    slots.shot.shot_id = [[select[0], 'shot_id']]
    slots.shot.project_id = [['p4', 'project_id'], ...(fit ? [['p6', 'project_id']] : [])]
    slots.shot.job_name = [['p2', 'name']]
    for (const [field, value] of [['shot_start', -1], ['shot_duration', 0]]) {
      slots.shot[field] = Object.entries(shot).filter(([, n]) => n.class_type === 'MajoorEditSkills').map(([id, n]) => { n.inputs[field] = value; return [id, field] })
    }
    slots.shot.seed = Object.entries(shot).filter(([, n]) => n.class_type === 'RandomNoise' && n.inputs.noise_seed > 1e6).map(([id]) => [id, 'noise_seed'])
    for (const [id, node] of Object.entries(stage1)) {
      if (node.class_type === 'MajoorEditSkills' && ['timeline_planner', 'prompt_enhancer'].includes(node.inputs.skill)) {
        ;(slots.stage1.planning_instructions ??= []).push([id, 'extra_instructions'])
      }
    }
    slots.final.sfx_library = [[assemble, 'sfx_library']]
    finalPrompt[assemble].inputs.sfx_library ??= ''
    finalPrompt[assemble].inputs.loudness_target ??= -14  // missing input defaults to social target; explicit 0 disables normalization
    finalPrompt[assemble].inputs.music_volume = 0
    finalPrompt.hyperframes = { class_type: 'MajoorHyperFrames', inputs: { video: finalPrompt[save].inputs.video, enabled: true, direction: 'editorial', shot_cues: '[]', timeline: '[]' }, _meta: { title: 'Optional HyperFrames finishing' } }
    finalPrompt[save].inputs.video = ['hyperframes', 0]
    for (const [slot, input] of Object.entries({ motion_design: 'enabled', hyperframes_direction: 'direction', motion_cues: 'shot_cues', motion_timeline: 'timeline' })) slots.final[slot] = [['hyperframes', input]]
    const oldMotion = Object.entries(finalPrompt).filter(([, n]) => n.class_type === 'MajoorMotionGraphics')
    const firstMotion = oldMotion.find(([, n]) => finalPrompt[String(n.inputs.video[0])]?.class_type === 'MajoorShotAssemble')
    if (!firstMotion) throw new Error('No motion input to migrate')
    finalPrompt.hyperframes.inputs.video = firstMotion[1].inputs.video
    finalPrompt.hyperframes.inputs.layers = '[]'
    finalPrompt.hyperframes.inputs.source_layers = '[]'
    finalPrompt.hyperframes.inputs.source_layers_enabled = false
    finalPrompt.hyperframes.inputs.project_id = ''
    if (mode === 'remix') {
      finalPrompt.hyperframes.inputs.source_layers = firstMotion[1].inputs.layers
      finalPrompt.hyperframes.inputs.source_layers_enabled = Object.values(finalPrompt).find(n => n.class_type === 'ComfySwitchNode' && JSON.stringify(n.inputs.on_true) === JSON.stringify([firstMotion[0], 0])).inputs.switch
    }
    const masked = oldMotion.find(([, n]) => n.inputs.mask)
    if (masked) finalPrompt.hyperframes.inputs.mask = finalPrompt[String(masked[1].inputs.mask[0])].inputs.on_true
    const removed = new Set(oldMotion.map(([id]) => id))
    for (const [id, n] of Object.entries(finalPrompt)) if (n.class_type === 'ComfySwitchNode' && oldMotion.some(([oldId]) => JSON.stringify(n.inputs.on_true) === JSON.stringify([oldId, 0]))) removed.add(id)
    for (const node of Object.values(finalPrompt)) for (const [field, value] of Object.entries(node.inputs)) {
      if (Array.isArray(value) && removed.has(String(value[0]))) node.inputs[field] = node.class_type === 'MajoorEnergyReport' ? ['hyperframes', 0] : firstMotion[1].inputs.video
    }
    for (const id of removed) delete finalPrompt[id]
    for (const key of Object.keys(slots.final)) slots.final[key] = slots.final[key].filter(([id]) => !removed.has(id))
    slots.final.unified_layers = [['hyperframes', 'layers'], [assemble, 'motion_layers']]  // the same layers reach the graphics and, as sound cues, the assembly
    slots.final.project_id.push(['hyperframes', 'project_id'])
    const files = { stage1, shot, final: finalPrompt, slots }
    if (mode === 'remix') {
      padShortRemix(shot)
      retainRemixPrompts(shot)
    }
    const source = Object.entries(shot).find(([, n]) => n.class_type === 'MajoorShotSource')
    if (source) {
      const localGraph = structuredClone(shot)
      localGraph[apply].inputs.video = [source[0], 1]
      files.local = ancestors(localGraph, ['p2'])
      slots.local = Object.fromEntries(Object.entries(slots.shot).map(([key, values]) => [key, values.filter(([id]) => id in files.local)]).filter(([, values]) => values.length))
    }
    if (mode !== 'remix' && slots.stage1.ref_video) {
      const [id, field] = slots.stage1.ref_video[0]
      finalPrompt.energy_reference = structuredClone(stage1[id])
      for (const node of Object.values(finalPrompt)) if (node.class_type === 'MajoorEnergyReport') node.inputs.reference_video = ['energy_reference', 0]
      slots.final.energy_reference = [['energy_reference', field]]
    }
    // Studio music direction is an app-level adaptation, like the project IO nodes above.
    if (mode === 'text') {
      const reference = Object.entries(output).find(([, node]) => node.class_type === 'TextGenerate' && Array.isArray(node.inputs.system_prompt) && output[String(node.inputs.system_prompt[0])]?.inputs.skill === 'prompt_enhancer')
      if (!reference) throw new Error('Cannot export music direction without the visual brief encoder')
      const system = "You are a music director. Translate the user brief into a concrete musical sound. Any genre, subgenre, era, cultural tradition or hybrid is allowed. Explicit music preferences override visual setting and editing profiles. Separate genre from mood; no default genre or instrument palette. Match vocal treatment to the request, including instrumental music, vocal chops, chanting, rap or singing; do not invent intelligible lyrics. Describe sound, not cameras or artist names. Preserve the requested musical identity while adapting energy to mood. Do not force clean production, restraint, acoustic instruments, a drop or a conventional song structure. Quiet, raw, distorted, sparse, dense or experimental sound are valid.\n\nBuild the music prompt in this order, as natural sound descriptions rather than headings: (1) genre/subgenre separately from emotional mood; (2) defining groove, pulse, straight/swing/syncopation/half-time feel and rhythmic density when relevant; (3) two to four distinctive sonic signatures, prioritizing a memorable hook instead of listing many instruments; (4) production character: raw/polished, dry/reverberant, saturated/soft and dense/spacious, only as justified by the request; (5) a duration-appropriate musical arc and ending. Each choice must support the requested style. Do not treat 'viral', 'cinematic' or 'energetic' as a complete sonic specification. Select concrete compatible sounds rather than vague adjectives or arbitrary instrumentation. Do not include all these dimensions when they are irrelevant to a sparse or experimental request. Describe desired sounds positively; add exclusions only when explicitly requested. Do not introduce new genre bans. A 20-second cue can be one memorable idea with a useful variation and an appropriate ending, without a mandatory drop. Event timestamps are intentions, not promises of exact synchronization. Do not invent fixed break/drop times (such as 9/12 seconds) without user or timeline support. If timing is unspecified, describe progression without numerical timestamps and return an empty moments list. The editor aligns to the events actually generated. Do not claim to have heard an audio reference that was not supplied to your perception input. Keep the existing JSON schema, with no additional fields, and keep the prompt under100 words.\nOUTPUT CONTRACT: Return only a JSON object with the fields below. Choose bpm60..200, energy calm/balanced/intense, and a key A..G with optional # or b followed by major/minor. The music prompt is at most100 words and the reason at most25. Unless the user supplies explicit timed musical accents, moments MUST be the empty array []; do not generate a timing plan. If timed accents are supplied, use objects with numeric at (seconds), event (text), strength (0..1). Do not use time/description fields.\n{\"prompt\":\"genre, mood, groove, selected sonic signatures, production, development and ending\", \"bpm\":120, \"energy\":\"balanced\", \"key\":\"C major\", \"reason\":\"brief musical rationale\", \"moments\":[]}"
      for (const phase of ['stage1', 'shot', 'final']) {
        const prompt = files[phase]
        const encoder = Object.values(prompt).find(node => ['TextEncodeAceStepAudio1.5', 'MajoorYuE2Style'].includes(node.class_type))
        if (!encoder) continue
        Object.assign(prompt, structuredClone(ancestors(output, [reference[0]])))
        prompt.music_vision = structuredClone(reference[1])
        Object.assign(prompt.music_vision.inputs, { prompt: '', system_prompt: system, max_length: 1536 })
        prompt.music_vision.inputs['sampling_mode.temperature'] = 0.4
        prompt.music_direction = { class_type: 'MajoorMusicDirection', inputs: { assessment: ['music_vision', 0], user_mood: '', bpm: 0 } }
        Object.assign(encoder.inputs, encoder.class_type === 'MajoorYuE2Style'
          ? { prompt: ['music_direction', 0], bpm: ['music_direction', 1], key: ['music_direction', 3], lyrics: '' }
          : { tags: ['music_direction', 0], bpm: ['music_direction', 1], keyscale: ['music_direction', 3], lyrics: '' })
        for (const node of Object.values(prompt)) {
          if (node.class_type === 'MajoorMusicFit') Object.assign(node.inputs, { energy_goal: ['music_direction', 2], moments_json: ['music_direction', 5] })
          if (node.class_type === 'ComfyMathExpression' && node.inputs.expression === 'a + 80') node.inputs.expression = 'max(24, a + 8)'
        }
        const roots = Object.entries(prompt).filter(([, n]) => ['SaveVideo', 'MajoorSaveProjectInfo', 'MajoorSaveProjectMusic', 'MajoorEnergyReport'].includes(n.class_type)).map(([id]) => id)
        files[phase] = ancestors(prompt, roots)
        slots[phase] = Object.fromEntries(Object.entries(slots[phase]).map(([key, entries]) => [key, entries.filter(([id]) => id in files[phase])]).filter(([, entries]) => entries.length))
        slots[phase].music_seed = Object.entries(files[phase]).filter(([, n]) => ['TextEncodeAceStepAudio1.5', 'KSampler'].includes(n.class_type) && 'seed' in n.inputs).map(([id]) => [id, 'seed'])
        Object.assign(slots[phase], { music_context: [['music_vision', 'prompt']], music_mood: [['music_direction', 'user_mood']], music_bpm: [['music_direction', 'bpm']] })
      }
    }
    for (const phase of ['stage1', 'shot', 'final', 'local']) {
      if (files[phase]) upgradeMusicToYuE2(files[phase], slots[phase])
    }
    if (mode === 'text' && files.stage1.music_vision) {
      const prompt = files.stage1
      const planner = Object.entries(prompt).find(([, n]) => n.class_type === 'TextGenerate' && Array.isArray(n.inputs.system_prompt) && prompt[String(n.inputs.system_prompt[0])]?.inputs.skill === 'timeline_planner')
      if (!planner) throw new Error('Text music needs its visual planner')
      prompt.music_story_context = { class_type: 'StringConcatenate', inputs: { string_a: '', string_b: [planner[0], 0], delimiter: '\n\nVISUAL NARRATIVE PLAN (timings describe visual intent, not heard musical events):\n' }, _meta: { title: 'Music context: visual plan first' } }
      prompt.music_vision.inputs.prompt = ['music_story_context', 0]
      prompt.music_vision.inputs.system_prompt += '\nThe supplied visual plan establishes the narrative order, causal actions, reveals and final hold. Shape the musical progression around that sequence while preserving explicit user genre and vocal preferences. The plan is context, not a replacement output contract. Its timestamps are intended visual events, not guaranteed generated musical attacks. Do not reorder the visual story to force an assumed drop.'
      slots.stage1.music_context = [['music_story_context', 'string_a']]
    }
    for (const [name, data] of Object.entries(files)) {
      await fetch('/api/userdata/' + encodeURIComponent(`secator_${mode}_${name}.json`) + '?overwrite=true', { method: 'POST', body: JSON.stringify(data) })
    }
    return { nodes: Object.fromEntries(Object.entries(files).map(([k, v]) => [k, Object.keys(v).length])), slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, Object.keys(v)])) }
  }
})()
