#!/usr/bin/env python3
"""
analyze.py — Trigger style analysis for one or all creators.
"""

import argparse
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.style_analyzer import StyleAnalyzer
from ingest import DATA_DIR, load_creators, CREATORS_FILE

def main():
    parser = argparse.ArgumentParser(description='Analyze creator storytelling style')
    parser.add_argument('--creator', '-c', help='Name of the creator to analyze')
    parser.add_argument('--output', '-o', help='Path to save JSON analysis results')

    args = parser.parse_args()

    # Load creators
    creators = load_creators(CREATORS_FILE)
    if args.creator:
        creators = [c for c in creators if c['name'] == args.creator]
        if not creators:
            print(f"❌ Creator '{args.creator}' not found.")
            sys.exit(1)

    analyzer = StyleAnalyzer(DATA_DIR)
    
    for creator in creators:
        name = creator['name']
        print(f"🧐 Analyzing style for: {name}...")
        
        try:
            results = analyzer.analyze_creator(name)
            
            if "error" in results:
                print(f"   ⚠️  {results['error']}")
                continue

            # Print a quick summary
            print(f"   ✅ Done! Analyzed {results['total_videos_analyzed']} videos.")
            print(f"   📊 Clusters found: {', '.join(results['clusters'].keys())}")
            
            # Save detailed analysis
            output_path = args.output or os.path.join(DATA_DIR, name, '_style_analysis.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"   📝 Detailed analysis saved to: {output_path}")

            # Save DNA Profile (Phase 3)
            dna_path = analyzer.save_dna_profile(name, results)
            print(f"   🧬 Uniqueness DNA Profile saved to: {dna_path}")

        except Exception as e:
            print(f"   💥 Error analyzing {name}: {e}")

if __name__ == '__main__':
    main()
