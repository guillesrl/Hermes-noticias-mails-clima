---
name: noticias-ia
description: "Reenvío de la sección de noticias del briefing de Hermes a Telegram y Kindle (repo guillesrl/Hermes-noticias-mails-clima, /opt/proyectos/noticias-ia). Usar al tocar scripts/noticias-ia-diarias.py o scripts/send-briefing-to-kindle.py, o al diagnosticar por qué no llegó el envío."
trigger: /noticias-ia
---

# /noticias-ia

Playbook de `/opt/proyectos/noticias-ia` (repo `guillesrl/Hermes-noticias-mails-clima`). El proyecto son dos scripts Python sin cron activo — se ejecutan a mano — que reenvían la sección de noticias de IA del briefing matutino de Hermes a Telegram y a Kindle. Ver `README.md` para el detalle de cada script.

## Ambos scripts dependen por completo de un archivo que genera OTRO sistema

`noticias-ia-diarias.py` y `send-briefing-to-kindle.py` no generan ni traducen ninguna noticia — leen `/home/ubuntu/hermes-notes/news/briefing-manana-YYYY-MM-DD.md`, que escribe el cron "Briefing matutino" de Hermes (`~/.hermes/cron/jobs.json`), un sistema con su propio prompt de LLM y su propio pipeline de noticias, totalmente ajeno a este repo. La extracción es un regex literal que busca `"Y en noticias de IA y tecnologia:"` ... `"Eso es todo por hoy."`. **Si Hermes cambia el prompt de ese cron y esas frases exactas dejan de aparecer, los dos scripts de este repo dejan de enviar cualquier cosa, en silencio, sin ningún error de este lado.** Al depurar un envío que no llegó, lo primero es abrir el `briefing-manana-*.md` de ese día y confirmar que esas dos frases literales siguen ahí.

## Correr `noticias-ia-diarias.py` a mano duplica el mensaje que Hermes ya mandó

El briefing de Hermes ya le llega al usuario como audio por Telegram esa misma mañana. `noticias-ia-diarias.py` reenvía la misma sección de noticias, como texto, al mismo chat (`8295693189`). Ejecutarlo "solo para probar" produce un mensaje de Telegram duplicado real, no es un efecto de prueba inocuo.

## Tres credenciales de Telegram distintas conviven en este repo chico

- `noticias-ia-diarias.py`: token hardcodeado como fallback en el propio archivo (`os.environ.get("TELEGRAM_BOT_TOKEN", "8312...")`), mismo chat que Hermes.
- `send-briefing-to-kindle.py`: cuando no hay briefing que enviar, avisa por Telegram leyendo un bot **completamente distinto** desde `/opt/telegram-bot/.env` (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_USER_ID`) — el bot del proyecto `telegram-bot`, no el de arriba.
No asumir que "cambiar el token de Telegram de este proyecto" es un solo cambio en un solo lugar.

## `send-briefing-to-kindle.py` solo mira el briefing de HOY, a propósito

`get_spanish_content()` solo acepta `briefing-manana-{hoy}.md`; si no existe todavía (Hermes tarda, por ejemplo) nunca cae al de ayer. Es deliberado — antes sí caía a traducir desde otra fuente y eso producía resúmenes cortados y texto crudo de RSS sin sentido para el lector. Si se toca esta función, no reintroducir un fallback que traiga contenido de un día distinto sin dar antes ese contexto al usuario.

## Remoto de git con token en texto plano

`git remote -v` en este repo expone un Personal Access Token de GitHub directo en la URL (`https://guillesrl:ghp_...@github.com/...`), guardado en `.git/config`. Funciona, pero es mala higiene (queda en logs, en cualquier `git remote -v`, y no es revocable sin romper el remoto). Si tocas la config de git de este repo, considera migrar a `gh auth login` o un credential helper y avisa al usuario antes de rotar el token — puede romper el push si algo más lo usa.

## `send-briefing-to-kindle.py` necesita el venv, no el Python del sistema

Requiere `google-auth`/`google-api-python-client`. Si se ejecuta a mano para depurar, usar `venv/bin/python3`, no `/usr/bin/python3`, o va a fallar por `ImportError` en vez de mostrar el bug real que se está buscando.

## El repo tiene cambios sin commitear que no aparecen en `git log`

Antes de tocar cualquiera de los dos scripts, correr `git status`/`git diff` — hay trabajo en progreso sin commitear en este repo que no se ve en el historial. No asumir que la última versión commiteada es la que corre hoy.
