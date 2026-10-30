# Metodología de cálculo del confort térmico

Este documento explica **qué fórmulas usa** `backend/generar_csv_confort.py`, **en qué orden**, **de dónde vienen** y **qué límites tiene** la implementación. Cada paso indica la función del script que lo hace.

## 1. Norma y dependencias

### Norma

- **ANSI/ASHRAE Standard 55, *Thermal Environmental Conditions for Human Occupancy*. Modelo de confort adaptativo** (sección 5.4 en la edición 2020: espacios naturalmente acondicionados y controlados por el ocupante).
- **Temperatura operativa:** apéndice normativo A de la misma norma (método simplificado con el coeficiente *A*).
- Los números de sección corresponden a la edición 2020. Los coeficientes del modelo adaptativo (0.31, 17.8, ±2.5/±3.5 °C, 10–33.5 °C y los escalones por velocidad del aire) son los mismos en las ediciones 2017 y 2020. Si se usa otra edición, hay que revisar que no hayan cambiado.

**Siempre se usa ASHRAE 55 adaptativo.** El método no es configurable.

### Dependencias

| Paquete | Para qué | ¿Hace cálculos de confort? |
|---|---|---|
| `pandas` | leer CSV, fechas, promedios diarios, agrupar por mes | No |
| `numpy` | operaciones vectoriales y condiciones (`np.where`, `np.clip`) | No |
| `pythermalcomfort` (solo desarrollo) | **verificar** que nuestras fórmulas den lo mismo que una implementación de referencia | Sí, pero **no se usa en el cálculo** |

Las fórmulas de ASHRAE 55 están **escritas directamente en el script**; no dependen de ninguna librería de confort. Así el cálculo queda a la vista y no cambia si una librería se actualiza.

**Verificación independiente.** `backend/pruebas/validar_ashrae55.py` compara nuestras fórmulas con **pythermalcomfort** (Center for the Built Environment, UC Berkeley; probado con la versión 4.7.0) en 5 000 casos aleatorios: temperatura operativa, temperatura de confort y límites inferior y superior al 80 % y al 90 %, con velocidades del aire de 0.1 a 1.2 m/s. **Resultado: diferencia máxima de 0.0000 °C en todos los casos.**

```bash
pip install -r backend/requirements-dev.txt
python backend/pruebas/validar_ashrae55.py
```

Documentación de pythermalcomfort: <https://pythermalcomfort.readthedocs.io/> (funciones `adaptive_ashrae` y `operative_tmp`). Herramienta web equivalente del CBE: <https://comfort.cbe.berkeley.edu/>.

## 2. Entradas que usa el cálculo

Datos de cada hora, de la serie del **punto central de la vivienda** (una sola zona):

| Símbolo | Columna | Unidad | Obligatoria |
|---|---|---|---|
| *t_o* | `T_operativa_C` | °C | sí, o en su lugar *t_a* y *t̄_r* |
| *t_a* | `T_aire_C` | °C | si no hay `T_operativa_C` |
| *t̄_r* | `T_radiante_media_C` | °C | si no hay `T_operativa_C` |
| *V* | `vel_aire_m_s` | m/s | no (sin ella se supone aire quieto) |
| *t_ext* | `T_exterior_C` o archivo EPW | °C | sí |
| *HR* | `HR_pct` | % | no (solo se reporta) |
| — | `energia_enfriamiento_kWh`, `energia_calefaccion_kWh` | kWh | no |

Datos de la configuración (`config.csv`): `aceptabilidad_pct` (80 o 90), `dias_media_exterior` (N), `energia_tipo`, `COP_enfriamiento`, `eficiencia_calefaccion` y `factor_emision_kgCO2e_kWh`.

> **Importante:** los 9 parámetros de `escenarios.csv` (valores U, SHGC, absortancias, sombreado, ventilación y `vel_aire_m_s`) **describen** el escenario, pero **no entran en ninguna fórmula**. Su efecto ya está en las temperaturas que entrega la simulación. En particular, el ajuste por velocidad del aire usa la columna **horaria** `vel_aire_m_s` del horario, no la del escenario.

