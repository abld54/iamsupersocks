#!/usr/bin/env python3
import json, urllib.request, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

url = "https://iamsupersocks.com/veille-data.json"
with urllib.request.urlopen(url, timeout=15) as r:
    d = json.loads(r.read())

arts = d['articles']
analyzed = [a for a in arts if a.get('analysis')]

print(f"Generated : {d['generated']}")
print(f"Count     : {d['count']} articles")
print(f"Analyzed  : {len(analyzed)} / {len(arts)}")
print()
print("--- 5 latest articles ---")
for a in arts[:5]:
    has_a = bool(a.get('analysis'))
    model = a.get('analysis', {}).get('model', 'none') if has_a else 'none'
    tag = f"OK:{model[:14]}" if has_a else "no analysis    "
    print(f"  [{a['date'][:10]}] {a['source']['name'][:12]:12} | {tag:20} | {a['title'][:45]}")

print()
print("--- Signal check (3 analyzed articles) ---")
for a in analyzed[:3]:
    sig = a.get('analysis', {}).get('signal', '')
    print(f"  [{a['source']['name'][:10]:10}] {sig[:90]}")
