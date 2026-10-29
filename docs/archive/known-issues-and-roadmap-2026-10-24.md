> Historical roadmap with selected status corrections on 2026-10-26. For current setup and licensing, use [installation](../installation.md), [licenses](../../LICENSES.md) and [submission readiness](../submission-readiness.md). Remaining estimates below are not current validation claims.

# Known issues, fixes and roadmap

State of the project on 24 October 2026, the week of the Open Source Higgsfield challenge (submissions close on 30 October, 9 am PT).

## Audit correction update

The local reliability fixes are documented in [audit-fixes.md](../notes/audit-fixes.md). They replace the older descriptions of job persistence, fixed shot-time estimates and shared mutable projects below. Remote/cloud execution, third-party licence questions, publication and new social editing features remain separate work; no cloud deployment or publication is implied by the local fixes.

Each issue says **what is true today**, **why it matters**, **how to fix it** and **how big the fix is** (rough estimates, not promises). What was tested and what was not is stated each time; "not tested" means no run was made, not that it fails.

- [1. Issues](#1-issues)
- [2. Roadmap](#2-roadmap)
- [3. What was tested](#3-what-was-tested)

---

## 1. Issues

### A. Cloud and distribution

#### A1. The three prompts share their state through the disk
- **Today.** A job runs three prompts one after the other: the plan, one prompt per shot, then the edit. They hand the project to each other through files that ComfyUI writes: `output/MajoorVideoTools/<project>/manifest.json` and `_jobs/<job>.json`. The app reads these files directly (`backend/runner.py`, `backend/server.py`).
- **Why it matters.** The Comfy SDK returns files only. On Comfy Cloud or on a deployment, nothing says that the prompts of one job run on a machine that shares a disk. The app cannot read the project folder of a remote machine either.
- **Fix.** Add a second way to run, next to the local one: **one prompt for the whole job** (plan → shots → edit in a single graph, as in the original workflow), whose only output is the final video and a small JSON of the plan. For regenerating one shot or editing again without regenerating, send the existing takes back as inputs (the SDK sends files) to a second template, "edit again".
- **Size.** 2 to 4 days with per-shot regeneration; about 1 day for "generate" only.
- **Not affected today.** Everything works locally.

#### A2. Custom nodes on a remote service
- **Today.** The workflows need ComfyUI-Majoor-VideoTools, KJNodes, comfyui_controlnet_aux and ComfyUI-Easy-Use.
- **Why it matters.** The Comfy pages say a *deployment* (Comfy API) carries its own nodes in a **Build** (ComfyUI version, custom nodes, models, Python dependencies). They do not say that Comfy Cloud itself accepts any node pack; assume it does not.
- **Fix.** Make a Build "SECATOR" with these four packs, deploy it, and point the app at it by changing `COMFY_BASE_URL`. The app needs few changes.
- **Open points (not checked).** The exact `comfy-cli` commands to create a Build; whether ffmpeg and the output folders of the nodes work in the Linux/NVIDIA image; the cost of a deployment that carries tens of GB of models. The service is in beta and needs a paid plan.
- **Size.** 2 to 3 days, most of it spent testing in the image.

#### A3. A judge without a key cannot try a cloud version
- **Today.** The app is local only; it needs a GPU with enough memory for H3, Gemma 4 and the other models.
- **Fix.** Keep local as the main path. For the contest: complete setup instructions, a short demo video, and a mock mode (`SECATOR_MOCK=1`) that runs the whole interface without a GPU. Cloud stays an option, configured by a key and a URL, and greyed out when absent.
- **Size.** Mostly done; the demo video is the missing part (to be recorded).

#### A4. A hybrid mode (planning and edit local, shots by API)
- **Idea.** Generate the shots with the Comfy Router (H3 as an API) and keep the rest local. It would let people without a large GPU try the app.
- **Cost.** A small prompt that registers a video received from the API as a take (`Apply Shot Metadata`), plus a settings choice. About 1 to 2 days.
- **Consequence.** It leaves the "Open Weights Only" category (partner API), so it is optional and must be labelled.

### B. Licences and rules

#### B1. MiniMax H3 licence territory
- **Today.** The licence of H3 grants its rights "solely within the Applicable Territory": the world except the European Union, the United Kingdom, the Republic of Korea and the United States. Section V.4 forbids using or displaying the weights *or their outputs* outside it. The README says so.
- **Why it matters.** Running H3 from one of these territories is outside the grant as written. This is a literal reading, not legal advice. The challenge itself features H3 with a bonus, so sponsorship does not establish a personal authorization. The official Comfy licensing page distinguishes local use from Cloud rights.
- **Fix.** Establish the required authorization with the model rights holder or authorized licensing channel. Separately ask the organizer to confirm category eligibility. Neither discussion nor a competition bonus establishes the other permission. A cloud alternative would need separate implementation and provider-term review.
- **Size.** One message.

#### B2. Other model licences
- ACE-Step belongs to historical experiments, not the maintained Studio generator path; the old risk label is not a current license clearance.
- Qwen3 4B base weights are identified as Apache-2.0 by the official model card; packaged checkpoint provenance still matters. Qwen3-VL 32B, FLUX.2 klein 4B, Gemma 4, BiRefNet and DWPose were read as Apache 2.0 or MIT from model pages or secondary sources.
- YuE2 **is the active music generator**. Its weight terms and additional individual-creator permission are documented in [LICENSES.md](../../LICENSES.md); the former blanket claim about noncommercial outputs was incorrect.
- **Fix.** Read the official licence of each model once more before the submission, and keep the table of the README up to date.

#### B3. Open Weights Only: category rules and model terms
- **Today.** The page says "no partner nodes or APIs, open-weights models only". The workflows use no partner node (checked on the exported prompts). H3 is open weights under a custom licence, not open source.
- **Fix.** Say exactly this in the submission form, and let the judges decide.

#### B4. Rights of the reference videos, the music and the people
- **Today.** A Remix follows the cuts, the camera and the rhythm of a reference video; a Music edit follows a track; the references can show real people. The app checks none of this, and keeps everything on the user's computer.
- **What is done.** A note next to the video and music slots, on the first screen and in the Remix presets ("use your own video or a free one"), and a section in the README.
- **Fix, later.** Free-to-use reference videos and tracks to ship with the presets (they were postponed), a short first-run notice that the user has to accept, and a "made with" line in the exported project.
- **Size.** Half a day, plus the choice of the media.

### C. What the app depends on

#### C1. The app edits the manifest of the pack
- **Today.** To change the prompt of a shot, the app writes `plan.prompt` in `manifest.json`; to choose a take, it writes `active_revision_id`; to free space, it deletes files and revisions. The next prompts read the manifest again.
- **Why it matters.** If the manifest format of VideoTools changes, the app breaks without a clear error.
- **Fix.** Add small nodes to the pack (`Set Shot Prompt`, `Choose Take`) that make these changes inside ComfyUI, and call them with a prompt. The manifest then stays private to the pack. Until then, the format is fixed by the tests of both repositories.
- **Size.** 1 day.

#### C2. The tempo is read from a warning
- **Today.** The timeline reads the tempo with a regular expression on the text "Tempo 120.1 BPM (detected)…" in the manifest warnings (`backend/server.py`, `/timeline`).
- **Fix.** Write the tempo and the beat phase as structured fields in the manifest (`detection.tempo_bpm`, `detection.beat_offset`), and read them. This also removes the need to *fit* the beat grid to the cuts in the interface (`frontend/src/rhythm.ts`): the real grid can be drawn.
- **Size.** Half a day.

#### C3. The output folder is guessed
- **Today.** The app finds the output folder of ComfyUI from `/system_stats` (the `--output-directory` argument). If ComfyUI was started another way, it cannot, and says so (`SECATOR_OUTPUT_DIR` sets it by hand).
- **Fix.** A node that returns the folder (or the `Save Project Info` node writing its absolute path), and a check in `/api/health` that says clearly what is missing.
- **Size.** Half a day.

#### C4. SDK and proxy versions
- **Today.** `comfy-sdk>=0.5,<0.6` and `comfy-api-proxy>=0.1.6`. The Comfy API v2 and the platform are in beta; changes inside v2 are additive, breaking ones ship as v3.
- **Fix.** Pin exact versions in the release, keep a smoke test (`scripts/run_job.py`) to run after each upgrade.

#### C5. No live preview during generation
- **Today.** The code handles `Preview` events, but the local proxy sent none in a full job (0 received). The player shows a progress card (stage, shots as they are made, time left) instead.
- **Fix.** Check whether the proxy has an option for previews, or poll the `/view` route of ComfyUI for the last output of the running node. If neither exists, keep the progress card.
- **Size.** Unknown until checked; 1 day to try.

### D. Quality and tests

#### D1. Voice and dialogue
- **Today.** The path works (a voice sample and a dialogue were sent, two jobs finished with an audio track). The sample was a synthetic tone, so the **quality of the voice was not judged**.
- **Fix.** Test with a real speech sample of 5 to 10 seconds, in the language of the dialogue, and write the result in the docs.

#### D2. Landscape and square videos
- **Today.** The viewer adapts to any format (empty frames were checked in 9:16, 16:9 and 1:1), but every real result tested so far was vertical (448×800 or 480×850).
- **Fix.** One Remix with a 16:9 source and one Text job in 16:9, then check the viewer, the beat grid and the export.
- **Size.** Half a day, mostly GPU time.

#### D3. Garbled takes are not detected
- **Today.** *Take Check* retries takes that are black, white or pure noise. A take with a distorted but non-empty picture passes.
- **Fix.** Add a cheap check on the take (for example temporal flicker, or a similarity score with the reference), or let the user lock and redo shots, which the interface already allows.

#### D4. Test coverage
- **Today.** 24 backend tests and 21 interface tests, all with a fake client or a simulation (no ComfyUI). Real runs were made by hand (Remix, Text, Music, cancel, regenerate, edit again).
- **Fix.** An opt-in end-to-end test (`pytest -m real`) that runs a 6-second draft Text job against a running ComfyUI and checks the video, the manifest and the cancel. A browser test (Playwright) for the main path.
- **Size.** 1 to 2 days.

#### D5. Time estimates in the shot panel
- **Today.** "about 30 s" comes from fixed numbers measured on one GPU (20, 45, 85 s per shot for draft, standard, max).
- **Fix.** Keep the duration of each shot in the job state and show the average of the shots already made.
- **Size.** Half a day.

#### D6. A place plate can contain a person
- **Today.** The empty plate of a place (FLUX.2 klein) is the last picture of every shot in that place. Nothing checks that it is empty; a person drawn into it would appear in every shot of the place. Higgsfield's Katana notes the same problem with its own plates (a person in 6 of 8, despite "no people").
- **Fix.** Look for a face or a body in the plate; if one is found, make the plate again with another seed (once).
- **Size.** Half a day.

#### D7. The energy of a reference video is not measured
- **Today.** In Remix the effects come from the source shots, and in Text and Music from the planner. Nothing measures how many cuts, flashes, shakes and camera moves per second a reference has, so a flat edit is not noticed.
- **Fix.** Measure those rates on the source (Scene Detect already gives the cuts), give them to the planner as a line of the EDIT RHYTHM, and compare with the result.
- **Size.** 1 day.

### E. Product and safety

#### E1. Local, single user, no login
- **Today.** The server listens on `127.0.0.1` only; uploads and projects are open to anyone who can reach it.
- **Fix.** Keep it local. If it must be shared on a network: a bearer token and a limit on upload sizes. Document that it is not meant to be exposed.

#### E2. Disk use
- **Today.** Projects and takes pile up in the output folder of ComfyUI (about 10 to 45 MB per short project, much more at full quality). The library shows the size and can delete the takes that are not used or the whole folder.
- **Fix.** An optional automatic clean-up of old projects, and a warning when the disk is almost full.

#### E3. Interface checks left
- Small windows (below 800 px) use the stacked layout; it was checked before the zoom control and not after.
- The French texts were written with the English ones and have not been proofread.
- Keyboard use and screen readers: lists, buttons and the shot panel have names and keys, but there was no audit.

#### E4. Presets have no media yet
- **Today.** Six presets, without pictures or loops (the cards show their mode symbol). The format supports `"preview": "file.gif|mp4|jpg"` in `presets/media/`.
- **Fix.** Add free-to-use reference videos once chosen (they were postponed by the author).

### F. Process, before the submission

- **The two repositories have uncommitted work.** `ComfyUI-Majoor-VideoTools` has changes after its last commit (take check, sound effects, project nodes, workflows) and the app repository has no commit yet.
- **The app repository is nested** in the folder of the pack and ignored by it. The contest wants a public repository: it must be pushed on its own.
- **The demo video is not recorded** and the form is not filled.

---

## 2. Roadmap

### Now: submission (before 30 October, 9 am PT = 5 pm in Paris)

| # | Task | Why | Size |
|---|---|---|---|
| 1 | Ask the organisers about the H3 territory (B1) | the only point that could disqualify | 1 message |
| 2 | Commit and push the pack, then the app repository, public, with a licence and the setup instructions (F) | required by the challenge | 1 hour |
| 3 | Re-read the licences (B2) and the README table | accuracy | 1 hour |
| 4 | Test voice with a real sample (D1) and a landscape Remix (D2) | avoid a surprise in the demo | half a day |
| 5 | Record the demo: Remix of a reference edit, Text, Music, regenerate one shot, edit again, cancel | the deliverable | the author |
| 6 | Fill the form and describe "Open Weights Only" and the H3 bonus as they are (B3) | the deliverable | 1 hour |
| 7 | Fresh install check on a clean folder: `pip install`, `npm run build`, start, one draft job | what a judge will do | 1 hour |
| 8 | README: say how SECATOR differs from Katana (local and free; Remix keeps the cuts and swaps the subject) | clear position | 30 minutes |
| 9 | Check that a place plate has no person (D6) | a stray person in every shot of a place | half a day |

### Next: v0.2, solid local (after the challenge)

| # | Task | Reference | Size |
|---|---|---|---|
| 1 | Nodes `Set Shot Prompt` and `Choose Take`; the app stops writing the manifest | C1 | 1 day |
| 2 | Structured tempo and beat phase in the manifest; real beat grid in the timeline | C2 | half a day |
| 3 | Output folder returned by a node; clearer health check | C3 | half a day |
| 4 | Real end-to-end test and a browser test | D4 | 1–2 days |
| 5 | Durations per shot, better time estimates | D5 | half a day |
| 6 | Look into live previews | C5 | 1 day |
| 7 | Presets with media | E4 | depends on the videos |
| 8 | Check of the small-window layout and French texts; accessibility pass | E3 | 1 day |
| 9 | Measure the energy of a reference video (cuts, flashes, shakes, camera moves per second) and give it to the planner (D7) | D7 | 1 day |
| 10 | Effects of the plan: `handheld`, `pan`, `roll` camera moves; `grain`, `vignette`, `light leak` layers for the VHS look | Katana review | 1 day |
| 11 | A pack of recorded CC0 sound effects instead of the ones made by the code, and a true-peak limiter at -1 dBTP | Katana review | 1 day |
| 12 | A shot that is only a flash, a colour or a title card is drawn by code, without calling H3 | Katana review | half a day |

### Then: v0.3, remote

| # | Task | Reference | Size |
|---|---|---|---|
| 1 | "One prompt" mode: the whole job in one graph, only the video and a JSON out | A1 | 1–4 days |
| 2 | "Edit again" template that takes the existing takes as inputs | A1 | 1–2 days |
| 3 | Build "SECATOR" and a deployment; the app points at it | A2 | 2–3 days |
| 4 | Hybrid mode: shots by the Router, the rest local, marked as not open-weights-only | A4 | 1–2 days |
| 5 | Optional token and size limits if the app is shared on a network | E1 | half a day |

### Later: ideas

- **Songs with words.** Historical proposal superseded by the YuE2 migration; the maintained Studio uses YuE2. Future vocal features still need appropriate terms and review (B2).
- **Reorder shots** by drag and drop, using the manual order that Shot Assemble already has.
- **A check for garbled takes** (D3).
- **Face-tracked graphics** (cheeks, ears, blush) as a separate layer, as Katana does; the code only measures the position, it never changes a face.
- **Automatic clean-up** of old projects (E2).
- **A container image** with the app, ComfyUI and the node packs, for a one-command start.

---

### Audit of the edit styles (25 October): what was corrected

| Finding | State |
|---|---|
| The dials chosen by the user were ignored without a profile | Fixed: they are written alone ("EDITING SETTINGS"); with a profile they are stated to win over its text |
| A softer transition setting kept the flash, strobe and glitch wording of the profile | Fixed: the setting says no flash, whip, strobe, glitch or punch, and that it wins over the profile text |
| A music grid of 18 steps made 18 generations | Fixed: the app asks for one take per ~3 s; the grid steps inside a take are its sub-cuts (15 s at 140 BPM: 5 takes, 18 cuts) |
| The sound of a take did not follow a sped-up or slowed cut | Fixed for constant speeds (`atempo`); a cut with a speed ramp has no sound of its own |
| The panel showed 50 % ducking where the edit used 0 % | Fixed: the panel shows what the final prompt applies; its changes stay until the edit succeeds |
| Effects off still let the planner write effects | Fixed: the planner is told to leave them out |
| `dissolve` and `crossfade` became a blur | Not implemented: the profiles no longer ask for them, the planner only knows the transitions the engine draws |
| The music could be made again at each edit | Fixed for Text and Music: the retained music is a file of the project (`music/retained.wav`) that the shots and the edit load. Projects made before this change have no such file. Remix still makes its music in its edit |
| The ten profiles were mixed texts | Rewritten on one structure: intent, progression, camera, rhythm, effects, art direction; the music of a profile is a fallback only |

### Audit of the text, the sound effects and the cuts on the music (25 October): what was corrected

| Finding | State |
|---|---|
| A text sat 2.8 % from the bottom of the frame, in the caption area of a phone app | Fixed: a safe box per format (a vertical video leaves about 9 % at the top, 24 % at the bottom, 7 % at the sides and 14 % on the right for a text anchored on the right) |
| A text longer than the frame was cut off and drawn in the top left corner | Fixed: the text is cut into lines and made smaller until it fits the safe box |
| The text had one font, one white colour, no outline and showed for the whole shot | Four looks (`impact`, `clean`, `serif`, `mono`; the first one of each list that the machine has), an outline and a soft shadow, `start` and `end` inside the shot, `fade` or `slide_up` |
| The sound effects started at the cut, a whoosh peaking after it | The whoosh and the swell now start before the cut so that their weight lands on it |
| A hit at the start of every shot, whatever the music | A hit is played only where the music has an attack, and goes onto it; no two effects closer than 0.4 s (the heavier stays); the level follows the loudness of the music; the hit and the impact sit above the sub of the music |
| The cuts of a shot went to every half beat, accent or not | A cut goes to the strongest attack (kick and sub weighted first) within a step and a half of the grid, half a second at most, and to the grid when no attack there is strong. On the music of the "Hook + product drop" test, with the planned cuts moved at random by up to 0.2 s, the share of cuts within 50 ms of a kick attack went from 20 % to 28 % |

Still open: the planner does not hear the music in Text mode (it writes the cuts, the cut snapping then moves them to the attacks); recorded sound effects instead of the ones made by the code; text animations beyond fade and slide; the placement of a text on a beat.

Still open: a real crossfade between two takes; the sound of a speed ramp; the Motion Graphics JSON in the edit panel (to fold); a rule of density and silence for the automatic sound effects.

---

## 3. What was tested

| Area | Checked | How |
|---|---|---|
| Remix, Text and Music jobs, start to finish | yes | real runs through the app (draft quality), the videos have audio |
| Remix with a reference video, a voice sample and a dialogue | yes, path only | a real run; the voice sample was synthetic |
| Text with a voice sample and a dialogue | yes, path only | same |
| Regenerate one shot, edit again with another style, choose another take | yes | real runs, from the API and from the interface |
| Cancel in the middle of a shot | yes | the queue of ComfyUI was empty afterwards |
| Errors named by node (failed prompt) | tests only | with a fake client |
| Live preview during generation | no | none arrives from the local proxy |
| Landscape or square results | no | only empty frames |
| Delete with files, free space | tests only | not run on real projects |
| Presets saved, imported, exported, applied and undone | tests and the interface | no preset has media |
| Interface at 70 to 110 % and at several window sizes | yes | measured in the browser pane (765 px to 1920 px wide) |
| Cloud, deployment, Build | no | research only (A1 to A4) |

Test commands: `.venv/Scripts/python -m pytest` (24 tests) and `cd frontend && npm test` (21 tests).
