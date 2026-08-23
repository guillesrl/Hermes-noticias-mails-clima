# Hermes - Noticias, Mails y Clima

Backup de la configuración de cron y de una skill del agente [Hermes](https://github.com/NousResearch/hermes-agent) que Guille usa para generar un briefing matutino en audio (clima + emails pendientes + noticias de IA/tech), entre otros jobs programados.

## Contenido

- `cron/jobs.json` — configuración de los cron jobs de Hermes (`~/.hermes/cron/jobs.json`).
- `skills/devops/cron-briefing-weather-spanish-tts/` — skill que documenta cómo formatear el clima de wttr.in para que sea pronunciable en TTS en español.

## ¿Se puede ejecutar esto con cualquier agente?

No. Aunque `jobs.json` es JSON plano y los prompts son texto, este cron depende del runtime específico de **Hermes**, no es portable a cualquier agente sin adaptación:

- El scheduler que lee `jobs.json` y dispara cada job es el plugin `cron_providers/chronos` de `hermes-agent`.
- Los jobs con `"no_agent": true` ejecutan un script de shell/Python directo (sin LLM de por medio).
- Los jobs con `"no_agent": false` corren dentro del agente Hermes y dependen de herramientas con nombre fijo que solo existen en ese runtime: `text_to_speech`, `write_file`, la skill `google-workspace` (para Gmail/Calendar).
- La convención `MEDIA:/ruta/al/archivo.ogg` como última línea de la respuesta solo la interpreta la capa de entrega de Hermes para adjuntar audio en Telegram.
- La entrega final depende de los campos `origin`/`deliver` (chat de Telegram configurado) que gestiona Hermes, no el agente en sí.

Otro agente puede leer y entender el prompt de cada job como texto, pero no puede ejecutarlo tal cual sin reimplementar ese runtime (scheduler, tools con esos nombres exactos, convención `MEDIA:`, entrega por Telegram).

## Jobs incluidos

| Job | Qué hace | Agente involucrado |
|---|---|---|
| Server Health Check | Chequeo de salud del servidor cada 5 min (8-21h) | No (script directo) |
| Limpiar audios antiguos | Borra audios viejos del cache diario | No (script directo) |
| Resumen día siguiente | Resume la agenda de Google Calendar del día siguiente | Sí (skill `google-workspace`) |
| Briefing matutino | Clima + emails + noticias IA/tech, compuesto en audio TTS | Sí (`text_to_speech`, `write_file`, Gmail) |
| Send morning briefing to Kindle | Envía el briefing de la mañana al Kindle (martes) | No (script directo) |

## Fuente de verdad

La fuente de verdad sigue siendo el servidor de Guille (`~/.hermes/cron/jobs.json` y `~/.hermes/skills/`). Este repo es un respaldo manual, no se sincroniza automáticamente.
