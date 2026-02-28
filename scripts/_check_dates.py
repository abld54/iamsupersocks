import json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = json.load(open('veille-data.json', encoding='utf-8'))
arts = d['articles']
print(f"Generated : {d['generated']}")
print(f"Total     : {d['count']} articles")
print()
print("Latest 10 articles:")
for a in arts[:10]:
    print(f"  {a['date'][:16]}  {a['source']['name'][:15]:15}  {a['title'][:50]}")
print()
# Check date distribution
from collections import Counter
dates = Counter(a['date'][:10] for a in arts)
print("Articles per day (last 7):")
for day, count in sorted(dates.items(), reverse=True)[:7]:
    print(f"  {day}: {count} articles")
