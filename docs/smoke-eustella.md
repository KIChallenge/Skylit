# eustella-Smoke-Test

- Datum: 05.11.2026
- Modell: `eustella-v1.5`
- Anfragen: 10 von maximal 14
- `max_tokens`: 4096
- Reasoning: aus, außer in Check 1 und im Standard-Aufruf von Check 6.
- Erzeugt mit `make smoke`. Jeder Wert ist eine Einzelmessung.

| Check | Ergebnis | Notizen |
|---|---|---|
| 1. Chat ohne Streaming | Bestanden | Chat: Latenz 1,02 s, erstes Token k. A., Tokens 296 ein, 55 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_1e37657fa4d7f742ae1ce0e4`. Ohne Streaming, Reasoning im Standard. |
| 2. Streaming mit `usage` | Bestanden | Stream: Latenz 2,15 s, erstes Token 1,27 s, Tokens 275 ein, 15 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_0c902e0db87e828a0c02d209`. |
| 3. Tool-Aufruf im Stream | Bestanden | Tool: Latenz 0,44 s, erstes Token 0,30 s, Tokens 542 ein, 28 aus, 0 gecacht, Ende `tool_calls`, X-Request-Id `req_8f5a26cc3ded5ee093e05dc7`. Tool `get_office_hours`, 3 Argument-Deltas, JSON gültig. |
| 4. Bild als Data-URL | Bestanden | Bild: Latenz 0,90 s, erstes Token 0,88 s, Tokens 2428 ein, 3 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_bdd11162b82ff25825967203`. PNG mit 174 KB als Data-URL. |
| 5. `json_schema` | Bestanden | JSON: Latenz 0,52 s, erstes Token 0,28 s, Tokens 282 ein, 24 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_34ce319c3ec3d6d71d218df5`. |
| 6. Reasoning aus und Standard | Bestanden | Reasoning aus: Latenz 1,46 s, erstes Token 0,45 s, Tokens 279 ein, 98 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_fd6b13e01af4ca9a1bd85295`. Reasoning Standard: Latenz 1,56 s, erstes Token 0,61 s, Tokens 303 ein, 111 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_83d68555857bd4b845c4de91`. Differenz 0,16 s. |
| 7. Prompt-Cache | Bestanden | Langer Prompt 1: Latenz 3,29 s, erstes Token 3,29 s, Tokens 27371 ein, 2 aus, 0 gecacht, Ende `stop`, X-Request-Id `req_f61ab420690cf0c9587d2c5b`. Langer Prompt 2: Latenz 0,40 s, erstes Token 0,39 s, Tokens 27371 ein, 2 aus, 27264 gecacht, Ende `stop`, X-Request-Id `req_d0d2ce15bece504222b56e66`. |
| 8. `GET /v1/models` | Bestanden | Modelle: Latenz 0,05 s, erstes Token k. A., X-Request-Id `req_5e4c244fb1da46bdf71251c8`. Felder: {"shutdown_date": null, "display_name": "eustella-v1.5", "max_output_tokens": 65536, "type": "model"}. |

## Folgen für den Plan

- `LLM_ENABLE_THINKING=false` bleibt Standard für Chat-Turns. Das erste Token kommt 0,16 s früher (eine Messung).
- Alle Checks sind bestanden. Der Plan bleibt unverändert.
