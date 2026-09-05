---
name: cron-news-delivery
description: "Daily news cron job workflow: search, format, and deliver text + TTS audio."
version: 1.5.0
---

# Cron Audio Digests

Workflow for automated daily audio digests: news briefings AND email summaries. Both share the same pipeline: search/filter, format plain text, TTS, deliver.

## Kindle Delivery Script Fix (2026-06-30)

**Problema**: El script `send-briefing-to-kindle.py` (6:45 UTC) enviaba noticias del día anterior porque:
- Buscaba primero en `/opt/proyectos/noticias-ia/noticias-es/` que no se actualizaba (el cron `noticias-ia-diarias` está deshabilitado desde 24/6)
- Como fallback usaba `briefing-tarde-29-jun.md` con contenido antiguo

**Solución**: El script ahora busca en este orden:
1. `briefing-manana-YYYY-MM-DD.md` (PRIORIDAD - ya está en español, generado a las 6:30 UTC)
2. `noticias-es-YYYY-MM-DD.md` solo si es del día actual  
3. Traducir desde summaries como último recurso

**Código clave agregado**:
```python
def extract_news_from_briefing(text):
    """Extract news section from briefing-manana file (already in Spanish)."""
    match = re.search(r'Y en noticias de IA y tecnologia:(.*?)Eso es todo por hoy\.', text, re.DOTALL)
    return match.group(1).strip() if match else None

# En get_spanish_content():
briefing_files = sorted(glob.glob(f"{BRIEFING_DIR}/briefing-manana-*.md"), reverse=True)
for f in briefing_files[:2]:
    text = Path(f).read_text(encoding="utf-8")
    if "Y en noticias de IA" in text:
        news_content = extract_news_from_briefing(text)
        if news_content and len(news_content) > 500:
            return news_content
```

## Email Summary Workflow

Trigger: User asks for recurring daily email digest with audio.

Steps:
1. Search Gmail for last 10 unread emails: `$GAPI gmail search "is:unread newer_than:1d" --max 10`
2. Filter by relevance: personal emails, newsletters (esp. AI/tech), important notifications. Discard: generic promos (Amazon bulk, AirAsia, RBA revistas), newsletters that are just promotional blurbs.
3. For each relevant email, call `$GAPI gmail get MESSAGE_ID` to read full body.
4. Generate summary text (max 3 min audio, ~3000 chars max). Style: news briefing, Spanish. Rules:
   - **Plain text only. NO asterisks `*`, NO bold, NO markdown of any kind.** This is critical — asterisks are read aloud by TTS and sound unnatural. Write in pure plain text with dashes or numbers as separators. Separator between topics: dashes or numbers, not `*` or `**`.
   - **Max 3000 chars** (Edge TTS limit is 5000 but the model truncates at ~3000 for Spanish).
5. Convert to TTS audio via `text_to_speech` with explicit output path:
   ```
   text_to_speech(text="...", output_path="/home/ubuntu/.hermes/audio_cache/emails-YYYY-MM-DD.ogg")
   ```
6. **CRITICAL for cron delivery**: The final cron response must be **ONLY the MEDIA path**, nothing else:
   ```
   MEDIA:/home/ubuntu/.hermes/audio_cache/emails-2026-05-25.ogg
   ```
   Do NOT include any text before or after the MEDIA line. The delivery system correctly sends media-only responses as native audio to Telegram. Adding surrounding text causes "No deliverable text or media remained after processing MEDIA tags" failures.

**Cron setup example:**
```bash
cronjob(action='create', name='Resumen Emails diario', schedule='0 9 * * *', prompt='...', skills=['google-workspace'], model={'model': 'qwen3.6-plus', 'provider': 'opencode-go'})
```

## News Delivery Workflow

Trigger: User asks for recurring daily news delivery via cron job with text + audio.

