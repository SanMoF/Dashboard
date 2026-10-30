# Dashboard de confort térmico

Herramienta para comparar **cambios a una vivienda** (aislamiento, vidrios, sombreado, ventilación…) y ver cuánto mejoran el **confort térmico según ASHRAE 55**, y cuánto cuestan en **energía** y **carbono**. Está pensada para que una persona de arquitectura pueda leer los resultados sin conocimientos de simulación.

Proyecto de becario dentro del proyecto SECIHTI de descarbonización de vivienda en Puebla. Los datos incluidos (`PUE-01`, `PUE-02`) son **de prueba (mock)** y no representan casas reales.

## Qué hace

1. **Backend (`backend/`)**: toma los resultados horarios de la simulación de cada escenario y genera **un CSV por vivienda** con los indicadores de confort.
2. **Datos (`datos/`)**: aquí se guardan esos CSV. El dashboard lee **todos** los `.csv` de esta carpeta, sin importar cuántos sean ni de cuántas viviendas.
3. **Dashboard (`dashboard/`)**: página web que muestra, por vivienda:
   - una tabla con cada escenario frente al caso base,
   - el rango de temperatura operativa (mínima a máxima) frente a los límites de ASHRAE 55,
   - el *tradeoff* confort contra energía,
   - la evolución mes a mes del escenario elegido frente al base.

## Cómo lo hace

- **Una vivienda = una zona.** La simulación entrega la temperatura y la humedad operativas de **un punto central de la casa**, lejos de los muros, para idealizar la temperatura de toda la vivienda.
- **ASHRAE 55, método adaptativo, siempre.** Con la temperatura exterior de los días previos se calcula, para cada hora, el rango aceptable de temperatura (banda de 80 % o 90 % de aceptabilidad; el límite superior sube si hay movimiento de aire).
- **Solo extremos.** No se cuentan horas: para el año, el mes más caliente, el mes más frío y cada mes se reportan la T operativa **máxima y mínima**, el límite ASHRAE en esas horas, cuánto se pasa de él (exceso/déficit) y la humedad máxima y mínima.
- **Comparación contra el base.** Cada escenario trae la diferencia contra el caso base en T máxima, T mínima y energía.
- **No inventa datos.** Si falta un dato, la celda queda vacía y se anota en un log (`<archivo>_log.md`).

Una fila del CSV = escenario × periodo (15 filas por escenario). Documentación detallada:

- [`docs/metodologia_calculo.md`](docs/metodologia_calculo.md): **todas las fórmulas** (ASHRAE 55 adaptativo), paso a paso, con un ejemplo numérico, supuestos y limitaciones. Las fórmulas están escritas en el propio script; la única librería de confort, `pythermalcomfort`, solo se usa para verificarlas (`python backend/pruebas/validar_ashrae55.py`).
- [`docs/contexto_esquema_confort.md`](docs/contexto_esquema_confort.md): las 34 columnas y el historial de decisiones del esquema.

## Estructura

```
backend/
  generar_csv_confort.py   genera el CSV de una vivienda
  requirements.txt         dependencias (pandas, numpy)
  requirements-dev.txt     + pythermalcomfort, solo para verificar
  pruebas/                 validación de fórmulas contra pythermalcomfort
  mock/crear_mock.py       crea entradas de prueba
datos/                     CSV que lee el dashboard (agrega aquí los tuyos)
dashboard/
  index.html               el dashboard
  servidor.py              servidor local (solo Python estándar)
docs/                      metodología de cálculo, contexto y decisiones
.claude/skills/            skill de Claude Code para trabajar el esquema
herramientas/              utilidades (empaquetar la skill)
```

## Probarlo en tu equipo

Necesitas **Python 3.10 o superior** y un navegador. El dashboard carga sus librerías de gráficas desde internet, así que necesitas conexión.

### 1. Ver el dashboard (no requiere instalar nada)

```bash
git clone <url-del-repositorio>
cd Dahsboard_Thermal_Comfort
python dashboard/servidor.py
```

En Windows usa `py` en lugar de `python` si `python` no existe. Se abre `http://localhost:8000` con los datos de `datos/`. Si otro programa ya usa ese puerto, el servidor prueba solo el siguiente libre (8001, 8002…) y muestra en la terminal la dirección correcta. Para cerrar el servidor: `Ctrl+C`.

Opciones: `--puerto 8080` para otro puerto, `--datos otra/carpeta` para leer CSV de otra carpeta, `--sin-navegador` para no abrir el navegador.

> Sin servidor también puedes abrir `dashboard/index.html` con doble clic y usar **«Abrir CSV sin servidor»** para elegir uno o varios CSV a mano.

### 2. Agregar datos

Copia cualquier CSV generado por el backend a `datos/` y pulsa **«Recargar datos/»** (o recarga la página). Puedes tener tantos archivos como quieras; el selector **Vivienda** muestra todas las viviendas encontradas. Si el mismo escenario de la misma vivienda aparece en dos archivos, se usa el del archivo que va después en orden alfabético y el dashboard lo avisa. Los archivos que no tienen el formato esperado se omiten con un aviso.

### 3. Generar CSV con el backend

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Con datos de prueba:

```bash
python backend/mock/crear_mock.py --vivienda PUE-03 --ajuste-clima 1
python backend/generar_csv_confort.py \
  --escenarios backend/mock/entradas/PUE-03/escenarios.csv \
  --config backend/mock/entradas/PUE-03/config.csv \
  --salida datos/confort_PUE-03_mock.csv
```

Recarga el dashboard y aparecerá la vivienda `PUE-03`.

Con datos reales necesitas tres tipos de archivo (el formato completo está al inicio de `backend/generar_csv_confort.py`):

| Archivo | Quién lo llena | Contenido |
|---|---|---|
| `escenarios.csv` | a mano | un renglón por escenario: id, nombre, si es el base, archivo horario y los 9 parámetros de la medida (U de muro/techo/ventana, SHGC, absortancias, sombreado, ventilación, velocidad del aire) |
| `config.csv` | a mano | `vivienda_id`, `aceptabilidad_pct` (80 o 90) y, si se tienen, factor de emisión y COP/eficiencias |
| `horario_<escenario>.csv` | simulación | por hora: `fecha_hora`, `T_operativa_C` del punto central (o `T_aire_C` + `T_radiante_media_C`), `HR_pct`, `T_exterior_C` (o se pasa un `--epw`), energía de enfriamiento y calefacción |

Revisa siempre el `_log.md` que se genera junto al CSV: dice qué quedó vacío y qué dato hace falta.

## Para Claude Code

El repositorio incluye la skill `esquema-confort-termico` en `.claude/skills/`, que se activa sola al abrir Claude Code en esta carpeta. Si cambias `backend/generar_csv_confort.py` o `docs/contexto_esquema_confort.md`, ejecuta `python herramientas/empaquetar_skill.py` para actualizar la copia de la skill y generar `dist/esquema-confort-termico.skill`.
