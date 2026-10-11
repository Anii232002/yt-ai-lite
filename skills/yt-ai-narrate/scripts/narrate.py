#!/usr/bin/env python3
"""Turn story.json into narration.mp3 with text-to-speech.

    python narrate.py --topic-id ID [--engine elevenlabs|kokoro] [--force] [--mock]
    python narrate.py --list-voices          # ElevenLabs voices on your account
    python narrate.py --download-models      # one-time download for the free local kokoro engine

Reads  assets/<id>/story.json
Writes assets/<id>/narration_beats/<beat>.<ext>  (one clip per beat, resumable)
       assets/<id>/narration.mp3                 (clips joined with a short gap)

Engines
  elevenlabs  hosted, needs ELEVENLABS_API_KEY and a voice id (ELEVENLABS_VOICE_ID or
              narrate.elevenlabs.voice_id in your config). Commercial use needs a paid
              ElevenLabs plan: check their current terms.
  kokoro      free, local (needs `pip install kokoro-onnx soundfile` and espeak-ng,
              plus --download-models once, about 330 MB).
Add your own engine: write a function `synth_<name>(text, out_path, cfg)` and register it in ENGINES.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from ytai_common import assets_dir, die, load_config, load_story, log_usage, models_dir

KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")


def apply_pronunciation(text: str, pronunciation: dict | None) -> str:
    """Substitute the story's phonetic respellings before synthesis (neither engine takes SSML)."""
    for word, phonetic in (pronunciation or {}).items():
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", phonetic, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------- engines

def synth_elevenlabs(text: str, out_path: Path, cfg: dict) -> None:
    import requests

    key = os.environ.get("ELEVENLABS_API_KEY")
    ecfg = cfg["elevenlabs"]
    voice = os.environ.get("ELEVENLABS_VOICE_ID") or ecfg["voice_id"]
    if not key or not voice:
        die("ELEVENLABS_API_KEY and a voice id are required. Run `narrate.py --list-voices` to find one, "
            "then set ELEVENLABS_VOICE_ID (or narrate.elevenlabs.voice_id in your config).")
    body = {"text": text, "model_id": ecfg["model_id"],
            "voice_settings": {"stability": ecfg["stability"], "similarity_boost": ecfg["similarity_boost"]}}
    for attempt in range(4):
        resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                             headers={"xi-api-key": key, "Content-Type": "application/json"},
                             json=body, timeout=90)
        if resp.status_code in (429, 500, 502, 503) and attempt < 3:
            wait = 5 * (attempt + 1)
            print(f"    ElevenLabs {resp.status_code}; retry in {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code == 401:
            die("ElevenLabs rejected the API key (401). Check ELEVENLABS_API_KEY.")
        if resp.status_code == 402 or resp.status_code == 403:
            die(f"ElevenLabs refused the request ({resp.status_code}): this voice or model may need a paid plan, "
                "or your credits are used up.")
        resp.raise_for_status()
        out_path.write_bytes(resp.content)  # mp3 bytes
        return


_kokoro = None


def synth_kokoro(text: str, out_path: Path, cfg: dict) -> None:
    global _kokoro
    import soundfile as sf

    if _kokoro is None:
        from kokoro_onnx import Kokoro

        model, voices = (models_dir() / f for f in KOKORO_FILES)
        if not model.exists() or not voices.exists():
            die(f"Kokoro model files not found in {models_dir()}. Run: narrate.py --download-models")
        print("loading Kokoro...")
        _kokoro = Kokoro(str(model), str(voices))
    k = cfg["kokoro"]
    samples, sr = _kokoro.create(text, voice=k["voice"], speed=k["speed"], lang="en-us",
                                 sentence_pause=0.45, clause_pause=0.22)
    sf.write(str(out_path), samples, sr)


def synth_mock(text: str, out_path: Path, cfg: dict) -> None:
    """Silence whose length is proportional to the word count. Offline testing only."""
    seconds = max(0.8, len(text.split()) / 2.6)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"anullsrc=r=24000:cl=mono:d={seconds:.2f}", str(out_path)], check=True)


ENGINES = {"elevenlabs": (synth_elevenlabs, "mp3"), "kokoro": (synth_kokoro, "wav"), "mock": (synth_mock, "wav")}

# ---------------------------------------------------------------- assembly


def concat_beats(clips: list[Path], out_mp3: Path, gap_ms: int) -> None:
    """Normalise every clip to 24 kHz mono, then join with a fixed silence gap.
    Normalising first matters: clips from different engines have different sample rates."""
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        silence = work / "silence.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"anullsrc=r=24000:cl=mono:d={gap_ms / 1000}", str(silence)], check=True)
        lines = []
        for i, clip in enumerate(clips):
            norm = work / f"{i:03d}.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-ar", "24000", "-ac", "1",
                            str(norm)], check=True)
            lines.append(f"file '{norm}'")
            if i < len(clips) - 1:
                lines.append(f"file '{silence}'")
        (work / "list.txt").write_text("\n".join(lines))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                        str(work / "list.txt"), "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3)], check=True)


def download_models() -> int:
    dest = models_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for name in KOKORO_FILES:
        target = dest / name
        if target.exists():
            print(f"already have {target}")
            continue
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(KOKORO_BASE + name, target)
    print(f"models in {dest}")
    return 0


def list_voices() -> int:
    import requests

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        die("set ELEVENLABS_API_KEY first")
    resp = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}, timeout=30)
    resp.raise_for_status()
    for v in resp.json().get("voices", []):
        print(f"{v['voice_id']}  {v.get('name', ''):<24} {v.get('category', '')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic-id")
    ap.add_argument("--engine", choices=sorted(ENGINES))
    ap.add_argument("--force", action="store_true", help="re-synthesise clips that already exist")
    ap.add_argument("--mock", action="store_true", help="silent placeholder audio, no API calls, no cost")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--download-models", action="store_true")
    args = ap.parse_args()

    cfg = load_config()["narrate"]
    if args.list_voices:
        return list_voices()
    if args.download_models:
        return download_models()
    if not args.topic_id:
        ap.error("--topic-id is required")

    engine = "mock" if args.mock else (args.engine or cfg["engine"])
    synth, ext = ENGINES[engine]
    story = load_story(args.topic_id)
    out_dir = assets_dir(args.topic_id)
    beats_dir = out_dir / "narration_beats"
    beats_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for beat in story["beats"]:
        text = apply_pronunciation(beat["narration"], beat.get("pronunciation"))
        # Engine and a hash of the text are part of the filename, so switching engines or editing a
        # line never reuses a stale clip, while an unchanged line is never paid for twice.
        digest = hashlib.sha1(f"{engine}|{text}".encode()).hexdigest()[:8]
        clip = beats_dir / f"{beat['id']}.{engine}.{digest}.{ext}"
        if clip.exists() and not args.force:
            print(f"  [{beat['id']}] unchanged, skipping")
        else:
            print(f"  [{beat['id']}] synthesising {len(text)} chars ({engine})...")
            synth(text, clip, cfg)
            if engine == "elevenlabs":
                log_usage(args.topic_id, "elevenlabs_chars", len(text))
        clips.append(clip)

    out_mp3 = out_dir / "narration.mp3"
    concat_beats(clips, out_mp3, cfg["beat_gap_ms"])
    print(f"wrote {out_mp3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
