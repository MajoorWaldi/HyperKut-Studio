from typing import Literal

from pydantic import BaseModel, Field, field_validator
from .direction import validate_direction

Mode = Literal["remix", "text", "music"]
Stage = Literal["analyze", "shots", "edit", "done"]
Status = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class Upload(BaseModel):
    id: str
    name: str
    kind: Literal["video", "image", "audio"]
    url: str


class Settings(BaseModel):
    """What the interface sets; the controls of the workflow of the mode are filled from it (see templates.py)."""

    prompt: str = ""
    art_direction: dict[str, str] = Field(default_factory=dict)
    approved_brief: str = Field('', max_length=5000)
    approved_brief_context: str = ''

    @field_validator('art_direction')
    @classmethod
    def check_direction(cls, value):
        return validate_direction(value)

    duration: float = Field(15.0, ge=2, le=120)
    ratio: Literal["9:16", "16:9", "1:1", "3:4"] = "9:16"
    quality: Literal["draft", "standard", "max", "xhigh"] = "draft"
    structure: int = Field(85, ge=0, le=100)
    creativity: int = Field(50, ge=0, le=100)
    seed: int = 42
    audio: Literal["original", "new", "voice"] = "original"
    mood: str = ""
    bpm: int = Field(120, ge=60, le=200)
    effects: bool = False
    text: bool = False
    sub_cuts: bool = False
    sound_design: bool = False
    sound_effects: bool = False
    music_sync: bool = False  # H3 hears the music under each shot (Text and Music)
    retry_bad_takes: bool = True
    dialogue: str = ""
    places: bool = True
    camera: str = ""
    motion_design: bool = False
    music_volume: float = Field(0.0, ge=0, le=4)
    motion_direction: str = Field("editorial", max_length=12000)
    motion_title: str = Field("", max_length=120)
    motion_cues: str = Field("[]", max_length=24000)
    motion_layers: str = "[]"  # the layers of Motion Graphics (JSON): see the README of ComfyUI-Majoor-VideoTools
    subject_mask: bool = False
    redraw_text: bool = False
    pose_only: bool = False
    quality_check: bool = False
    music_energy: Literal["peak", "calm", "balanced", "intense"] = "peak"
    music_start: float = -1.0
    style: str = "none"  # the profile of the planner (Text and Music)
    cut_density: Literal["auto", "low", "medium", "high"] = "auto"
    transition_intensity: Literal["auto", "subtle", "moderate", "bold"] = "auto"
    cut_every: Literal["half_beat", "beat", "2_beats", "bar", "2_bars", "4_bars"] = "2_beats"  # the grid of the cuts on your music
    music_edit_mode: Literal["legacy", "adaptive", "random", "regular", "free"] = "legacy"
    music_cut_variation: float = Field(0.5, ge=0, le=1)
    music_cut_sync: float = Field(0.8, ge=0, le=1)
    text_allowed: str = ""  # the words the edit may write on the screen
    efficient_sources: bool = False
    reference_style: Literal['camera','montage'] = 'camera'
    sfx_library: str = ''


class JobRequest(BaseModel):
    mode: Mode
    settings: Settings = Settings()
    source: str | None = None  # id of an upload
    refs: list[str] = Field(default_factory=list, max_length=5)
    ref_video: str | None = None
    music: str | None = None
    voice: str | None = None


class JobInputs(BaseModel):
    """What a job was made from, with the files: the interface puts it back when a project is opened."""

    mode: Mode
    settings: Settings
    source: Upload | None = None
    refs: list[Upload] = []
    ref_video: Upload | None = None
    music: Upload | None = None
    voice: Upload | None = None


class Shot(BaseModel):
    id: str
    start: float
    duration: float
    prompt: str = ""
    generation_prompt: str = ""
    version: int = 1
    locked: bool = False
    thumb: str | None = None
    done: bool = False
    takes: int = 0  # how many takes were generated for it: the versions of the interface
    generation_frames: int = 0
    render_source: str = 'generated'


