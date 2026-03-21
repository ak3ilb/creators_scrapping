"""
writer.py — Write structured output to data/<creator>/<video_id>/.

Creates:
  - transcript.json  (machine-readable timed segments)
  - transcript.txt   (human-readable [MM:SS] format)
  - metadata.json    (video info + ingestion status)
"""

import json
import os
from datetime import datetime, timezone


def write_video_data(
    data_dir: str,
    creator_name: str,
    result,  # TranscriptResult from transcript.py
):
    """
    Write all output files for a single video.

    Args:
        data_dir: path to the data/ directory
        creator_name: creator folder name
        result: TranscriptResult object
    """
    video_dir = os.path.join(data_dir, creator_name, result.video_id)
    os.makedirs(video_dir, exist_ok=True)

    # Write transcript files (only if we have segments)
    if result.segments:
        _write_transcript_json(video_dir, result)
        _write_transcript_txt(video_dir, result)

    # Write metadata.json (ALWAYS LAST — acts as completion flag for scanner)
    _write_metadata(video_dir, creator_name, result)


def _write_metadata(video_dir: str, creator_name: str, result):
    """Write metadata.json."""
    meta = {
        'video_id': result.video_id,
        'title': result.title or 'Unknown',
        'channel': creator_name,
        'description': result.description or '',
        'duration_seconds': result.duration_seconds,
        'publish_date': result.publish_date,
        'transcript_status': result.status,
        'transcript_language': result.language,
        'transcript_source': result.source,
        'segment_count': len(result.segments),
        'ingested_at': datetime.now(timezone.utc).isoformat(),
    }

    if result.error:
        meta['error'] = result.error

    path = os.path.join(video_dir, 'metadata.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def _write_transcript_json(video_dir: str, result):
    """Write transcript.json — machine-readable."""
    data = {
        'video_id': result.video_id,
        'language': result.language,
        'source': result.source,
        'segments': result.segments,
    }

    path = os.path.join(video_dir, 'transcript.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _write_transcript_txt(video_dir: str, result):
    """Write transcript.txt — human-readable [MM:SS] format."""
    path = os.path.join(video_dir, 'transcript.txt')
    with open(path, 'w', encoding='utf-8') as f:
        for seg in result.segments:
            ts = _format_timestamp(seg['start'])
            f.write(f"[{ts}] {seg['text']}\n")


def _format_timestamp(seconds) -> str:
    """Convert seconds (float or int) to MM:SS format."""
    try:
        total = int(float(seconds))
    except (ValueError, TypeError):
        total = 0
    minutes = total // 60
    secs = total % 60
    return f"{minutes:02d}:{secs:02d}"


def get_ingestion_summary(data_dir: str, creator_name: str) -> dict:
    """
    Return a summary of ingested data for a creator.

    Returns dict with counts: total, ok, low_quality, no_transcript, no_speech
    """
    creator_dir = os.path.join(data_dir, creator_name)
    summary = {
        'total': 0,
        'ok': 0,
        'low_quality': 0,
        'no_transcript': 0,
        'no_speech': 0,
    }

    if not os.path.isdir(creator_dir):
        return summary

    for entry in os.scandir(creator_dir):
        if entry.is_dir() and not entry.name.startswith('_'):
            meta_path = os.path.join(entry.path, 'metadata.json')
            if os.path.isfile(meta_path):
                summary['total'] += 1
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                    status = meta.get('transcript_status', '').lower()
                    if status == 'ok':
                        summary['ok'] += 1
                    elif status == 'low_quality':
                        summary['low_quality'] += 1
                    elif status == 'no_transcript':
                        summary['no_transcript'] += 1
                    elif status == 'no_speech':
                        summary['no_speech'] += 1
                except Exception:
                    pass

    return summary
