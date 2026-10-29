# Changes

A log of what was changed, newest first. Each entry has its date and time, the files, how to check it, and what is needed for it to take effect.

## 2026-10-27 - Choose the source portion in Shot

- Generated takes now expose a draggable source window in the Shot panel, with keyboard adjustment, local loop preview, explicit Apply and Reset start. The edit keeps its shot lengths and music timing. EN/FR labels follow the Studio language.
- The source start is stored per take as optional `source_start_seconds` (old projects default to zero). Assembly seeks picture and take audio together, including sub-cuts and composed layers; cache keys and thumbnails reflect the changed selection. Source files, takes and previous exports stay intact.
- Available movement accounts for speed and sub-cut source consumption. Unknown-duration, fully used, inactive or locked takes cannot be moved; server validation also rejects out-of-bounds values and changes during generation. Original, ungenerated Remix segments are outside this initial control.
- Verified with decoded picture/audio and unchanged frame count; backend 126 passed/7 skipped, frontend 54 passed and production build passed. No H3/Yue2 generation or commit. Activate only after the current generation finishes, then reload the Studio.

## 2026-10-27 - Incremental engine and finishing improvements

- Rhythm analysis distinguishes absent/unreliable pulse from a measured tempo and a user-requested grid. Silent/ambient inputs retain usable windows without invented bar timing; edge fades remain applied. Existing rhythmic cases and tuple callers remain supported.
- SFX preparation/landing relationships preserve a planned riser with its impact while retaining collision/action protections. Optional sample anchors and seeded sound palettes preserve old banks and custom sample offsets. Local RMS balance diagnostics do not adjust gain automatically.
- Narrative coherence no longer freezes every location. H3 writers use the current dialogue/voice-reference notation and declared media mode, keep local scope, and add brief performance/optics guidance only where relevant. The default writer stays within its existing 2100-word budget.
- Assembly persists fingerprinted segment boundaries; HyperFrames records advisory observations from encoded frames. Real Canvas/HTML layout measurements supplement previews without a new UI panel. Missing optional diagnostics remain explicitly unmeasured.
- Short effect windows extract only their active frames; optical tracking keeps the full path. Optional layer-JSON packs and conservative reference-color accents do not change global defaults. Explicit accents retain the complete motion direction. Cache version advanced; no template re-export or new dependency.
- Verification: final broad pack pass 398 passed/1 skipped/1 deselected; final layout/prompt changes 26 focused tests passed. Backend 124 passed/7 skipped; frontend 51 passed, no frontend source changes. Real 4 s, 480x832, 96-frame HyperFrames smoke passed in 16.06 s. The 8 s, seed-427 narrative test completed after one documented technical retry for a seconds-suffix parser error. A finishing-only thin-line comparison preserves the takes/audio. These checks do not replace listening or artistic review.
- Planner timing accepts explicit seconds suffixes and rejects unrelated units. Geometry instructions explicitly use normalized fractions; the planner example remains synchronized. Existing subject masks can report text-bound overlap without another segmentation pass; faces and perceived contrast remain unmeasured.
- Installation uses existing services; original projects/media preserved. No commit. See pack docs/finishing-options.md for opt-in JSON and limitations.

## 2026-10-27 - Honest creative controls and retained briefs

- Text/Music now show three named fidelity/freedom levels; Remix shows actual 0.40–1.00 pose strength, retaining legacy behavior. Added accessible labels, scope/help text, no-reference handling and consistent preset chips. EN/FR copy is available.
- Shared semantic choices now reach enrichment and planning. Identity/outfit/product design remain invariants unless explicitly changed; flexible fidelity concerns framing/background/treatment, not arbitrary identity changes.
- Control-level changes preserve approved/manual text. Effective contexts normalize equivalent numeric settings, with legacy approval compatibility. `/api/brief-approve` reuses a retained edited brief with current validated settings without invoking a model. Existing-job regeneration keeps original settings, explicitly explained in the UI.
- Validation: 121 backend tests passed / 7 skipped; 51 frontend tests and production build passed; 26 pack profile/skill tests passed / 1 skipped. No new H3/Yue2 render or commit. Perceptual comparisons between levels remain future validation.

