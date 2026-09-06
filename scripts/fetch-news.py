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
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Ars Technica Security", "https://arstechnica.com/security/feed/"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Infobae Tecnología", "https://www.infobae.com/arc/outboundfeeds/rss/category/tecno/"),
    ("Xataka", "https://feeds.weblogssl.com/xataka2"),
    ("Genbeta", "https://feeds.weblogssl.com/genbeta"),
    # Fuentes primarias y especializadas para evitar depender de agregadores.
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/"),
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss"),
    ("OpenAI News", "https://openai.com/news/rss.xml"),
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


def collect(hours, seen_titles):
    """Recopila entradas recientes y devuelve filas intercalables por fuente."""
    feed_rows = []
    for source, url in FEEDS:
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
            if age > hours or age < -6:
                continue
            title = clean(field(b, "title"))
            summary = clean(field(b, "description", "summary", "content"))[:600]
            if title:
                # Algunos medios replican el mismo artículo en varios feeds.
                title_key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                rows.append((d, title, summary))
        rows.sort(key=lambda r: r[0], reverse=True)
        feed_rows.append((source, rows[:8]))
    return feed_rows

seen_titles = set()
feed_rows = collect(HOURS, seen_titles)
collected = sum(len(rows) for _, rows in feed_rows)
window_label = f"ultimas {HOURS}h"

# Los fines de semana y festivos algunos feeds se actualizan menos. Ampliaremos
# solo si la ventana normal no ofrece suficiente material, sin inventar noticias.
if HOURS == 24 and collected < 25:
    extra_rows = collect(48, seen_titles)
    existing = {source: rows for source, rows in feed_rows}
    for source, rows in extra_rows:
        existing.setdefault(source, []).extend(rows)
    feed_rows = [(source, rows[:8]) for source, rows in existing.items()]
    collected = sum(len(rows) for _, rows in feed_rows)
    window_label = "ultimas 48h (fallback por baja cobertura)"

# Intercalar las fuentes para evitar que una sola domine la selección posterior.
print("===NOTICIAS POR FUENTE (%s) ===" % window_label)
for index in range(8):
    for source, rows in feed_rows:
        if index >= len(rows):
            continue
        d, title, summary = rows[index]
        print("[%s] %s: %s" % (
            d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"), source, title
        ))
        if summary:
            print("    %s" % summary)
        print()