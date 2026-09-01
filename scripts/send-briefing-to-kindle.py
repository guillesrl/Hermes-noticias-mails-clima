#!/usr/bin/env python3
"""Send noticias-ia-diarias to Kindle as .txt attachment.
Reads Spanish file if available, otherwise translates from summaries via OpenRouter."""

import os
import glob
import re
import json
import base64
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BRIEFING_DIR = "/home/ubuntu/hermes-notes/news"
NEWS_DIR = "/opt/proyectos/noticias-ia/noticias-es"

today = datetime.now(timezone.utc).strftime('%Y-%m-%d')


def extract_news_from_briefing(text):
    """Extract news section from briefing-manana file (already in Spanish).
    Cada noticia (Uno., Dos., ...) queda como párrafo propio separado por una
    línea en blanco, para que Kindle no las colapse todas juntas."""
    match = re.search(r'Y en noticias de IA y tecnolog[ií]a:(.*?)Eso es todo por hoy\.', text, re.DOTALL)
    if not match:
        return None
    section = match.group(1).strip()
    items = re.split(r'\n(?=(?:Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez)\.)', section)
    out = []
    for it in items:
        it = it.strip()
        if not it:
            continue
        it = re.sub(r'^(?:Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez)\.\s+', '• ', it)
        out.append(it)
    return '\n\n'.join(out) if out else section


# Un titular es la primera frase de la noticia, si es corta. Si el briefing no
# la trae separada (o se va de largo), no se subraya nada y el párrafo sale
# entero: mejor sin subrayado que subrayando media noticia.
# El prompt pide titulares de menos de 120 caracteres, pero el modelo se pasa a
# menudo; 175 da margen sin llegar a subrayar media noticia (2026-08-06).
TITLE_MAX = 175


def split_headline(item):
    """Devuelve (titular, resto). El titular puede ser cadena vacía."""
    body = item[2:] if item.startswith('• ') else item
    m = re.match(r'\s*(.+?[.:])\s+(?=[«"¿¡A-ZÁÉÍÓÚÑ0-9])(.*)', body, re.DOTALL)
    if m and len(m.group(1)) <= TITLE_MAX and m.group(2).strip():
        return m.group(1).strip(), m.group(2).strip()
    return '', body.strip()


def build_html(content, fecha):
    """Documento HTML para Kindle: titulares subrayados, resto en párrafos."""
    import html as _html
    partes = []
    for item in content.split('\n\n'):
        item = item.strip()
        if not item:
            continue
        titular, resto = split_headline(item)
        if titular:
            partes.append(
                f'<p><u>{_html.escape(titular)}</u> {_html.escape(resto)}</p>'
            )
        else:
            partes.append(f'<p>{_html.escape(resto)}</p>')
    cuerpo = '\n'.join(partes)
    return (
        '<html><head><meta charset="utf-8"><title>Noticias IA</title></head>'
        f'<body><h1>Noticias IA</h1><p><i>{fecha}</i></p>\n{cuerpo}\n</body></html>'
    )


def get_spanish_content():
    # 1. Try TODAY'S briefing-manana file (generado a las 06:30) - PRIORITY.
    #    SOLO el de hoy: si aún no está listo, NO caer al de ayer (evita reenviar
    #    noticias repetidas cuando el briefing tarda más que el cron del Kindle).
    today_briefing = f"{BRIEFING_DIR}/briefing-manana-{today}.md"
    if os.path.exists(today_briefing):
        text = Path(today_briefing).read_text(encoding="utf-8")
        if "Y en noticias de IA" in text:
            news_content = extract_news_from_briefing(text)
            if news_content and len(news_content) > 500:
                print(f"Using briefing file: {today_briefing}")
                return news_content
    
    # 2. Try pre-translated Spanish file from noticias-ia-diarias cron
    es_files = sorted(glob.glob(f"{NEWS_DIR}/noticias-es-*.md"), reverse=True)
    for f in es_files[:2]:
        content = Path(f).read_text(encoding="utf-8").strip()
        if content and len(content) > 200:
            # Check if file is from today
            if today in f:
                print(f"Using Spanish file: {f}")
                return content
    
    # 3. Sin briefing de hoy: NO enviar. El fallback de traducir los summaries
    #    producia resumenes cortados y texto crudo del RSS, peor que no mandar
    #    nada (2026-08-05). Se avisa por Telegram y se sale sin enviar.
    print("No hay briefing de hoy; no se envia nada al Kindle.")
    notify_telegram(
        "Kindle: no se ha enviado el briefing de hoy.\n"
        f"No existe (o esta incompleto) briefing-manana-{today}.md."
    )
    return None


def notify_telegram(text):
    """Aviso a Telegram con el bot que ya usa el monitor de errores."""
    try:
        env = Path("/opt/telegram-bot/.env").read_text(encoding="utf-8")
        token = re.search(r'^TELEGRAM_BOT_TOKEN=(.+)$', env, re.MULTILINE).group(1).strip().strip('"\'')
        chat = re.search(r'^TELEGRAM_USER_ID=(.+)$', env, re.MULTILINE).group(1).strip().strip('"\'')
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20
        ).read()
    except Exception as e:
        print(f"No se pudo avisar por Telegram: {e}")


# Remove URLs from the content (keep only source name, not full links)
def strip_urls(content: str) -> str:
    """Remove URLs from news content, keeping only source names."""
    lines = []
    for line in content.split('\n'):
        # Skip lines that are just URLs (start with https://)
        if line.strip().startswith('https://'):
            continue
        lines.append(line)
    return '\n'.join(lines)


try:
    content = get_spanish_content()
except Exception as e:
    print(f"No se pudo obtener contenido ({e}); se omite el envio.")
    exit(0)
if not content:
    print("No content to send, skipping")
    exit(0)

# Strip URLs before sending to Kindle
content = strip_urls(content)

full_content = build_html(content, today)

token_path = os.environ.get("GOOGLE_TOKEN_PATH", "/home/ubuntu/.hermes/google_token.json")
with open(token_path, 'r') as f:
    token_data = json.load(f)

creds = Credentials.from_authorized_user_info(token_data)

msg = MIMEMultipart()
msg['To'] = 'guillesrl_QDobKJ@kindle.com'
msg['From'] = 'guillesrl@gmail.com'
msg['Subject'] = 'Noticias IA'
msg.attach(MIMEText('', 'plain'))
txt_part = MIMEText(full_content, 'html', 'utf-8')
txt_part.add_header('Content-Disposition', 'attachment', filename=f'noticias-ia-{today}.html')
msg.attach(txt_part)

raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
service = build('gmail', 'v1', credentials=creds)
sent = service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
print(f"Sent to Kindle: {sent['id']}")
