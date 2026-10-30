---
name: esquema-confort-termico
description: Contexto y procedimiento para armar el CSV único de confort térmico (ASHRAE 55), energía y carbono por escenario de la vivienda PUE-01 para el dashboard, solo con datos de los archivos dados.
---

# Esquema de datos de confort térmico — CSV único para el dashboard

Usa esta skill cuando se trabaje el esquema de datos del dashboard de confort térmico (proyecto de becario, vivienda mock **PUE-01**, proyecto SECIHTI de descarbonización en Puebla), o cuando se pida generar o corregir el CSV a partir de archivos (Revit/IFC, gbXML, índice de viviendas, salidas del simulador, EPW).

## 1. Qué se busca

- **Estándar fijo:** el confort siempre se mide con **ASHRAE 55** (adaptativo); no hay otro criterio ni opción de configuración.
- **Usuario final:** una persona de arquitectura que compara los tradeoffs de confort (y energía/carbono) de cambios a la vivienda. El CSV debe ser claro para ella: nombres legibles, un escenario = un conjunto de medidas, deltas contra el base ya calculados.
- Una sola vivienda (PUE-01) con superficie fija. Lo que cambia entre corridas son **medidas** sobre la envolvente u operación (valor U de muros/techo/ventanas, SHGC, absortancia, sombreado, ventilación, velocidad del aire).
- Cada escenario se simula y se compara contra el caso base en **confort térmico (ASHRAE 55)**, **energía** y **carbono**.
- Todo vive en **un solo CSV** que el dashboard lee sin hacer uniones entre tablas.
- Los casos límite importan más que el promedio: por eso se reportan máximos y mínimos del **mes caliente**, del **mes frío** y del **año**. No hay filas diarias.

## 2. Regla principal: no inventar

Cada valor del CSV debe poder rastrearse a una de estas fuentes:
1. Un archivo dado (IFC/Revit, gbXML, índice, salida del simulador, EPW).
2. Algo que el usuario dijo explícitamente en la conversación (por ejemplo, factor de emisión o COP).
3. Constantes de ASHRAE 55 (fórmula adaptativa, bandas, límites de aplicabilidad), que son del estándar y no datos de la vivienda.

**No se permite:**
- Usar valores típicos de memoria (U de un block, factor de emisión de la red, COP de un equipo, horarios de ocupación).
- Convertir un rango estimado ("U ≈ 2–3") en un número.
- Rellenar huecos interpolando o copiando de otra vivienda.

**Si falta un dato:** la celda queda **vacía** (nunca "ND" en columnas numéricas) y se anota en el log `<salida>_log.md`, en *Datos faltantes*. Las decisiones de método (por ejemplo, 7 días para la media exterior si no se especificó) van en *Supuestos de método*. Antes de entregar, se le dice al usuario qué quedó vacío y qué dato hace falta para llenarlo.

## 3. Estructura del CSV

**Una fila = escenario × periodo.** La vivienda se modela como **una sola zona, sin habitaciones** (v3 del CSV): no hay filas por cuarto ni fila TOTAL.

- Periodos (columna `nivel`):
  - `clave`: `anual`, `mes_caliente`, `mes_frio`
  - `mes`: `ene` … `dic`
  - El mes caliente y el mes frío salen **del clima**: el mes con la media exterior más alta y la más baja. `mes` dice cuál fue. El dashboard **no debe sumar** filas `clave` con filas `mes`.
- **No se cuentan horas.** Lo que importa son los extremos: T_op máxima y mínima de cada periodo, el límite ASHRAE 55 vigente en esas horas y cuánto se pasa la T_op de él. No hay horas de confort, % de confort, grados-hora, ocupación, promedios ni desglose de energía. La humedad sí se reporta, también como máximo y mínimo.
- Cada fila trae el **estado completo** de la casa en ese escenario (todos los parámetros, no solo lo que cambió) y los supuestos, para que se pueda leer sola.

Formato: UTF-8, separador coma, punto decimal, encabezados en snake_case sin acentos y con la unidad en el nombre, 2 decimales. 34 columnas.

### Diccionario de columnas

