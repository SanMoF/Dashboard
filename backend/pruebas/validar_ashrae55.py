#!/usr/bin/env python3
"""
validar_ashrae55.py — Compara los límites ASHRAE 55 adaptativos de generar_csv_confort.py
contra pythermalcomfort (CBE, UC Berkeley), una implementación independiente y de referencia.

No es parte del cálculo: pythermalcomfort solo se usa aquí para verificar.
La T_operativa la da el simulador, así que se compara con tdb = tr = T_operativa.
Uso:  pip install -r backend/requirements-dev.txt
      python backend/pruebas/validar_ashrae55.py
Sale con código 1 si alguna diferencia supera 0.01 °C.
"""
import os, sys, warnings
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import generar_csv_confort as g
from pythermalcomfort.models import adaptive_ashrae

warnings.filterwarnings("ignore")  # avisos de rango de pythermalcomfort, no afectan la comparación
rng = np.random.default_rng(1)
n = 5000
top = rng.uniform(12, 36, n)                 # temperatura operativa (del simulador)
tpma = rng.uniform(10.5, 33, n)              # media exterior predominante (dentro del alcance)
v = rng.choice([0.1, 0.3, 0.5, 0.6, 0.8, 0.9, 1.0, 1.2], n)

lim80 = np.array([g.limites(a, b, c, 80) for a, b, c in zip(tpma, top, v)])
lim90 = np.array([g.limites(a, b, c, 90) for a, b, c in zip(tpma, top, v)])
propio = {"limite_inf_80": lim80[:, 0], "limite_sup_80": lim80[:, 1],
          "limite_inf_90": lim90[:, 0], "limite_sup_90": lim90[:, 1]}

r = adaptive_ashrae(tdb=top, tr=top, t_running_mean=tpma, v=v, round_output=False)
ref = {"limite_inf_80": r.tmp_cmf_80_low, "limite_sup_80": r.tmp_cmf_80_up,
       "limite_inf_90": r.tmp_cmf_90_low, "limite_sup_90": r.tmp_cmf_90_up}

falla = False
for k in propio:
    a, b = np.asarray(propio[k], float), np.asarray(ref[k], float)
    ok = ~np.isnan(b)                         # pythermalcomfort deja NaN fuera de sus rangos de entrada
    d = np.abs(a[ok] - b[ok])
    malos = int((d > 0.01).sum())
    falla |= malos > 0
    print(f"{k:14s} comparados {ok.sum():5d}  dif. máx {d.max():.4f} °C  fuera de tolerancia {malos}")
print("RESULTADO:", "DIFERENCIAS" if falla else "coincide con pythermalcomfort")
sys.exit(1 if falla else 0)