class EditStyle(BaseModel):
    """How the shots are put together: what the edit takes again without making a shot again. A field left out keeps what the workflow has."""

    motion_design: bool | None = None
    motion_direction: str | None = Field(None, max_length=12000)
    motion_title: str | None = Field(None, max_length=120)
    motion_cues: str | None = Field(None, max_length=24000)
    effects: bool | None = None
    text: bool | None = None
    sub_cuts: bool | None = None  # the cuts of the plan inside each shot
    auto_sfx: bool | None = None
    shot_volume: float | None = Field(None, ge=0, le=4)
    duck: float | None = Field(None, ge=0, le=1)  # how much the music gives way to the sound of the shots
    music_volume: float | None = Field(None, ge=0, le=4)
    motion_layers: str | None = None
    rendered_layers: str | None = None


class JobState(BaseModel):
    id: str
    mode: Mode
    status: Status = "queued"
    stage: Stage = "analyze"
    progress: float = 0.0  # 0 to 1 over the whole job
    node: str | None = None
    step: int | None = None
    steps: int | None = None
    shots: list[Shot] = []
    output_url: str | None = None
    error: str | None = None
    project_id: str | None = None
    style: EditStyle = EditStyle()
    preview: int = 0  # how many preview pictures came: the address of the picture changes with it
    title: str = ""
    created_at: float = 0.0
    pinned: bool = False
    operation: int = 0
    generation_budget: dict[str, float] = {}
    energy: dict | None = None
    warnings: list[str] = []
    manual_export: dict | None = None


class TimelineShot(BaseModel):
    id: str
    cuts: list[float] = []  # the cuts inside the shot, in seconds from its start
    effects: list[str] = []  # what the plan does to it: zoom, speed, flip, look, text, the transitions


class TimelineInfo(BaseModel):
    """What the plan says about the rhythm of the edit: the tempo it was cut to, and for every shot its cuts and effects."""

    bpm: float | None = None
    shots: list[TimelineShot] = []
    beat_times: list[float] = []


class JobPatch(BaseModel):
    title: str | None = Field(None, max_length=120)
    pinned: bool | None = None


class PresetTranslationIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field('', max_length=200)
    prompt: str = ''
    settings: dict = Field(default_factory=dict)


class PresetInputs(BaseModel):
    source: Upload | None = None
    refs: list[Upload | None] = Field(default_factory=list, max_length=5)
    refVideo: Upload | None = None
    music: Upload | None = None
    voice: Upload | None = None


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    mode: Mode
    description: str = Field("", max_length=200)
    prompt: str = ""
    settings: dict = {}
    translations: dict[Literal['en', 'fr'], PresetTranslationIn] = Field(default_factory=dict)

    inputs: PresetInputs | None = None


class Take(BaseModel):
    id: str
    active: bool
    generation_prompt: str = ""
    url: str
    duration: float = 0.0
    start: float = 0.0
    window: float = 0.0
    max_start: float = 0.0
    step: float = 1 / 24


class TrimTake(BaseModel):
    take: str = Field(min_length=1)
    start: float = Field(ge=0, allow_inf_nan=False)


class ActiveTake(BaseModel):
    take: str


class Regenerate(BaseModel):
    shots: list[str]
    prompts: dict[str, str] = {}


class AICandidateRequest(BaseModel):
    operation: Literal['regenerate', 'extend_before', 'extend_after']
    take: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=12000)
    seconds: float = Field(3, ge=0.25, le=10, allow_inf_nan=False)
    seed: int = Field(42, ge=0, le=2**48, strict=True)

    @field_validator('prompt')
    @classmethod
    def nonempty_prompt(cls, value):
        if not value.strip():
            raise ValueError('The generation prompt is empty')
        return value


class TimelineSave(BaseModel):
    document: dict
    expected: str | None = Field(None, max_length=64)
    enabled: bool = True


class TimelineVersion(BaseModel):
    expected: str | None = Field(None, max_length=64)


class ShotPatch(BaseModel):
    locked: bool
