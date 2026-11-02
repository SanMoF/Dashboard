# Diccionario de variables

Todas las variables del esquema (v9): las que **entran** al script y las 30 columnas que **salen** en el CSV del dashboard. Para cada una se indica qué es, su unidad, **de dónde viene** y **qué valores admite**.

**Origen:**

| Etiqueta | Significa |
|---|---|
| **Usuario** | la escribe a mano quien arma las entradas (`escenarios.csv`, `config.csv`) |
| **Simulador** | sale del simulador preciso, alimentado con los parámetros del escenario (`resultados_<escenario>.csv`) |
| **Clima** | sale del archivo de clima (`--epw` o `clima.csv`) |
| **Calculada** | la calcula `backend/generar_csv_confort.py`; se da la fórmula |
| **Copia** | el script la pasa tal cual de una entrada a la salida |

**Valores admitidos:** es el rango con sentido físico o el que exige ASHRAE 55. El script **no** rechaza valores fuera de rango, salvo donde se indica ("Lo revisa el script"). Lo que falta queda **vacío** y se anota en `<salida>_log.md`; nunca se rellena con valores típicos.

Las fórmulas completas, con ejemplo numérico, están en [`metodologia_calculo.md`](metodologia_calculo.md).

---

## 1. Entradas

### 1.1 `escenarios.csv` — una fila por escenario (Usuario)

| Variable | Qué es | Unidad | Valores admitidos |
|---|---|---|---|
| `escenario_id` | identificador corto del escenario (p. ej. `ESC-00`) | — | texto, único por vivienda |
| `escenario_nombre` | descripción legible de las medidas | — | texto |
| `es_base` | marca el caso base contra el que se comparan los demás | — | `Si` / `No` (también acepta `sí`, `1`). **Exactamente uno** en `Si`; si no, deltas vacíos y aviso en el log. *Lo revisa el script.* |
| `archivo_resultados` | ruta al `resultados_<escenario>.csv` del simulador, relativa a `escenarios.csv` | — | ruta existente; si no existe, el escenario se omite y se anota en el log. *Lo revisa el script.* |
| `U_muro_ext` | transmitancia térmica del muro exterior completo (todas sus capas y películas de aire): calor que pasa por m² y por °C de diferencia | W/m²K | > 0. Menor = más aislado |
| `U_techo` | transmitancia térmica del techo o losa completa | W/m²K | > 0. Menor = más aislado |
| `U_ventana` | transmitancia térmica de la ventana completa (vidrio + marco) | W/m²K | > 0. Menor = más aislante (p. ej. doble vidrio) |
| `SHGC_ventana` | coeficiente de ganancia solar: fracción de la radiación solar que incide en la ventana y entra como calor | adimensional | **0 a 1**. Menor = deja pasar menos calor solar |
| `absortancia_muro` | fracción de la radiación solar que absorbe la cara exterior del muro (el resto se refleja) | adimensional | **0 a 1**. 0 = refleja todo (blanco ideal), 1 = absorbe todo (negro ideal) |
| `absortancia_techo` | ídem, para la cara exterior del techo | adimensional | **0 a 1**. Un acabado claro la baja |
| `sombreado_m` | profundidad del volado o alero sobre las ventanas | m | ≥ 0. 0 = sin volado |
| `ventilacion_ach` | renovaciones de aire por hora: cuántas veces por hora se cambia todo el volumen de aire de la vivienda | 1/h | ≥ 0 |
| `vel_aire_m_s` | velocidad del aire interior en el escenario (p. ej. con ventilador) | m/s | ≥ 0. Para ASHRAE 55 solo cuentan los escalones 0.6, 0.9 y 1.2 m/s; por encima de 1.2 se trata igual que 1.2 |

Los 9 parámetros (de `U_muro_ext` a `vel_aire_m_s`) **alimentan al simulador**. En el script **solo `vel_aire_m_s` entra en una fórmula** (ajuste del límite superior, sección 2.4). Los demás se copian a la salida para describir el escenario: su efecto ya viene en la T_operativa del simulador.

### 1.2 `config.csv` — pares `clave,valor` (Usuario)