## 2026-10-27 - Capability matrix and maintained roadmap

- Added the pack-level `ROADMAP.md`: available/partial/planned capabilities, implemented foundation, creative-quality improvements, narrated shorts, subtitles, clipping, reframing, dubbing, infographics, additional backends, 4K upscale, agent orchestration and release work.
- Updated pack and Studio README status sections; corrected obsolete quality limits, Text music-order wording, location-plate descriptions and animated-counter claims. Retired presets and scene-illustration experiments are distinguished from adopted features.
- Replaced the historical roadmap landing document with current priorities and preserved its previous content under `docs/archive/known-issues-and-roadmap-2026-10-24.md`, with adjusted relative links.
- Documentation checks: four maintained documents decoded as UTF-8, balanced code fences and valid local Markdown targets; root documentation diff passes whitespace checks. No application code, service restart, model call or commit.

## 2026-10-27 - Adaptive dense edits

- Planner/enhancer distinguish global progression, generated takes and edited segments. Removed the one-take-per-1.2s ceiling; explicit counts and independent viewpoints take precedence over economy defaults. Existing H3 minimum generation length stays at 124 frames.
- Music Studio planning uses a candidate grid, not one generated take per three seconds. The new optional Create Timeline `rhythm_reference_only` labels timing as advisory; the Studio removes only the musical skeleton constraint, fits total duration, and applies the same deterministic density guard as Text. Manually fixed skeletons remain fixed.
- Dense-edit checks count short independent takes. The guard preserves existing cuts and protected actions, no longer treats any slow sub-cut as sufficient high density, and may add accents to up to three eligible interior takes without generating new viewpoints.
- H3 instructions and examples now describe one continuous take by default; post cuts/crops/transitions remain with the assembler unless filmed internal cuts are explicitly requested. Example copies synchronized.
- Validation: 39 focused pack tests; 118 backend tests passed, 7 skipped. Real procedural assembly: twenty segments across five takes, 15 seconds / 360 frames at 24 fps, with 3-frame inserts. Full pack: 376 passed, four stale example/recipe assertions identified and resolved; affected-file recheck had 84 passed / 1 skipped, with the final updated example assertion then passing separately. Fashion example now keeps editing in JSON; location recipe copies are synchronized. Evidence in external audit workspace `work/dense-full-core.log`, `work/dense-final-targets.log` and `outputs/dense-edit-verification/`.
- No UI changes, new H3/Yue2 audition, model download, illustration prepass, preset creation or commit. Studio and ComfyUI restarted at idle; final health is clear and the live Create Timeline schema confirms the new optional input.

## 2026-10-27 - Set-dressed location plates

- Kept the existing generation pipeline: no scene-illustration pre-generation adopted. The H3/FLUX illustration experiments remain external test artifacts.
- Location planning now describes useful fixed furnishings, objects, mounted artwork, practical lights and their placement. Local prompts/image prompts carry the relevant elements because the video writer receives only its selected shot.
- PLACE instructions preserve this set dressing, distinguish actor identity from printed artwork, and let movable/action props follow the current shot state rather than resetting to the cached plate.
- Creative Text/Music source workflows and their shot API templates use an unoccupied, set-dressed plate prompt rather than an empty-room/no-text blanket instruction. Requested physical artwork is allowed; invented lettering and actual people are excluded. The visual checker distinguishes clearly mounted printed figures from actual people and treats ambiguity as uncertain. This is a vision-model instruction, not a guaranteed semantic classifier.
- Validation: 36 focused skills/location-contract tests passed; example prompts synchronized. No frontend controls, model download, new video generation or commit. This affects future requests using the existing Places option.

## 2026-10-27 - Compact edit controls

