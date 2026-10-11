#!/usr/bin/env python3
"""Shared helpers for the yt-ai skill pack (standard library only).

Every stage skill ships an identical copy of this file next to its scripts.
`tools/sync_common.sh` keeps the copies in sync and `tests/check_pack.py`
fails if they drift. Edit src/ytai_common.py, never a copy.

Where things live
-----------------
Everything the pack reads or writes lives in ONE workspace folder:

    $YTAI_WORKDIR            (default: ./yt-ai-work in the current directory)
      yt-ai.config.json      your settings (created by `init`, safe to edit)
      .env                   optional API keys (or use real environment vars)
      prompts/story.md       optional: your own copy of the story prompt
      prompts/notes.md       optional: your running style notes for the writer
      topics/<id>/topic.json input for one video
      assets/<id>/...        everything generated for that video
      render/                Remotion project (copied from the pack on first render)

Nothing here is tied to a particular machine, user or account.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

DEFAULT_CONFIG: dict = {
    "story": {
        "default_format": "you_are_there",
        "formats": ["you_are_there", "what_if", "this_really_happened"],
        # Formats that must come with a non-empty known_facts list in topic.json.
        "require_known_facts_for": ["this_really_happened"],
        # Measured words per second of FINISHED video (narration + pauses).
        "words_per_second": 2.15,
        "estimate_tolerance": 0.20,
        "max_seconds_warning": 90,
        "hook": {
            # Reject a cold open whose first words are a date stamp.
            "no_date_opening": True,
            "opening_words": 12,
            # The first N beats must fit inside S seconds combined.
            "window_enabled": True,
            "window_seconds": 15,
            "window_beats": 3,
        },
        "prompt_file": "prompts/story.md",
        "notes_file": "prompts/notes.md",
    },
    "illustrate": {
        "model": "klein",
        "models": {
            "klein": "black-forest-labs/flux-2-klein-4b",
            "pro": "black-forest-labs/flux-1.1-pro",
        },
        "aspect_ratio": "9:16",
        "style_prefix": (
            "Cinematic, atmospheric, moody lighting, dramatic composition, "
            "photographic realism, film-still quality, no text, no watermark, "
            "no letters, no numbers, vertical 9:16 framing. Depicting: "
        ),
        # Seconds to wait between image requests. 0 = no pacing; the script
        # switches to 11s automatically after the first rate-limit (429).
        "request_spacing_seconds": 0,
        "max_retries": 5,
    },
    "narrate": {
        "engine": "elevenlabs",
        "beat_gap_ms": 350,
        "elevenlabs": {
            "voice_id": "",  # or set ELEVENLABS_VOICE_ID
            "model_id": "eleven_flash_v2_5",
            "stability": 0.6,
            "similarity_boost": 0.75,
        },
        "kokoro": {"voice": "am_michael", "speed": 0.82},
    },
    "align": {"whisper_model": "small", "end_pad_seconds": 1.0},
    "render": {
        "brand_text": "",  # small text at the bottom of the frame; empty = none
        "accent_color": "#7c3aed",
        "font_family": "system-ui, sans-serif",
        "caption_font_size": 38,
        "caption_bottom": 420,
        "show_waveform": True,
        "show_on_screen_text": True,
        "timeout_ms": 120000,  # per-frame timeout handed to Remotion
        "browser_executable": "",  # path to Chrome/Chromium; empty = let Remotion download its own
    },
    "pricing_estimates": {
        "_note": "Rough USD estimates used only for the end-of-run cost summary. Check your providers' current pricing.",
        "image_usd": {"klein": 0.015, "pro": 0.04},
        "elevenlabs_usd_per_1k_chars": 0.04,
    },
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in (over or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def die(message: str, code: int = 1) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def workdir() -> Path:
    env = os.environ.get("YTAI_WORKDIR")
    base = Path(env).expanduser() if env else Path.cwd() / "yt-ai-work"
    return base.resolve()


def _parse_env_file(path: Path) -> dict:
    out: dict = {}
    try:
        text = path.read_text()
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and val:
            out[key] = val
    return out


def load_env() -> None:
    """Fill os.environ from .env files without overriding real env vars.
    Precedence: real environment > <workdir>/.env > ./.env > ~/.config/yt-ai/.env"""
    for path in (workdir() / ".env", Path.cwd() / ".env", Path.home() / ".config" / "yt-ai" / ".env"):
        for key, val in _parse_env_file(path).items():
            os.environ.setdefault(key, val)


def load_config() -> dict:
    load_env()
    path = workdir() / "yt-ai.config.json"
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        user = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")
    cfg = deep_merge(DEFAULT_CONFIG, user)
    exe = os.environ.get("YTAI_BROWSER_EXECUTABLE")  # handy for CI and firewalled machines
    if exe:
        cfg["render"]["browser_executable"] = exe
    return cfg


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "untitled"


def valid_topic_id(topic_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", topic_id):
        die(f"topic id {topic_id!r} must be lowercase letters, digits and hyphens (try: {slugify(topic_id)})")
    return topic_id


def topic_dir(topic_id: str) -> Path:
    return workdir() / "topics" / valid_topic_id(topic_id)


def assets_dir(topic_id: str) -> Path:
    return workdir() / "assets" / valid_topic_id(topic_id)


def models_dir() -> Path:
    return Path(os.environ.get("YTAI_MODELS_DIR", Path.home() / ".cache" / "yt-ai" / "models")).expanduser()


def load_story(topic_id: str) -> dict:
    path = assets_dir(topic_id) / "story.json"
    if not path.exists():
        die(f"{path} not found -- run the story stage first")
    return json.loads(path.read_text())


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def log_usage(topic_id: str, key: str, amount: float) -> None:
    """Accumulate billable usage (images, characters) for the end-of-run cost summary."""
    path = assets_dir(topic_id) / "usage.json"
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except json.JSONDecodeError:
        data = {}
    data[key] = data.get(key, 0) + amount
    save_json(path, data)


def estimate_cost(topic_id: str, cfg: dict) -> dict:
    path = assets_dir(topic_id) / "usage.json"
    usage = json.loads(path.read_text()) if path.exists() else {}
    price = cfg["pricing_estimates"]
    images = 0.0
    for model, per_image in price["image_usd"].items():
        images += usage.get(f"images_{model}", 0) * per_image
    voice = usage.get("elevenlabs_chars", 0) / 1000 * price["elevenlabs_usd_per_1k_chars"]
    return {"usage": usage, "images_usd": round(images, 3), "voice_usd": round(voice, 3),
            "total_usd": round(images + voice, 3)}


def init_workspace() -> Path:
    root = workdir()
    for sub in ("topics", "assets", "prompts"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    cfg_path = root / "yt-ai.config.json"
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
    notes = root / "prompts" / "notes.md"
    if not notes.exists():
        notes.write_text(
            "<!-- Your running style notes. Claude reads this before writing every story.\n"
            "     Add short, imperative rules as you learn what works for your channel.\n"
            "     Example: 'Open on a number. Never open on a date.' -->\n"
        )
    return root


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "paths"
    if cmd == "init":
        root = init_workspace()
        print(f"workspace ready: {root}")
        print(f"settings:        {root / 'yt-ai.config.json'}")
        return 0
    if cmd == "paths":
        print(json.dumps({"workdir": str(workdir()), "version": VERSION}, indent=1))
        return 0
    if cmd == "config":
        print(json.dumps(load_config(), indent=2))
        return 0
    if cmd == "slug":
        print(slugify(" ".join(argv[2:])))
        return 0
    print("usage: ytai_common.py [init|paths|config|slug <text>]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