## 3. Paso a paso

### Paso 1. Temperatura media exterior predominante, *t_pma* — función `clima_diario`

ASHRAE 55 (5.4.2.1) define *t_pma* como la media de la temperatura exterior de los **días anteriores** (entre 7 y 30). Se usa la **media aritmética simple**, una de las dos opciones que permite la norma (la otra es una media con pesos exponenciales).

1. Media diaria de la temperatura exterior: `t_ext_d = promedio de las 24 horas del día`.
2. Para cada día *d*:

$$
t_{pma}(d) = \frac{1}{N}\sum_{i=1}^{N} t_{ext,d}(d-i)
$$

   - **N** = `dias_media_exterior`. Si no se da, **N = 7** y se anota en el log como supuesto.
   - El día actual **no** se incluye (son los *N* días previos).
3. **Inicio de año.** Si hay un año completo (≥ 365 días), los primeros días de enero toman los últimos días de diciembre del mismo archivo, como si el año se repitiera (año típico, EPW). Si el periodo es más corto, los primeros *N* días no tienen *t_pma* y quedan fuera.

Todas las horas de un mismo día comparten la misma *t_pma*.

### Paso 2. Temperatura operativa, *t_o* — función `evaluar` (con `a_coef`)

- Si el horario trae `T_operativa_C` (temperatura operativa del punto central), se usa **tal cual**.
- Si no, se calcula con el método simplificado del apéndice A de ASHRAE 55:

$$
t_o = A\,t_a + (1 - A)\,\bar t_r
$$

| Velocidad del aire *V* | *A* |
|---|---|
| *V* < 0.2 m/s, o sin dato | 0.5 |
| 0.2 ≤ *V* < 0.6 m/s | 0.6 |
| *V* ≥ 0.6 m/s | 0.7 |

ASHRAE 55 da *A* = 0.7 solo hasta 1.0 m/s. Para *V* > 1.0 m/s el script sigue usando 0.7, igual que pythermalcomfort.

### Paso 3. Temperatura de confort, *t_cmf* — función `evaluar`

ASHRAE 55, 5.4.2:

$$
t_{cmf} = 0.31\,t_{pma} + 17.8
$$

### Paso 4. Límites de aceptabilidad — función `evaluar` (con `extra_vel`)

| `aceptabilidad_pct` | Banda Δ |
|---|---|
| 80 | 3.5 °C |
| 90 | 2.5 °C |

$$
\text{límite inferior} = t_{cmf} - \Delta
$$

$$
\text{límite superior} = t_{cmf} + \Delta + \Delta_V \qquad (\Delta_V \text{ solo si } t_o > 25\ ^\circ\text{C})
$$

**Ajuste por velocidad del aire, Δ_V** (ASHRAE 55, 5.4.2.4). Solo sube el límite superior, y solo en las horas con *t_o* > 25 °C:

| *V* (columna horaria) | Δ_V |
|---|---|
| *V* < 0.6 m/s, o sin dato | 0 |
| 0.6 ≤ *V* < 0.9 m/s | +1.2 °C |
| 0.9 ≤ *V* < 1.2 m/s | +1.8 °C |
| *V* ≥ 1.2 m/s | +2.2 °C |

Se usan escalones, sin interpolar, igual que pythermalcomfort.

**Rango de aplicación:** el modelo adaptativo solo vale con **10 °C ≤ t_pma ≤ 33.5 °C**. En las horas fuera de ese rango:

- no hay límites, así que tampoco exceso ni déficit en esa hora;
- la *t_o* de esa hora **sí cuenta** para la máxima y la mínima del periodo;
- el log dice cuántas horas quedaron fuera.

**Detalles de configuración:**

- Si falta `aceptabilidad_pct`, no se calculan límites y el log lo marca como faltante.
- Cualquier valor distinto de 90 se trata como 80 % (banda de 3.5 °C).

### Paso 5. Exceso y déficit por hora — función `evaluar`

