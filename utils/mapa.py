"""
utils/mapa.py — Mapa completo de Venezuela Roleplay.
Sectores, canales, conexiones de transporte y propiedades.
"""

SECTORES = {
    "petare": {
        "display": "Petare",
        "emoji": "🏚️",
        "peligro": 4,
        "ciudad": "caracas",
        "casas_total": 20,
        "canales": {
            "mercado-negro-petare":    {"emoji": "🖤", "tipo": "mercado",    "peligro": 5, "casas": 0},
            "barrio-jose-felix-ribas": {"emoji": "🏘️", "tipo": "barrio",    "peligro": 4, "casas": 8},
            "barrio-la-union-petare":  {"emoji": "🏠", "tipo": "barrio",    "peligro": 4, "casas": 6},
            "calle-principal-petare":  {"emoji": "🛣️", "tipo": "calle",    "peligro": 3, "casas": 4},
            "parada-bus-petare":       {"emoji": "🚌", "tipo": "transporte","peligro": 2, "casas": 0},
            "metro-petare":            {"emoji": "🚇", "tipo": "transporte","peligro": 2, "casas": 0},
            "casa-abandonada-petare":  {"emoji": "🏚️", "tipo": "peligro",  "peligro": 5, "casas": 0},
        }
    },
    "las-mercedes": {
        "display": "Las Mercedes",
        "emoji": "🌟",
        "peligro": 1,
        "ciudad": "caracas",
        "casas_total": 15,
        "canales": {
            "av-rio-de-janeiro":    {"emoji": "🛣️", "tipo": "avenida",   "peligro": 1, "casas": 0},
            "cc-sambil-mercedes":   {"emoji": "🏬", "tipo": "comercio",  "peligro": 1, "casas": 0},
            "restaurante-zona":     {"emoji": "🍽️", "tipo": "comercio",  "peligro": 1, "casas": 0},
            "residencias-mercedes": {"emoji": "🏡", "tipo": "barrio",    "peligro": 1, "casas": 10},
            "parada-bus-mercedes":  {"emoji": "🚌", "tipo": "transporte","peligro": 1, "casas": 0},
            "banco-mercantil":      {"emoji": "🏦", "tipo": "banco",     "peligro": 1, "casas": 0},
            "concesionario-toyota": {"emoji": "🚗", "tipo": "concesionario", "peligro": 1, "casas": 0},
        }
    },
    "distrito-capital": {
        "display": "Distrito Capital",
        "emoji": "🏛️",
        "peligro": 2,
        "ciudad": "caracas",
        "casas_total": 10,
        "canales": {
            "banco-central-venezuela": {"emoji": "🏦", "tipo": "banco",      "peligro": 1, "casas": 0},
            "palacio-miraflores":      {"emoji": "🏛️", "tipo": "gobierno",   "peligro": 2, "casas": 0},
            "av-urdaneta":             {"emoji": "🛣️", "tipo": "avenida",    "peligro": 2, "casas": 0},
            "metro-capitolio":         {"emoji": "🚇", "tipo": "transporte", "peligro": 2, "casas": 0},
            "tribunal-supremo":        {"emoji": "⚖️", "tipo": "gobierno",   "peligro": 1, "casas": 0},
            "comisaria-libertador":    {"emoji": "🚔", "tipo": "policia",    "peligro": 1, "casas": 0},
            "hospital-vargas":         {"emoji": "🏥", "tipo": "hospital",   "peligro": 1, "casas": 0},
            "concesionario-capital":   {"emoji": "🚗", "tipo": "concesionario","peligro": 1,"casas": 0},
        }
    },
    "23-de-enero": {
        "display": "23 de Enero",
        "emoji": "🔴",
        "peligro": 4,
        "ciudad": "caracas",
        "casas_total": 20,
        "canales": {
            "bloques-23-enero":  {"emoji": "🏢", "tipo": "barrio",    "peligro": 4, "casas": 12},
            "calle-norte-2":     {"emoji": "🛣️", "tipo": "calle",    "peligro": 3, "casas": 0},
            "mercado-23":        {"emoji": "🛒", "tipo": "mercado",   "peligro": 3, "casas": 0},
            "colectivos-zona":   {"emoji": "⚠️", "tipo": "peligro",   "peligro": 5, "casas": 0},
            "parada-bus-23":     {"emoji": "🚌", "tipo": "transporte","peligro": 3, "casas": 0},
        }
    },
    "ciudad-universitaria": {
        "display": "Ciudad Universitaria",
        "emoji": "🎓",
        "peligro": 2,
        "ciudad": "caracas",
        "casas_total": 10,
        "canales": {
            "ucv-campus":        {"emoji": "🏫", "tipo": "educacion", "peligro": 2, "casas": 0},
            "biblioteca-central":{"emoji": "📚", "tipo": "educacion", "peligro": 1, "casas": 0},
            "residencias-ucv":   {"emoji": "🏠", "tipo": "barrio",    "peligro": 2, "casas": 6},
            "cafeteria-ucv":     {"emoji": "☕", "tipo": "comercio",  "peligro": 1, "casas": 0},
            "estadio-ucv":       {"emoji": "⚽", "tipo": "recreacion","peligro": 1, "casas": 0},
            "metro-ciudad-univ": {"emoji": "🚇", "tipo": "transporte","peligro": 1, "casas": 0},
        }
    },
    "miranda": {
        "display": "Miranda",
        "emoji": "🌳",
        "peligro": 2,
        "ciudad": "caracas",
        "casas_total": 15,
        "canales": {
            "los-palos-grandes":    {"emoji": "🏡", "tipo": "barrio",    "peligro": 1, "casas": 8},
            "chacao":               {"emoji": "🏙️", "tipo": "barrio",    "peligro": 2, "casas": 6},
            "cc-sambil-chacao":     {"emoji": "🏬", "tipo": "comercio",  "peligro": 1, "casas": 0},
            "policia-miranda":      {"emoji": "🚔", "tipo": "policia",   "peligro": 1, "casas": 0},
            "hospital-de-clinicas": {"emoji": "🏥", "tipo": "hospital",  "peligro": 1, "casas": 0},
            "metro-chacao":         {"emoji": "🚇", "tipo": "transporte","peligro": 1, "casas": 0},
            "estacion-tren-miranda":{"emoji": "🚂", "tipo": "transporte","peligro": 1, "casas": 0},
        }
    },
    "la-alameda": {
        "display": "La Alameda",
        "emoji": "🌲",
        "peligro": 2,
        "ciudad": "caracas",
        "casas_total": 15,
        "canales": {
            "residencias-alameda":{"emoji": "🏘️", "tipo": "barrio",    "peligro": 2, "casas": 8},
            "plaza-alameda":      {"emoji": "🏞️", "tipo": "recreacion","peligro": 2, "casas": 0},
            "bodega-alameda":     {"emoji": "🏪", "tipo": "comercio",  "peligro": 2, "casas": 0},
            "parada-bus-alameda": {"emoji": "🚌", "tipo": "transporte","peligro": 2, "casas": 0},
        }
    },
    "la-trinidad": {
        "display": "La Trinidad",
        "emoji": "💎",
        "peligro": 1,
        "ciudad": "caracas",
        "casas_total": 15,
        "canales": {
            "residencias-trinidad":{"emoji": "🏡", "tipo": "barrio",   "peligro": 1, "casas": 10},
            "gym-trinidad":        {"emoji": "💪", "tipo": "deporte",  "peligro": 1, "casas": 0},
            "restaurante-trinidad":{"emoji": "🍽️", "tipo": "comercio","peligro": 1, "casas": 0},
            "parada-bus-trinidad": {"emoji": "🚌", "tipo": "transporte","peligro": 1,"casas": 0},
            "banesco-trinidad":    {"emoji": "🏦", "tipo": "banco",    "peligro": 1, "casas": 0},
            "rent-a-car-trinidad": {"emoji": "🚗", "tipo": "concesionario","peligro": 1,"casas": 0},
        }
    },
    # ── EL MONTE ──────────────────────────────────────────────────────────────
    "el-monte": {
        "display": "El Monte",
        "emoji": "🌿",
        "peligro": 5,
        "ciudad": "caracas",
        "casas_total": 8,
        "canales": {
            "monte-entrada":           {"emoji": "🌿", "tipo": "calle",  "peligro": 4, "casas": 0},
            "monte-profundo":          {"emoji": "🌳", "tipo": "peligro","peligro": 5, "casas": 0},
            "casas-abandonadas-monte": {"emoji": "🏚️", "tipo": "barrio", "peligro": 5, "casas": 8},
            "rio-guaire":              {"emoji": "💧", "tipo": "general", "peligro": 4, "casas": 0},
            "laboratorio-monte":       {"emoji": "🧪", "tipo": "peligro","peligro": 5, "casas": 0},
        }
    },
    # ── OTRAS CIUDADES VENEZUELA ──────────────────────────────────────────────
    "maracaibo": {
        "display": "Maracaibo",
        "emoji": "🌅",
        "peligro": 3,
        "ciudad": "maracaibo",
        "casas_total": 15,
        "canales": {
            "centro-maracaibo":    {"emoji": "🏙️", "tipo": "barrio",    "peligro": 3, "casas": 6},
            "lago-maracaibo":      {"emoji": "🌊", "tipo": "recreacion","peligro": 2, "casas": 0},
            "mercado-las-pulgas":  {"emoji": "🛒", "tipo": "mercado",   "peligro": 4, "casas": 0},
            "terminal-maracaibo":  {"emoji": "🚌", "tipo": "transporte","peligro": 3, "casas": 0},
            "hospital-maracaibo":  {"emoji": "🏥", "tipo": "hospital",  "peligro": 2, "casas": 0},
            "aeropuerto-maracaibo":{"emoji": "✈️", "tipo": "transporte","peligro": 1, "casas": 0},
            "banco-occidental":    {"emoji": "🏦", "tipo": "banco",     "peligro": 1, "casas": 0},
        }
    },
    "valencia": {
        "display": "Valencia",
        "emoji": "🏭",
        "peligro": 3,
        "ciudad": "valencia",
        "casas_total": 15,
        "canales": {
            "zona-industrial-val": {"emoji": "🏭", "tipo": "trabajo",   "peligro": 2, "casas": 0},
            "centro-valencia":     {"emoji": "🏙️", "tipo": "barrio",    "peligro": 3, "casas": 8},
            "terminal-valencia":   {"emoji": "🚌", "tipo": "transporte","peligro": 3, "casas": 0},
            "cc-sambil-valencia":  {"emoji": "🏬", "tipo": "comercio",  "peligro": 1, "casas": 0},
            "aeropuerto-valencia": {"emoji": "✈️", "tipo": "transporte","peligro": 1, "casas": 0},
        }
    },
    # ── INTERNACIONALES ───────────────────────────────────────────────────────
    "medellin": {
        "display": "Medellín, Colombia",
        "emoji": "🇨🇴",
        "peligro": 3,
        "ciudad": "medellin",
        "casas_total": 10,
        "canales": {
            "el-poblado-medellin": {"emoji": "🏙️", "tipo": "barrio",    "peligro": 2, "casas": 4},
            "metro-medellin":      {"emoji": "🚇", "tipo": "transporte","peligro": 2, "casas": 0},
            "aeropuerto-rionegro": {"emoji": "✈️", "tipo": "transporte","peligro": 1, "casas": 0},
            "mercado-medellin":    {"emoji": "🛒", "tipo": "mercado",   "peligro": 3, "casas": 0},
        }
    },
    "bogota": {
        "display": "Bogotá, Colombia",
        "emoji": "🇨🇴",
        "peligro": 2,
        "ciudad": "bogota",
        "casas_total": 10,
        "canales": {
            "candelaria-bogota": {"emoji": "🏛️", "tipo": "barrio",    "peligro": 3, "casas": 2},
            "aeropuerto-bogota": {"emoji": "✈️", "tipo": "transporte","peligro": 1, "casas": 0},
            "transmilenio":      {"emoji": "🚌", "tipo": "transporte","peligro": 2, "casas": 0},
        }
    },
    "miami": {
        "display": "Miami, USA",
        "emoji": "🇺🇸",
        "peligro": 1,
        "ciudad": "miami",
        "casas_total": 10,
        "canales": {
            "little-havana-miami":{"emoji": "🌴", "tipo": "barrio",    "peligro": 2, "casas": 4},
            "south-beach":        {"emoji": "🏖️", "tipo": "recreacion","peligro": 1, "casas": 0},
            "aeropuerto-miami":   {"emoji": "✈️", "tipo": "transporte","peligro": 1, "casas": 0},
            "doral-miami":        {"emoji": "🏘️", "tipo": "barrio",    "peligro": 1, "casas": 6},
            "car-dealership-miami":{"emoji": "🚗","tipo": "concesionario","peligro": 1,"casas": 0},
            "casino-fontainebleau-miami": {"emoji": "🎰", "tipo": "recreacion", "peligro": 1, "casas": 0},
        }
    },
    # ── PRISIÓN DE YARE ───────────────────────────────────────────────────────
    "prision-yare": {
        "display": "Prisión de Yare",
        "emoji": "⛓️",
        "peligro": 5,
        "ciudad": "miranda",
        "casas_total": 0,
        "canales": {
            "celda-yare":            {"emoji": "🔒", "tipo": "celda",   "peligro": 4, "casas": 0},
            "patio-yare":            {"emoji": "🏛️", "tipo": "patio",   "peligro": 5, "casas": 0},
            "oficina-director-yare": {"emoji": "📋", "tipo": "oficina", "peligro": 1, "casas": 0},
            "celda-1":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-2":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-3":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-4":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-5":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-6":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-7":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-8":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-9":  {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
            "celda-10": {"emoji": "🔒", "tipo": "celda", "peligro": 3, "casas": 0},
        }
    },
}

# ── TIEMPOS DE VIAJE (minutos) entre sectores ─────────────────────────────────
TIEMPOS_VIAJE = {
    ("petare", "distrito-capital"):          {"caminar": 90, "metro": 25, "autobus": 40, "coche": 20, "bicicleta": 45},
    ("petare", "miranda"):                   {"caminar": 60, "metro": 15, "autobus": 25, "coche": 15, "bicicleta": 30},
    ("petare", "las-mercedes"):              {"caminar": 100,"metro": 30, "autobus": 50, "coche": 25, "bicicleta": 55},
    ("petare", "23-de-enero"):               {"caminar": 70, "metro": 20, "autobus": 35, "coche": 20, "bicicleta": 40},
    ("petare", "el-monte"):                  {"caminar": 40, "coche": 20, "bicicleta": 30},
    ("distrito-capital", "23-de-enero"):     {"caminar": 40, "metro": 10, "autobus": 20, "coche": 12, "bicicleta": 20},
    ("distrito-capital", "ciudad-universitaria"):{"caminar":50,"metro":15,"autobus":25,"coche":15,"bicicleta":25},
    ("distrito-capital", "la-alameda"):      {"caminar": 35, "metro": 12, "autobus": 20, "coche": 12, "bicicleta": 18},
    ("miranda", "las-mercedes"):             {"caminar": 30, "metro": 10, "autobus": 15, "coche": 10, "bicicleta": 15},
    ("miranda", "la-trinidad"):              {"caminar": 45, "autobus": 20, "coche": 15, "bicicleta": 25},
    ("las-mercedes", "la-trinidad"):         {"caminar": 35, "autobus": 15, "coche": 12, "bicicleta": 20},
    ("la-alameda", "23-de-enero"):           {"caminar": 50, "autobus": 20, "coche": 15, "bicicleta": 25},
    ("miranda", "ciudad-universitaria"):     {"caminar": 40, "metro": 12, "autobus": 20, "coche": 12, "bicicleta": 20},
    ("el-monte", "petare"):                  {"caminar": 40, "coche": 20, "bicicleta": 30},
    ("el-monte", "23-de-enero"):             {"caminar": 55, "coche": 25, "bicicleta": 40},
    # Viajes entre ciudades venezolanas
    ("distrito-capital", "maracaibo"):       {"autobus": 600, "coche": 480, "avion": 60},
    ("distrito-capital", "valencia"):        {"autobus": 180, "coche": 150, "tren": 120},
    ("maracaibo", "valencia"):               {"autobus": 420, "coche": 360, "avion": 50},
    # Viajes internacionales
    ("distrito-capital", "medellin"):        {"autobus": 1440,"coche": 1200,"avion": 90},
    ("distrito-capital", "bogota"):          {"autobus": 1560,"coche": 1320,"avion": 100},
    ("distrito-capital", "miami"):           {"avion": 210},
    ("medellin", "bogota"):                  {"autobus": 240, "coche": 180, "avion": 45},
    ("miami", "bogota"):                     {"avion": 180},
    # Prisión
    ("miranda", "prision-yare"):             {"coche": 45, "autobus": 60},
    ("distrito-capital", "prision-yare"):    {"coche": 50, "autobus": 70},
    ("prision-yare", "prision-yare"):        {"caminar": 1},
}


def get_tiempo(origen: str, destino: str, metodo: str) -> int:
    key = (origen, destino)
    rev = (destino, origen)
    rutas = TIEMPOS_VIAJE.get(key) or TIEMPOS_VIAJE.get(rev) or {}
    return rutas.get(metodo, 0)


def _slug_sector(texto: str, max_len: int = 12) -> str:
    """Replica el slug que usa cogs/propiedades.py al renombrar canales de casas."""
    import re as _re
    t = texto.lower()
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        t = t.replace(src, dst)
    t = _re.sub(r'[^a-z0-9\-]', '-', t)
    t = _re.sub(r'-+', '-', t).strip('-')
    return t[:max_len]


def sector_de_canal_casa(canal: str) -> str | None:
    """Los canales de casas NO están en SECTORES['canales'] porque se renombran
    dinámicamente al comprarlas: `casa-{N}-{sector_slug}` o
    `casa-{N}-{sector_slug}-{nombre}`. Antes esto hacía que get_sector_de_canal()
    devolviera None para cualquier casa comprada, y por eso era imposible viajar
    desde o hacia una casa ("no hay ruta", "canal no encontrado en el mapa").
    Aquí se deduce el sector a partir del nombre del canal."""
    if not canal or not canal.startswith("casa-"):
        return None
    partes = canal.split("-")
    if len(partes) < 3:
        return None  # "casa-5" a secas: sin sector, ambiguo entre sectores
    # El slug del sector puede tener guiones (ej: las-mercedes), así que se prueba
    # de la coincidencia más larga a la más corta.
    resto = partes[2:]
    for n in range(len(resto), 0, -1):
        candidato = "-".join(resto[:n])
        for sec_key in SECTORES:
            if _slug_sector(sec_key) == candidato:
                return sec_key
    return None


def get_sector_de_canal(canal: str) -> str | None:
    for sec_key, sec in SECTORES.items():
        if canal in sec["canales"]:
            return sec_key
    return sector_de_canal_casa(canal)


def es_canal_casa(canal: str) -> bool:
    return bool(canal) and canal.startswith("casa-")


def get_canal_info(canal: str) -> dict | None:
    for sec in SECTORES.values():
        if canal in sec["canales"]:
            return sec["canales"][canal]
    if es_canal_casa(canal):
        sector = sector_de_canal_casa(canal)
        if sector:
            return {"emoji": "🏠", "tipo": "vivienda", "peligro": 1, "casas": 1}
    return None


def metodos_disponibles(sector: str) -> list[str]:
    metodos = ["caminar"]
    sec = SECTORES.get(sector, {})
    canales = sec.get("canales", {})
    for nombre in canales:
        if "metro" in nombre:
            metodos.append("metro")
        if "bus" in nombre or "terminal" in nombre or "parada" in nombre:
            metodos.append("autobus")
        if "tren" in nombre or "estacion-tren" in nombre:
            metodos.append("tren")
        if "aeropuerto" in nombre:
            metodos.append("avion")
    return list(set(metodos))


# ── PATHFINDING (rutas con escalas) ───────────────────────────────────────────
# Antes, si no había una ruta DIRECTA entre dos sectores, /rutas simplemente
# decía "usa escalas" sin decir cuáles, y !viajar solo probaba una escala fija
# con el mismo método en ambos tramos. Esto calcula la ruta real más rápida
# (Dijkstra) combinando cualquier número de tramos y métodos distintos.
TRANSFER_OVERHEAD_MIN = 10  # minutos extra por cada transbordo (espera, caminata a la parada, etc.)


def _grafo_viaje() -> dict:
    """Construye un grafo no dirigido: sector -> {vecino: (minutos, metodo)} usando
    siempre el método más rápido disponible para cada tramo directo."""
    grafo: dict[str, dict[str, tuple[int, str]]] = {}
    for (a, b), metodos in TIEMPOS_VIAJE.items():
        if not metodos:
            continue
        metodo_mejor = min(metodos, key=lambda m: metodos[m])
        tiempo_mejor = metodos[metodo_mejor]
        grafo.setdefault(a, {})
        if b not in grafo[a] or tiempo_mejor < grafo[a][b][0]:
            grafo[a][b] = (tiempo_mejor, metodo_mejor)
        grafo.setdefault(b, {})
        if a not in grafo[b] or tiempo_mejor < grafo[b][a][0]:
            grafo[b][a] = (tiempo_mejor, metodo_mejor)
    return grafo


def mejor_ruta(origen: str, destino: str) -> dict | None:
    """Dijkstra sobre el grafo de sectores. Devuelve:
        {"pasos": [(desde, hasta, metodo, minutos_tramo), ...], "total_minutos": int}
    o None si no existe ningún camino (ni con escalas) entre origen y destino.
    Cada transbordo entre pasos suma TRANSFER_OVERHEAD_MIN minutos extra."""
    if origen == destino:
        return {"pasos": [], "total_minutos": 0}

    import heapq
    grafo = _grafo_viaje()
    dist = {origen: 0}
    prev: dict[str, tuple[str, str, int]] = {}
    visitado = set()
    heap = [(0, origen)]

    while heap:
        d, nodo = heapq.heappop(heap)
        if nodo in visitado:
            continue
        visitado.add(nodo)
        if nodo == destino:
            break
        for vecino, (tiempo, metodo) in grafo.get(nodo, {}).items():
            extra = TRANSFER_OVERHEAD_MIN if nodo in prev else 0  # transbordo si no es el origen
            nd = d + tiempo + extra
            if nd < dist.get(vecino, float("inf")):
                dist[vecino] = nd
                prev[vecino] = (nodo, metodo, tiempo)
                heapq.heappush(heap, (nd, vecino))

    if destino not in dist:
        return None

    pasos = []
    cur = destino
    while cur in prev:
        anterior, metodo, tiempo = prev[cur]
        pasos.append((anterior, cur, metodo, tiempo))
        cur = anterior
    pasos.reverse()
    return {"pasos": pasos, "total_minutos": dist[destino]}


CANALES_PUBLICOS = {
    "canal-info-drogas":        1359320811420520614,
    "canal-info-robos":         1359412448976965713,
    "canal-info-precios":       1359320811420520609,
    "canal-comprar-vehic":      1369438606694944799,
    "canal-personajes-muertos": 1359320811420520613,
    "canal-mas-buscados":       1369438636260724856,
    "canal-info-trabajos":      1369365887156617428,
}

PELIGRO_EFECTOS = {
    1: {"robo_prob": 0.01, "tiroteo_prob": 0.001, "evento_random_prob": 0.05},
    2: {"robo_prob": 0.03, "tiroteo_prob": 0.005, "evento_random_prob": 0.08},
    3: {"robo_prob": 0.08, "tiroteo_prob": 0.02,  "evento_random_prob": 0.12},
    4: {"robo_prob": 0.15, "tiroteo_prob": 0.05,  "evento_random_prob": 0.18},
    5: {"robo_prob": 0.25, "tiroteo_prob": 0.10,  "evento_random_prob": 0.25},
}