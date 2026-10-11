---
name: yt-ai-story
description: Write the script for a faceless vertical short video from a topic. Turns a topic into a validated beat-by-beat story.json (narration, on-screen text, image prompts) using your own Claude subscription. Use when the user asks for a short-video script, a Shorts/Reels/TikTok story, or the "story" stage of the yt-ai pipeline.
---

# yt-ai-story: topic to script

You (the model running this session) write the script yourself. There is no separate
model call, no API key, and no extra billing: it uses the user's own Claude plan.

`$SKILL_DIR` is the folder containing this SKILL.md. Run scripts with
`${YTAI_PYTHON:-python3}`. All files live in the user's workspace (`$YTAI_WORKDIR`,
default `./yt-ai-work`); never write outside it.

## Steps

1. **Create the topic** if the user has not already (skip if `topics/<id>/topic.json` exists):

   ```bash
   ${YTAI_PYTHON:-python3} $SKILL_DIR/scripts/story_tools.py new-topic \
     --premise "<one or two sentences>" [--format you_are_there|what_if|this_really_happened] \
     [--fact "<verified fact>"]... [--constraint "<must include/avoid>"]...
   ```

   It prints the topic id. `this_really_happened` requires at least one `--fact`: ask the
   user for facts, or research and confirm them with the user. Never invent them.

2. **Get the paths:**

   ```bash
   ${YTAI_PYTHON:-python3} $SKILL_DIR/scripts/story_tools.py context --topic-id <id>
   ```

   This returns the topic file, the prompt to follow (the user's own copy if they made
   one, otherwise the default), optional style notes, and where to write `story.json`.

3. **Read** the topic, the prompt and the notes (if any). **Write** `story.json` to the
   path given, following the prompt exactly. Do the word-count arithmetic for
   `estimated_seconds` yourself; do not guess it.

4. **Validate:**

   ```bash
   ${YTAI_PYTHON:-python3} $SKILL_DIR/scripts/story_tools.py validate --topic-id <id>
   ```

   - `OK: ...` means done.
   - `INVALID: ...` means fix exactly what it names in `story.json` and re-run. Up to 3
     attempts, then show the user the error and ask how to proceed. The validator's rules
     (no date opening, 15-second hook window, length arithmetic) are defaults the user can
     change in `yt-ai.config.json` under `story`; do not weaken them yourself.

5. Tell the user the title, beat count and estimated length. Offer to continue with `yt-ai-narrate`
   for the voiceover. Images, timing and the finished video are in the full pack (coming soon on Gumroad).

## Customising

- Edit the prompt: `story_tools.py init-prompt` copies the default into
  `$YTAI_WORKDIR/prompts/story.md`, which then takes precedence.
- Standing style rules go in `$YTAI_WORKDIR/prompts/notes.md`.
- Formats, length rules and hook rules live in `$YTAI_WORKDIR/yt-ai.config.json`.
