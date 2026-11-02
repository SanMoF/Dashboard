#!/usr/bin/env python3
"""
empaquetar_skill.py — Sincroniza y empaqueta la skill esquema-confort-termico.

1. Copia las fuentes de verdad a la skill:
     backend/generar_csv_confort.py   -> .claude/skills/esquema-confort-termico/scripts/
     docs/contexto_esquema_confort.md -> .claude/skills/esquema-confort-termico/
     docs/metodologia_calculo.md      -> .claude/skills/esquema-confort-termico/
     docs/diccionario_variables.md    -> .claude/skills/esquema-confort-termico/
2. Crea dist/esquema-confort-termico.skill (zip) para instalarla en otro lugar (p. ej. claude.ai).

Uso: python herramientas/empaquetar_skill.py
"""
import os, shutil, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(RAIZ, ".claude", "skills")
NOMBRE = "esquema-confort-termico"
SKILL = os.path.join(SKILLS, NOMBRE)

shutil.copy2(os.path.join(RAIZ, "backend", "generar_csv_confort.py"), os.path.join(SKILL, "scripts"))
for doc in ["contexto_esquema_confort.md", "metodologia_calculo.md", "diccionario_variables.md"]:
    shutil.copy2(os.path.join(RAIZ, "docs", doc), SKILL)

os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
salida = os.path.join(RAIZ, "dist", f"{NOMBRE}.skill")
with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
    for carpeta, _, archivos in os.walk(SKILL):
        for a in sorted(archivos):
            ruta = os.path.join(carpeta, a)
            z.write(ruta, os.path.relpath(ruta, SKILLS))
print(f"Skill sincronizada y empaquetada en {os.path.relpath(salida, RAIZ)}")
