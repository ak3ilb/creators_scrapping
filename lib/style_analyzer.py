"""
lib/style_analyzer.py — Extract storytelling DNA (Hooks, Pacing, Structure) from transcripts.
"""

import json
import os
import re
from datetime import datetime
from collections import Counter

class StyleAnalyzer:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def analyze_creator(self, creator_name: str) -> dict:
        """
        Analyze all ingested transcripts for a creator and find style patterns.
        """
        creator_path = os.path.join(self.data_dir, creator_name)
        if not os.path.exists(creator_path):
            raise Exception(f"No data found for creator: {creator_name}")

        videos_data = []
        for entry in os.scandir(creator_path):
            if entry.is_dir() and not entry.name.startswith('_'):
                transcript_path = os.path.join(entry.path, 'transcript.json')
                meta_path = os.path.join(entry.path, 'metadata.json')
                
                if os.path.exists(transcript_path) and os.path.exists(meta_path):
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript = json.load(f)
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    if meta.get('transcript_status') == 'OK':
                        videos_data.append({
                            'id': entry.name,
                            'segments': transcript.get('segments', []),
                            'title': meta.get('title', ''),
                            'duration': meta.get('duration_seconds', 0)
                        })

        if not videos_data:
            return {"error": "No valid transcripts found to analyze."}

        # 1. Analyze individual videos
        video_profiles = [self._analyze_video_dna(v) for v in videos_data]

        # 2. Cluster patterns (Simulated clustering for now based on segment counts and WPS)
        clusters = self._cluster_profiles(video_profiles)

        # 3. Aggregate results
        return {
            "creator": creator_name,
            "total_videos_analyzed": len(videos_data),
            "clusters": clusters,
            "overall_avg_wps": sum(p['avg_wps'] for p in video_profiles) / len(video_profiles) if video_profiles else 0
        }

    def _analyze_video_dna(self, video: dict) -> dict:
        """
        Extract specific metrics for a single video.
        """
        segments = video['segments']
        if not segments:
            return {}

        # Pacing (Words Per Second)
        total_words = sum(len(s['text'].split()) for s in segments)
        duration = video['duration'] or (segments[-1]['start'] + 3.0)
        avg_wps = total_words / duration if duration > 0 else 0

        # Hook DNA (First 2 segments)
        hook = " ".join([s['text'] for s in segments[:2]])
        
        # Structure
        num_segments = len(segments)
        
        return {
            "video_id": video['id'],
            "avg_wps": avg_wps,
            "num_segments": num_segments,
            "duration": duration,
            "hook": hook,
            "last_segment": segments[-1]['text'] if segments else ""
        }

    def _cluster_profiles(self, profiles: list[dict]) -> dict:
        """
        Groups videos into behavior types (clusters).
        """
        # Logic: 
        # Short (< 30s) vs Long (>= 30s)
        # Fast Paced (WPS > 2.5) vs Slow Paced (WPS <= 2.5)
        
        clusters = {
            "story_deep_dive": [], # Long, moderate pace
            "fast_facts": [],     # Short, fast pace
            "quick_hook": [],      # Very short
            "other": []
        }

        for p in profiles:
            if p['duration'] >= 45:
                clusters["story_deep_dive"].append(p)
            elif p['avg_wps'] > 3.0:
                clusters["fast_facts"].append(p)
            elif p['duration'] < 20:
                clusters["quick_hook"].append(p)
            else:
                clusters["other"].append(p)

        # Summarize each cluster
        summary = {}
        for name, members in clusters.items():
            if members:
                summary[name] = {
                    "count": len(members),
                    "avg_wps": sum(m['avg_wps'] for m in members) / len(members),
                    "avg_duration": sum(m['duration'] for m in members) / len(members),
                    "common_hook_patterns": self._extract_common_phrases([m['hook'] for m in members]),
                    "sample_hooks": [m['hook'][:100] for m in members[:3]]
                }
        
        return summary

    def save_dna_profile(self, creator_name: str, analysis: dict):
        """
        Saves a condensed 'DNA Profile' for the creator to creator_pattern/.
        """
        pattern_dir = os.path.join(os.path.dirname(self.data_dir), 'creator_pattern')
        os.makedirs(pattern_dir, exist_ok=True)
        
        # Condensed profile for token efficiency
        profile = {
            "creator": creator_name,
            "last_updated": datetime.now().isoformat(),
            "pacing": {
                "avg_wps": analysis.get("overall_avg_wps", 0),
                "clusters": {name: {"wps": c["avg_wps"], "duration": c["avg_duration"]} 
                            for name, c in analysis.get("clusters", {}).items()}
            },
            "signature_hooks": self._aggregate_hooks(analysis),
            "uniqueness_traits": self._extract_traits(analysis)
        }
        
        path = os.path.join(pattern_dir, f"{creator_name}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        return path

    def _aggregate_hooks(self, analysis: dict) -> list:
        """Collect top hooks from all clusters."""
        all_hooks = []
        for cluster in analysis.get("clusters", {}).values():
            all_hooks.extend(cluster.get("common_hook_patterns", []))
        return list(set(all_hooks))[:10]

    def _extract_traits(self, analysis: dict) -> list:
        """Heuristic traits based on data."""
        traits = []
        if analysis.get("overall_avg_wps", 0) > 3.2:
            traits.append("High Energy / Fast Paced")
        elif analysis.get("overall_avg_wps", 0) < 2.8:
            traits.append("Calm / Explanatory")
            
        # Check cluster dominance
        clusters = analysis.get("clusters", {})
        if clusters.get("story_deep_dive", {}).get("count", 0) > 20:
            traits.append("Storytelling Specialist")
        if clusters.get("fast_facts", {}).get("count", 0) > 10:
            traits.append("Information Heavy / Listicle Style")
            
        return traits

    def _extract_common_phrases(self, texts: list[str]) -> list:
        """
        Finds repeated 2-3 word sequences (n-grams) in the text.
        """
        bi_grams = []
        tri_grams = []
        
        for t in texts:
            # Simple split by whitespace and strip common punctuation
            words = [w.strip('.,!?;:()[]"') for w in t.lower().split() if w.strip('.,!?;:()[]"')]
            
            # Bigrams
            for i in range(len(words) - 1):
                bi_grams.append(f"{words[i]} {words[i+1]}")
            
            # Trigrams
            for i in range(len(words) - 2):
                tri_grams.append(f"{words[i]} {words[i+1]} {words[i+2]}")

        # Filter out common stop-word-only phrases
        bi_counts = Counter(bi_grams).most_common(20)
        tri_counts = Counter(tri_grams).most_common(20)

        results = []
        results.extend([b for b, count in bi_counts if count > 1])
        results.extend([t for t, count in tri_counts if count > 1])
        
        return results[:15]