| Variable | Qué es | Unidad | Valores admitidos |
|---|---|---|---|
| `vivienda_id` | identificador de la vivienda (p. ej. `PUE-01`) | — | texto. Si falta, se anota en el log |
| `aceptabilidad_pct` | nivel de aceptabilidad de ASHRAE 55: qué porcentaje de ocupantes se espera que esté conforme | % | `80` o `90`. Cualquier otro valor se trata como 80. Si falta, no hay límites. *Lo revisa el script.* |
| `factor_emision_kgCO2e_kWh` | emisiones de la red por kWh consumido (lo da el usuario; nunca un valor típico) | kgCO₂e/kWh | ≥ 0. Si falta, el carbono queda vacío |
| `energia_tipo` | tipo de energía que entrega el simulador | — | `electrica` (se usa tal cual) o `termica` (cargas; se convierte con COP/eficiencia). Si falta, se usa tal cual y se avisa |
| `COP_enfriamiento` | kWh de frío por kWh eléctrico del equipo de enfriamiento | adimensional | > 0. Solo se usa si `energia_tipo = termica` |
| `eficiencia_calefaccion` | kWh de calor por kWh consumido del equipo de calefacción | adimensional | > 0 (≤ 1 en equipos de combustión o resistencia; > 1 en bomba de calor). Solo con `energia_tipo = termica` |

### 1.3 `resultados_<escenario>.csv` — una fila por mes y, opcional, una anual (Simulador)

| Variable | Qué es | Unidad | Valores admitidos |
|---|---|---|---|
| `mes` | periodo de la fila | — | `1`–`12`, `ene`–`dic` o `anual`. Otros valores se ignoran con aviso; un mes repetido usa la primera fila. *Lo revisa el script.* |
| `T_operativa_C` | temperatura operativa del **punto central de la vivienda**: combina la temperatura del aire y la de las superficies (la que "siente" la persona). Un valor por periodo, tal como lo calcula el simulador | °C | cualquier real. El script no la modifica |
| `HR_pct` | humedad relativa del aire en el punto central | % | 0 a 100 |
| `energia_enfriamiento_kWh` | energía de enfriamiento del periodo (cargas ideales o consumo, según `energia_tipo`) | kWh | ≥ 0 |
| `energia_calefaccion_kWh` | energía de calefacción del periodo | kWh | ≥ 0 |

### 1.4 Clima — `clima.csv` por mes, o `--epw` horario (Clima)

| Variable | Qué es | Unidad | Valores admitidos |
|---|---|---|---|
| `mes` | periodo (igual que en resultados) | — | `1`–`12`, `ene`–`dic` o `anual` |
| `T_ext_max_C` | temperatura exterior más alta del periodo | °C | real, ≥ `T_ext_media_C` |
| `T_ext_min_C` | temperatura exterior más baja del periodo | °C | real, ≤ `T_ext_media_C` |
| `T_ext_media_C` | temperatura exterior media del periodo | °C | real. **Para que haya límites ASHRAE: 10 a 33.5** |

Con EPW, el script obtiene las tres por mes desde la temperatura de bulbo seco horaria: máximo, mínimo y promedio de las horas del mes.

---

## 2. Salida: las 30 columnas del CSV

Una fila = escenario × periodo (15 por escenario).

### 2.1 Identificación y escenario (Copia)

| Columna | Qué es | Unidad | Origen | Valores |
|---|---|---|---|---|
| `vivienda_id` | vivienda | — | Copia de `config.csv` | texto |
| `escenario_id`, `escenario_nombre` | escenario | — | Copia de `escenarios.csv` | texto |
| `es_base` | si es el caso base | — | Copia de `escenarios.csv` | `Si` / `No` |
| `U_muro_ext`, `U_techo`, `U_ventana` | transmitancias (ver 1.1) | W/m²K | Copia de `escenarios.csv` | > 0 |
| `SHGC_ventana` | ganancia solar de la ventana | — | Copia | 0 a 1 |
| `absortancia_muro`, `absortancia_techo` | absortancia solar exterior | — | Copia | 0 a 1 |
| `sombreado_m` | volado | m | Copia | ≥ 0 |
| `ventilacion_ach` | renovaciones de aire | 1/h | Copia | ≥ 0 |
| `vel_aire_m_s` | velocidad del aire interior | m/s | Copia | ≥ 0 |
| `aceptabilidad_pct` | nivel de aceptabilidad usado | % | Copia de `config.csv` | 80 o 90 |

### 2.2 Periodo (Calculada)

| Columna | Qué es | Origen | Valores |
|---|---|---|---|
| `nivel` | tipo de fila | Calculada | `clave` (anual, mes caliente, mes frío) o `mes` (ene…dic). Las filas `clave` repiten datos de las `mes`: **nunca se suman** |
| `periodo` | periodo de la fila | Calculada | `anual`, `mes_caliente`, `mes_frio`, `ene` … `dic` |
| `mes` | número del mes | Calculada | 1–12; vacío en `anual` |

**Mes caliente / mes frío:** el mes con la `T_ext_media_C` más alta / más baja. La fila es una copia de la de ese mes, y `mes` dice cuál es.