Steps:
1. **NO cargar skills pesadas** — usar `skills=[]` para evitar context bloat.
2. **Check recent coverage** — Before searching, read the last 2-3 news files in `/home/ubuntu/hermes-notes/news/` and the latest cron output in the appropriate job directory to identify already-covered stories. Extract key topics/headlines to avoid.
3. **Search news via RSS using curl** (see "Fuentes RSS" pitfall below). Get 7 relevant stories. Avoid topics already covered.
4. Format results without URLs in the main text — use source names only (e.g., "Fuente: Ars Technica"). Ensure sources are distinct.
5. **Write the full news content FIRST** to `/home/ubuntu/hermes-notes/news/` using write_file — this is the permanent record.
6. Generate TTS audio using `text_to_speech`. **Edge TTS limit: keep text under 4,000 characters** (hard cap at 5,000). The audio text must be plain — no asterisks, no markdown. Numera como "Uno", "Dos", "Tres" para que suene natural. No leas URLs ni fuentes en el audio — solo el contenido noticioso.
7. **CRITICAL for cron delivery**: The final cron response must be **ONLY the MEDIA path**, nothing else:
```
MEDIA:/home/ubuntu/.hermes/audio_cache/news-YYYY-MM-DD.ogg
```
Do NOT include any text before or after the MEDIA line.

## Briefing Matutino (Combined Weather + Emails + News)

Trigger: User wants a single morning briefing instead of separate email/news digests.

Steps:
1. **NO cargar la skill google-workspace** — inyecta ~340 lineas de documentacion que consumen el contexto. Usar `skills=[]`.
2. Search weather for Andorra TODAY via curl: `curl -s "https://wttr.in/Andorra?format=%c+%t+%h+%w+%T+%m"`
3. Email section is optional — if gmail access fails, skip and continue.
4. Search latest AI/tech news via RSS feeds using curl (see "Fuentes RSS" pitfall below). Get 7 stories.
5. Combine into single plain-text summary starting with "Buenos dias Guille, aqui va tu briefing."
6. Sections in order: clima primero ("En Andorra hoy: ..."), emails if any ("Mails importantes:"), noticias ("Y en noticias de IA y tecnologia: Uno. Dos. Tres..." hasta "Siete.")
7. OBLIGATORY: include weather and 7 news. Emails optional. Target 3000-4800 characters.
8. **PASO 4 - write_file FIRST**: Write to `/home/ubuntu/hermes-notes/news/briefing-manana-YYYY-MM-DD.md` BEFORE TTS.
9. Convert to TTS with `output_path="/home/ubuntu/.hermes/audio_cache/briefing-YYYY-MM-DD.ogg"`
10. Final response: ONLY `MEDIA:/home/ubuntu/.hermes/audio_cache/briefing-YYYY-MM-DD.ogg`
11. Enable toolsets: web, tts, file, terminal

**Cron setup:**
```bash
cronjob(action='create', name='Briefing matutino', schedule='30 6 * * *', skills=[], enabled_toolsets=['web', 'tts', 'file', 'terminal'], model={'model': 'qwen3.6-plus', 'provider': 'opencode-go'})
```

## Pitfalls

