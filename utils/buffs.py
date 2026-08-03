"""
utils/buffs.py — Bonuses TEMPORALES por consumibles (energizantes, comida
especial, etc.). Se guardan en personajes.buffs_activos como una lista de:
    {"item": "monster_energy", "stat": "agilidad", "bonus": 3, "expira_ts": ...}

No reemplazan el sistema de HP (utils/lesiones.py se encarga de las
penalizaciones por heridas); esto es exclusivamente para bonuses positivos y
temporales de estadísticas por haber consumido algo.
"""
from __future__ import annotations

import time

from utils import db

# stat -> (bonus, duración en minutos)
BUFFS_CONSUMIBLES = {
    "monster_energy":   {"stat": "agilidad",     "bonus": 3, "duracion_min": 45,
                         "msg": "⚡ El Monster te dispara la adrenalina. +3 Agilidad por 45 min."},
    "cafe_energizante": {"stat": "inteligencia", "bonus": 2, "duracion_min": 30,
                         "msg": "☕ La cafeína te despeja la mente. +2 Inteligencia por 30 min."},
    "barra_proteina":   {"stat": "fuerza",       "bonus": 2, "duracion_min": 40,
                         "msg": "💪 La barra de proteína te carga de energía. +2 Fuerza por 40 min."},
    "bebida_isotonica": {"stat": "resistencia",  "bonus": 3, "duracion_min": 35,
                         "msg": "🥤 La bebida isotónica te repone electrolitos. +3 Resistencia por 35 min."},
}


async def aplicar_buff(user_id, item: str) -> str | None:
    """Añade un buff temporal al personaje. Devuelve el mensaje de sabor o
    None si el item no da ningún buff."""
    info = BUFFS_CONSUMIBLES.get(item)
    if not info:
        return None
    datos = await db.get("personajes", str(user_id)) or {}
    buffs = datos.get("buffs_activos", [])
    buffs.append({
        "item": item,
        "stat": info["stat"],
        "bonus": info["bonus"],
        "expira_ts": time.time() + info["duracion_min"] * 60,
    })
    await db.update("personajes", str(user_id), {"buffs_activos": buffs})
    return info["msg"]


def _limpiar(buffs: list) -> list:
    ahora = time.time()
    return [b for b in buffs if b.get("expira_ts", 0) > ahora]


async def buffs_vigentes(user_id, datos: dict | None = None) -> list:
    """Devuelve los buffs activos (ya filtrados de los vencidos) y limpia en
    la BD los que hayan expirado, para no acumular basura."""
    datos = datos or await db.get("personajes", str(user_id)) or {}
    buffs = datos.get("buffs_activos", [])
    vigentes = _limpiar(buffs)
    if len(vigentes) != len(buffs):
        await db.update("personajes", str(user_id), {"buffs_activos": vigentes})
    return vigentes


async def stats_con_buffs(user_id, datos: dict | None = None) -> dict:
    """Devuelve una COPIA de las stats base con los bonuses temporales ya
    sumados. No modifica la BD (las stats base se guardan limpias)."""
    datos = datos or await db.get("personajes", str(user_id)) or {}
    stats = dict(datos.get("stats", {}))
    for b in await buffs_vigentes(user_id, datos):
        stat = b.get("stat")
        if stat in stats:
            stats[stat] = stats[stat] + b.get("bonus", 0)
    return stats
