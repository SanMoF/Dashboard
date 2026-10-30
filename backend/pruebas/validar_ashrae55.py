#!/usr/bin/env python3
"""
validar_ashrae55.py — Compara las fórmulas ASHRAE 55 de generar_csv_confort.py contra
pythermalcomfort (CBE, UC Berkeley), una implementación independiente y de referencia.

No es parte del cálculo: pythermalcomfort solo se usa aquí para verificar.
Uso:  pip install -r backend/requirements-dev.txt
      python backend/pruebas/validar_ashrae55.py
Sale con código 1 si alguna diferencia supera 0.01 °C.
"""
import os, sys, warnings
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import generar_csv_confort as g
from pythermalcomfort.models import adaptive_ashrae
from pythermalcomfort.environment import operative_tmp

warnings.filterwarnings("ignore")  # avisos de rango de pythermalcomfort (tr < 10 °C), no afectan la comparación
rng = np.random.default_rng(1)
n = 5000
tdb = rng.uniform(12, 36, n)                 # temperatura del aire
tr = tdb + rng.uniform(-3, 3, n)             # temperatura radiante media
tpma = rng.uniform(10.5, 33, n)              # media exterior predominante (dentro del alcance)
v = rng.choice([0.1, 0.3, 0.5, 0.6, 0.8, 0.9, 1.0, 1.2], n)

A = g.a_coef(v)
top = A * tdb + (1 - A) * tr
tc = 0.31 * tpma + 17.8
extra = np.where(top > 25, g.extra_vel(v), 0)
propio = {"T_operativa": top, "T_confort": tc,
          "limite_inf_80": tc - 3.5, "limite_sup_80": tc + 3.5 + extra,
          "limite_inf_90": tc - 2.5, "limite_sup_90": tc + 2.5 + extra}

r = adaptive_ashrae(tdb=tdb, tr=tr, t_running_mean=tpma, v=v, round_output=False)
ref = {"T_operativa": operative_tmp(tdb, tr, v, standard="ASHRAE"), "T_confort": r.tmp_cmf,
       "limite_inf_80": r.tmp_cmf_80_low, "limite_sup_80": r.tmp_cmf_80_up,
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