$$
\text{exceso}(h) = \max\big(0,\ t_o(h) - \text{límite superior}(h)\big)
$$

$$
\text{déficit}(h) = \max\big(0,\ \text{límite inferior}(h) - t_o(h)\big)
$$

El exceso mide cuántos grados por **encima** del rango aceptable está la casa (calor) y el déficit cuántos por **debajo** (frío). Si la hora está dentro del rango, ambos valen 0.

### Paso 6. Agregación por periodo — función `agregar`

Periodos: `anual` (12 meses), `mes_caliente`, `mes_frio` y cada mes (`ene` … `dic`).

- **Mes caliente / mes frío:** el mes con el **promedio mensual de temperatura exterior** más alto o más bajo.

Columnas de cada periodo. **Solo se reportan extremos; no se cuentan horas ni se promedian temperaturas.**

| Columna | Cálculo |
|---|---|
| `T_op_max_C` | máximo de *t_o* en el periodo (todas las horas) |
| `T_op_min_C` | mínimo de *t_o* en el periodo |
| `mes_T_op_max`, `mes_T_op_min` | mes en que ocurrió cada extremo |
| `limite_sup_C` | límite superior **en la hora del máximo** de *t_o* |
| `limite_inf_C` | límite inferior **en la hora del mínimo** de *t_o* |
| `max_exceso_sobre_limite_C` | máximo del exceso horario en el periodo |
| `max_deficit_bajo_limite_C` | máximo del déficit horario en el periodo |
| `HR_max_pct`, `HR_min_pct` | máximo y mínimo de *HR* (no entra en ASHRAE 55 adaptativo, solo se reporta) |
| `T_ext_max_C`, `T_ext_min_C` | máximo y mínimo de *t_ext* |

**Por qué el límite se reporta en la hora del extremo:** el rango aceptable cambia cada día con *t_pma*. Un promedio del periodo no se puede comparar con la máxima. El límite de esa misma hora sí.

**Exceso máximo frente a (T_op_max − limite_sup_C):** normalmente coinciden. Pueden diferir si el peor exceso ocurre en otra hora con un límite más bajo (un día con *t_pma* menor). El exceso máximo es el indicador correcto de cuánto se sale del confort.

### Paso 7. Energía y carbono — función `energia_total` y `main`

Según `energia_tipo` en la configuración:

- **`electrica`:** E = E_enf + E_cal, tal como vienen del simulador.
- **`termica`** (cargas ideales):

$$
E = \frac{E_{enf}}{COP} + \frac{E_{cal}}{\eta}
$$

  Si falta el COP o la eficiencia, la energía queda **vacía**. No se supone ningún valor.
- **Sin `energia_tipo`:** se suma tal como viene y el log lo avisa.

Después:

- `energia_total_kWh` = suma de *E* en las horas del periodo.
- `carbono_kgCO2e` = `energia_total_kWh` × `factor_emision_kgCO2e_kWh`. Solo carbono de operación; queda vacío si no se da el factor.

### Paso 8. Comparación contra el caso base — `main`

Se compara cada escenario con el escenario base (`es_base = Si`) **en el mismo periodo**:

$$
\Delta T_{op,max} = T_{op,max}^{esc} - T_{op,max}^{base} \qquad
\Delta T_{op,min} = T_{op,min}^{esc} - T_{op,min}^{base}
$$

$$
\Delta E\,[\%] = 100\,\frac{E^{esc} - E^{base}}{E^{base}} \quad (\text{vacío si } E^{base} = 0)
$$

No hay delta de carbono: con un solo factor de emisión sería idéntico al de energía.

Interpretación para el dashboard:

- Un Δ T_op,max **negativo** es una mejora (la casa se calienta menos).
- Un Δ T_op,min **positivo** es una mejora (la casa se enfría menos).

### Paso 9. Redondeo

Todos los valores numéricos se redondean a **2 decimales** al final, solo al escribir el CSV. Los cálculos intermedios no se redondean.