- **Duplicate stories across days**: The same major news (e.g., Google I/O, Trump orders) dominates search results for 3-4 days. Always cross-reference recent files in `/home/ubuntu/hermes-notes/news/` before selecting stories. If a topic appears in yesterday's or the day-before's file, skip it and find a different angle or completely different story.
- **TTS text must be plain text — NO markdown, NO asterisks**: The asterisks/bold markers are read aloud by TTS and sound unnatural. Write in pure plain text. Use words like "negrita" only if you need to describe formatting intentionally. Separator between topics: dashes or numbers, not `*` or `**`.: The daily cron uses Air Street Press and Crescendo.ai as primary sources. When the user asks for news "different from those already covered" or "noticias diferentes", DO NOT extract from Air Street Press, Crescendo.ai, or similar AI-news aggregators — they recycle the same stories. Instead, search for primary sources: company press releases, academic papers, regulatory filings, mainstream media (Reuters, Bloomberg, WSJ, CNET, STAT News), and niche outlets (The Information, FierceBiotech, Data Center Watch). If a story appeared in the cron's markdown file (even from a different angle), skip it entirely.
- **Source diversification for cron prompts**: To permanently prevent repetition in the daily cron, update the cron's prompt to include a curated list of alternative sources it should search actively. When you encounter repetitive news, run `cronjob action='update'` on the job and add an explicit sources paragraph to the prompt with outlets the cron does NOT normally hit. Proven alternative sources for AI news: theinformation.com (exclusive industry), bloomberg.com/technology (finance), statnews.com + biospace.com (biotech/pharma AI), usnews.com + gallup.com (public opinion/polls), cnet.com (consumer products), help.openai.com (release notes), 36kr.eu/kr.asia (China AI/investments), battery-tech.net (hardware/energy). Include these in the cron prompt so every run auto-diversifies.
- **Edge TTS hard limit is 5,000 characters**: `PROVIDER_MAX_TEXT_LENGTH["edge"] = 5000`. Audio beyond this is silently truncated. Keep audio text under 4,000 chars with buffer. This means ~3-5 min of spoken audio, not 30+ min. Write full news detail in the markdown file; the audio should only cover key points.
- **Provider naming: look up the ID in docs first, NOT in config.yaml**: `model.provider` in config.yaml might be WRONG if the user misconfigured it. A config showing `provider: google` with `base_url: https://opencode.ai/zen/go/v1` is SILENTLY WRONG — the OpenCode Go base_url exists under the provider `opencode-go`, not `google`. The provider `google` exists in Hermes (for Google/Gemini), so the config parses without error but routes to the wrong backend. The correct provider ID is `opencode-go` — confirmed from the docs at `hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime` → "OpenCode Zen / OpenCode Go: `opencode-zen`, `opencode-go`". Real case: user had `google` + OpenCode Go base_url → cron silently failed until fixed to `opencode-go` + `minimax-m2.7`. Also confirmed: `hermes config set model opencode-go/minimax-m2.7` sets the global config correctly. The `.env` file with `OPENCODE_GO_API_KEY` is what actually authenticates — the provider ID just routes to the right backend.
- **`provider: auto` on auxiliary models resolves to Gemini when GOOGLE_API_KEY is present**: If `auxiliary.*.provider` is set to `auto` in config.yaml AND `GOOGLE_API_KEY` exists in `.env`, Hermes silently routes auxiliary calls (compression, vision, web_extract, etc.) to Gemini. This causes HTTP 404 errors on cron jobs that don't have explicit model/provider overrides. Fix: set all auxiliary providers explicitly to the desired provider (e.g., `opencode-go`) via `hermes config set auxiliary.compression.provider opencode-go` (repeat for vision, web_extract, skills_hub, approval, mcp, title_generation, triage_specifier, kanban_decomposer, profile_describer, curator, session_search) OR use the Python script approach to bulk-update config.yaml. Real case: Briefing matutino and Resumen dia siguiente both failed with "RuntimeError: HTTP 404: Gemini" until auxiliary providers were changed from `auto` to `opencode-go`.
- **Model hardcoding in cron jobs**: Cron jobs store the model+provider at creation/update time. When the user switches the default model in Hermes config, the cron still uses the old hardcoded model. Workaround: after switching models in Hermes, manually run `cronjob(action='update', job_id='...', model={'model': 'CURRENT_MODEL', 'provider': 'CURRENT_PROVIDER'})`. To discover the current model: `grep -E "^model:" ~/.hermes/config.yaml`.
- **Debugging "provider failed" after Hermes restart**: When the gateway shows `⚠️ The model provider failed after retries` on startup, the root cause is often `provider: auto` in auxiliary models resolving to Gemini (via `GOOGLE_API_KEY` in `.env`). Diagnosis steps: (1) `grep 'provider: auto' ~/.hermes/config.yaml` — if any matches, that's likely the culprit. (2) `grep 'GOOGLE_API_KEY=' ~/.hermes/.env` — if present, `auto` will resolve to Gemini. (3) Fix by setting all auxiliary providers explicitly: Python script to bulk-update config.yaml is fastest. (4) Verify with `python -c "import yaml; c=yaml.safe_load(open('~/.hermes/config.yaml')); [print(f'{k}: {v.get("provider")}') for k,v in c.get('auxiliary',{}).items()]"` . The user can select the model manually from the Telegram menu as a temporary workaround because it creates a session model override that bypasses the broken `auto` resolution.
- **New cron jobs MUST specify model+provider**: When creating a new cron job with `cronjob(action='create')`, ALWAYS pass `model={'model': 'qwen3.6-plus', 'provider': 'opencode-go'}` (or whatever the current default is). Without explicit model/provider, the system defaults to Gemini which returns HTTP 404 for this user's setup. Real case: Briefing matutino cron failed with "RuntimeError: HTTP 404: Gemini" until model+provider was explicitly set via update.
- **Do not substitute related content for requested content**: When the user asks for "audio like the news but with my emails", execute the email summary workflow — search Gmail, filter relevant emails, summarize, create TTS, deliver. Do NOT deliver an existing news audio file or any other related-but-different content. The user asked for emails; give them emails.
- **Email audio delivery via send_message fails with MEDIA tags**: When sending `.mp3` audio files from `~/.hermes/audio_cache/` via `send_message`, Telegram returns "No deliverable text or media remained after processing MEDIA tags" if the message only contains the MEDIA tag with no accompanying text. Workaround: send a short text prefix first (e.g. "Aquí tienes tu resumen de emails:"), then send the media in a follow-up message. If that also fails, regenerate the audio via `text_to_speech` with the email summary text instead of trying to reuse the cron-generated file.
- **Correct fix for email and news cron audio delivery**: The root cause is the cron prompt including extra text around the MEDIA path. The cron prompt must end with ONLY `MEDIA:/path/to/audio.ogg` (emails) or `MEDIA:/home/ubuntu/.hermes/audio_cache/news-YYYY-MM-DD.ogg` (news) — no surrounding description, no backticks, no explanatory text. The delivery system interprets media-only responses and sends them as native Telegram voice messages. This is the preferred fix over send_message workarounds. Both email and news cron jobs now use this pattern.
- **text_to_speech must use explicit output_path**: The cron prompt must say "Convierte el texto a audio usando text_to_speech con output_path='/home/ubuntu/.hermes/audio_cache/FILENAME.ogg'". If the prompt just says "genera un audio" without `output_path`, the agent may skip calling the tool entirely and just write a MEDIA path to an old file.
- **All sources same name**: If the agent defaults to one source (e.g., "Reuters") for all items, explicitly instruct to use the REAL source name from each URL.
- **URLs in audio**: Instruct the agent NOT to read URLs aloud. Only mention source names like "Fuente Politico" or "Segun Reuters".
- **User asks "noticia número X" de hoy**: NO buscar en la web. Los briefings se guardan en `/home/ubuntu/hermes-notes/news/`. El archivo del dia puede ser `briefing-tarde-YYYY-MM-DD.md` (vespertino 13:00 UTC), `briefing-manana-YYYY-MM-DD.md` (matutino 06:30 UTC), o `YYYY-MM-DD.md` (formato antiguo). Leer el archivo mas reciente del dia y buscar la noticia numerada en el contenido. Las noticias estan numeradas con "Uno.", "Dos.", "Tres.", etc. **Si el usuario dice "completa" o "trae la noticia X"**, devolver el texto COMPLETO de esa noticia (todos los parrafos, detalles, contexto), no un resumen ni solo el titular.
- **TODOS los cron prompts de briefing/incluso deben incluir write_file antes de TTS**: Pitfall descubierto: el Briefing matutino no guardaba archivo .md porque su prompt terminaba directamente con "Tu respuesta FINAL: SOLO MEDIA:..." sin instruccion de escribir el archivo. El Briefing vespertino SÍ tenia "Escribe el contenido completo en /home/ubuntu/hermes-notes/news/briefing-tarde-YYYY-MM-DD.md". **Regla**: todo cron que genera contenido de noticias/clima/emails DEBE incluir una instruccion explicita de `write_file` al path correspondiente ANTES de la instruccion de `text_to_speech`. Sin ella, el agente solo genera el audio y se pierde el texto permanente.
- **NO cargar skills pesadas en cron jobs de briefing**: La skill `google-workspace` inyecta ~340 lineas de documentacion completa en el contexto del cron, consumiendo casi todo el contexto y dejando al agente sin espacio para ejecutar pasos intermedios (curl a RSS, write_file, etc.). El agente salta directo a `text_to_speech` + `MEDIA` sin escribir el archivo. **Fix**: usar `skills=[]` en cron jobs de briefing. Incluir los comandos de gmail directamente en el prompt si se necesitan. Marcar emails como opcionales.
- **El agente salta el paso de emails en cron de briefing**: En multiples pruebas, el agente del cron ejecuta clima, noticias, write_file y audio pero SALTAN el paso de buscar emails con `gmail search`, incluso cuando esta marcado como OBLIGATORIO. Causa raiz: el agente prioriza llegar al `MEDIA:` final y se salta pasos intermedios que no bloquean el output. **Workaround efectivo**: incluir el comando GAPI directamente en el prompt con formato explicito, y marcar emails como opcionales ("Si no hay emails relevantes, omite esta seccion"). No bloquear el flujo si gmail falla.
- **Cron prompt estructura verificada (confirmada working 2026-05-30)**: La estructura final que funciona para briefing matutino/vespertino:
  1. PASO 1 - CLIMA via curl a wttr.in
  2. PASO 2 - EMAILS via GAPI directo (no via skill google-workspace)
  3. PASO 3 - NOTICIAS via curl a 6 RSS feeds
  4. PASO 4 - COMPONER TEXTO en formato plain text
  5. PASO 5 - ESCRIBIR ARCHIVO con write_file (OBLIGATORIO antes del audio)
  6. PASO 6 - AUDIO con text_to_speech usando el MISMO texto del PASO 4
  Final: SOLO la linea MEDIA. Skills: [], toolsets: [web, tts, file, terminal].
