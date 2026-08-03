"""
migrar_json_a_db.py — Migra los datos viejos de data/*.json hacia la nueva base
de datos (SQLite o MySQL, según DB_BACKEND en tu entorno).

Uso:
    python migrar_json_a_db.py

Es seguro correrlo más de una vez: si una tabla ya tiene datos en la nueva DB,
te pregunta antes de sobreescribir.
"""
import asyncio
import json
from pathlib import Path

from utils import db

DATA_DIR = Path("data")


async def main():
    print(f"Backend activo: {db.backend_name()}")
    json_files = sorted(DATA_DIR.glob("*.json"))
    if not json_files:
        print("No se encontraron archivos .json en data/. Nada que migrar.")
        return

    for jf in json_files:
        tabla = jf.stem
        # npcs.json y personajes.json de ejemplo en /data ya se leen aparte por
        # algunos cogs como archivos estáticos; igual los migramos como tabla.
        try:
            contenido = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠️  {jf.name}: no se pudo leer ({e}), se omite.")
            continue

        if not isinstance(contenido, dict):
            print(f"  ⚠️  {jf.name}: no tiene forma de tabla clave→valor, se omite.")
            continue

        existentes = await db.all(tabla)
        if existentes:
            resp = input(
                f"  La tabla '{tabla}' ya tiene {len(existentes)} registros en la DB nueva. "
                f"¿Sobreescribir con los {len(contenido)} de {jf.name}? [s/N]: "
            ).strip().lower()
            if resp != "s":
                print(f"  → Se omite '{tabla}'.")
                continue

        for key, value in contenido.items():
            await db.set(tabla, key, value)
        print(f"  ✅ {jf.name} → tabla '{tabla}' ({len(contenido)} registros)")

    await db.close()
    print("Migración completa.")


if __name__ == "__main__":
    asyncio.run(main())