## 4. Ejemplo numérico

**Datos de la hora.** Los 7 días previos tuvieron medias exteriores de 16, 17, 18, 19, 18, 19 y 19 °C. Aceptabilidad del 80 %. A las 15:00: *t_a* = 30 °C, *t̄_r* = 28 °C, *V* = 0.9 m/s.

| Paso | Cálculo | Resultado |
|---|---|---|
| 1. *t_pma* | (16+17+18+19+18+19+19) / 7 | 18.00 °C |
| 2. *A* | *V* = 0.9 ≥ 0.6 | 0.7 |
| 2. *t_o* | 0.7·30 + 0.3·28 | 29.40 °C |
| 3. *t_cmf* | 0.31·18 + 17.8 | 23.38 °C |
| 4. límite inferior | 23.38 − 3.5 | 19.88 °C |
| 4. Δ_V | *t_o* > 25 y 0.9 ≤ *V* < 1.2 | +1.8 °C |
| 4. límite superior | 23.38 + 3.5 + 1.8 | 28.68 °C |
| 5. exceso | máx(0, 29.40 − 28.68) | **0.72 °C** |
| 5. déficit | máx(0, 19.88 − 29.40) | 0 °C |

Esa hora está 0.72 °C por encima del rango aceptable. Sin el ventilador (*V* < 0.2 m/s), *A* = 0.5, *t_o* = 29.0 °C y el límite superior sería 26.88 °C: el exceso subiría a 2.12 °C.

**Energía** (`energia_tipo = termica`, COP = 3, η = 0.9, factor = 0.435 kgCO₂e/kWh). Con 10 kWh de enfriamiento y 4 kWh de calefacción:

- E = 10/3 + 4/0.9 = 3.33 + 4.44 = 7.78 kWh
- Carbono = 7.78 × 0.435 = 3.38 kgCO₂e

## 5. Supuestos y limitaciones

1. **Condiciones para usar el modelo adaptativo.** ASHRAE 55 lo permite solo en espacios naturalmente acondicionados, sin enfriamiento mecánico en operación, con ocupantes de actividad sedentaria (≈ 1.0–1.3 met) que pueden ajustar su ropa y abrir ventanas. **El script no verifica estas condiciones;** se supone que la vivienda las cumple.
2. **Temperatura de libre evolución frente a cargas ideales.** Para que el confort adaptativo tenga sentido, la *t_o* debe venir de una simulación **sin climatización** (libre evolución). Si la energía se obtiene con cargas ideales que mantienen la casa en un rango, esa corrida debe ser **otra** distinta a la de temperaturas. De lo contrario, la *t_o* reflejaría la casa climatizada. Hay que confirmarlo al definir la simulación.
3. **Una sola zona.** Se idealiza toda la vivienda con un punto central. No se capturan diferencias entre cuartos ni cerca de muros y ventanas.
4. **Media exterior simple** de *N* días (por defecto 7). No se usa la media con pesos exponenciales.
5. **Velocidad del aire.** Se usan escalones sin interpolar, y *A* = 0.7 también por encima de 1.0 m/s.
6. **Humedad.** No afecta los límites del modelo adaptativo; solo se informa.
7. **Escenarios.** Los parámetros del escenario son descriptivos (ver la sección 2).
8. **Exceso/déficit en el dashboard.** La gráfica de *tradeoff* suma `max_exceso_sobre_limite_C + max_deficit_bajo_limite_C` como un solo indicador de qué tan fuera del rango queda la vivienda. Esa suma la hace el dashboard, no está en el CSV.

## 6. Mapa función → paso

| Función en `backend/generar_csv_confort.py` | Pasos |
|---|---|
| `clima_diario` | 1 |
| `a_coef` | 2 (coeficiente *A*) |
| `evaluar` | 2, 3, 4, 5 |
| `extra_vel` | 4 (Δ_V) |
| `agregar` | 6 |
| `energia_total` | 7 |
| `main` | mes caliente/frío, energía por periodo, carbono, deltas (8), redondeo (9) |