- Edit style: Motion Graphics layer JSON is collapsed by default; Reset uses the shared secondary button style and spaced action row.
- Shot prompt panel: removed the Lock/Unlock button. Existing locked-state handling and timeline controls remain compatible.
- Prompt/input panel: Final audio choices are directly visible instead of hidden inside a disclosure. Existing EN/FR labels retained.
- Validation: production frontend build passed, 46 tests passed. Live browser confirms Final audio is a heading with visible audio choices. Refresh the Studio page to load the new bundle; no service restart or generation interruption.

## 2026-10-27 - Global narrative, local shot generation

- `core/skills.py` and `nodes/edit_skills.py`: the H3 plan writer receives the selected shot's local message without the full-film brief when local rhythm/shot data exists. Reference/media announcements and local dialogue are retained. Brief-only usage and other skills, including Remix, remain compatible.
- Planner, enhancer and H3 writer skills distinguish persistent identity/design from intentionally evolving location, light, emotion and prop state. Each narrative shot performs its own event once, inherits prior state without replaying it, then holds its consequence. No fixed five-event formula is imposed on abstract/performance edits.
- The inspected Sun Thief manifest had five distinct plan prompts; full-brief leakage into the writer was confirmed in the graph, but visual semantic repetition is not automatically measured. This fixes input scope rather than promising model compliance.
- Validation: 26 targeted tests passed; planner/writer example copies synchronized. Studio and ComfyUI restarted at idle; final health reports proxy, ComfyUI and VideoTools available with no load errors or missing nodes/models. No new H3/Yue2 generation, workflow re-export, UI control or commit.

## 2026-10-27 - Motion Graphics audit corrections (supersedes 13:01 validation)

- Planned text now reaches the `words` renderer through `core/fx.py`; explicit existing animations are preserved. Legacy FFmpeg falls back to fade for `words`.
- Planned text carries shot-local timing and `shot_id`, keeping musical onset snapping within its shot. Word indexing is cumulative across lines, wrapping and repeats; `accent_last: false` survives parsing.
- Reading advisories include word stagger and exit time. HyperFrames receives the shared Python safe boxes and timing constants, bounds moved/rotated text, and eases fades while preserving explicit linear easing. Cache version 9; CLI remains pinned at 0.8.201.
- Validation: 12 focused tests and 117 backend tests passed (6 GPU skips). A real 72-frame white-background render was visually inspected for outline and final-word accent. Full pack run: 368 passed, 1 skipped, 1 deselected; one assertion still expected the old independent safe margins. That test is replaced with real-render checks against the shared safe-box contract in landscape, portrait and square; its result is recorded in the external correction report.
- The three shared-safe-box render checks passed. Studio and ComfyUI restarted at idle; final health confirms ComfyUI, proxy and VideoTools available, with no load errors or missing nodes/models. No workflow re-export, commit, model call, new panel, runtime upgrade, style pack, subject-colour extraction or counters.
- Evidence and final activation status: external audit workspace `docs/CORRECTIONS-MOTION-GRAPHICS-2026-10-27.md`, `outputs/motion-graphics-fixed/`, `work/motion-fix-final-core.log`, `work/motion-fix-safe-matrix.log`.

## 2026-10-27 13:01 - Motion Graphics text: readable, timed to the music, word by word

- `web/hyperframes_layers.js`: text layers get a black outline by default (5 % of the font size); entrances ease out on a quartic curve; an exit lasts half of the entrance (at least 0.1 s); new animation `words` reveals each word through a mask, 0.09 s apart, and draws the last word in the accent colour of the direction.
- `core/motion.py`: `words` added to the animations; text layers default to the safe box (`safe` true) and to a 0.05 outline.
- `backend/unified_motion.py`: planned text uses `words` by default and `sync: onset`, so its start snaps to the nearest attack of the music (within 0.15 s).
- Tests: the full suite passes (346 passed, 2 skipped). No generation was run, so the look of the result was not checked on a video yet.
- Not done: items 4 (a fixed motion pack per style) and 5 (accent colour drawn from the subject), counters in the word animation. Restart ComfyUI and re-export the templates for the change to reach the Studio.


## 2026-10-27 - Story-first choice and final scoped validation

