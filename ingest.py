#!/usr/bin/env python3
"""
ingest.py — Scan YouTube channels and fetch transcripts for all Shorts.

Usage:
    python3 ingest.py                              # All active creators
    python3 ingest.py --creator Shivanshu.Agrawal  # One creator only
    python3 ingest.py --creator Shivanshu.Agrawal --limit 5  # First 5 only
    python3 ingest.py --force                      # Re-fetch all (skip incremental check)
"""

import argparse
import json
import logging
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.scanner import scan_channel, get_existing_video_ids, filter_new_videos, update_channel_meta
from lib.transcript import fetch_transcript
from lib.writer import write_video_data, get_ingestion_summary

# DELAYS: Increased per user suggestion to mitigate 429 (Too Many Requests)
DELAY_BETWEEN_VIDEOS = 5    # seconds
DELAY_BETWEEN_CREATORS = 15  # seconds

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CREATORS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'creators.json')


def load_creators(filepath: str) -> list[dict]:
    """Load creator configs from creators.json."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get('creators', [])


def ingest_single_video(creator: dict, video: dict, all_videos: list[dict]) -> str:
    """
    Ingest a single video. Returns the result status.
    """
    name = creator['name']
    languages = creator.get('languages', ['hi', 'en'])
    v_id = video['id']
    v_title = video.get('title', 'Unknown')

    print(f"\n   -> {v_id} — {v_title[:50]}")

    try:
        result = fetch_transcript(v_id, languages=languages)

        # Write output
        write_video_data(DATA_DIR, name, result)

        # Delete directory if no transcript is found (so we can retry later)
        if not result.segments:
            video_dir = os.path.join(DATA_DIR, name, result.video_id)
            if os.path.exists(video_dir):
                import shutil
                shutil.rmtree(video_dir)
                print(f"       🗑️  No transcript — cleaned up directory")

        status = (result.status or 'error').lower()
        
        status_icon = {
            'ok': '✅',
            'low_quality': '⚠️',
            'no_transcript': '❌',
            'no_speech': '🔇',
        }.get(status, '❓')

        seg_count = len(result.segments) if result.segments else 0
        print(f"       {status_icon} {status} | {seg_count} segments | "
              f"lang={result.language} | via={result.source}")
        
        # Update channel meta after every video for real-time dashboard
        update_channel_meta(DATA_DIR, creator, all_videos)
        return status

    except Exception as e:
        print(f"       💥 Error: {e}")
        return 'error'


def main():
    parser = argparse.ArgumentParser(
        description='Ingest YouTube Shorts transcripts'
    )
    parser.add_argument(
        '--creator', '-c',
        help='Process only this creator (by name from creators.json)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int, default=0,
        help='Max number of Shorts to scan per creator (0 = all)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Re-fetch all videos (ignore existing data)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Load creators
    creators = load_creators(CREATORS_FILE)
    if not creators:
        print("❌ No creators found in creators.json")
        sys.exit(1)

    # Filter to specific creator if requested
    if args.creator:
        creators = [c for c in creators if c['name'] == args.creator]
        if not creators:
            print(f"❌ Creator '{args.creator}' not found in creators.json")
            sys.exit(1)

    # Filter to active only
    active_creators = [c for c in creators if c.get('active', True)]
    if not active_creators:
        print("❌ No active creators to process")
        sys.exit(1)

    print(f"🚀 YouTube Shorts Transcript Ingestion (Interleaved)")
    print(f"   Creators: {len(active_creators)}")
    print(f"   Limit: {'all' if args.limit == 0 else args.limit}")
    print(f"   Force: {args.force}")

    # Phase 1: Scan all channels
    creator_queues = []
    total_new = 0

    print(f"\n📡 Scanning all active channels...")
    for creator in active_creators:
        name = creator['name']
        print(f"   -> {name}...", end="", flush=True)
        videos = scan_channel(creator)
        
        if not args.force:
            existing = get_existing_video_ids(DATA_DIR, name)
            new_videos = filter_new_videos(videos, existing)
        else:
            new_videos = videos
        
        if args.limit > 0 and len(new_videos) > args.limit:
            new_videos = new_videos[:args.limit]
        
        print(f" {len(new_videos)} new / {len(videos)} total")
        
        # Always update meta to show current state (creates directory + _channel_meta.json)
        update_channel_meta(DATA_DIR, creator, videos)
        
        # Small delay between scans to avoid 429
        time.sleep(2)
        
        if new_videos:
            creator_queues.append({
                'creator': creator,
                'all_videos': videos,
                'queue': new_videos
            })
            total_new += len(new_videos)

    if total_new == 0:
        print("\n✅ All creators are up to date! Nothing to process.")
        return

    print(f"\n📦 Starting interleaved ingestion of {total_new} videos...")
    
    # Phase 2: Interleaved processing (Round-robin)
    processed_count = 0
    while any(c['queue'] for c in creator_queues):
        for q in creator_queues:
            if not q['queue']:
                continue
            
            creator = q['creator']
            video = q['queue'].pop(0)
            processed_count += 1
            
            print(f"\n[{processed_count}/{total_new}] Creator: {creator['name']}")
            ingest_single_video(creator, video, q['all_videos'])
            
            # Global delay between any two videos to avoid IP ban
            if processed_count < total_new:
                time.sleep(DELAY_BETWEEN_VIDEOS)

    # Final summary
    print(f"\n{'='*60}")
    print(f"  🎉 ALL INGESTION COMPLETE")
    print(f"{'='*60}")
    for creator in active_creators:
        summary = get_ingestion_summary(DATA_DIR, creator['name'])
        print(f"\n  {creator['name']}:")
        print(f"    Total: {summary['total']} | OK: {summary['ok']} | "
              f"No transcript: {summary['no_transcript']} | "
              f"No speech: {summary['no_speech']}")


if __name__ == '__main__':
    main()
