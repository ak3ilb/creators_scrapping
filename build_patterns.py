#!/usr/bin/env python3
"""
build_patterns.py — Deep Creator Pattern Analysis Pipeline (Layer 1 + 2).

Scans all transcript.txt files for each creator and produces:
  patterns/<creator>/videos/<id>.json   (Layer 1: per-video)
  patterns/<creator>/synthesis.md       (Layer 2: cross-video aggregation)
  patterns/<creator>/_meta.json         (tracking for incremental updates)

Layer 3 (dna.md) is written by AI intelligence, not this script.

Usage:
  python3 build_patterns.py                    # All creators
  python3 build_patterns.py --creator GenZway  # Single creator
  python3 build_patterns.py --incremental      # Only new/changed transcripts
  python3 build_patterns.py --cleanup          # Remove stale pattern data
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.pattern_analyzer import (
    scan_creator_transcripts,
    analyze_single_video,
    synthesize_patterns,
    load_meta,
    save_meta
)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PATTERNS_DIR = os.path.join(os.path.dirname(__file__), 'patterns')
CREATORS_FILE = os.path.join(os.path.dirname(__file__), 'creators.json')


def load_creators():
    with open(CREATORS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Handle both {"creators": [...]} and [...] formats
    if isinstance(data, dict) and "creators" in data:
        return data["creators"]
    return data


def process_creator(creator_name: str, incremental: bool = False):
    """Run Layer 1 + Layer 2 analysis for a single creator."""
    print(f"\n{'='*60}")
    print(f"🔬 Analyzing: {creator_name}")
    print(f"{'='*60}")

    # Scan for transcripts
    transcripts = scan_creator_transcripts(DATA_DIR, creator_name)
    if not transcripts:
        print(f"   ⚠️  No transcripts found for {creator_name}")
        return

    print(f"   📁 Found {len(transcripts)} transcripts")

    # Setup directories
    creator_patterns_dir = os.path.join(PATTERNS_DIR, creator_name)
    videos_dir = os.path.join(creator_patterns_dir, 'videos')
    os.makedirs(videos_dir, exist_ok=True)

    # Load existing meta for incremental mode
    meta = load_meta(PATTERNS_DIR, creator_name)
    old_hashes = meta.get("transcript_hashes", {})

    # ─── Layer 1: Per-Video Analysis ───────────────────────────────
    analyzed = 0
    skipped = 0
    all_analyses = []

    for t in transcripts:
        vid = t["video_id"]
        video_json_path = os.path.join(videos_dir, f"{vid}.json")

        # Incremental: skip if hash unchanged
        if incremental and vid in old_hashes and old_hashes[vid] == t["file_hash"]:
            # Load existing analysis
            if os.path.exists(video_json_path):
                with open(video_json_path, 'r', encoding='utf-8') as f:
                    all_analyses.append(json.load(f))
                skipped += 1
                continue

        # Analyze
        result = analyze_single_video(vid, t["transcript_path"])
        if "error" not in result:
            with open(video_json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            all_analyses.append(result)
            analyzed += 1
        else:
            skipped += 1

    print(f"   ✅ Layer 1 complete: {analyzed} analyzed, {skipped} skipped")

    # Update meta
    meta["transcript_hashes"] = {t["video_id"]: t["file_hash"] for t in transcripts}
    meta["videos_analyzed"] = len(all_analyses)
    meta["videos_available"] = len(transcripts)
    save_meta(PATTERNS_DIR, creator_name, meta)

    # ─── Layer 2: Cross-Video Synthesis ────────────────────────────
    if all_analyses:
        synthesis = synthesize_patterns(all_analyses)
        
        # Write synthesis as markdown for human readability
        synthesis_md = _format_synthesis_md(creator_name, synthesis)
        synthesis_path = os.path.join(creator_patterns_dir, 'synthesis.md')
        with open(synthesis_path, 'w', encoding='utf-8') as f:
            f.write(synthesis_md)
        
        # Also save raw JSON for programmatic access
        synthesis_json_path = os.path.join(creator_patterns_dir, 'synthesis.json')
        with open(synthesis_json_path, 'w', encoding='utf-8') as f:
            json.dump(synthesis, f, indent=2, ensure_ascii=False)

        print(f"   ✅ Layer 2 complete: synthesis.md written")
        print(f"   📊 Avg WPS: {synthesis['pacing']['avg_wps']}")
        print(f"   🌐 Language: Hindi {synthesis['language']['avg_hindi_pct']}% / English {synthesis['language']['avg_english_pct']}%")
        print(f"   🎯 Top hook type: {max(synthesis['hook_types'], key=synthesis['hook_types'].get) if synthesis['hook_types'] else 'N/A'}")
    else:
        print(f"   ⚠️  No valid analyses to synthesize")

    print(f"\n   ⏳ Layer 3 (dna.md) requires AI intelligence — run separately")


def _format_synthesis_md(creator_name: str, synthesis: dict) -> str:
    """Format the synthesis data as a readable markdown document."""
    n = synthesis["total_videos"]
    lines = [
        f"# {creator_name} — Cross-Video Pattern Synthesis",
        f"",
        f"**Videos Analyzed:** {n}",
        f"**Generated:** {__import__('datetime').datetime.now().isoformat()[:19]}",
        f"",
        f"> This is mechanical aggregation (Layer 2). The AI-written DNA profile (Layer 3) is in `dna.md`.",
        f"",
        f"## Pacing",
        f"- Average WPS: **{synthesis['pacing']['avg_wps']}**",
        f"- Range: {synthesis['pacing']['min_wps']} – {synthesis['pacing']['max_wps']}",
        f"",
        f"## Language Mix",
        f"- Hindi: **{synthesis['language']['avg_hindi_pct']}%**",
        f"- English: **{synthesis['language']['avg_english_pct']}%**",
        f"",
        f"## Hook Types",
    ]
    for h_type, count in synthesis.get("hook_types", {}).items():
        pct = round(count / n * 100)
        lines.append(f"- {h_type}: {count}/{n} ({pct}%)")

    lines.extend([
        f"",
        f"## Closing Types",
    ])
    for c_type, count in synthesis.get("closing_types", {}).items():
        pct = round(count / n * 100)
        lines.append(f"- {c_type}: {count}/{n} ({pct}%)")

    lines.extend([
        f"",
        f"## Video Structures",
    ])
    for s_type, count in synthesis.get("structures", {}).items():
        pct = round(count / n * 100)
        lines.append(f"- {s_type}: {count}/{n} ({pct}%)")

    lines.extend([
        f"",
        f"## Audience Addressing",
    ])
    for style, count in synthesis.get("audience_addressing", {}).items():
        lines.append(f"- {style}: {count} occurrences")

    lines.extend([
        f"",
        f"## Vocabulary Frequency",
        f"",
        f"### Consistent (>60% of videos)",
        f"| Word | Videos Present |",
        f"|------|---------------|",
    ])
    for word, count in synthesis.get("vocabulary", {}).get("consistent", {}).items():
        lines.append(f"| {word} | {count}/{n} |")
    
    lines.extend([
        f"",
        f"### Variable (15-60% of videos)",
        f"| Word | Videos Present |",
        f"|------|---------------|",
    ])
    for word, count in synthesis.get("vocabulary", {}).get("variable", {}).items():
        lines.append(f"| {word} | {count}/{n} |")

    lines.extend([
        f"",
        f"### Rare (<15% of videos)",
        f"| Word | Videos Present |",
        f"|------|---------------|",
    ])
    for word, count in synthesis.get("vocabulary", {}).get("rare", {}).items():
        lines.append(f"| {word} | {count}/{n} |")

    lines.extend([
        f"",
        f"## Sample Hooks (Real Opening Lines)",
    ])
    for i, hook in enumerate(synthesis.get("sample_hooks", []), 1):
        lines.append(f"{i}. \"{hook[:150]}\"")

    lines.extend([
        f"",
        f"## Sample Closings (Real Ending Lines)",
    ])
    for i, closing in enumerate(synthesis.get("sample_closings", []), 1):
        lines.append(f"{i}. \"{closing[:150]}\"")

    return "\n".join(lines) + "\n"


def cleanup_patterns():
    """Remove pattern data for creators no longer in creators.json."""
    creators = load_creators()
    active_names = {c["name"] for c in creators}
    
    if not os.path.exists(PATTERNS_DIR):
        print("No patterns directory found.")
        return

    archive_dir = os.path.join(PATTERNS_DIR, '_archive')
    
    for entry in os.scandir(PATTERNS_DIR):
        if entry.is_dir() and not entry.name.startswith('_'):
            if entry.name not in active_names:
                os.makedirs(archive_dir, exist_ok=True)
                dest = os.path.join(archive_dir, entry.name)
                os.rename(entry.path, dest)
                print(f"   📦 Archived: {entry.name} → _archive/")


def main():
    parser = argparse.ArgumentParser(description='Deep Creator Pattern Analysis')
    parser.add_argument('--creator', '-c', help='Analyze a specific creator')
    parser.add_argument('--incremental', '-i', action='store_true',
                        help='Only analyze new/changed transcripts')
    parser.add_argument('--cleanup', action='store_true',
                        help='Archive patterns for removed creators')
    args = parser.parse_args()

    if args.cleanup:
        cleanup_patterns()
        return

    creators = load_creators()
    
    if args.creator:
        matching = [c for c in creators if c["name"] == args.creator]
        if not matching:
            print(f"❌ Creator '{args.creator}' not found in creators.json")
            sys.exit(1)
        creators = matching

    print(f"🧠 Deep Pattern Analysis Pipeline")
    print(f"   Mode: {'Incremental' if args.incremental else 'Full'}")
    print(f"   Creators: {len(creators)}")

    for creator in creators:
        process_creator(creator["name"], incremental=args.incremental)

    print(f"\n{'='*60}")
    print(f"✅ Layer 1 + 2 complete for all creators!")
    print(f"📁 Results in: {PATTERNS_DIR}/")
    print(f"⏳ Next step: AI writes Layer 3 (dna.md) for each creator")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