- After listening to the two bounded Yue2 auditions, the user selected narration before music. Text `stage1.api.json`, its slots and `scripts/export_templates.js` now feed the visual plan and original music preferences into the existing music director through Core StringConcatenate. No extra model call; graph-cycle tests pass. Music/Remix template fingerprints remain unchanged.
- `core/story.py` also warns about an explicitly declared handoff changing state without new information explaining it. This is an advisory declaration check, not semantic pixel analysis. Final continuity/plan checks: 14 passed, one real-workspace report test deselected.
- Backend final: 117 passed, 6 GPU tests skipped. Frontend remains at 46 passed with successful production build. All three short modes reached a final export. Text and Music exports are 768x1344; Remix retains its 608x1056 source dimensions.
- The intrusive Text graphic was replaced using the existing shot-local layer override, without a new take. Music's framing changes were present in the raw H3 take, so disabling assembly sub-cuts alone could not remove them. Its stable 3.0-5.0 s portion was registered as a labelled derived take and reassembled; original take_001 remains available. No H3 or Yue2 call for these visual corrections. Derived Music export: 2.005 s, -14.3 LUFS, -1.8 dBTP.
- The progress-state fix limits cosmetic disk writes while keeping live UI events; critical transitions and request handles still persist immediately. A Windows 2.2 s reader-lock test passed. This prevents a transient cosmetic-state lock from cancelling valid GPU work.
- Final report and evidence live in the external audit workspace: `docs/VALIDATION-FINALE-SKILLS-SECATOR.md` and `outputs/skills-short-mode-checks/`. The checklist is closed only for its documented sample/contract scope. Human identity and general long-form narrative quality are not certified by product smoke tests.
- Activation: Studio and ComfyUI restarted at idle; final health confirms proxy, ComfyUI and VideoTools available with no missing nodes/models or load errors. No commit, model download, new production renderer or additional Studio panel.

## 2026-10-27 - Shared sound arbitration and live proxy contract

- Pack `core/editorial_cues.py`, `assembler.py`, `motion_scenes.py`: one limiter for automatic and explicit graphic cues, declared action/reveal/narrative/decoration priorities, protected action windows, repeat and density limits. Resolved timestamps and visual layers are retained; slower held edits with sparse measured attacks get more space. Assembly cache version 4; existing sound-effects switch retained.
- Pack `core/story.py`, `plan_checks.py`: advisory comparison of declared repeated events and possible returns to a pre-action state. Negations/numbers and deliberate loops/flashbacks are distinguished. No pixel semantics, automatic story rewrite or quality guarantee.
- Pack `skills/timeline_planner.md` and its generated example: document optional sound event roles. The example and skill remain synchronized.
- A real local submission exposed the proxy's rejection of SDK label objects. `backend/config.py` and `runner.py` now omit unsupported metadata labels by default while retaining the persisted idempotency key and known request handle. `SECATOR_JOB_METADATA_LABELS=1` is only for a host that explicitly supports platform label maps. An uncertain local submission with no handle remains blocked for manual reconciliation; no unfiltered history match or automatic retry is attempted. This supersedes any earlier claim that filtered label recovery was verified on this local proxy.
- A live planner returned `type: line`. Pack `core/motion.py` now accepts only the unambiguous aliases line/dot/ring for vector layers. Geometry and timing are preserved; conflicting aliases and unknown types remain errors.
- Validation: 112 backend tests passed, 6 GPU tests skipped; real public SDK/proxy text-only submission accepted without metadata. Pack integration run: 359 passed, one example-sync failure, one skipped and one deselected; corrected example then passed all 20 skills tests. Ten focused vector-alias/arbitration tests passed; four actual assembly/score tests passed. Three short 1 MP mode checks are tracked separately; no completion claim until their terminal states and artifacts are reviewed.
- Activation: Studio and ComfyUI were restarted at idle before the mode checks. No runtime/model upgrade, additional production renderer or commit. Registry fixtures, source-license snapshots and audit artifacts stay outside the product.

