#!/usr/bin/env python3
"""
search.py — Search transcripts by keyword/topic across all creators.

Usage:
    python3 search.py "education system"
    python3 search.py "education" --creator Shivanshu.Agrawal
    python3 search.py "design" --max 10
"""

import argparse
import json
import os
import sys
import re


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def search_transcripts(
    query: str,
    creator_filter: str = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Search all transcript.txt files for lines matching the query.

    Returns list of matches with context.
    """
    results = []
    query_lower = query.lower()

    # Walk the data directory
    if not os.path.isdir(DATA_DIR):
        return results

    for creator_name in sorted(os.listdir(DATA_DIR)):
        creator_dir = os.path.join(DATA_DIR, creator_name)
        if not os.path.isdir(creator_dir):
            continue

        # Apply creator filter
        if creator_filter and creator_name != creator_filter:
            continue

        for video_id in sorted(os.listdir(creator_dir)):
            video_dir = os.path.join(creator_dir, video_id)
            if not os.path.isdir(video_dir) or video_id.startswith('_'):
                continue

            transcript_path = os.path.join(video_dir, 'transcript.txt')
            metadata_path = os.path.join(video_dir, 'metadata.json')

            if not os.path.isfile(transcript_path):
                continue

            # Load metadata for title
            title = 'Unknown'
            if os.path.isfile(metadata_path):
                try:
                    with open(metadata_path) as f:
                        meta = json.load(f)
                    title = meta.get('title', 'Unknown')
                except Exception:
                    pass

            # Search transcript lines
            with open(transcript_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            matching_lines = []
            for line in lines:
                if query_lower in line.lower():
                    matching_lines.append(line.strip())

            if matching_lines:
                results.append({
                    'creator': creator_name,
                    'video_id': video_id,
                    'title': title,
                    'matches': matching_lines,
                    'total_lines': len(lines),
                })

                if len(results) >= max_results:
                    return results

    return results


def search_full_transcripts(
    query: str,
    creator_filter: str = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Search transcript.json for segment-level matches with timing info.
    """
    results = []
    query_lower = query.lower()

    if not os.path.isdir(DATA_DIR):
        return results

    for creator_name in sorted(os.listdir(DATA_DIR)):
        creator_dir = os.path.join(DATA_DIR, creator_name)
        if not os.path.isdir(creator_dir):
            continue

        if creator_filter and creator_name != creator_filter:
            continue

        for video_id in sorted(os.listdir(creator_dir)):
            video_dir = os.path.join(creator_dir, video_id)
            if not os.path.isdir(video_dir) or video_id.startswith('_'):
                continue

            json_path = os.path.join(video_dir, 'transcript.json')
            metadata_path = os.path.join(video_dir, 'metadata.json')

            if not os.path.isfile(json_path):
                continue

            title = 'Unknown'
            if os.path.isfile(metadata_path):
                try:
                    with open(metadata_path) as f:
                        meta = json.load(f)
                    title = meta.get('title', 'Unknown')
                except Exception:
                    pass

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue

            matching_segments = []
            for seg in data.get('segments', []):
                text = seg.get('text', '')
                if query_lower in text.lower():
                    matching_segments.append(seg)

            if matching_segments:
                results.append({
                    'creator': creator_name,
                    'video_id': video_id,
                    'title': title,
                    'language': data.get('language', '?'),
                    'matching_segments': matching_segments,
                })

                if len(results) >= max_results:
                    return results

    return results


def _format_timestamp(seconds) -> str:
    """Convert seconds to MM:SS."""
    try:
        total = int(float(seconds))
    except (ValueError, TypeError):
        total = 0
    return f"{total // 60:02d}:{total % 60:02d}"


def main():
    parser = argparse.ArgumentParser(
        description='Search YouTube Shorts transcripts by keyword'
    )
    parser.add_argument(
        'query',
        help='Search term or phrase'
    )
    parser.add_argument(
        '--creator', '-c',
        help='Limit search to this creator'
    )
    parser.add_argument(
        '--max', '-m',
        type=int, default=20,
        help='Max number of video matches to return (default: 20)'
    )
    parser.add_argument(
        '--timed', '-t',
        action='store_true',
        help='Show timed segment matches from transcript.json'
    )

    args = parser.parse_args()

    print(f"🔍 Searching for: \"{args.query}\"")
    if args.creator:
        print(f"   Creator filter: {args.creator}")
    print()

    if args.timed:
        results = search_full_transcripts(args.query, args.creator, args.max)

        if not results:
            print("   No matches found.")
            return

        for r in results:
            print(f"📺 [{r['creator']}] {r['title']}")
            print(f"   ID: {r['video_id']} | Lang: {r['language']}")
            for seg in r['matching_segments']:
                ts = _format_timestamp(seg['start'])
                print(f"   [{ts}] {seg['text']}")
            print()
    else:
        results = search_transcripts(args.query, args.creator, args.max)

        if not results:
            print("   No matches found.")
            return

        for r in results:
            print(f"📺 [{r['creator']}] {r['title']}")
            print(f"   ID: {r['video_id']} | Matches: {len(r['matches'])} / {r['total_lines']} lines")
            for line in r['matches'][:3]:
                print(f"   {line}")
            if len(r['matches']) > 3:
                print(f"   ... and {len(r['matches']) - 3} more")
            print()

    print(f"📊 Total: {len(results)} videos matched")


if __name__ == '__main__':
    main()
