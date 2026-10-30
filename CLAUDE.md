# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Thermal-comfort dashboard for an intern project inside the SECIHTI housing-decarbonization project (Puebla). Each dwelling (mock: PUE-01, PUE-02) is modeled as a **single thermal zone** whose temperature/humidity come from a central point of the house; scenarios vary envelope/operation measures. Question answered: which changes improve ASHRAE 55 comfort most, and at what energy/carbon cost, focusing on extremes. Docs, code identifiers and UI text are in Spanish. `README.md` is the user-facing guide.

Layout:
- `backend/generar_csv_confort.py` — the whole pipeline (pandas/numpy, `backend/requirements.txt`). Source of truth.
- `backend/mock/crear_mock.py` — fake inputs into `backend/mock/entradas/<vivienda>/` (gitignored).
- `datos/` — output CSVs. The dashboard reads **every** `.csv` here (any number of dwellings); `_log.md` files are ignored by it.
- `dashboard/index.html` — static page (Chart.js + PapaParse from cdnjs). `dashboard/servidor.py` (stdlib only) serves it plus `/api/csv` (list of CSVs in `datos/`) and `/datos/<file>.csv`. Without the server the page only works via its multi-file picker.
- `docs/metodologia_calculo.md` — every formula (ASHRAE 55 adaptive), step by step, mapped to script functions, with assumptions/limitations. Update it whenever a calculation changes.
- `docs/contexto_esquema_confort.md` — decision history (v1–v8.1), column list, calculation logic, open questions. Read before changing the schema.
- `.claude/skills/esquema-confort-termico/` — project-local skill. Its `scripts/` and context copy are synced from `backend/` and `docs/` by `python herramientas/empaquetar_skill.py`, which also builds `dist/esquema-confort-termico.skill` (gitignored). Run it after editing either source.

## Commands

```
pip install -r backend/requirements.txt
python backend/mock/crear_mock.py --vivienda PUE-01 [--ajuste-clima 0]
python backend/generar_csv_confort.py --escenarios backend/mock/entradas/PUE-01/escenarios.csv --config backend/mock/entradas/PUE-01/config.csv [--epw clima.epw] --salida datos/confort_PUE-01_mock.csv
python dashboard/servidor.py [--puerto 8000] [--datos datos] [--sin-navegador]
python herramientas/empaquetar_skill.py
pip install -r backend/requirements-dev.txt && python backend/pruebas/validar_ashrae55.py   # checks formulas vs pythermalcomfort
```
The ASHRAE 55 formulas are hand-written in the script on purpose; `pythermalcomfort` is a dev-only reference, never a runtime dependency. No linter exists. `archivo_horario` in `escenarios.csv` is resolved relative to that file.

## Architecture / invariants

Flow: hourly series for the whole dwelling (`T_operativa_C` at the central point, or `T_aire_C` + `T_radiante_media_C`) → adaptive ASHRAE 55 limits from prevailing mean outdoor temp (`clima_diario`, EPW or `T_exterior_C`) → hourly limits in `evaluar` → `agregar` per period (T_op max/min, limit at that hour, max exceedance/deficit, HR max/min) → deltas vs. the single `es_base` scenario.

Output is one long-format CSV per run, one row = scenario × periodo (15 per scenario), 34 columns fixed by `COLUMNAS`. `nivel=clave` rows (`anual`, `mes_caliente`, `mes_frio`) and `nivel=mes` rows overlap and must never be summed. Changing the schema means updating `COLUMNAS`, the skill's column dictionary, the context doc, and the dashboard (`REQUERIDAS` and the fields it reads). The dashboard merges all CSVs keyed by `vivienda_id × escenario_id × periodo` (later file alphabetically wins) and colors scenarios by their order in the data, never by filter position.

Rules that must be preserved:
- Comfort is ALWAYS measured with ASHRAE 55 adaptive; it is not configurable. PMV/PPD may only be a complementary addition.
- The audience is someone from architecture comparing comfort tradeoffs: keep columns few, clearly named, with deltas vs. base precomputed.
- **Never invent data.** Missing input → empty cell + entry in the log (`log("faltantes"|"supuestos"|"avisos", ...)`). No "typical" U-values, emission factors, COPs; ranges are not turned into numbers.
- Only extremes matter: no hour counts, % comfort, degree-hours, occupancy or averages. Humidity is kept as max/min only. Limits (`limite_sup_C`/`limite_inf_C`) are reported at the hour of the T_op max/min; T_op extremes and exceedance/deficit use all hours.
- Single zone: no `espacio_id`; reducing a multi-room model to one series happens before the script.
- Thermal energy is converted to electric only if `energia_tipo=termica` and COP/efficiency are given; carbon is operational only (energy × given factor), so only `delta_energia_pct` exists.
- Adaptive method is valid only for prevailing mean 10–33.5 °C; hours outside get no limits (T_op still counts for max/min) and are reported in the log.
- Each scenario row carries the full state of the house (all 9 parameters).
