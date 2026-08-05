"""
utils/armas.py — Catálogo completo de armas, herramientas y equipamiento defensivo.
"""

# ── ARMAS CUERPO A CUERPO ─────────────────────────────────────────────────────
ARMAS_MELEE = {
    "navaja":              {"daño": 12, "precio": 15,   "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Navaja de bolsillo. Fácil de ocultar."},
    "cuchillo_cocina":     {"daño": 14, "precio": 8,    "tipo": "melee", "ilegal": False, "ocultable": True,  "descripcion": "Cuchillo de cocina reutilizado como arma."},
    "cuchillo_militar":    {"daño": 22, "precio": 80,   "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Cuchillo militar de combate. Muy peligroso."},
    "punio_americano":     {"daño": 18, "precio": 25,   "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Puños americanos. +daño melee, fácil de ocultar."},
    "bate_baseball":       {"daño": 25, "precio": 30,   "tipo": "melee", "ilegal": False, "ocultable": False, "descripcion": "Bate de béisbol de madera. Arma contundente."},
    "bate_metal":          {"daño": 30, "precio": 45,   "tipo": "melee", "ilegal": False, "ocultable": False, "descripcion": "Bate de béisbol metálico. Más daño que el de madera."},
    "palo":                {"daño": 10, "precio": 0,    "tipo": "melee", "ilegal": False, "ocultable": False, "descripcion": "Un palo cualquiera. Daño mínimo."},
    "machete":             {"daño": 35, "precio": 25,   "tipo": "melee", "ilegal": True,  "ocultable": False, "descripcion": "El machete venezolano clásico."},
    "hacha":               {"daño": 40, "precio": 40,   "tipo": "melee", "ilegal": True,  "ocultable": False, "descripcion": "Hacha de leña adaptada."},
    "daga":                {"daño": 28, "precio": 60,   "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Daga de doble filo."},
    "martillo":            {"daño": 22, "precio": 15,   "tipo": "melee", "ilegal": False, "ocultable": False, "descripcion": "Martillo de ferretería."},
    "destornillador":      {"daño": 8,  "precio": 5,    "tipo": "melee", "ilegal": False, "ocultable": True,  "descripcion": "Destornillador improvisado como arma."},
    "punial_improvisado":  {"daño": 15, "precio": 10,   "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Punzón artesanal. Hecho con materiales del entorno."},
    "cuchillo":            {"daño": 15, "precio": 8,    "tipo": "melee", "ilegal": True,  "ocultable": True,  "descripcion": "Cuchillo genérico."},
}

# ── PISTOLAS ──────────────────────────────────────────────────────────────────
PISTOLAS = {
    "glock_17":            {"daño": 38, "precio": 450,  "tipo": "pistola", "ilegal": True,  "municion": "9mm",   "cargador": 17, "descripcion": "Glock 17 — la más común. Confiable y ligera."},
    "beretta_92":          {"daño": 36, "precio": 500,  "tipo": "pistola", "ilegal": True,  "municion": "9mm",   "cargador": 15, "descripcion": "Beretta 92. Pistola italiana clásica."},
    "sig_sauer_p320":      {"daño": 40, "precio": 600,  "tipo": "pistola", "ilegal": True,  "municion": "9mm",   "cargador": 17, "descripcion": "SIG Sauer P320. Muy precisa."},
    "colt_m1911":          {"daño": 45, "precio": 700,  "tipo": "pistola", "ilegal": True,  "municion": ".45ACP","cargador": 7,  "descripcion": "Colt M1911. Clásico americano. Mucho daño."},
    "desert_eagle":        {"daño": 65, "precio": 1500, "tipo": "pistola", "ilegal": True,  "municion": ".50AE", "cargador": 7,  "descripcion": "Desert Eagle. Monstruosa. Máximo daño entre pistolas."},
    "fn_five_seven":       {"daño": 42, "precio": 800,  "tipo": "pistola", "ilegal": True,  "municion": "5.7mm", "cargador": 20, "descripcion": "FN Five-seveN. Perfora chalecos básicos."},
    "sw_model_29":         {"daño": 60, "precio": 900,  "tipo": "revolver","ilegal": True,  "municion": ".44Mag","cargador": 6,  "descripcion": "Smith & Wesson Model 29. El Dirty Harry."},
    "colt_python":         {"daño": 55, "precio": 1100, "tipo": "revolver","ilegal": True,  "municion": ".357",  "cargador": 6,  "descripcion": "Colt Python. Revólver de precisión élite."},
    "ruger_gp100":         {"daño": 52, "precio": 750,  "tipo": "revolver","ilegal": True,  "municion": ".357",  "cargador": 6,  "descripcion": "Ruger GP100. Robusto y fiable."},
}