## 2026-10-27 - Literal planner inputs, bilingual presets and keyboard focus

- `backend/direction.py`, `backend/runner.py`: pass the actual duration, frame budget and exhaustive approved overlay text to the existing timeline planner. The brief enhancer receives no additional planning pass. Existing action-protection rules remain in the original planner skill.
- `scripts/planner_eval.py`: use the same contract as production, wire the requested seed to the actual TextGenerate nodes, and fingerprint the contract implementation. Ten-brief baseline: 7 errors/9 warnings; equal-budget expanded-contract run: 7 errors/3 warnings, including three schema failures. That expanded instruction was reduced. Two further literal-contract smoke cases had valid schemas but still repeated one title and missed one requested duration. No structural or artistic improvement is claimed from these small samples.
- The seven existing user presets now have individually authored French translations alongside their original English versions. Existing settings and base prompts were preserved; before/after snapshots are retained in the external audit workspace.
- `frontend/src/components/Dropdown.tsx`, `Library.tsx`, `index.css`: focused listbox, Home/End and arrow navigation, Escape return, normal forward Tab traversal, disabled empty lists, visible keyboard focus and library focus restoration. Secondary options keep their collapsed defaults.
- Validation: 110 backend tests passed, 6 GPU tests skipped; 46 frontend tests passed; TypeScript and production build passed. Chrome checks verified library and language-list focus restoration and collapsed secondary options. Document language now follows the selected interface language. A complete live journey remains separate.
- Activation: Studio backend restarted after an idle check; ComfyUI retained. Reload the built frontend. No model, runtime version, additional production renderer or commit was added. The registry component downloaded for inspection remains outside the project.

## 2026-10-27 - Continued skills adaptation

- Audio: decoded AAC true-peak verification, one bounded headroom correction, explicit 1 LU target assessment, silence/no-audio preserved. HyperFrames reports audio measured after its final remux. Explicit loudness_target=0 survives template export; missing values still default to -14.
- Shared score: assembly writes a per-export score linked to the video and layer fingerprints. SFX and finishing use the same frame-resolved layers and measured music events when available. Stale/incompatible scores fall back to existing finishing behavior. Cache versions bumped.
- Planner benchmark: fixed seeds, prompt/template/brief fingerprints, settings and elapsed time; bounded runs and timeout; scoped interruption; optional extended continuity fixtures. No statistical before/after quality gain claimed without live runs.
- Reuse existing story metadata and warnings in plan checks; flag sub-cuts in protected actions. No second planning model or workflow.
- SDK submission: persist idempotency intent before POST, attach a unique metadata label, recover a lost acknowledgement by public list_jobs lookup. No automatic resubmission. Ambiguous/missing matches remain blocked for reconciliation rather than duplicating GPU work.
- Presets: FR/EN variants preserved through backend save/reload/reimport and frontend import. Unknown vector shapes rejected before submission.
- Tests: pack CPU 350 passed, 1 skipped, 1 deselected; backend final 107 passed, 6 GPU skipped; frontend 41 passed and production build passed. A real 2-second HyperFrames fixture render verified score reuse, previews and decoded final audio; the event time was injected for the controlled test. No H3/Yue2 generation launched.
- UTF-8 checklist repaired and reread; completion markers now reflect verified implementation or existing coverage. Live planner baseline, subjective video comparisons, registry additions and full keyboard audit remain open.
- Documentation: workspace docs/SKILLS-EXECUTION-RESULTATS.md and PLAN-ADAPTATION-SKILLS-SECATOR.md. Targeted backups in work/skills-rest-backup. No commit.
- Activation: restart idle Studio/ComfyUI; frontend build is ready. Do not restart active work.

## 2026-10-27 - Skills adaptation, first verified increment

No GPU generation or commit was performed for this increment. Changes extend the existing implementation; existing Windows bounded replacement retries were preserved.

