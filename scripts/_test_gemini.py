#!/usr/bin/env python3
"""Quick test of Gemini API key."""
import json, os, urllib.request

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    print("ERROR: GEMINI_API_KEY not set")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
body = json.dumps({
    "contents": [{"parts": [{"text": "Analyze this: 'OpenAI releases GPT-5 with reasoning capabilities'. Respond with JSON: {\"signal\": \"one sentence\", \"summary\": \"two sentences\", \"context\": \"context\", \"critique\": \"critique\", \"themes\": [\"AI\", \"Models\"]}"}]}],
    "generationConfig": {
        "responseMimeType": "application/json",
        "maxOutputTokens": 300,
        "temperature": 0.4,
    },
}).encode("utf-8")

req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read())
    text = resp["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    print("KEY OK - works")
    print(f"signal:  {parsed.get('signal', '')[:80]}")
    print(f"summary: {parsed.get('summary', '')[:80]}")
    print(f"themes:  {parsed.get('themes', [])}")
except Exception as e:
    print(f"ERROR: {e}")