# ── SUBFUSILES / SMG ──────────────────────────────────────────────────────────
SUBFUSILES = {
    "mp5":                 {"daño": 42, "precio": 2500,  "tipo": "smg",    "ilegal": True, "municion": "9mm",   "cargador": 30, "descripcion": "HK MP5. Arma de las fuerzas especiales."},
    "uzi":                 {"daño": 38, "precio": 1800,  "tipo": "smg",    "ilegal": True, "municion": "9mm",   "cargador": 32, "descripcion": "Uzi israelí. Cadencia alta."},
    "kriss_vector":        {"daño": 44, "precio": 3000,  "tipo": "smg",    "ilegal": True, "municion": ".45ACP","cargador": 25, "descripcion": "Kriss Vector. Muy baja vibración."},
    "fn_p90":              {"daño": 46, "precio": 3500,  "tipo": "smg",    "ilegal": True, "municion": "5.7mm", "cargador": 50, "descripcion": "FN P90. Compacto y letal."},
}

# ── RIFLES DE ASALTO ──────────────────────────────────────────────────────────
RIFLES = {
    "ak47":                {"daño": 58, "precio": 3000,  "tipo": "rifle",  "ilegal": True, "municion": "7.62mm","cargador": 30, "descripcion": "AK-47. El más conocido del mundo."},
    "m4_carbine":          {"daño": 55, "precio": 3500,  "tipo": "rifle",  "ilegal": True, "municion": "5.56mm","cargador": 30, "descripcion": "M4 Carbine. Versátil y preciso."},
    "hk416":               {"daño": 57, "precio": 4000,  "tipo": "rifle",  "ilegal": True, "municion": "5.56mm","cargador": 30, "descripcion": "HK416. Usado por Fuerzas Especiales."},
    "fn_scar":             {"daño": 62, "precio": 5000,  "tipo": "rifle",  "ilegal": True, "municion": "7.62mm","cargador": 20, "descripcion": "FN SCAR. Alta precisión a largo alcance."},
    "steyr_aug":           {"daño": 54, "precio": 4200,  "tipo": "rifle",  "ilegal": True, "municion": "5.56mm","cargador": 30, "descripcion": "Steyr AUG. Bullpup austríaco."},
    "ar15":                {"daño": 52, "precio": 2800,  "tipo": "rifle",  "ilegal": True, "municion": "5.56mm","cargador": 30, "descripcion": "AR-15 semi-automático."},
    "ak103":               {"daño": 60, "precio": 3200,  "tipo": "rifle",  "ilegal": True, "municion": "7.62mm","cargador": 30, "descripcion": "AK-103. Versión mejorada del AK. Usado por FANB."},
    "cavim_caribe":        {"daño": 50, "precio": 2500,  "tipo": "rifle",  "ilegal": True, "municion": "5.56mm","cargador": 30, "descripcion": "CAVIM Caribe. Fabricado en Venezuela."},
}

# ── ESCOPETAS ─────────────────────────────────────────────────────────────────
ESCOPETAS = {
    "remington_870":       {"daño": 70, "precio": 1200,  "tipo": "escopeta","ilegal": True, "municion": "12g",   "cargador": 7,  "descripcion": "Remington 870. Devastadora a corta distancia."},
    "mossberg_500":        {"daño": 68, "precio": 900,   "tipo": "escopeta","ilegal": True, "municion": "12g",   "cargador": 6,  "descripcion": "Mossberg 500. Clásica y fiable."},
    "benelli_m4":          {"daño": 75, "precio": 2000,  "tipo": "escopeta","ilegal": True, "municion": "12g",   "cargador": 7,  "descripcion": "Benelli M4. Semi-auto. Usada por militares."},
    "escopeta_goma":       {"daño": 25, "precio": 800,   "tipo": "escopeta","ilegal": False,"municion": "goma",  "cargador": 5,  "descripcion": "Escopeta de balas de goma. Uso policial. No letal."},
}

# ── FRANCOTIRADOR ─────────────────────────────────────────────────────────────
FRANCOTIRADORES = {
    "barrett_m82":         {"daño": 120,"precio": 8000,  "tipo": "sniper",  "ilegal": True, "municion": ".50BMG","cargador": 10, "descripcion": "Barrett M82. Anti-material. Devastador."},
}