| Columna | Unidad | Regla / fuente |
|---|---|---|
| vivienda_id | — | config (PUE-01) |
| escenario_id, escenario_nombre | — | tabla de escenarios (ESC-00 = base) |
| es_base | Si/No | exactamente un escenario Si |
| U_muro_ext, U_techo, U_ventana | W/m²K | valor U del elemento completo, de archivo o del usuario |
| SHGC_ventana | 0–1 | ídem |
| absortancia_muro, absortancia_techo | 0–1 | ídem |
| sombreado_m | m | profundidad de volado/alero |
| ventilacion_ach | 1/h | renovaciones de aire |
| vel_aire_m_s | m/s | velocidad del aire interior supuesta en el escenario |
| nivel | clave/mes | — |
| periodo | — | anual, mes_caliente, mes_frio, ene…dic |
| mes | 1–12 | vacío en anual |
| T_ext_max_C, T_ext_min_C | °C | EPW o T_exterior del simulador, en el periodo |
| T_op_max_C, T_op_min_C | °C | extremos de la T_operativa horaria de la vivienda en el periodo (todas las horas) |
| mes_T_op_max, mes_T_op_min | 1–12 | mes en que ocurrió cada extremo |
| HR_max_pct, HR_min_pct | % | extremos de la humedad relativa horaria en el punto central de la vivienda (de `HR_pct` del simulador) |
| limite_sup_C | °C | límite superior ASHRAE 55 vigente en la hora del T_op máximo: 0.31·t_pma + 17.8 + banda (3.5 u 2.5), más el ajuste por velocidad del aire |
| limite_inf_C | °C | límite inferior ASHRAE 55 vigente en la hora del T_op mínimo |
| max_exceso_sobre_limite_C | °C | mayor valor de (T_op − límite superior) en el periodo; 0 si nunca lo supera |
| max_deficit_bajo_limite_C | °C | mayor valor de (límite inferior − T_op) en el periodo; 0 si nunca baja de él |
| energia_total_kWh | kWh | suma de enfriamiento + calefacción del simulador (cargas ideales); se convierte a eléctrica solo con COP/eficiencia dados |
| carbono_kgCO2e | kgCO₂e | energia_total × factor_emision (solo si el factor fue dado) |
| delta_T_op_max_C, delta_T_op_min_C | °C | contra el base, mismo periodo |
| delta_energia_pct | % | ídem; vacío si la base es 0. El delta de carbono sería igual (mismo factor), por eso no existe |
| aceptabilidad_pct | % | config (80 o 90) |

## 4. Lógica de cálculo (ASHRAE 55, método adaptativo)

Detalle completo, con ejemplo numérico y limitaciones: `metodologia_calculo.md` (en el repositorio: `docs/metodologia_calculo.md`). Las fórmulas están verificadas contra pythermalcomfort con `backend/pruebas/validar_ashrae55.py`.


- **Punto de medición:** la simulación entrega la temperatura operativa de **un punto central de la vivienda**, lejos de los muros, para idealizar la temperatura de toda la casa y reducir la varianza cerca de las paredes. Se prefiere la columna `T_operativa_C`; si el simulador solo da aire y radiante, se calcula así.
- **T_operativa** = A·T_aire + (1−A)·T_radiante, con A = 0.5 (v < 0.2 m/s), 0.6 (0.2–0.6) o 0.7 (0.6–1.0). Si el simulador solo da temperatura operativa, se pone el mismo valor en ambas columnas y se anota en el log.
- **T_confort** = 0.31·t_pma + 17.8. Banda de ±3.5 °C (80 %) o ±2.5 °C (90 %).
- **Aplicabilidad:** 10 ≤ t_pma ≤ 33.5 °C. En las horas fuera de ese rango no hay límites (ni exceso/déficit) y se avisa en el log; la T_op de esas horas sí cuenta para el máximo y el mínimo.
- **Velocidad del aire** (cuando T_op > 25 °C, solo el límite superior): +1.2 °C (0.6 m/s), +1.8 °C (0.9 m/s), +2.2 °C (1.2 m/s).
- **Año típico (EPW):** la media predominante de los primeros días de enero se calcula con los últimos días de diciembre.
- **Energía:** la del horario de la vivienda completa (una sola serie).

## 5. Procedimiento

