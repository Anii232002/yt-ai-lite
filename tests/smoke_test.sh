#!/usr/bin/env bash
# Free smoke test for yt-ai-lite: validate a sample script, make placeholder audio, check the result.
# Needs only Python 3.10+ and ffmpeg. No keys, no network.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${YTAI_PYTHON:-python3}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
export YTAI_WORKDIR="$WORK/yt-ai-work"
ID="smoke-sample"
mkdir -p "$YTAI_WORKDIR/topics/$ID" "$YTAI_WORKDIR/assets/$ID"
cp "$HERE/tests/fixtures/smoke-sample/topic.json" "$YTAI_WORKDIR/topics/$ID/"
cp "$HERE/tests/fixtures/smoke-sample/story.json" "$YTAI_WORKDIR/assets/$ID/"

echo "== story: validate the sample script"
"$PY" "$HERE/skills/yt-ai-story/scripts/story_tools.py" validate --topic-id "$ID"

echo "== story: the validator must reject a date-stamped opening"
BAD="$WORK/bad"; mkdir -p "$BAD/topics/$ID" "$BAD/assets/$ID"; cp "$YTAI_WORKDIR/topics/$ID/topic.json" "$BAD/topics/$ID/"
"$PY" - "$YTAI_WORKDIR/assets/$ID/story.json" "$BAD/assets/$ID/story.json" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1])); s["beats"][0]["narration"] = "July 23, 1983. " + s["beats"][0]["narration"]
json.dump(s, open(sys.argv[2], "w"))
PYEOF
if YTAI_WORKDIR="$BAD" "$PY" "$HERE/skills/yt-ai-story/scripts/story_tools.py" validate --topic-id "$ID" >/dev/null; then
  echo "validator accepted a date-stamped opening" >&2; exit 1; else echo "rejected as expected"; fi

echo "== narrate: placeholder audio (no API call)"
"$PY" "$HERE/skills/yt-ai-narrate/scripts/narrate.py" --topic-id "$ID" --mock
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$YTAI_WORKDIR/assets/$ID/narration.mp3")
"$PY" -c "import sys; d=float('$DUR'); sys.exit(0 if d>20 else 1)" || { echo "narration too short: $DUR" >&2; exit 1; }
echo "narration.mp3 is ${DUR}s"
echo; echo "LITE SMOKE TEST PASSED"
