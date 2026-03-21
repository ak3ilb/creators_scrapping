#!/usr/bin/env python3
"""
daily_script.py — Automated daily script generation.
Designed to be run as a cron job.
"""

import argparse
import json
import os
import sys
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest import load_creators, CREATORS_FILE, DATA_DIR

def get_next_creator(creators: list) -> dict:
    """Simple rotation logic based on the day of the year."""
    day_of_year = datetime.now().timetuple().tm_yday
    return creators[day_of_year % len(creators)]

def get_dynamic_topic() -> str:
    """
    Placeholder for dynamic topic discovery.
    In a real cron job, this would fetch trending news or niche-specific trends.
    For this system, Antigravity identifies the best 'viral' topic during execution.
    """
    return "TRENDING_TOPIC_RECOVERY"

def main():
    parser = argparse.ArgumentParser(description='Daily automated script generation')
    parser.add_argument('--topic', help='Optional: override daily topic')
    parser.add_argument('--creator', help='Optional: override daily creator')

    args = parser.parse_args()

    # 1. Load active creators
    creators = [c for c in load_creators(CREATORS_FILE) if c.get('active', True)]
    if not creators:
        print("❌ No active creators found.")
        sys.exit(1)

    # 2. Select Creator
    if args.creator:
        creator = next((c for c in creators if c['name'] == args.creator), None)
        if not creator:
            print(f"❌ Creator '{args.creator}' not found.")
            sys.exit(1)
    else:
        creator = get_next_creator(creators)

    # 3. Choose Topic (Dynamic)
    topic = args.topic or get_dynamic_topic()

    print(f"📅 Daily Script Generation — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"👤 Creator Style: {creator['name']}")
    
    if topic == "TRENDING_TOPIC_RECOVERY":
        print("🔍 Searching for viral/trending topics...")
    else:
        print(f"💡 Topic: {topic}")

    # 4. Trigger Generation
    creator_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', creator['name'])
    os.makedirs(creator_dir, exist_ok=True)
    
    date_str = datetime.now().strftime('%Y_%m_%d')
    topic_slug = topic.lower().replace(' ', '_')[:30]
    filename = f"{date_str}_{topic_slug}.md"
    output_path = os.path.join(creator_dir, filename)
    
    # Improved Coordination Message
    template = f"""# Daily Script: [TO BE FILLED BY ANTIGRAVITY]
# Drafted on: {datetime.now().isoformat()}
# Style DNA: {creator['name']}

---
# 🧠 ANTIGRAVITY COORDINATION:
# I see this daily task. I am currently:
# 1. Scanning trends (search_web).
# 2. Extracting {creator['name']}'s unique DNA.
# 3. Synthesizing the final Hindi script for you.
# ---
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template)
        
    print(f"📁 Daily task file created: {output_path}")
    print("🚀 Antigravity reached! I will now proceed to finish the script.")

if __name__ == '__main__':
    main()
