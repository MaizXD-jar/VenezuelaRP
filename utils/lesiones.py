"""
utils/lesiones.py — Sistema de lesiones.

Las lesiones se generan al "caer" en una pelea o tiroteo (ver cogs/combate.py)
en vez de morir directamente. Cada lesión penaliza estadísticas mientras esté
activa, sana sola con el tiempo, o se puede tratar antes en el hospital
(ver cogs/hospital.py). Las lesiones más graves tienen riesgo de matar si
nunca se atienden a tiempo.
"""
import time
import random

from utils import db

LESIONES_TIPOS = {
    "contusion": {
        "display": "Contusión leve", "severidad": 1,
        "penalizacion": {"agilidad": -1},
        "duracion_horas": 2, "costo_tratamiento": 20,
        "riesgo_muerte_sin_tratar": False,
    },
    "hueso_roto": {
        "display": "Hueso roto", "severidad": 2,
        "penalizacion": {"fuerza": -2, "agilidad": -2},
        "duracion_horas": 8, "costo_tratamiento": 80,
        "riesgo_muerte_sin_tratar": False,
    },
    "herida_bala": {
        "display": "Herida de bala", "severidad": 3,
        "penalizacion": {"fuerza": -2, "resistencia": -2},
        "duracion_horas": 12, "costo_tratamiento": 200,
        "riesgo_muerte_sin_tratar": False,
    },
    "hemorragia": {
        "display": "Hemorragia interna", "severidad": 4,
        "penalizacion": {"resistencia": -3, "agilidad": -3},
        "duracion_horas": 24, "costo_tratamiento": 450,
        "riesgo_muerte_sin_tratar": True,
    },
    "herida_critica": {
        "display": "Herida crítica", "severidad": 5,
        "penalizacion": {"fuerza": -4, "agilidad": -4, "resistencia": -4},
        "duracion_horas": 48, "costo_tratamiento": 900,
        "riesgo_muerte_sin_tratar": True,
    },
    "sobredosis_leve": {
        "display": "Sobredosis leve", "severidad": 2,
        "penalizacion": {"resistencia": -2, "inteligencia": -1},
        "duracion_horas": 6, "costo_tratamiento": 100,
        "riesgo_muerte_sin_tratar": False,
    },
    "sobredosis_grave": {
        "display": "Sobredosis grave", "severidad": 4,
        "penalizacion": {"resistencia": -3, "agilidad": -2, "inteligencia": -2},
        "duracion_horas": 18, "costo_tratamiento": 350,
        "riesgo_muerte_sin_tratar": True,
    },
}

# Probabilidad de morir CADA VEZ que se revisa (cada hora) una lesión de riesgo
# que ya venció su tiempo y nunca se trató.
PROB_MUERTE_SIN_ATENCION = 0.25


async def agregar_lesion(user_id, tipo: str) -> dict:
    info = LESIONES_TIPOS[tipo]
    lesion = {
        "tipo": tipo,
        "ts_inicio": time.time(),
        "vence_ts": time.time() + info["duracion_horas"] * 3600,
    }
    lista = await db.get("lesiones", str(user_id)) or []
    lista.append(lesion)
    await db.set("lesiones", str(user_id), lista)
    return lesion


async def lesiones_activas(user_id) -> list:
    return await db.get("lesiones", str(user_id)) or []


async def stats_con_penalizacion(user_id, stats_base: dict) -> dict:
    """Devuelve una COPIA de stats_base con las penalizaciones de lesiones activas
    aplicadas. No modifica ni persiste nada — es solo para cálculos puntuales
    (como el daño de combate)."""
    lista = await lesiones_activas(user_id)
    stats = dict(stats_base)
    for lesion in lista:
        info = LESIONES_TIPOS.get(lesion["tipo"], {})
        for stat, valor in info.get("penalizacion", {}).items():
            stats[stat] = max(1, stats.get(stat, 5) + valor)
    return stats


async def curar_lesion(user_id, tipo: str) -> bool:
    lista = await lesiones_activas(user_id)
    for i, lesion in enumerate(lista):
        if lesion["tipo"] == tipo:
            lista.pop(i)
            await db.set("lesiones", str(user_id), lista)
            return True
    return False


async def acortar_lesiones(user_id, factor: float = 0.5):
    """Reduce a la mitad (por defecto) el tiempo restante de todas las lesiones
    activas. Se usa al ingresar formalmente al hospital."""
    lista = await lesiones_activas(user_id)
    ahora = time.time()
    for lesion in lista:
        restante = max(0.0, lesion.get("vence_ts", ahora) - ahora)
        lesion["vence_ts"] = ahora + restante * factor
    await db.set("lesiones", str(user_id), lista)


async def resolver_vencidas(bot):
    """Tarea periódica: las lesiones que ya vencieron sanan solas, salvo las
    de riesgo, que tienen una probabilidad de matar si nunca se atendieron."""
    from utils import muerte as _muerte

    todas = await db.all("lesiones")
    ahora = time.time()
    for uid, lista in list(todas.items()):
        if not lista:
            continue

        restantes = []
        causa_muerte = None
        for lesion in lista:
            if ahora < lesion.get("vence_ts", 0):
                restantes.append(lesion)
                continue
            info = LESIONES_TIPOS.get(lesion["tipo"], {})
            if info.get("riesgo_muerte_sin_tratar") and random.random() < PROB_MUERTE_SIN_ATENCION:
                causa_muerte = f"No recibió atención médica a tiempo ({info.get('display', lesion['tipo'])})."
                break
            # si no arriesga muerte (o se salvó la tirada), simplemente sana sola

        if causa_muerte:
            datos = await db.get("personajes", uid)
            if datos and not datos.get("muerto"):
                await _muerte.procesar_muerte(bot, int(uid), datos, causa=causa_muerte)
            await db.set("lesiones", uid, [])
        elif len(restantes) != len(lista):
            await db.set("lesiones", uid, restantes)