- **Agente puede generar audio vacio (0 bytes) en cron**: En las primeras ejecuciones, `text_to_speech` produjo archivo de 0 bytes. Esto puede deberse a timeout del contexto del cron o texto demasiado largo. **Fix**: regenerar manualmente con text_to_speech desde el archivo .md si el audio queda vacio.
- **Deteccion de duplicados entre cron matutino y vespertino**: El briefing vespertino DEBE tener un PASO 0 obligatorio ANTES de buscar noticias: leer `read_file` de `/home/ubuntu/hermes-notes/news/briefing-manana-YYYY-MM-DD.md` (mismo dia) y extraer los temas/titulares cubiertos. Descartar cualquier noticia de los feeds RSS que trate el mismo tema, aunque sea desde otro angulo. Si los feeds solo repiten noticias de la manana, buscar angulos secundarios o usar fuentes alternativas (CNET, 36kr). El prompt del vespertino debe estructurarse como "PASO 0 - DETECCION DE DUPLICADOS (OBLIGATORIO, hazlo ANTES de buscar noticias): Lee el archivo...".
- **Estructura de pasos numerados para cron prompts**: Cuando un cron tiene 3+ acciones, usar estructura PASO 1, PASO 2, etc. con orden secuencial explicito. Marcar write_file como "OBLIGATORIO, hazlo ANTES del audio". Funciono tras 3 intentos fallidos:
```
PASO 1 - CLIMA: Ejecuta curl ... y anota el resultado.
PASO 2 - NOTICIAS: Ejecuta curl para obtener RSS ...
PASO 3 - COMPONER TEXTO: Crea el texto del briefing ...
PASO 4 - ESCRIBIR ARCHIVO (OBLIGATORIO, hazlo ANTES del audio): Usa write_file ...
PASO 5 - AUDIO (usa el MISMO texto del PASO 3): Usa text_to_speech ...
```

