"""Download a video's captions and save them (run locally: YouTube blocks cloud IPs)."""
import json
import sys
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

OUT_DIR = Path(__file__).resolve().parents[1] / "eval" / "transcripts"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/fetch_transcript.py VIDEO_ID")
    video_id = sys.argv[1]

    fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB", "en-IN"])
    segments = fetched.to_raw_data()  # list of {"text", "start", "duration"}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{video_id}.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")

    # A readable copy with timestamps, to help you write questions.
    lines = []
    for seg in segments:
        minutes, seconds = divmod(int(seg["start"]), 60)
        lines.append(f"[{minutes}:{seconds:02d}] {seg['text']}")
    (OUT_DIR / f"{video_id}.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"saved {len(segments)} segments to {OUT_DIR}")


if __name__ == "__main__":
    main()