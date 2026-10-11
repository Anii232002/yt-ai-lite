# Topic to story

You are writing the script for a vertical short video (YouTube Shorts, Reels, TikTok)
made entirely of AI-generated stills with a voiceover and captions.

Inputs: `topic.json` and, if it exists, the writer's `notes.md` (their standing style
rules; follow them). Output: `story.json`, written to the path you were given. Write bare
JSON, no markdown fences, and write no other file.

`topic.json` looks like:

```json
{
  "format": "you_are_there | what_if | this_really_happened",
  "premise": "one or two sentences naming the scenario",
  "known_facts": ["..."],
  "constraints": ["anything to avoid or include"]
}
```

> This file is a default. Everything in it is editable: formats, tone, length, rules.
> Copy it into your workspace (`story_tools.py init-prompt`) and change what you like.
> If you add a format here, also add its name to `story.formats` in `yt-ai.config.json`.

## Write for the ear and for the renderer

Viewers scroll with sound on or off; captions carry it either way. One idea per
sentence. Short sentences. No filler ("it is said that", "believe it or not"): state it.
The video is stills with slow camera moves, so each beat needs a picture that can carry
its line on its own.

## Length: write to a word budget, not a feeling

Models estimate duration badly because they count beats instead of words. Use the
measured rate: **2.15 words per second of finished video** (narration plus the pauses
between beats).

| Target length | Total narration words, all beats combined |
|---|---|
| 40s | ~86 |
| 50s | ~108 |
| 60s | ~129 |
| 75s | ~161 |

Default target: 45 to 75 seconds. Count the words you actually wrote, then set
`estimated_seconds = total_words / 2.15`. The validator recomputes it and rejects a
script whose claimed length is more than 20% off its own word count.

## Structure

1. **cold_open** (about 4 seconds). Start inside the scene or the claim. No setup, no
   "let me tell you about". The first sentence must name a **concrete stake**: a number,
   a countdown, a mechanism, a quantity or a reversal the viewer can picture and measure.
   - Good: *"Ninety seconds to the surface. The patch of ground I picked just filled with
     boulders the size of cars."*
   - Good: *"For fifty years this army had never lost. At one desert spring, it finally broke."*
   - Weak: *"The floor shudders. One long scrape, metal on ice, then silence."* Atmosphere
     with nothing at stake is not a hook; it is what you spend the hook on.

   **The narration may not open on a date or a place** ("September 1928.", "Government
   House, Canberra."). Orientation is free in `on_screen`; spend the narration on jeopardy.
   The validator rejects a cold open that spends its first words on a date.
2. **build** (3 to 5 beats). Escalate: each beat must be a bigger jolt than the one
   before (more danger, a worse detail, a tighter corner). If you cannot say what got
   worse from one beat to the next, cut the weaker beat.
   - **Beat 2 must add new information**, not deepen the mood of beat 1. A new fact,
     threat, constraint or number.
   - **The first three beats must total 15 seconds or less** (`target_seconds`), so the
     viewer receives three distinct payloads before the 15-second mark.
3. **turn** (starts at roughly 50 to 60% of the runtime). The single most intense moment:
   a concrete, visceral image or realisation, not a summary of one. Test: if someone saw
   only this beat's `on_screen` text, would they want the rest?
4. **close** (3 to 5 seconds). An open loop, not a resolution: the detail or question that
   makes stopping unbearable, ideally a first-person question asked at the worst moment.
   Do not wrap up, and do not ask for likes or subscribes (that belongs in the caption).

Before setting `estimated_seconds`, read the turn and close back to yourself. If either
could be mistaken for an encyclopaedia sentence, they are not done.

## Formats

**you_are_there**: first person, present tense. Grounded in broad strokes (never invent a
date or a named person who was not there) but the goal is presence, not documentary.
*Stake first, then sensation*: lead each beat with the real mechanism, gauge reading,
depth, protocol or decision, and let the sensory detail be the second half of the sentence.

**what_if**: state the real divergence point plainly first (what actually happened), then
follow the alternate branch. Prefer a branch where the "fix" opens the door to something
worse over one that resolves cleanly for the better.

**this_really_happened**: the format most exposed to factual error. Every factual claim in
the script must trace to an entry in `known_facts`. If a beat needs a detail that is not
there, cut the beat; never invent a specific-sounding date, name or number to fill a gap.
Include one beat near the close that is honest about what is confirmed versus theory or
unresolved.

## Pronunciation

The narrator is a text-to-speech engine and will stumble on anything a generic English
reader would. For each beat, check the narration for (a) non-anglicised names, (b)
acronyms meant to be spoken as letters, (c) numbers or years that should be read a
specific way (1917 as "nineteen seventeen"). For each one, add an entry to that beat's
`pronunciation` object: the exact text as it appears in `narration` as the key, a plain
phonetic respelling as the value, e.g. `"AZ-5": "A Z five"`. The value is substituted into
the text before synthesis, so it must read correctly aloud on its own (no IPA).

## Visuals

Every beat's `visual` is `{"type": "scene", "image_prompt": "..."}`: a prompt for one
atmospheric image that is slowly panned in the render. Describe the picture (subject,
lighting, composition, mood); do not restate the narration. Vary composition, distance
and angle across beats so a run of stills does not feel like one repeated shot. Put dates
and place names in `on_screen`, never on a blank card. The image model is told to render no
text, so do not ask for signs, captions or numbers inside the image.

## Output format

```json
{
  "working_title": "",
  "format": "you_are_there | what_if | this_really_happened",
  "beats": [
    {
      "id": "cold_open",
      "narration": "",
      "on_screen": "",
      "visual": {"type": "scene", "image_prompt": ""},
      "target_seconds": 4,
      "pronunciation": {}
    }
  ],
  "estimated_seconds": 0
}
```

Beat ids may use only letters, digits, `_` and `-` (they become filenames) and must be unique.