- `backend/storage.py`: serialize cooperating JSON writers with a per-file lock; keep atomic replacement, fsync, bounded Windows sharing retries and temporary-file cleanup.
- `backend/server.py`: serialize reconciliation of persisted SDK handles; concurrent requests no longer recover the same handle together.
- `backend/runner.py`: if progress/state tracking fails after submission, attempt targeted cancellation with a bounded wait. If cancellation cannot be confirmed, retain the saved handle for later recovery. Empty exception messages now identify the exception and explain that saved takes are retained. No automatic resubmission.
- `tests/test_skill_reliability.py`: six regression cases covering concurrent writers, previous-state preservation, concurrent recovery, empty timeout and lost progress with/without a reachable proxy.
- `core/text_timing.py`, `fx.py`, `motion_scenes.py`: shared readable hold budget, with entrance/exit outside the hold. Legacy overlay timing extends inside the containing shot only; unified finishing reports insufficient windows without changing explicit cut timings or words. HyperFrames cache version increased to 6 for updated advisories.
- `core/plan_checks.py`: inspect planned motion text, reject extra words even when the authorized title is present, count bursts as 3-6 frames at the plan FPS, and interpret text/cut negations in context.
- `core/edit_report.py`: sample inside every segment, including the opening, rather than always 0.3 s after a cut; report reconstructed-timeline provenance and its limitations.
- Validation: backend 100 passed, 6 GPU tests skipped; frontend 40 passed; targeted pack checks 44 passed, 1 deselected (the excluded existing test writes a planner report into the Studio workspace). Global pack suite not rerun. No artistic/full-video validation claimed.
- Remaining: unknown submission outcome before receiving an SDK id, final audio compliance policy, reproducible planner baseline and further plan lots. The checklist records partial progress, not blanket completion.
- Activation: Studio restart for backend changes; ComfyUI restart for core changes. Do not restart while any generation is active.

## 2026-10-27 10:08 · ComfyUI restarted, templates exported again

No generation was run.

- ComfyUI was restarted: the new `loudness_target` input of Shot Assemble and the new nodes are loaded; the queue was empty.
- The three templates (`workflows/text`, `music`, `remix`: `stage1`, `shot`, `final`, `local`, `slots.json`) were exported again from the graphs.
- `scripts/export_templates.js`, two fixes found while exporting:
  - `loudness_target` is set to -14 on the final prompt when the graph gives 0 (a graph saved before the input existed gives 0, and `??=` did not replace it). The three final templates now have `loudness_target = -14`: this activates a target, not a guarantee of final loudness or true peak compliance; validate the delivered mix.
  - The slot `unified_layers` of the final prompt also feeds the `motion_layers` input of Shot Assemble (the same layers reach the graphics and, as sound cues, the assembly). The export had only the graphics, and `tests/test_unified_motion.py` failed on it.
- Tests after the export: studio backend 94 passed, 6 skipped; pack 317 passed, 2 skipped (run before the export).
- Not run: a job with the new templates. The loudness step, the text timing and the edit report have not yet been seen on a new edit.

## 2026-10-27 09:24 · text timing, loudness, planner measure, edit report

No generation was run for any of this: the checks are unit tests and reads of finished jobs. ComfyUI was busy.

**Historical activation note (completed by the 10:08 entry above).** Restart ComfyUI (the Python of the nodes changed, and Shot Assemble has a new input), then export the templates again (`scripts/export_templates.js`): the exporter now sets `loudness_target` to -14 on the final prompt, and the templates in `workflows/` do not have it yet.

**State of the tests.** Pack: 317 passed, 2 skipped. Studio backend: 94 passed, 6 skipped.

### 1. Text: reading time, slower entrance, eased slide

- `core/fx.py`: `reading_seconds(content)` (one second, and a quarter of a second more per word past three); `text_overlay_filters` keeps a text on the screen at least that long when the shot allows it, brings it in over 0.35 s and takes it out over 0.18 s (an exit is about half an entrance); the `slide_up` offset eases out faster (`pow(1-p, 4)`, 4 % of the height; it was `pow(1-p, 2)`, 3 %).
- Not done: the words appearing one after the other with a mask, a rolling number.
- Test: `tests/integration/test_edit_polish.py` (`test_a_text_appears_and_leaves_at_its_time_inside_the_cut_that_holds_it`, `test_a_text_stays_long_enough_to_be_read`).
- Idea taken from the `motion-design` skill of `whaleyxbt/claude-motion` (MIT): a reading hold of at least one second plus 0.25 s per word beyond three, exits about half an entrance.

