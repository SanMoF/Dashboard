#!/usr/bin/env python3
"""
generar_csv_confort.py — Esquema de datos de confort térmico (v3: solo máximos y mínimos)
Genera el CSV único para el dashboard a partir de archivos dados. No inventa
valores: lo que no está en las entradas queda vacío y se anota en el log.
La vivienda es una sola zona (sin habitaciones) y el confort siempre se mide con
ASHRAE 55 adaptativo. No se cuentan horas: se reportan los extremos de T_op
(máx y mín), el límite ASHRAE vigente en esas horas y cuánto se pasan de él.
Una fila por escenario × periodo.

Entradas
  --escenarios  CSV: escenario_id, escenario_nombre, es_base, archivo_horario,
                [U_muro_ext, U_techo, U_ventana, SHGC_ventana, absortancia_muro,
                 absortancia_techo, sombreado_m, ventilacion_ach, vel_aire_m_s]
  --config      CSV clave,valor: vivienda_id, aceptabilidad_pct (80|90),
                [factor_emision_kgCO2e_kWh, dias_media_exterior,
                 energia_tipo (electrica|termica), COP_enfriamiento,
                 eficiencia_calefaccion]
  --epw         (opcional) archivo de clima; si falta, el horario debe traer
                T_exterior_C
  Horario por escenario (archivo_horario): fecha_hora y la temperatura
                operativa del PUNTO CENTRAL de la vivienda (lejos de los muros, para
                reducir la varianza): T_operativa_C, o bien T_aire_C y
                T_radiante_media_C (el script calcula T_op). Opcionales:
                [HR_pct, vel_aire_m_s, T_exterior_C,
                energia_enfriamiento_kWh, energia_calefaccion_kWh].
                Una fila por hora, de toda la vivienda.
Salidas
  --salida CSV final y <salida>_log.md con faltantes, supuestos y avisos.
"""
import argparse, os, sys
import numpy as np
import pandas as pd