## Cron Job Setup

```bash
hermes cron create "0 10 * * *" --prompt "[news prompt]" --toolsets web,tts
```

Update existing job:
```bash
hermes cron edit [job_id]
```

Enable TTS toolset on the job if not already enabled.

## Audio Cache Maintenance

A `no_agent` cron script cleans old audio files **daily** at 6:00 UTC:
- Job: `Limpiar audios antiguos` (job_id: `1d7c97544636`)
- Script: `scripts/cleanup-old-audio.sh` — deletes `.ogg/.mp3/.wav` in `~/.hermes/audio_cache/` older than today
- Audio cache dir: `~/.hermes/audio_cache/` — ALL cron audio files must use this directory

## Calendar Event Reminder Pattern

Trigger: User wants daily reminder of tomorrow's calendar events.

**Key requirement**: Use `[SILENT]` when there are no events — prevents unnecessary notifications.

**Cron setup:**
```bash
cronjob(action='create', name='Resumen día siguiente', schedule='0 21 * * *', skills=['google-workspace'], prompt='...')
```

**Prompt pattern:**
```
If NO events: respond ONLY with [SILENT] and nothing more.
If there ARE events: generate a brief text summary. No markdown, no asterisks, plain text only.
Final response: just the plain text summary.
```

The `[SILENT]` response suppresses delivery entirely — the user receives nothing when the calendar is empty.

