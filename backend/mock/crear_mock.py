#!/usr/bin/env python3
"""Crea entradas MOCK (datos inventados, no reales) para probar generar_csv_confort.py.
Uso: python crear_mock.py [--vivienda PUE-01] [--ajuste-clima 0]
Escribe en backend/mock/entradas/<vivienda>/ (escenarios.csv, config.csv, horario_*.csv)."""
import argparse, os
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--vivienda", default="PUE-01")
ap.add_argument("--ajuste-clima", type=float, default=0.0, help="°C que se suman al clima sintético")
args = ap.parse_args()
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entradas", args.vivienda)
os.makedirs(d, exist_ok=True)
t = pd.date_range("2001-01-01", periods=8760, freq="h")
rng = np.random.default_rng(42)
doy, hr = t.day_of_year.values, t.hour.values
# clima sintético tipo Puebla (valores mensuales aproximados, inventados para el mock):
# mes más caliente mayo, más frío enero; lluvias jun-sep = más húmedo y menos oscilación diaria
T_MES = [13.3, 14.6, 16.8, 18.5, 19.0, 18.5, 17.6, 17.7, 17.4, 16.3, 14.8, 13.6]  # media °C
OSC_MES = [8.0, 8.5, 8.5, 8.0, 7.5, 6.0, 5.0, 5.0, 5.0, 6.0, 7.0, 7.5]          # semiamplitud diaria °C
HR_MES = [55, 50, 45, 48, 55, 70, 75, 75, 78, 70, 62, 58]                         # HR media %
mitad = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])       # día juliano a mitad de cada mes
mensual = lambda v: np.interp(doy, np.r_[mitad[-1] - 365, mitad, mitad[0] + 365], np.r_[v[-1], v, v[0]])
diario = np.sin((hr - 9) / 24 * 2 * np.pi)  # máx ~15 h, mín ~3 h
te = args.ajuste_clima + mensual(T_MES) + mensual(OSC_MES) * diario + rng.normal(0, 0.8, len(t))
hre = np.clip(mensual(HR_MES) - 18 * diario + rng.normal(0, 5, len(t)), 10, 100)
sol = np.clip(np.sin((hr - 6) / 12 * np.pi), 0, None)

# escenario: U_muro, U_techo, U_ventana, SHGC, abs_muro, abs_techo, sombreado, ach, vel_aire
ESC = [
    ("ESC-00", "Base (block, losa, vidrio sencillo)", "Si", 2.5, 3.0, 5.8, 0.85, 0.6, 0.6, 0.0, 0.5, 0.1),
    ("ESC-01", "Aislamiento en techo", "No", 2.5, 0.6, 5.8, 0.85, 0.6, 0.3, 0.0, 0.5, 0.1),
    ("ESC-02", "Muro aislado + techo aislado", "No", 0.8, 0.6, 5.8, 0.85, 0.6, 0.3, 0.0, 0.5, 0.1),
    ("ESC-03", "Aislamiento + vidrio doble + volado", "No", 0.8, 0.6, 2.8, 0.50, 0.4, 0.3, 0.6, 0.5, 0.1),
    ("ESC-04", "Todo lo anterior + ventilación nocturna y ventilador", "No", 0.8, 0.6, 2.8, 0.50, 0.4, 0.3, 0.6, 3.0, 0.9),
]
filas = []
for eid, nom, base, um, ut, uv, shgc, am, at, som, ach, v in ESC:
    ganancia = (um * 0.9 + ut * 1.6 + uv * 0.5) * 0.35  # sensibilidad inventada a la envolvente
    sol_g = sol * (am * 3 + at * 4 + shgc * 6 * (1 - som * 0.3))
    inercia = pd.Series(te).rolling(6, min_periods=1).mean().values
    ta0 = 0.55 * inercia + 0.45 * 29 + sol_g * 0.7 + (ganancia - 1.2) * (te - 21) * 0.15
    ta = ta0 - 0.12 * (ach - 0.5) * np.clip(ta0 - te, 0, None)  # la ventilación acerca el interior al exterior
    tr = ta + 0.4 * sol_g * 0.3 - 0.2
    # cargas ideales mock: enfría sobre 26 °C, calienta bajo 18 °C (escala ~3 MWh/año en la base)
    enf = np.clip(ta - 26, 0, None) * 0.14 * (1 + 0.2 * ganancia)
    cal = np.clip(18 - ta, 0, None) * 0.09 * (1 + 0.2 * ganancia)
    arch = f"horario_{eid}.csv"
    pd.DataFrame({"fecha_hora": t, "T_aire_C": ta.round(2), "T_radiante_media_C": tr.round(2),
                  "HR_pct": np.clip(18 + 0.6 * hre - 1.0 * (ta - 22), 15, 95).round(1), "vel_aire_m_s": v,
                  "T_exterior_C": te.round(2),
                  "energia_enfriamiento_kWh": enf.round(3), "energia_calefaccion_kWh": cal.round(3)}
                 ).to_csv(os.path.join(d, arch), index=False)
    filas.append([eid, nom, base, arch, um, ut, uv, shgc, am, at, som, ach, v])
pd.DataFrame(filas, columns=["escenario_id", "escenario_nombre", "es_base", "archivo_horario", "U_muro_ext", "U_techo",
    "U_ventana", "SHGC_ventana", "absortancia_muro", "absortancia_techo", "sombreado_m", "ventilacion_ach", "vel_aire_m_s"]
    ).to_csv(os.path.join(d, "escenarios.csv"), index=False)
open(os.path.join(d, "config.csv"), "w").write(
    f"clave,valor\nvivienda_id,{args.vivienda}\naceptabilidad_pct,80\n"
    "factor_emision_kgCO2e_kWh,0.435\ndias_media_exterior,7\nenergia_tipo,electrica\n")
print("Mock listo en", d)
