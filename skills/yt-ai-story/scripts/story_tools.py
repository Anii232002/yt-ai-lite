#!/usr/bin/env python3
"""Story-stage helpers: create a topic, find the prompt, validate story.json.

    python story_tools.py new-topic --premise "..." [--format F] [--fact "..."]... [--constraint "..."]...
    python story_tools.py context  --topic-id ID      # where to read/write, as JSON
    python story_tools.py validate --topic-id ID      # exit 0 = ok, 1 = fix and re-run
    python story_tools.py init-prompt                 # copy the default prompt into your workspace to edit

Claude (the model in your own session) writes assets/<id>/story.json by following
prompts/story.md. This script only checks the result; it makes no model or network calls.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ytai_common import (assets_dir, die, init_workspace, load_config, save_json, slugify, topic_dir,
                         workdir)

SKILL_DIR = Path(__file__).resolve().parent.parent
REQUIRED_TOP_FIELDS = {"working_title", "format", "beats", "estimated_seconds"}
REQUIRED_BEAT_FIELDS = {"id", "narration", "on_screen", "visual", "target_seconds"}

_MONTHS = ("January February March April May June July August September "
           "October November December").split()
# "march", "may" and "august" are ordinary words, so they only count as a date
# when a number sits next to them.
_AMBIGUOUS_MONTHS = {"March", "May", "August"}
_ORDINALS = ("first second third fourth fifth sixth seventh eighth ninth tenth "
             "eleventh twelfth thirteenth twentieth thirtieth").split()


class StoryError(ValueError):
    pass


def opens_on_date(narration: str, opening_words: int) -> str | None:
    """Return a reason if the narration spends its opening words on a date stamp."""
    opening = " ".join(narration.strip().split()[:opening_words])
    has_month = False
    for month in _MONTHS:
        if not re.search(rf"\b{month}\b", opening):  # case-sensitive: "March" is a date, "march" is a verb
            continue
        if month in _AMBIGUOUS_MONTHS:
            near = re.search(
                rf"\b{month}\b[\s,]+(\d|{'|'.join(_ORDINALS)})|(\d|{'|'.join(_ORDINALS)})[\s,]+\b{month}\b",
                opening, re.IGNORECASE)
            if not near:
                continue
        has_month = True
        break
    has_year = bool(re.search(r"\b(1\d{3}|20\d{2})\b", opening))
    if not (has_month or has_year):
        return None
    return (f"the cold open's narration opens on a date within its first {opening_words} words: "
            f"{opening!r}. Put the date in on_screen (it is free there) and spend the narration "
            "on a concrete stake: a number, a countdown, a mechanism or a reversal.")


def validate(story: dict, topic: dict, cfg: dict) -> dict:
    sc = cfg["story"]
    missing = REQUIRED_TOP_FIELDS - story.keys()
    if missing:
        raise StoryError(f"story.json is missing fields: {sorted(missing)}")
    if story["format"] != topic["format"]:
        raise StoryError(f"story format {story['format']!r} does not match topic format {topic['format']!r}")
    beats = story["beats"]
    if not isinstance(beats, list) or not beats:
        raise StoryError("beats must be a non-empty list")

    seen_ids = set()
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            raise StoryError(f"beat {i} is not an object")
        gap = REQUIRED_BEAT_FIELDS - beat.keys()
        if gap:
            raise StoryError(f"beat {i} ({beat.get('id')}) is missing fields: {sorted(gap)}")
        if beat["id"] in seen_ids:
            raise StoryError(f"duplicate beat id {beat['id']!r}")
        seen_ids.add(beat["id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(beat["id"])):
            raise StoryError(f"beat id {beat['id']!r} may only use letters, digits, '_' and '-' (it becomes a filename)")
        if not isinstance(beat["narration"], str) or not beat["narration"].strip():
            raise StoryError(f"beat {beat['id']} has empty narration; every beat needs a voiceover line")
        visual = beat["visual"]
        if not isinstance(visual, dict) or visual.get("type") != "scene":
            raise StoryError(f"beat {beat['id']} has invalid visual {visual!r}; only {{'type': 'scene', 'image_prompt': ...}} is allowed")
        if not isinstance(visual.get("image_prompt"), str) or not visual["image_prompt"].strip():
            raise StoryError(f"beat {beat['id']} needs a non-empty visual.image_prompt")
        if not isinstance(beat["target_seconds"], (int, float)) or beat["target_seconds"] <= 0:
            raise StoryError(f"beat {beat['id']} needs a positive target_seconds")

    hook = sc["hook"]
    if hook["no_date_opening"]:
        reason = opens_on_date(beats[0]["narration"], hook["opening_words"])
        if reason:
            raise StoryError(reason)
    if hook["window_enabled"] and len(beats) >= hook["window_beats"]:
        opening = beats[: hook["window_beats"]]
        total = sum(b["target_seconds"] for b in opening)
        if total > hook["window_seconds"]:
            shape = ", ".join(f"{b['id']}={b['target_seconds']}s" for b in opening)
            raise StoryError(
                f"the first {hook['window_beats']} beats run {total}s ({shape}); the limit is "
                f"{hook['window_seconds']}s combined, so the viewer gets three distinct payloads "
                "before the fifteen-second mark. Shorten them (or change story.hook in your config).")

    words = sum(len(b["narration"].split()) for b in beats)
    wps = sc["words_per_second"]
    predicted = words / wps
    claimed = story.get("estimated_seconds") or 0
    if claimed and abs(claimed - predicted) / predicted > sc["estimate_tolerance"]:
        raise StoryError(
            f"estimated_seconds={claimed} does not match the script: {words} words at {wps} words/sec "
            f"is about {predicted:.0f}s. Set estimated_seconds to total_words / {wps}.")
    story["estimated_seconds"] = round(predicted)
    if predicted > sc["max_seconds_warning"]:
        print(f"warning: about {predicted:.0f}s ({words} words) is past the {sc['max_seconds_warning']}s guidance",
              file=sys.stderr)
    return story


def load_topic(topic_id: str, cfg: dict) -> dict:
    path = topic_dir(topic_id) / "topic.json"
    if not path.exists():
        die(f"{path} not found -- create it with: story_tools.py new-topic --premise \"...\"")
    topic = json.loads(path.read_text())
    fmt = topic.get("format")
    if fmt not in cfg["story"]["formats"]:
        die(f"{path}: format must be one of {cfg['story']['formats']}, got {fmt!r}")
    if fmt in cfg["story"]["require_known_facts_for"] and not topic.get("known_facts"):
        die(f"{path}: format {fmt!r} requires a non-empty known_facts list (it is not allowed to invent facts)")
    if not str(topic.get("premise", "")).strip():
        die(f"{path}: premise is empty")
    return topic


def prompt_path(cfg: dict) -> Path:
    """Your workspace copy wins; otherwise the default that ships with this skill."""
    mine = workdir() / cfg["story"]["prompt_file"]
    return mine if mine.exists() else SKILL_DIR / "prompts" / "story.md"


def cmd_new_topic(args, cfg) -> int:
    init_workspace()
    fmt = args.format or cfg["story"]["default_format"]
    if fmt not in cfg["story"]["formats"]:
        die(f"format must be one of {cfg['story']['formats']}")
    topic_id = args.id or slugify(args.premise)
    tdir = topic_dir(topic_id)
    if (tdir / "topic.json").exists() and not args.overwrite:
        die(f"{tdir / 'topic.json'} already exists (use --overwrite, or pick another --id)")
    topic = {"format": fmt, "premise": args.premise.strip(), "known_facts": args.fact or [],
             "constraints": args.constraint or []}
    if fmt in cfg["story"]["require_known_facts_for"] and not topic["known_facts"]:
        die(f"format {fmt!r} requires at least one --fact")
    save_json(tdir / "topic.json", topic)
    print(topic_id)
    return 0


def cmd_context(args, cfg) -> int:
    load_topic(args.topic_id, cfg)
    notes = workdir() / cfg["story"]["notes_file"]
    print(json.dumps({
        "topic_json": str(topic_dir(args.topic_id) / "topic.json"),
        "prompt": str(prompt_path(cfg)),
        "notes": str(notes) if notes.exists() else None,
        "write_story_to": str(assets_dir(args.topic_id) / "story.json"),
        "words_per_second": cfg["story"]["words_per_second"],
    }, indent=1))
    return 0


def cmd_validate(args, cfg) -> int:
    topic = load_topic(args.topic_id, cfg)
    path = assets_dir(args.topic_id) / "story.json"
    if not path.exists():
        print(f"INVALID: {path} does not exist -- write story.json there first")
        return 1
    try:
        story = json.loads(path.read_text())
        story = validate(story, topic, cfg)
    except json.JSONDecodeError as e:
        print(f"INVALID: story.json is not valid JSON ({e}). Write bare JSON with no markdown fences.")
        return 1
    except StoryError as e:
        print(f"INVALID: {e}")
        return 1
    save_json(path, story)
    words = sum(len(b["narration"].split()) for b in story["beats"])
    print(f"OK: \"{story['working_title']}\" {len(story['beats'])} beats, {words} words, ~{story['estimated_seconds']}s")
    return 0


def cmd_init_prompt(args, cfg) -> int:
    init_workspace()
    dest = workdir() / cfg["story"]["prompt_file"]
    if dest.exists() and not args.overwrite:
        die(f"{dest} already exists (use --overwrite to replace it)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((SKILL_DIR / "prompts" / "story.md").read_text())
    print(f"copied default prompt to {dest} -- edit it; it now takes precedence")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new-topic")
    p.add_argument("--premise", required=True)
    p.add_argument("--id")
    p.add_argument("--format")
    p.add_argument("--fact", action="append")
    p.add_argument("--constraint", action="append")
    p.add_argument("--overwrite", action="store_true")
    for name in ("context", "validate"):
        p = sub.add_parser(name)
        p.add_argument("--topic-id", required=True)
    p = sub.add_parser("init-prompt")
    p.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    return {"new-topic": cmd_new_topic, "context": cmd_context, "validate": cmd_validate,
            "init-prompt": cmd_init_prompt}[args.cmd](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