1. **Inventario.** Lista los archivos dados y qué columna del esquema puede salir de cada uno:
   - `Indice_viviendas_Puebla_SECIHTI.xlsx`, hoja `IFC_espacios`: ya no aporta columnas al CSV (el área total no se reporta).
   - `gbXML_PUE-01_analisis.xlsx`: volúmenes y avisos de calidad. Los valores térmicos del gbXML son **por defecto de Revit** (Madrid, oficina, R-13…) y no se usan como parámetros de escenario.
   - Tabla de escenarios / medidas que dé el usuario: parámetros U, SHGC, etc.
   - Salidas del simulador (DesignBuilder/EnergyPlus): horario de la vivienda completa (una sola zona; si el modelo tiene varios cuartos, se reduce a una serie antes del script, p. ej. un nodo térmico o promedio ponderado por área).
   - EPW de Puebla: clima.
2. **Arma las entradas del script** en una carpeta de trabajo:
   - `escenarios.csv`: escenario_id, escenario_nombre, es_base, archivo_horario + los 9 parámetros (vacíos si no están en los archivos).
   - `config.csv` (clave,valor): vivienda_id, aceptabilidad_pct, factor_emision_kgCO2e_kWh, dias_media_exterior, energia_tipo (electrica/termica), COP_enfriamiento, eficiencia_calefaccion. Solo lo dado.
   - Un horario por escenario con columnas normalizadas: fecha_hora, T_operativa_C (o T_aire_C y T_radiante_media_C), HR_pct, vel_aire_m_s, T_exterior_C, energia_enfriamiento_kWh, energia_calefaccion_kWh. Para EnergyPlus: "Zone Air Relative Humidity" → HR_pct. Si el punto central da la operativa, → T_operativa_C. Si no: "Zone Mean Air Temperature" → T_aire_C, "Zone Mean Radiant Temperature" → T_radiante_media_C, "Site Outdoor Air Drybulb Temperature" → T_exterior_C, "Zone Ideal Loads … Cooling/Heating Energy [J]" ÷ 3.6e6 → kWh (energia_tipo = termica). Solo cambios de nombre y de unidad, nada más.
3. **Ejecuta** el script de la sección 7:
   `python3 generar_csv_confort.py --escenarios escenarios.csv --config config.csv [--epw clima.epw] --salida confort_PUE-01.csv`
   Dentro del repositorio del proyecto: `python backend/generar_csv_confort.py … --salida datos/confort_<vivienda>.csv`. Todo CSV que quede en `datos/` lo lee el dashboard automáticamente.
4. **Valida** antes de entregar:
   - Filas = escenarios con horario × 15.
   - Un solo `es_base = Si`, y sus deltas son 0.
   - Para cada escenario y periodo: T_op_min ≤ T_op_max; exceso y déficit ≥ 0; en mes_caliente y mes_frio, T_op_max/min coinciden con los de su mes.
   - El horario no tiene `fecha_hora` repetida (una sola serie por escenario).
   - `mes` lleno en mes_caliente/mes_frio.
   - Abre el log y revisa cada faltante: ¿de verdad no estaba en ningún archivo?
5. **Entrega** el CSV y el log, y di en 2–3 líneas qué quedó vacío y qué dato lo llenaría.

## 6. Contexto de PUE-01 (de los archivos)

- Casa Luis Bautista, San Bernardino Tlaxcalancingo (San Andrés Cholula), 2 niveles. Modelo Revit de Diana Aguilar (`PUE-01_Diana.ifc`).
- 13 espacios acondicionados, tratados como una sola zona: 185.4 m², 421.6 m³. Cochera y patio no están acondicionados.
- Norte real −20.5°. Medianeras E, S, O (adiabáticas). Muro expuesto ~96 m², ventanas exteriores 9.66 m², WWR global ≈ 0.10.
- Los valores de construcción "reales" del análisis del gbXML son **estimados a confirmar en campo** (rangos): no se usan como números sin confirmación del usuario.

## 7. Script de referencia

`scripts/generar_csv_confort.py` (necesita pandas y numpy; copia de `backend/generar_csv_confort.py` del repositorio, que es la fuente de verdad). Úsalo tal cual: no copies su código aquí. Tras cambiar el backend o el contexto, corre `python herramientas/empaquetar_skill.py` para sincronizar la skill y generar `dist/esquema-confort-termico.skill`. Se probó con datos sintéticos de dos escenarios, sin EPW y con la columna `T_exterior_C` del horario.

## 8. Mejora continua

Si un cambio al esquema se acuerda con el usuario: actualiza `COLUMNAS` y el diccionario, sube la versión (v2 → v3) en el docstring y registra el cambio en el MD de contexto del proyecto (`docs/contexto_esquema_confort.md`), en la sección de historial, y vuelve a empaquetar la skill.
