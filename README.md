# yt-ai-lite: topic in, script and voiceover out

```
/yt-ai-story a first-person minute inside a submarine that loses power at 300 metres
   → a validated, hook-first script: 6 beats, about 50 seconds, image prompts included
/yt-ai-narrate
   → narration.mp3, one voice, every line timed to its beat
```

Two free skills for [Claude Code](https://claude.com/claude-code) that run inside **your own Claude session**:
no API key for the writing, no extra model bill.

### Want the finished video too?

**Full pack (coming soon on Gumroad): one command from topic to a finished 9:16 Short.**
Adds AI images, word-level timing, the Remotion render with captions and camera moves, and the `/yt-ai`
orchestrator. About $0.12 a video.

---

## Install

```bash
npx skills add Anii232002/yt-ai-lite
```

or as a Claude Code plugin: `/plugin marketplace add Anii232002/yt-ai-lite`, then
`/plugin install yt-ai-lite@yt-ai-lite`. Or copy `skills/*` into `~/.claude/skills/`.

Needs Python 3.10+ and ffmpeg. For the voice, an ElevenLabs API key (`pip install requests`), or the free local
voice (`pip install kokoro-onnx soundfile`, plus `espeak-ng`).

## What's in the box

| Skill | What it does |
|---|---|
| `yt-ai-story` | Claude writes a beat-by-beat script from your topic; a validator checks it and Claude fixes it until it passes |
| `yt-ai-narrate` | the script becomes a voiceover with ElevenLabs or a free local voice; edited lines are re-recorded, unchanged ones are never paid for twice |

The validator enforces: no date-stamped openings, the first three beats fit in 15 seconds, the length
claim matches the word count, and `this_really_happened` scripts must come with verified facts. Every rule
is a setting you can change in `yt-ai.config.json`, and the prompt is a file you can edit.

## Try it (free, no keys)

```bash
tests/smoke_test.sh        # validates a sample script and makes placeholder audio with ffmpeg
```

## Make it yours

Run `story_tools.py init-prompt` to copy the prompt into your workspace and edit it. Add standing style rules
to `prompts/notes.md`. Change formats, hook rules, voice and pace in `yt-ai.config.json`.

---

Licence: MIT (this lite version). The full pack is licensed separately for personal and commercial use,
without resale. It is coming soon on Gumroad.
