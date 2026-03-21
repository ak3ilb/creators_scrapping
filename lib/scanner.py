"""
scanner.py — List all Short video IDs for a YouTube channel.

Uses yt-dlp's extract_flat mode to quickly enumerate videos
without downloading any content.
"""

import yt_dlp
import json
import os
from datetime import datetime, timezone
from lib.writer import get_ingestion_summary


def scan_channel(creator: dict) -> list[dict]:
    """
    Scan a creator's Shorts page and return a list of all video entries.

    Args:
        creator: dict with 'name', 'url', 'languages', 'active'

    Returns:
        List of dicts: [{'id': str, 'title': str, 'url': str}, ...]
    """
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'ignoreerrors': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(creator['url'], download=False)

    entries = info.get('entries', [])
    videos = []
    for e in entries:
        if e and e.get('id'):
            videos.append({
                'id': e['id'],
                'title': e.get('title', 'Unknown'),
                'url': f"https://www.youtube.com/watch?v={e['id']}",
            })

    return videos


def get_existing_video_ids(data_dir: str, creator_name: str) -> set:
    """
    Return set of video IDs already ingested for a creator.
    Reads from data/<creator>/ directory.
    """
    creator_dir = os.path.join(data_dir, creator_name)
    if not os.path.isdir(creator_dir):
        return set()

    existing = set()
    for entry in os.scandir(creator_dir):
        if entry.is_dir() and not entry.name.startswith('_'):
            # Check if transcript.json exists (completed ingestion)
            meta_path = os.path.join(entry.path, 'metadata.json')
            if os.path.isfile(meta_path):
                existing.add(entry.name)
    return existing


def filter_new_videos(videos: list[dict], existing_ids: set) -> list[dict]:
    """Return only videos not yet ingested."""
    return [v for v in videos if v['id'] not in existing_ids]


def update_channel_meta(data_dir: str, creator: dict, videos: list[dict]):
    """
    Write/update _channel_meta.json for the creator with dynamic stats and video registry.
    """
    creator_name = creator['name']
    creator_dir = os.path.join(data_dir, creator_name)
    os.makedirs(creator_dir, exist_ok=True)

    meta_path = os.path.join(creator_dir, '_channel_meta.json')
    
    # Get current stats from disk
    stats = get_ingestion_summary(data_dir, creator_name)

    # Build video registry (dynamic list of all shorts and their statuses)
    registry = []
    for v in videos:
        v_id = v['id']
        v_meta_path = os.path.join(creator_dir, v_id, 'metadata.json')
        status = "pending"
        if os.path.isfile(v_meta_path):
            with open(v_meta_path, 'r', encoding='utf-8') as f:
                v_meta = json.load(f)
            status = v_meta.get('transcript_status', 'unknown')
        
        registry.append({
            'video_id': v_id,
            'title': v.get('title', 'Unknown'),
            'status': status
        })

    meta = {
        'name': creator_name,
        'url': creator['url'],
        'languages': creator['languages'],
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_discovered': len(videos),
        'ingestion_stats': stats,
        'completion_percentage': f"{(stats['total'] / len(videos) * 100):.1f}%" if len(videos) > 0 else "0%",
        'videos': registry
    }

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