PARAMS = ["U_muro_ext", "U_techo", "U_ventana", "SHGC_ventana", "absortancia_muro",
          "absortancia_techo", "sombreado_m", "ventilacion_ach", "vel_aire_m_s"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
COLUMNAS = (
    ["vivienda_id", "escenario_id", "escenario_nombre", "es_base"] + PARAMS +
    ["nivel", "periodo", "mes",
     "T_ext_max_C", "T_ext_min_C",
     "T_op_max_C", "T_op_min_C", "mes_T_op_max", "mes_T_op_min",
     "HR_max_pct", "HR_min_pct",
     "limite_sup_C", "limite_inf_C", "max_exceso_sobre_limite_C", "max_deficit_bajo_limite_C",
     "energia_total_kWh", "carbono_kgCO2e",
     "delta_T_op_max_C", "delta_T_op_min_C", "delta_energia_pct",
     "aceptabilidad_pct"])

LOG = {"faltantes": [], "supuestos": [], "avisos": []}
def log(tipo, msg):
    if msg not in LOG[tipo]:
        LOG[tipo].append(msg)

def num(x):
    try:
        if x is None or (isinstance(x, str) and x.strip().upper() in ("", "ND", "NA", "N/A")):
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan

def leer_config(path):
    df = pd.read_csv(path, dtype=str).fillna("")
    cfg = {r["clave"].strip(): r["valor"].strip() for _, r in df.iterrows()}
    for k in ["vivienda_id", "aceptabilidad_pct"]:
        if not cfg.get(k):
            log("faltantes", f"config: falta '{k}'")
    return cfg

def leer_epw(path):
    rows = pd.read_csv(path, skiprows=8, header=None)
    yr = 2001  # año ficticio no bisiesto solo para indexar; el EPW es un año típico
    fh = pd.to_datetime(dict(year=yr, month=rows[1], day=rows[2], hour=rows[3] - 1))
    return pd.DataFrame({"fecha_hora": fh, "T_exterior_C": rows[6].astype(float)})

def a_coef(v):
    """ASHRAE 55 apéndice: peso A de T_aire en T_operativa según velocidad del aire."""
    return np.where(np.isnan(v) | (v < 0.2), 0.5, np.where(v < 0.6, 0.6, 0.7))

def extra_vel(v):
    """Aumento del límite superior adaptativo por velocidad del aire (ASHRAE 55, escalones)."""
    return np.where(np.isnan(v), 0.0, np.where(v >= 1.2, 2.2, np.where(v >= 0.9, 1.8, np.where(v >= 0.6, 1.2, 0.0))))

def clima_diario(ext, cfg):
    """Media exterior diaria y media predominante (media simple de N días previos)."""
    d = ext.set_index("fecha_hora")["T_exterior_C"].resample("D").mean().dropna()
    n_cfg = num(cfg.get("dias_media_exterior"))
    n = 7 if np.isnan(n_cfg) else int(n_cfg)
    if np.isnan(n_cfg):
        log("supuestos", f"dias_media_exterior no dado: se usa {n} días (rango ASHRAE 55: 7–30)")
    if len(d) >= 365:  # año completo: los primeros días toman los últimos del año (año típico)
        ext_d = pd.concat([d.iloc[-n:], d])
        tpma = ext_d.shift(1).rolling(n).mean().iloc[n:]
        log("supuestos", "media predominante de los primeros días de enero calculada con los últimos días de diciembre (año típico)")
    else:
        tpma = d.shift(1).rolling(n).mean()
        log("avisos", "periodo menor a un año: los primeros días no tienen media predominante y se excluyen")
    return tpma

def evaluar(hor, ext, tpma, cfg):
    """Agrega T_op y los límites ASHRAE 55 a cada hora del horario."""
    acept = num(cfg.get("aceptabilidad_pct"))
    banda = 2.5 if acept == 90 else 3.5
    if np.isnan(acept):
        log("faltantes", "aceptabilidad_pct no dada: no se calculan límites de confort")
    h = hor.copy()
    h["mes"] = h["fecha_hora"].dt.month
    if "T_exterior_C" not in h or h["T_exterior_C"].isna().all():
        h = h.drop(columns=[c for c in ["T_exterior_C"] if c in h]).merge(ext, on="fecha_hora", how="left")
    v = h["vel_aire_m_s"].astype(float).values if "vel_aire_m_s" in h else np.full(len(h), np.nan)
    if "vel_aire_m_s" not in h:
        log("supuestos", "sin vel_aire_m_s horaria: sin ajuste por velocidad del aire" + ("" if "T_operativa_C" in h else " y T_operativa con A=0.5"))
    if "T_operativa_C" in h:
        h["T_op"] = h["T_operativa_C"].astype(float)
    else:
        A = a_coef(v)
        h["T_op"] = A * h["T_aire_C"] + (1 - A) * h["T_radiante_media_C"]
    h["tpma"] = h["fecha_hora"].dt.normalize().map(tpma)
    t_conf = 0.31 * h["tpma"] + 17.8
    valida = (h["tpma"] >= 10) & (h["tpma"] <= 33.5)
    h["lim_inf"] = np.where(valida, t_conf - banda, np.nan)
    h["lim_sup"] = np.where(valida, t_conf + banda + np.where(h["T_op"] > 25, extra_vel(v), 0), np.nan)
    if np.isnan(acept):
        h["lim_inf"] = h["lim_sup"] = np.nan
    fuera = int((~valida & h["tpma"].notna()).sum())
    if fuera:
        log("avisos", f"{fuera} horas con media predominante fuera de 10–33.5 °C: fuera del alcance del método adaptativo, sin límites ni exceso/déficit")
    h["exceso"] = np.clip(h["T_op"] - h["lim_sup"], 0, None)
    h["deficit"] = np.clip(h["lim_inf"] - h["T_op"], 0, None)
    return h

def energia_total(df, cfg):
    """Serie horaria de energía total (kWh); convierte carga térmica solo con COP dado. None si no se puede."""
    enf = df["energia_enfriamiento_kWh"].astype(float) if "energia_enfriamiento_kWh" in df else None
    cal = df["energia_calefaccion_kWh"].astype(float) if "energia_calefaccion_kWh" in df else None
    if enf is None and cal is None:
        log("faltantes", "el horario no trae energía: columnas de energía y carbono vacías")
        return None
    tipo = cfg.get("energia_tipo", "").lower()
    if tipo == "termica":
        cop, efi = num(cfg.get("COP_enfriamiento")), num(cfg.get("eficiencia_calefaccion"))
        if (enf is not None and np.isnan(cop)) or (cal is not None and np.isnan(efi)):
            log("faltantes", "energía térmica sin COP/eficiencia: no se convierte a energía eléctrica (queda vacía)")
            return None
        enf = enf / cop if enf is not None else 0
        cal = cal / efi if cal is not None else 0
    elif tipo != "electrica":
        log("avisos", "config sin energia_tipo: se usa la energía tal como la entrega el simulador")
    return (enf if enf is not None else 0) + (cal if cal is not None else 0)

def agregar(h, periodo_meses):
    x = h[h["mes"].isin(periodo_meses)]
    if x.empty:
        return None
    imax, imin = x["T_op"].idxmax(), x["T_op"].idxmin()
    return {"T_op_max_C": x.loc[imax, "T_op"], "T_op_min_C": x.loc[imin, "T_op"],
            "mes_T_op_max": int(x.loc[imax, "mes"]), "mes_T_op_min": int(x.loc[imin, "mes"]),
            "limite_sup_C": x.loc[imax, "lim_sup"], "limite_inf_C": x.loc[imin, "lim_inf"],
            "HR_max_pct": x["HR_pct"].max() if "HR_pct" in x else np.nan,
            "HR_min_pct": x["HR_pct"].min() if "HR_pct" in x else np.nan,
            "max_exceso_sobre_limite_C": x["exceso"].max(), "max_deficit_bajo_limite_C": x["deficit"].max()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenarios", required=True)
    ap.add_argument("--config", required=True); ap.add_argument("--epw")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    base_dir = os.path.dirname(os.path.abspath(a.escenarios))
    cfg = leer_config(a.config)
    esc = pd.read_csv(a.escenarios, dtype=str).fillna("")
    for p in PARAMS:
        if p not in esc or (esc[p] == "").all():
            log("faltantes", f"escenarios: parámetro '{p}' sin valor en ningún escenario")
    if (esc["es_base"].str.lower().isin(["si", "sí", "1"])).sum() != 1:
        log("avisos", "debe haber exactamente un escenario con es_base = Si; deltas vacíos si no")
    factor = num(cfg.get("factor_emision_kgCO2e_kWh"))
    if np.isnan(factor):
        log("faltantes", "factor_emision_kgCO2e_kWh no dado: carbono vacío")
    ext_epw = leer_epw(a.epw) if a.epw else None

    filas = []
    for _, s in esc.iterrows():
        ruta = s["archivo_horario"] if os.path.isabs(s["archivo_horario"]) else os.path.join(base_dir, s["archivo_horario"])
        if not s["archivo_horario"] or not os.path.exists(ruta):
            log("faltantes", f"{s['escenario_id']}: no existe archivo_horario '{s['archivo_horario']}' — escenario sin resultados")
            continue
        hor = pd.read_csv(ruta)
        hor["fecha_hora"] = pd.to_datetime(hor["fecha_hora"])
        if ext_epw is not None:
            hor["fecha_hora"] = hor["fecha_hora"].apply(lambda t: t.replace(year=2001))
        if "T_operativa_C" not in hor:
            for c in ["T_aire_C", "T_radiante_media_C"]:
                if c not in hor:
                    sys.exit(f"{ruta}: falta T_operativa_C o, en su lugar, {c}")
        if "HR_pct" not in hor:
            log("faltantes", f"{s['escenario_id']}: el horario no trae HR_pct: HR_max_pct y HR_min_pct vacías")
        if hor["fecha_hora"].duplicated().any():
            log("avisos", f"{s['escenario_id']}: fecha_hora repetida en el horario; debe haber una sola serie para toda la vivienda")
        if ext_epw is not None:
            ext = ext_epw
        elif "T_exterior_C" in hor:
            ext = hor[["fecha_hora", "T_exterior_C"]]
        else:
            sys.exit("Sin EPW ni T_exterior_C en el horario: no se puede aplicar ASHRAE 55 adaptativo")
        tpma = clima_diario(ext, cfg)
        h = evaluar(hor, ext, tpma, cfg)
        ext = ext.assign(mes=ext["fecha_hora"].dt.month)
        mens = ext.groupby("mes")["T_exterior_C"].mean()
        m_cal, m_fri = int(mens.idxmax()), int(mens.idxmin())
        en = energia_total(hor, cfg)
        mes_h = hor["fecha_hora"].dt.month
        periodos = [("clave", "anual", list(range(1, 13)), None), ("clave", "mes_caliente", [m_cal], m_cal),
                    ("clave", "mes_frio", [m_fri], m_fri)] + [("mes", MESES[m - 1], [m], m) for m in range(1, 13)]
        comunes = {"vivienda_id": cfg.get("vivienda_id", ""), "escenario_id": s["escenario_id"],
                   "escenario_nombre": s["escenario_nombre"], "es_base": s["es_base"],
                   **{p: num(s.get(p, "")) for p in PARAMS},
                   "aceptabilidad_pct": num(cfg.get("aceptabilidad_pct"))}
        for nivel, per, meses, mes in periodos:
            xe = ext[ext["mes"].isin(meses)]
            r = agregar(h, meses)
            if r is None:
                log("faltantes", f"{s['escenario_id']}: sin datos horarios para {per}")
                continue
            e_tot = en[mes_h.isin(meses)].sum() if en is not None else np.nan
            r.update(T_ext_max_C=xe["T_exterior_C"].max(), T_ext_min_C=xe["T_exterior_C"].min(),
                     energia_total_kWh=e_tot, carbono_kgCO2e=e_tot * factor)
            r.update(comunes, nivel=nivel, periodo=per, mes=mes if mes else "")
            filas.append(r)
    if not filas:
        sys.exit("Sin filas generadas: revisar el log")
    df = pd.DataFrame(filas).reindex(columns=COLUMNAS)
    # deltas contra base (mismo periodo)
    b = df[df["es_base"].str.lower().isin(["si", "sí", "1"])].set_index("periodo")
    if len(b):
        k = list(df["periodo"])
        g = lambda c: np.array([b[c].get(i, np.nan) for i in k], dtype=float)
        df["delta_T_op_max_C"] = df["T_op_max_C"] - g("T_op_max_C")
        df["delta_T_op_min_C"] = df["T_op_min_C"] - g("T_op_min_C")
        with np.errstate(divide="ignore", invalid="ignore"):
            be = g("energia_total_kWh")
            df["delta_energia_pct"] = np.where(be > 0, 100 * (df["energia_total_kWh"] - be) / be, np.nan)
    num_cols = df.select_dtypes("number").columns
    df[num_cols] = df[num_cols].round(2)
    for c in ["mes", "mes_T_op_max", "mes_T_op_min"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df.to_csv(a.salida, index=False, encoding="utf-8")
    with open(os.path.splitext(a.salida)[0] + "_log.md", "w", encoding="utf-8") as f:
        f.write(f"# Log de generación — {os.path.basename(a.salida)}\n\n")
        f.write(f"Filas: {len(df)} · Escenarios: {df['escenario_id'].nunique()}\n\n")
        for t, titulo in [("faltantes", "Datos faltantes (celdas vacías)"), ("supuestos", "Supuestos de método aplicados"), ("avisos", "Avisos")]:
            f.write(f"## {titulo}\n\n" + ("\n".join(f"- {m}" for m in LOG[t]) or "- Ninguno") + "\n\n")
    print(f"OK: {len(df)} filas → {a.salida}")

if __name__ == "__main__":
    main()
