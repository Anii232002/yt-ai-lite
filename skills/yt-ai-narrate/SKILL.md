---
name: yt-ai-narrate
description: Turn a short-video story.json into a voiceover (narration.mp3) with ElevenLabs or a free local voice. Use after yt-ai-story when the user wants the voiceover for a faceless video, wants to change the narrator voice, or re-record edited lines.
---

# yt-ai-narrate: story to voiceover

`$SKILL_DIR` is the folder containing this SKILL.md. Run scripts with
`${YTAI_PYTHON:-python3}`. Files live in the user's workspace (`$YTAI_WORKDIR`, default
`./yt-ai-work`).

## Run

```bash
${YTAI_PYTHON:-python3} $SKILL_DIR/scripts/narrate.py --topic-id <id> [--engine elevenlabs|kokoro] [--force]
```

Reads `assets/<id>/story.json`, synthesises each beat separately, and joins them with a
short gap into `assets/<id>/narration.mp3`. **Resumable and edit-aware:** each clip's filename
carries a hash of its text and engine, so an unchanged line is never paid for twice and an
edited line is always re-recorded.

## Engines

| Engine | Cost | Needs |
|---|---|---|
| `elevenlabs` (default) | paid, per character | `pip install requests`; `ELEVENLABS_API_KEY`; a voice id |
| `kokoro` | free, runs locally | `pip install kokoro-onnx soundfile`; `espeak-ng`; `narrate.py --download-models` once (about 330 MB) |

- Find a voice id: `narrate.py --list-voices`, then set `ELEVENLABS_VOICE_ID` or
  `narrate.elevenlabs.voice_id` in `yt-ai.config.json`.
- **Licensing:** ElevenLabs' free plan does not allow commercial use of the audio. Anyone
  monetising videos needs a paid plan; tell the user and point them at ElevenLabs' current
  terms. Kokoro's own licence terms are upstream's; they should read them.
- Pronunciation: each beat's `pronunciation` map (from the story stage) is substituted into
  the text before synthesis. To fix one mispronounced word, add it there in `story.json`
  and re-run.
- `--mock` writes silent placeholder audio with no API call (for testing the pipeline).

## Customising

Voice, model, stability and the gap between beats are in the `narrate` section of
`yt-ai.config.json`. To add another engine (OpenAI, Azure, a local model), write
`synth_<name>(text, out_path, cfg)` in `narrate.py` and register it in `ENGINES`.

Next: the full pack adds images, word-level timing and the finished 9:16 video, in one command (coming soon on Gumroad).
