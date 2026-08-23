---
name: cron-briefing-weather-spanish-tts
description: "Optimiza cron de briefing para clima TTS en español."
version: 1.0.0
author: Hermes Agent
category: devops
---

# Optimización de Clima en TTS para Cron de Briefing

## Problema
Los cron jobs de briefing matutino obtenían el clima de wttr.in con formato que incluía símbolos no pronunciables por TTS (°C, %, →, etc.) y mezclas de idiomas, resultando en audio poco claro.

## Solución
Formatear cada componente del clima por separado para que sea legible y comprensible en síntesis de voz (TTS) en español.

## Implementación

### Paso 1: Extraer y formatear componentes del clima
```bash
# Condición meteorológica (texto en español)
CONDICION=$(curl -s "https://wttr.in/Andorra?format=%C&lang=es")

# Temperatura actual: número + "grados"
TEMP_ACTUAL_NUM=$(curl -s "https://wttr.in/Andorra?format=%t&lang=es" | sed 's/[^0-9-]//g')
TEMP_ACTUAL="${TEMP_ACTUAL_NUM} grados"

# Temperatura máxima: número + "grados"
TEMP_MAX_NUM=$(curl -s "https://wttr.in/Andorra" 2>/dev/null | sed "s/\\x1b\\\\[[0-9;]*m//g" | grep -oP "\\d+(?= °C)" | sort -n | tail -1)
TEMP_MAX="${TEMP_MAX_NUM} grados"

# Humedad: número + "por ciento" (evitando el símbolo %)
HUMEDAD_NUM=$(curl -s "https://wttr.in/Andorra?format=%h&lang=es" | sed 's/[^0-9]//g')
HUMEDAD="${HUMEDAD_NUM} por ciento"

# Viento: convertir símbolo de dirección a frase y velocidad a formato hablado
VIENTO_RAW=$(curl -s "https://wttr.in/Andorra?format=%w&lang=es")  # Ej: "↗13km/h"
VIENTO_DIR_SYMBOL=$(echo "$VIENTO_RAW" | sed 's/[^↖↗↘↙→←↑↓]//g')
VIENTO_SPEED=$(echo "$VIENTO_RAW" | sed 's/[^0-9]//g')
case "$VIENTO_DIR_SYMBOL" in
  "↖") VIENTO_DIR="noroeste" ;;
  "↗") VIENTO_DIR="noreste" ;;
  "↘") VIENTO_DIR="sureste" ;;
  "↙") VIENTO_DIR="suroeste" ;;
  "→") VIENTO_DIR="este" ;;
  "←") VIENTO_DIR="oeste" ;;
  "↑") VIENTO_DIR="norte" ;;
  "↓") VIENTO_DIR="sur" ;;
  *) VIENTO_DIR="dirección variable" ;;
esac
VIENTO="del $VIENTO_DIR a $VIENTO_SPEED kilómetros por hora"
```

### Paso 2: Uso en el prompt del cron job
Integrar las variables formateadas en el texto del briefing:
```prompt
Buenos días Guille, aquí va tu briefing.

En Andorra hoy: [CONDICION], [TEMP_ACTUAL], máxima [TEMP_MAX], humedad [HUMEDAD], viento [VIENTO].

[ resto del briefing... ]
```

### Paso 3: Ejemplo de prompt actualizado (referencia)
Este cron genera un briefing matutino con clima, emails y noticias IA en un solo audio. EJECUTA CADA PASO EN ORDEN ANTES DE PASAR AL SIGUIENTE.

PASO 1 - RECOPILAR (clima + dedup + noticias) EN UN SOLO comando terminal, no lo dividas en varios:
# [Insertar el bloque de formateo de clima de arriba]
echo "===MAX==="
echo "$TEMP_MAX_NUM"
echo "===DEDUP==="
grep -oP "(?:Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez). \\K[^\\n]+" $(ls -t /home/ubuntu/hermes-notes/news/briefing-manana-*.md 2>/dev/null | head -1) 2>/dev/null | head -9; python3 /home/ubuntu/scripts/fetch-news.py 4

[ resto del prompt para emails, noticias, etc. ]

PASO 4 - COMPONER TEXTO: Utilizar las variables formateadas [CONDICION], [TEMP_ACTUAL], etc. en el texto del briefing.

## Verificación
Después de aplicar, el briefing debe contener frases como:
- "En Andorra hoy: Soleado, 21 grados, máxima 21 grados, humedad 45 por ciento, viento del noreste a 13 kilómetros por hora."
En lugar de:
- "En Andorra hoy: ☀️  +21°C 45% ↗13km/h"

## Pitfalls a Evitar
1. No usar el formato compacto de wttr.in (%c+%t+%h+%w) que incluye símbolos no pronunciables.
2. Olvidar el parámetro `&lang=es` para asegurar texto en español.
3. No procesar correctamente los símbolos de dirección del viento (↗, →, etc.).
4. Dejar el símbolo `%` en humedad; siempre convertir a "por ciento".
5. No agregar unidades explícitas como "grados" o "kilómetros por hora".

## Beneficios
- Audio del briefing completamente comprensible y natural en español.
- Consistencia lingüística a lo largo del briefing.
- Eliminación de errores de pronunciación en la salida de TTS.
- Reutilizable en otros cron jobs que requieran información del clima para TTS.