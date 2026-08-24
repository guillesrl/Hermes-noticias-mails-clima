#!/usr/bin/env python3
"""Extrae titulares recientes de los feeds del briefing, con fecha.
Uso: fetch-news.py [horas]   (por defecto 24)
Soporta RSS (item/pubDate) y Atom (entry/updated|published), con y sin CDATA.
Imprime solo entradas dentro de la ventana, ordenadas de mas nueva a mas vieja.
"""
import re
import sys
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://arstechnica.com/security/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.infobae.com/arc/outboundfeeds/rss/category/tecno/",
]

HOURS = int(sys.argv[1]) if len(sys.argv[1:]) and sys.argv[1].isdigit() else 24
now = datetime.now(timezone.utc)


def clean(s):
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(raw):
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def field(block, *names):
    for n in names:
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (n, n), block, re.S | re.I)
        if m:
            return m.group(1)
    return ""


def fetch(url):
    try:
        return subprocess.run(
            ["curl", "-sL", "--max-time", "15", "-H", "User-Agent: Mozilla/5.0", url],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return ""


for url in FEEDS:
    xml = fetch(url)
    blocks = re.findall(r"<item[ >].*?</item>|<entry[ >].*?</entry>", xml, re.S | re.I)
    rows = []
    for b in blocks:
        d = parse_date(clean(field(b, "pubDate", "updated", "published", "dc:date")))
        if not d:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        age = (now - d).total_seconds() / 3600
        if age > HOURS or age < -6:
            continue
        title = clean(field(b, "title"))
        summary = clean(field(b, "description", "summary", "content"))[:300]
        if title:
            rows.append((d, title, summary))
    rows.sort(key=lambda r: r[0], reverse=True)
    print("===FEED %s (ultimas %dh: %d) ===" % (url, HOURS, len(rows)))
    for d, title, summary in rows[:5]:
        print("[%s] %s" % (d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"), title))
        if summary:
            print("    %s" % summary)
    if not rows:
        print("(sin novedades en la ventana)")
    print()