"""
transcript.py — Fetch timed transcripts with 4-level fallback.

Level 1: youtube-transcript-api (fast, timed)
Level 2: yt-dlp auto-sub download (catches API blind spots)
Level 3: Chrome headless (bypasses IP blocks)
Level 4: metadata-only (save what we can)
"""

import time
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
)
import yt_dlp

logger = logging.getLogger(__name__)


class TranscriptResult:
    """Container for a transcript extraction result."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.segments = []          # list of {start, duration, text}
        self.language = None        # e.g. 'hi', 'en'
        self.source = None          # which level succeeded
        self.status = None          # OK, LOW_QUALITY, NO_TRANSCRIPT, NO_SPEECH
        self.title = None
        self.description = None
        self.duration_seconds = None
        self.publish_date = None
        self.error = None           # error message if failed


def fetch_transcript(video_id: str, languages: list[str] = None) -> TranscriptResult:
    """
    Try all 4 fallback levels to get a timed transcript.

    Args:
        video_id: YouTube video ID
        languages: ordered list of language codes to try (default: ['hi', 'en'])

    Returns:
        TranscriptResult with status and data
    """
    if languages is None:
        languages = ['hi', 'en']

    result = TranscriptResult(video_id)

    # Fetch metadata first via yt-dlp (lightweight, always works)
    _fetch_metadata(result)

    # Level 1: youtube-transcript-api
    if _try_level1(result, languages):
        return result

    # Level 2: yt-dlp auto-sub
    if _try_level2(result, languages):
        return result

    # Level 3: Chrome headless
    if _try_level3(result, languages):
        return result

    # Level 4: metadata-only
    _finalize_no_transcript(result)
    return result


def _fetch_metadata(result: TranscriptResult):
    """Fetch video metadata via yt-dlp (no download)."""
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f'https://www.youtube.com/watch?v={result.video_id}',
                download=False
            )
            result.title = info.get('title', 'Unknown')
            result.description = info.get('description', '')
            result.duration_seconds = info.get('duration')
            result.publish_date = info.get('upload_date')

            # Check if video has any captions at all
            auto_caps = info.get('automatic_captions', {})
            manual_subs = info.get('subtitles', {})
            if not auto_caps and not manual_subs:
                result.status = 'NO_SPEECH'
                result.error = 'No captions available on YouTube'
                logger.info(f"[{result.video_id}] No captions at all — NO_SPEECH")
    except Exception as e:
        logger.warning(f"[{result.video_id}] Metadata fetch failed: {e}")


def _try_level1(result: TranscriptResult, languages: list[str]) -> bool:
    """Level 1: youtube-transcript-api."""
    if result.status == 'NO_SPEECH':
        return False

    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(result.video_id, languages=languages)

        segments = []
        for snippet in transcript.snippets:
            segments.append({
                'start': snippet.start,
                'duration': snippet.duration,
                'text': snippet.text,
            })

        if segments:
            result.segments = segments
            result.language = transcript.language
            result.source = 'youtube-transcript-api'
            result.status = 'OK'
            logger.info(
                f"[{result.video_id}] Level 1 OK: {len(segments)} segments, "
                f"lang={result.language}"
            )
            return True

    except NoTranscriptFound:
        logger.info(f"[{result.video_id}] Level 1: No transcript found for {languages}")
    except TranscriptsDisabled:
        logger.info(f"[{result.video_id}] Level 1: Transcripts disabled")
    except Exception as e:
        err_name = type(e).__name__
        logger.info(f"[{result.video_id}] Level 1 failed ({err_name}): {str(e)[:80]}")

    return False


def _try_level2(result: TranscriptResult, languages: list[str]) -> bool:
    """Level 2: yt-dlp auto-sub extraction."""
    if result.status == 'NO_SPEECH':
        return False

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'writeautomaticsub': True,
            'subtitleslangs': languages,
            'subtitlesformat': 'json3',
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f'https://www.youtube.com/watch?v={result.video_id}',
                download=False
            )

            # Check requested_subtitles for what was found
            req_subs = info.get('requested_subtitles', {})
            if not req_subs:
                logger.info(f"[{result.video_id}] Level 2: No auto-subs available")
                return False

            # Try each language
            for lang in languages:
                if lang in req_subs:
                    sub_info = req_subs[lang]
                    sub_url = sub_info.get('url')
                    if sub_url:
                        segments = _download_and_parse_json3(sub_url, ydl)
                        if segments:
                            result.segments = segments
                            result.language = lang
                            result.source = 'yt-dlp-auto-sub'
                            result.status = 'OK'
                            logger.info(
                                f"[{result.video_id}] Level 2 OK: "
                                f"{len(segments)} segments, lang={lang}"
                            )
                            return True

    except Exception as e:
        logger.info(f"[{result.video_id}] Level 2 failed: {str(e)[:80]}")

    return False


def _download_and_parse_json3(url: str, ydl) -> list[dict]:
    """Download json3 subtitle URL and parse into segments."""
    import json
    try:
        response = ydl.urlopen(url)
        data = json.loads(response.read())
        events = data.get('events', [])

        segments = []
        for ev in events:
            segs = ev.get('segs', [])
            if segs:
                text = ''.join(s.get('utf8', '') for s in segs).strip()
                if text and text != '\n':
                    t_ms = ev.get('tStartMs', 0)
                    d_ms = ev.get('dDurationMs', 0)
                    segments.append({
                        'start': t_ms / 1000.0,
                        'duration': d_ms / 1000.0,
                        'text': text,
                    })
        return segments
    except Exception as e:
        logger.warning(f"json3 parse failed: {e}")
        return []


def _try_level3(result: TranscriptResult, languages: list[str]) -> bool:
    """Level 3: Chrome headless — scrape transcript panel."""
    if result.status == 'NO_SPEECH':
        return False

    try:
        from lib.chrome_fallback import fetch_transcript_via_chrome
        segments, language = fetch_transcript_via_chrome(result.video_id, languages)

        if segments:
            result.segments = segments
            result.language = language
            result.source = 'chrome-headless'
            result.status = 'OK'
            logger.info(
                f"[{result.video_id}] Level 3 OK: "
                f"{len(segments)} segments, lang={language}"
            )
            return True
    except ImportError:
        logger.info(f"[{result.video_id}] Level 3: chrome_fallback not available")
    except Exception as e:
        logger.info(f"[{result.video_id}] Level 3 failed: {str(e)[:80]}")

    return False


def _finalize_no_transcript(result: TranscriptResult):
    """Level 4: Give up on transcript, save metadata only."""
    if result.status != 'NO_SPEECH':
        result.status = 'NO_TRANSCRIPT'
        result.error = 'All extraction methods failed'
    logger.info(f"[{result.video_id}] Final status: {result.status}")