### 2. Loudness: the finished edit is brought to a target

- `core/audio_quality.py`: `measure_loudness(path)` (integrated LUFS and true peak, from FFmpeg's `ebur128`; both `None` for a file with no audio) and `normalize_loudness(path, out, target, ceiling, max_gain)`: a gain to the target, a limiter 0.5 dB under the ceiling (-1.5 dBTP by default), the picture copied, the audio encoded again at 256 kbit/s. A file with no audio, one below -60 LUFS (too quiet to be a mix) or one already within half a LU is copied as it is. The gain is capped at 18 dB.
- `core/assembler.py`: `AssemblyOptions.loudness_target` (0 leaves the mix as it is); the target is part of the cache key of the export; the normalization runs after the export is validated, and a warning says what was done (`Loudness -17.4 -> -14.0 LUFS (+3.4 dB), true peak ... dBTP`).
- `nodes/shot_assemble.py`: new optional input `loudness_target` (default 0).
- `scripts/export_templates.js`: `loudness_target` is set to -14 on the final prompt.
- Test: `tests/integration/test_loudness.py` (a quiet tone, a loud tone, a click track that only has to stay under the ceiling, silence, a file that is already at the target).
- Measured before this change, on the finished edit of the "Hook + product drop" job `8c3064a9cbc9`: -17.4 LUFS, true peak -1.5 dBTP.
- Idea taken from the `sound-design` skill of `claude-motion` (mastering to -14 LUFS, true peak under -1 dBTP); the code is new and uses FFmpeg, nothing was copied.

### 3. Planner measure: the same briefs, the same checks, before and after a change

- `core/plan_checks.py`: `check_plan(text, duration, density, text_allowed, text_on)` returns the issues of a plan without any model: the JSON and the schema; the durations add up to the length asked for; the sub-cuts add up to their shot; a burst of 3 or more cuts of 3 to 6 frames when the cut density is high, sub-cuts when it is medium, none when it is low; the words allowed on the screen are there once, no other text is invented, no text when it is off, at most 3 texts of 3 words; no usable prompt; a negation in a prompt; an unknown transition. `summarize(issues)` counts them.
- `tests/fixtures/planner_briefs.json`: ten briefs (perfume, slow point of view, hype, dream, outfit change, glow-up, beauty, cinematic, music video, aura) with their length, style, cut density and allowed text.
- `HyperKut Studio/scripts/planner_eval.py`: `--plans <folder>` checks plans that were saved (no model); `--run [--runs N]` asks the planner of the running ComfyUI for each brief (the language model generates: not while the GPU is busy), saves the plans to `workspace/planner_plans/` and writes `workspace/planner_eval.json`. It prints one line per brief.
- Tests: `tests/integration/test_plan_checks.py` (7).
- How to use: run `--run --runs 3` once before a change of the planner prompt and once after, and compare the totals.
- Not run: no plan was generated for the ten briefs, so there is no baseline yet.

### 4. Edit report: contact sheet, first frame, black stretches, cuts against the music, loudness

- `core/edit_report.py`: `cut_times(manifest)`, `contact_sheet(video, times, out_dir)` (one frame 0.3 s after each cut, tiled 4 x 2 with its time), `first_frame(video)`, `black_stretches(video)` (FFmpeg `blackdetect`), `sync_report(cuts, attacks, strength)`, `edit_report(project, video)` (writes `exports/edit_report.json` and `exports/sheet-N.png` in the project), and `REVIEW_CHECKLIST`, the checklist that a person or a vision model reads against the sheet.
- `scripts/edit_report.py`: `python scripts/edit_report.py <project id> --video <edit.mp4>`. No model and no GPU.
- Test: `tests/integration/test_edit_report.py` (5).
- Idea taken from the `review-loop` skill of `claude-motion`: look at a frame after every beat and check a list, never call a video done unread.
- Run on the finished job `8c3064a9cbc9` (read only): first frame fine; loudness -17.4 LUFS, true peak -1.5 dBTP; 9 cuts, 7 within 50 ms of a strong attack of the music (median 18 ms); **one black stretch from 2.17 s to 3.42 s** (the first tile of the sheet at 2.38 s is almost black: the silhouette-reveal shot after the whip). Whether that is wanted was not judged.
- Not done: the vision model that reads the sheet (it needs a generation), a button in the Studio.

### Other changes in the same pass

- `docs/changes.md`: this file.
- `tests/integration/test_loudness.py`, `test_plan_checks.py`, `test_edit_report.py`, `test_edit_polish.py` are new or extended; they use FFmpeg and Pillow only.

## 2026-10-27 (morning, before 09:24) · interface

- The line of the four steps under the timeline (Analysis, Shots, Edit & sound, Done) was removed: `frontend/src/components/Timeline.tsx`, its CSS, and the texts `stages` and `tip.stage` in `i18n.ts`.
- The length of the video can be typed in seconds (2 to 120) next to the list of 10, 15, 20 and 30 s: `frontend/src/components/Toolbar.tsx` (`SecondsField`, set when the field is left or Enter is pressed), `i18n.ts`, `index.css`, and `backend/models.py` (the limit went from 60 to 120 s). A length that is not in the list is added to it. Test: `frontend/src/__tests__/duration.test.tsx`.
- The Claude Code skills `caveman`, `caveman-commit` and `caveman-review` (from `juliusbrussee/caveman`) and `motion-design`, `review-loop`, `sound-design` and `web-sims` (from `whaleyxbt/claude-motion`) were installed in `~/.claude/skills`. They are not part of this repository.

## 2026-10-29 — Visual README and demo gallery
- New English README and French companion: purpose, three modes, local editable workflow, sourced Katana/Genjutsu comparison, Windows setup and dependency scope.
- Preserved previous README as README-REFERENCE.md with a supersession notice.
- Added eight supplied demo files, posters, local HTML players and SHA-256 manifest under docs/media/demos. Private review only; no media permission inferred from code licensing.
- Corrected stale default-enabled graphics wording in dependency-scopes.md. No application behavior changed; no restart or commit.


## 2026-10-29 — Contest README evidence pass
- Put the 1:40 presentation first, with a lighter 720p video and explicit provenance for the animated UI sequence, original Seedance intro and ElevenLabs narration.
- Added three live read-only browser screenshots, simple architecture, a recorded Fashion Remix recipe (seed/settings/input hashes) and dated validation scope.
- Distinguished recorded test results and presentation-render timing from fresh GPU generation qualification. Public source packaging and cleared reproducible media remain open.
- No generation, project edit, application-code change, restart, commit or publication.


## 2026-10-29 — Landscape README demo
- Replaced README presentation/poster with a simulated 16:9 walkthrough (about 70 seconds), reusing the approved voice and actual saved result. Previous vertical delivery retained separately.
- Full checks passed and final 1080p/24 fps file decoded without errors; README uses a smaller 720p copy. No source-code, generation, project edit, restart, commit or publication.

## 2026-10-29 — Landscape README demo
- Replaced README presentation/poster with a simulated 16:9 walkthrough (about 70 seconds), reusing the approved voice and actual saved result. Previous vertical delivery retained separately.
- Full checks passed and final 1080p/24 fps file decoded without errors; README uses a smaller 720p copy. No source-code, generation, project edit, restart, commit or publication.

## 2026-10-29 — Fashion Remix source attribution
- Credited silver.muse with profile link and thanks in both READMEs, demo provenance/media notes, recorded recipe and asset manifest. Attribution follows the owner identification supplied by the project author; no redistribution permission or endorsement is inferred.