## Active Cron Jobs (as of 2026-06-30)

| Job | ID | Schedule | Description |
|-----|------|----------|-------------|
| Briefing matutino | 903e48204612 | 06:30 UTC (08:30 Andorra) | Weather + emails + news in single audio. Output: briefing-manana-YYYY-MM-DD.md. Skills: [] (gmail-api kept but documented). |
| Briefing vespertino | f393354a5d50 | 13:00 UTC (15:00 Andorra) | Weather + emails + news in single audio. Output: briefing-tarde-YYYY-MM-DD.md. Skills: [] (gmail-api kept but documented). |
| Resumen día siguiente | a0f40735e7e2 | 21:00 UTC (23:00 Andorra) | Tomorrow's calendar events. [SILENT] if empty |
| Server Health | 6f4534000283 | every 5min (08-21 UTC) | RAM, disk, CPU, swap, Docker, PM2 alerts via curl |
| Limpiar audios | 1d7c97544636 | 06:00 UTC | Delete old audio files |
| Send morning briefing to Kindle | cbfff4cb9282 | 06:45 UTC (08:45 Andorra) | Reads briefing-manana-*, sends to Kindle |

Removed: `noticias-ia-diarias` (0b708f73defb) — disabled, replaced by Kindle reading briefing directly.

## Consolidated briefing rules

These rules apply to every news briefing and replace the former standalone weather and evening-briefing notes.

### Shared pipeline

1. Collect weather and RSS news with `terminal`; use `/home/ubuntu/scripts/fetch-news.py` and do not substitute `web_search`.
2. Apply deduplication before selection. The morning briefing uses a 24-hour window. The evening briefing uses a 12-hour window, reads eight rows per feed, and excludes every topic already covered in that day's morning briefing.
3. Select at most seven valid, distinct AI/technology stories. If feeds contain no valid non-duplicate stories, state that explicitly rather than inventing items.
4. Compose plain Spanish text with accents and ñ; write the complete markdown artifact with `write_file` before calling `text_to_speech`.
5. Generate audio with an explicit `output_path` under `~/.hermes/audio_cache/`; keep TTS input below 4,000 characters when using Edge TTS.
6. Verify the text artifact, audio existence and non-zero size, item count, and final `MEDIA:` delivery path.

### Weather formatting for speech

Use separate `wttr.in` requests for condition, current temperature, humidity, and wind. Prefer the JSON endpoint (`format=j1`) for the daily maximum temperature. Convert symbols to spoken Spanish: "grados", "por ciento", and "kilómetros por hora"; spell out wind direction instead of retaining arrows or other symbols.

### Evening briefing parameters

The evening job is independent from the morning job: use `briefing-tarde-YYYY-MM-DD.md`, a 12-hour news window, eight rows per feed, and no more than seven stories. Read `briefing-manana-YYYY-MM-DD.md` for the same date before collecting or selecting stories, and reject repeated topics even when the headline uses a different angle.

## Voice Configuration