# ── EQUIPAMIENTO POLICIAL / DEFENSIVO ─────────────────────────────────────────
EQUIPO_DEFENSIVO = {
    "chaleco_antibalas":   {"defensa": 30, "precio": 300,  "tipo": "armadura", "ilegal": False, "descripcion": "Reduce el daño de bala un 30%. Nivel IIIA."},
    "casco_antidisturbios":{"defensa": 15, "precio": 150,  "tipo": "armadura", "ilegal": False, "descripcion": "Protege la cabeza. Policial."},
    "escudo":              {"defensa": 40, "precio": 500,  "tipo": "armadura", "ilegal": False, "descripcion": "Escudo antidisturbios. Reduce daño físico masivamente."},
    "escudo_casco":        {"defensa": 55, "precio": 650,  "tipo": "armadura", "ilegal": False, "descripcion": "Combinación escudo + casco. Protección máxima."},
}

# ── EQUIPO POLICIAL ───────────────────────────────────────────────────────────
EQUIPO_POLICIAL = {
    "radio":               {"precio": 80,   "tipo": "equipo", "descripcion": "Radio de comunicaciones policial."},
    "linterna":            {"precio": 25,   "tipo": "equipo", "descripcion": "Linterna táctica."},
    "baston_policial":     {"precio": 50,   "tipo": "equipo", "daño": 18,   "descripcion": "Bastón policial. Uso legítimo en fuerzas del orden."},
    "lanzador_gas":        {"precio": 400,  "tipo": "equipo", "daño": 5,    "descripcion": "Lanzador de gas lacrimógeno. Incapacita."},
    "esposas":             {"precio": 30,   "tipo": "equipo", "descripcion": "Esposas de policía. Para arrestar."},
}

# ── CATÁLOGO UNIFICADO ────────────────────────────────────────────────────────
TODAS_LAS_ARMAS = {
    **ARMAS_MELEE,
    **PISTOLAS,
    **SUBFUSILES,
    **RIFLES,
    **ESCOPETAS,
    **FRANCOTIRADORES,
}

TODO_EQUIPO = {
    **EQUIPO_DEFENSIVO,
    **EQUIPO_POLICIAL,
}

def get_daño(arma: str) -> int:
    """Retorna el daño de un arma, 0 si no es arma."""
    if arma in TODAS_LAS_ARMAS:
        return TODAS_LAS_ARMAS[arma].get("daño", 0)
    if arma in EQUIPO_POLICIAL:
        return EQUIPO_POLICIAL[arma].get("daño", 0)
    return 0

def get_defensa(equipo: str) -> int:
    """Retorna la defensa de un equipo."""
    if equipo in EQUIPO_DEFENSIVO:
        return EQUIPO_DEFENSIVO[equipo].get("defensa", 0)
    return 0

def calcular_defensa_total(inventario: dict) -> int:
    """Calcula la reducción total de daño por equipo defensivo."""
    total = 0
    for item in inventario:
        total += get_defensa(item)
    return min(total, 80)  # máximo 80% reducción

def es_arma_de_fuego(arma: str) -> bool:
    fuego = {**PISTOLAS, **SUBFUSILES, **RIFLES, **ESCOPETAS, **FRANCOTIRADORES}
    return arma in fuego

def es_arma_ilegal(arma: str) -> bool:
    if arma in TODAS_LAS_ARMAS:
        return TODAS_LAS_ARMAS[arma].get("ilegal", False)
    return False

# ── ARMAS BLANCAS (cuchillos, navajas, dagas...) ──────────────────────────────
# Un arma de filo es mortal a corta distancia: en combate cuerpo a cuerpo tiene
# alta probabilidad de clavarse una puñalada extra, a diferencia de un arma
# contundente (bate, palo, martillo...).
ARMAS_CORTANTES = {
    "navaja", "cuchillo_cocina", "cuchillo_militar", "daga",
    "punial_improvisado", "cuchillo", "machete",
}


def es_arma_cortante(arma: str) -> bool:
    return arma in ARMAS_CORTANTES

# Categorías para la tienda
CATEGORIAS_ARMAS = {
    "melee": ARMAS_MELEE,
    "pistola": PISTOLAS,
    "smg": SUBFUSILES,
    "rifle": RIFLES,
    "escopeta": ESCOPETAS,
    "sniper": FRANCOTIRADORES,
    "armadura": EQUIPO_DEFENSIVO,
    "equipo_policial": EQUIPO_POLICIAL,
}