### 2.3 Clima, temperatura operativa y humedad

| Columna | Qué es | Unidad | Origen | Valores |
|---|---|---|---|---|
| `T_ext_max_C` | T exterior máxima del periodo | °C | Clima | real |
| `T_ext_min_C` | T exterior mínima del periodo | °C | Clima | real |
| `T_ext_media_C` | T exterior media del periodo. **En un mes es la temperatura media exterior predominante (t_pma) de ASHRAE 55** | °C | Clima. En `anual`, si `clima.csv` no la trae, se **calcula**: media de los 12 meses ponderada por sus días (31, 28, 31…) | real; 10–33.5 para tener límites |
| `T_operativa_C` | temperatura operativa del punto central | °C | **Simulador** (copia). Vacía en `anual` si el simulador no da fila anual: los meses no se promedian | real |
| `HR_pct` | humedad relativa del punto central | % | **Simulador** (copia) | 0 a 100 |

### 2.4 Límites de confort ASHRAE 55 adaptativo (Calculada)

Con *t_pma* = `T_ext_media_C` del mes, Δ = 3.5 °C (80 %) o 2.5 °C (90 %), y Δ_V el ajuste por velocidad del aire:

$$
t_{cmf} = 0.31\,t_{pma} + 17.8
$$

| Columna | Qué es | Unidad | Fórmula | Valores |
|---|---|---|---|---|
| `limite_inf_C` | temperatura operativa más baja aceptable en el mes | °C | $t_{cmf} - \Delta$ | 17.4 a 25.7 (con t_pma de 10 a 33.5). Vacío si t_pma sale de 10–33.5, si falta `aceptabilidad_pct` y siempre en `anual` |
| `limite_sup_C` | temperatura operativa más alta aceptable en el mes | °C | $t_{cmf} + \Delta + \Delta_V$ | 23.4 a 33.9. Mismos casos vacíos |

Δ_V depende de `vel_aire_m_s` y **solo se suma si `T_operativa_C` > 25 °C**:

| `vel_aire_m_s` | Δ_V |
|---|---|
| < 0.6 o vacío | 0 |
| 0.6 a < 0.9 | +1.2 °C |
| 0.9 a < 1.2 | +1.8 °C |
| ≥ 1.2 | +2.2 °C |

### 2.5 Exceso y déficit (Calculada)

| Columna | Qué es | Unidad | Fórmula | Valores |
|---|---|---|---|---|
| `exceso_sobre_limite_C` | cuántos grados por **encima** del rango aceptable está la vivienda (calor) | °C | mes: $\max(0,\ T_{op} - \text{límite sup})$. Año: el mayor de los 12 meses (peor mes) | ≥ 0; 0 = dentro del rango. Vacío si falta un dato; en `anual`, vacío si falta la T_op de algún mes |
| `deficit_bajo_limite_C` | cuántos grados por **debajo** del rango aceptable está la vivienda (frío) | °C | mes: $\max(0,\ \text{límite inf} - T_{op})$. Año: el mayor de los 12 meses | ≥ 0; mismos casos vacíos |

En un mismo mes nunca son ambos mayores que 0, porque el límite inferior siempre es menor que el superior.

### 2.6 Energía y carbono (Calculada)

| Columna | Qué es | Unidad | Fórmula | Valores |
|---|---|---|---|---|
| `energia_total_kWh` | energía total del periodo para enfriar y calentar | kWh | `electrica`: $E = E_{enf} + E_{cal}$. `termica`: $E = E_{enf}/COP + E_{cal}/\eta$. Año: suma de los 12 meses (si falta alguno, la fila `anual` del simulador) | ≥ 0. Vacía si no hay energía, o si es térmica sin COP/eficiencia |
| `carbono_kgCO2e` | emisiones de operación del periodo | kgCO₂e | $E \times$ `factor_emision_kgCO2e_kWh` | ≥ 0. Vacío sin factor |

### 2.7 Comparación contra el caso base (Calculada)

Se compara siempre el **mismo periodo** del escenario y del base.

| Columna | Qué es | Unidad | Fórmula | Valores |
|---|---|---|---|---|
| `delta_T_operativa_C` | cuánto cambia la T operativa respecto al base | °C | $T_{op}^{esc} - T_{op}^{base}$ | real; 0 en el base. Positivo = más cálido (mejora en frío, empeora en calor) |
| `delta_energia_pct` | cambio porcentual de energía respecto al base | % | $100\,(E^{esc} - E^{base}) / E^{base}$ | ≥ −100, sin tope; 0 en el base. Vacío si la energía del base es 0. Negativo = ahorro |

No hay delta de carbono: con un solo factor de emisión es igual al de energía.
