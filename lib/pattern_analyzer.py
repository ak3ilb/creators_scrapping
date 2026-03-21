#!/usr/bin/env python3
"""
lib/pattern_analyzer.py — Deep per-video pattern extraction engine (Layer 1 + Layer 2).

Layer 1: Mechanical per-video analysis (WPS, language mix, hook/closing extraction, vocab frequency)
Layer 2: Cross-video aggregation (consistent vs variable vs rare patterns)

Layer 3 (DNA Profile) is written by AI intelligence, not this code.
"""

import json
import os
import re
import hashlib
from datetime import datetime
from collections import Counter


# ─── Hindi/Devanagari detection ────────────────────────────────────────────
DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')
LATIN_RE = re.compile(r'[A-Za-z]')

def _language_mix(text: str) -> dict:
    """Estimate % Hindi vs English vs mixed in a text."""
    dev_chars = len(DEVANAGARI_RE.findall(text))
    lat_chars = len(LATIN_RE.findall(text))
    total = dev_chars + lat_chars
    if total == 0:
        return {"hindi": 0, "english": 0, "total_chars": 0}
    return {
        "hindi": round(dev_chars / total * 100, 1),
        "english": round(lat_chars / total * 100, 1),
        "total_chars": total
    }


def _file_hash(path: str) -> str:
    """SHA256 of file contents for change detection."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _parse_transcript_txt(path: str) -> list[dict]:
    """
    Parse a transcript.txt file into segments.
    Format: [HH:MM] text or [MM:SS] text
    """
    segments = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Match [00:00] or [01:23] prefix
            m = re.match(r'\[(\d+):(\d+)\]\s*(.*)', line)
            if m:
                mins, secs = int(m.group(1)), int(m.group(2))
                start = mins * 60 + secs
                text = m.group(3).strip()
                if text and text != '[संगीत]':
                    segments.append({"start": start, "text": text})
    return segments


def _extract_words(text: str) -> list[str]:
    """Split text into words, stripping punctuation."""
    return [w.strip('.,!?;:()[]"\'।') for w in text.split() if w.strip('.,!?;:()[]"\'।')]


# ─── Layer 1: Per-Video Analysis ───────────────────────────────────────────

def analyze_single_video(video_id: str, transcript_path: str) -> dict:
    """
    Extract all mechanical patterns from a single video transcript.
    Returns a structured dict with 10 pattern categories.
    """
    segments = _parse_transcript_txt(transcript_path)
    if not segments:
        return {"video_id": video_id, "error": "empty_or_unparseable"}

    all_text = " ".join(s["text"] for s in segments)
    all_words = _extract_words(all_text)
    
    # Duration estimation
    if len(segments) > 1:
        duration = segments[-1]["start"] + 5  # approximate last segment length
    else:
        duration = max(len(all_words) / 3, 10)  # rough estimate
    
    # WPS
    wps = round(len(all_words) / duration, 2) if duration > 0 else 0

    # Language mix
    lang = _language_mix(all_text)

    # Hook (first segment)
    hook_text = segments[0]["text"] if segments else ""
    hook_type = _classify_hook(hook_text)
    
    # Closing (last segment)
    closing_text = segments[-1]["text"] if segments else ""
    closing_type = _classify_closing(closing_text)

    # Word frequency (top 30)
    word_freq = Counter(w.lower() for w in all_words if len(w) > 1)
    top_words = word_freq.most_common(30)

    # Bigram frequency
    bigrams = []
    for i in range(len(all_words) - 1):
        bigrams.append(f"{all_words[i].lower()} {all_words[i+1].lower()}")
    bigram_freq = Counter(bigrams).most_common(15)

    # Audience addressing style
    audience_style = _detect_audience_style(all_text)

    # Structure (how many segments and their rough purpose)
    structure = _detect_structure(segments)

    return {
        "video_id": video_id,
        "duration_seconds": duration,
        "wps": wps,
        "total_words": len(all_words),
        "language_mix": lang,
        "hook": {
            "type": hook_type,
            "text": hook_text[:200]
        },
        "closing": {
            "type": closing_type,
            "text": closing_text[:200]
        },
        "audience_addressing": audience_style,
        "structure": structure,
        "top_words": [{"word": w, "count": c} for w, c in top_words[:20]],
        "top_bigrams": [{"phrase": p, "count": c} for p, c in bigram_freq[:10]],
        "segment_count": len(segments)
    }


def _classify_hook(text: str) -> str:
    """Classify the opening hook type."""
    text_lower = text.lower()
    if any(q in text_lower for q in ['क्या', '?', 'अगर', 'if', 'do you', 'have you']):
        return "question"
    if any(s in text_lower for s in ['ये ', 'this', 'एक ']):
        return "statement"
    if any(n in text for n in ['₹', '$', '%', 'लाख', 'करोड़', 'billion', 'million', 'crore']):
        return "shock_number"
    if any(w in text_lower for w in ['imagine', 'सोचो', 'कल्पना']):
        return "imagination"
    if any(w in text_lower for w in ['so if', 'most of']):
        return "direct_address"
    return "general_statement"


def _classify_closing(text: str) -> str:
    """Classify the closing CTA type."""
    text_lower = text.lower()
    if any(w in text_lower for w in ['कमेंट', 'comment', 'बताओ', 'बताएं', 'let me know']):
        return "question_to_audience"
    if any(w in text_lower for w in ['फॉलो', 'follow', 'subscribe', 'सब्सक्राइब', 'बायो', 'bio', 'लिंक']):
        return "direct_cta"
    if any(w in text_lower for w in ['think about', 'सोचो', 'याद रखना']):
        return "reflection"
    return "punchline_or_open"


def _detect_audience_style(text: str) -> list[str]:
    """Detect how the creator addresses their audience."""
    patterns = []
    if 'तुम लोग' in text or 'तुम्हें' in text or 'तुम्हारे' in text:
        patterns.append("तुम लोग (informal plural)")
    if 'भाई' in text or 'भैया' in text:
        patterns.append("भाई/भैया (bro-style)")
    if 'आप' in text or 'आपको' in text or 'आपके' in text:
        patterns.append("आप (formal)")
    if re.search(r'\byou\b', text, re.IGNORECASE):
        patterns.append("you (English)")
    if 'so if you' in text.lower() or 'if you' in text.lower():
        patterns.append("conditional address (if you...)")
    return patterns if patterns else ["neutral/third_person"]


def _detect_structure(segments: list[dict]) -> str:
    """Detect the high-level structure of the video."""
    n = len(segments)
    if n <= 3:
        return "micro_punch"  # Very short, few segments
    if n <= 7:
        return "standard_short"  # Typical short
    if n <= 15:
        return "detailed_explainer"  # Medium length
    return "long_form_story"  # Longer narrative


# ─── Layer 1: Scanning & Tracking ──────────────────────────────────────────

def scan_creator_transcripts(data_dir: str, creator_name: str) -> list[dict]:
    """
    Find all transcript.txt files for a creator.
    Returns list of {video_id, transcript_path, file_hash}.
    """
    creator_path = os.path.join(data_dir, creator_name)
    if not os.path.exists(creator_path):
        return []

    results = []
    for entry in sorted(os.scandir(creator_path), key=lambda e: e.name):
        if entry.is_dir() and not entry.name.startswith('_'):
            txt_path = os.path.join(entry.path, 'transcript.txt')
            if os.path.exists(txt_path) and os.path.getsize(txt_path) > 10:
                results.append({
                    "video_id": entry.name,
                    "transcript_path": txt_path,
                    "file_hash": _file_hash(txt_path)
                })
    return results


def load_meta(patterns_dir: str, creator_name: str) -> dict:
    """Load _meta.json for a creator, or return empty defaults."""
    meta_path = os.path.join(patterns_dir, creator_name, '_meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"creator": creator_name, "transcript_hashes": {}, "videos_analyzed": 0}


def save_meta(patterns_dir: str, creator_name: str, meta: dict):
    """Save _meta.json for a creator."""
    creator_dir = os.path.join(patterns_dir, creator_name)
    os.makedirs(creator_dir, exist_ok=True)
    meta["last_updated"] = datetime.now().isoformat()
    with open(os.path.join(creator_dir, '_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# ─── Layer 2: Cross-Video Synthesis ────────────────────────────────────────

def synthesize_patterns(video_analyses: list[dict]) -> dict:
    """
    Aggregate all per-video analyses to find consistent vs variable vs rare patterns.
    This is the mechanical aggregation — AI interpretation happens separately.
    """
    if not video_analyses:
        return {"error": "no_data"}

    n = len(video_analyses)
    
    # Pacing stats
    wps_values = [v["wps"] for v in video_analyses if "wps" in v]
    avg_wps = round(sum(wps_values) / len(wps_values), 2) if wps_values else 0
    min_wps = round(min(wps_values), 2) if wps_values else 0
    max_wps = round(max(wps_values), 2) if wps_values else 0

    # Language mix averages
    hindi_pcts = [v["language_mix"]["hindi"] for v in video_analyses if "language_mix" in v]
    avg_hindi = round(sum(hindi_pcts) / len(hindi_pcts), 1) if hindi_pcts else 0

    # Hook type distribution
    hook_types = Counter(v["hook"]["type"] for v in video_analyses if "hook" in v)
    
    # Closing type distribution
    closing_types = Counter(v["closing"]["type"] for v in video_analyses if "closing" in v)
    
    # Structure distribution
    structures = Counter(v["structure"] for v in video_analyses if "structure" in v)

    # Audience address frequency
    audience_all = []
    for v in video_analyses:
        audience_all.extend(v.get("audience_addressing", []))
    audience_dist = Counter(audience_all)

    # Aggregate word frequency across all videos
    global_word_freq = Counter()
    for v in video_analyses:
        for w in v.get("top_words", []):
            global_word_freq[w["word"]] += w["count"]
    
    # Classify words by video-level frequency
    word_video_presence = Counter()
    for v in video_analyses:
        seen_words = set(w["word"] for w in v.get("top_words", []))
        for w in seen_words:
            word_video_presence[w] += 1
    
    # Categorize: consistent (>60%), variable (15-60%), rare (<15%)
    consistent_words = {w: c for w, c in word_video_presence.items() if c / n >= 0.6}
    variable_words = {w: c for w, c in word_video_presence.items() if 0.15 <= c / n < 0.6}
    rare_words = {w: c for w, c in word_video_presence.items() if c / n < 0.15 and c >= 2}

    # Collect all hooks and closings
    all_hooks = [v["hook"]["text"] for v in video_analyses if v.get("hook", {}).get("text")]
    all_closings = [v["closing"]["text"] for v in video_analyses if v.get("closing", {}).get("text")]

    return {
        "total_videos": n,
        "pacing": {
            "avg_wps": avg_wps,
            "min_wps": min_wps,
            "max_wps": max_wps
        },
        "language": {
            "avg_hindi_pct": avg_hindi,
            "avg_english_pct": round(100 - avg_hindi, 1)
        },
        "hook_types": dict(hook_types.most_common()),
        "closing_types": dict(closing_types.most_common()),
        "structures": dict(structures.most_common()),
        "audience_addressing": dict(audience_dist.most_common()),
        "vocabulary": {
            "consistent": dict(sorted(consistent_words.items(), key=lambda x: -x[1])[:20]),
            "variable": dict(sorted(variable_words.items(), key=lambda x: -x[1])[:20]),
            "rare": dict(sorted(rare_words.items(), key=lambda x: -x[1])[:15])
        },
        "sample_hooks": all_hooks[:8],
        "sample_closings": all_closings[:8]
    }
