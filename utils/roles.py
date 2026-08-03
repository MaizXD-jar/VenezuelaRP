"""
utils/roles.py — Todos los IDs de roles del servidor y helpers.
"""

# ── ROLES DE ESTADO ───────────────────────────────────────────────────────────
ROL_MUERTO           = 1359320808585035788
ROL_INFORMATICO      = 1359320808585035790
ROL_GRADUADO         = 1359320808585035786
ROL_ESTUDIANTE       = 1359320808585035794
ROL_MANTENIDO        = 1359320808585035792
ROL_EXTRANJERO       = 1359320808593559663
ROL_PRIMARIA         = 1359320808509538340
ROL_CRIMINAL         = 1359320808509538343
ROL_PRISIONERO       = 1360251875470868550
ROL_UNIVERSITARIO    = 1359320808509538342
ROL_SECUNDARIA       = 1359320808509538341
ROL_CIUDADANO        = 1369362859188027543
ROL_INDOCUMENTADO    = 1359320808463274144
ROL_HOMBRE           = 1359320808526450786
ROL_MUJER            = 1359320808526450785

# ── ROLES DE TRABAJO ──────────────────────────────────────────────────────────
ROL_PANADERO         = 1359320808526450784
ROL_MEDICO           = 1359320808585035789
ROL_FUNCIONARIO      = 1359320808585035793
ROL_QUIMICO          = 1359320808585035787
ROL_INGENIERO        = 1359320808572321908
ROL_PESCADERO        = 1359320808526450782
ROL_GANADERO         = 1359320808526450781
ROL_MAESTRO          = 1359320808526450779
ROL_VENDEDOR         = 1359320808526450778
ROL_BOMBERO          = 1359320808509538345
ROL_CIRUJANO         = 1359320808509538344
ROL_PRODUCTOR_EXEC   = 1382432319276716082
ROL_FANB             = 1382433542814040084
ROL_EJERCITO         = 1382433888852381828
ROL_SEBIN            = 1382434157858390016
ROL_ABOGADO          = 1382434498758836366
ROL_JEFE_PRENSA      = 1382434978993803274
ROL_EDITOR_NOTICIAS  = 1382435203863023626
ROL_CORRESPONSAL     = 1382435453466050570
ROL_REPORTERO        = 1382435679627251913
ROL_GUARDIA_PRISION  = 1382435925111472229
ROL_POLICIA_CNPB     = 1359320808526450780  # Cuerpo de Policía Nacional Bolivariana

# ── ROLES DE SALARIO ──────────────────────────────────────────────────────────
ROLES_SALARIO = {
    "minimo":     1359320808572321909,
    "bajo":       1369552405435514951,
    "medio_bajo": 1369553098338734120,
    "medio":      1359320808572321910,
    "medio_alto": 1369553333643378739,
    "alto":       1359320808572321911,
    "muy_alto":   1369553498974326876,
    "extranjero": 1359320808593559663,
}

# ── SALARIOS BASE POR NIVEL ($/hora, puede variar) ────────────────────────────
SALARIO_BASE = {
    "minimo":     0.50,   # Salario mínimo Venezuela real (~$3.5/mes ÷ 168h)
    "bajo":       1.50,
    "medio_bajo": 4.00,
    "medio":      8.00,
    "medio_alto": 15.00,
    "alto":       30.00,
    "muy_alto":   60.00,
    "extranjero": 120.00,
}

# ── MAPA TRABAJO → ROL ───────────────────────────────────────────────────────
TRABAJO_A_ROL = {
    "panadero":           ROL_PANADERO,
    "medico":             ROL_MEDICO,
    "funcionario":        ROL_FUNCIONARIO,
    "quimico":            ROL_QUIMICO,
    "ingeniero":          ROL_INGENIERO,
    "pescadero":          ROL_PESCADERO,
    "ganadero":           ROL_GANADERO,
    "maestro":            ROL_MAESTRO,
    "vendedor_ambulante": ROL_VENDEDOR,
    "comerciante":        ROL_VENDEDOR,
    "bombero":            ROL_BOMBERO,
    "cirujano":           ROL_CIRUJANO,
    "productor_ejecutivo":ROL_PRODUCTOR_EXEC,
    "fanb":               ROL_FANB,
    "ejercito":           ROL_EJERCITO,
    "sebin":              ROL_SEBIN,
    "abogado":            ROL_ABOGADO,
    "jefe_prensa":        ROL_JEFE_PRENSA,
    "editor_noticias":    ROL_EDITOR_NOTICIAS,
    "corresponsal":       ROL_CORRESPONSAL,
    "reportero":          ROL_REPORTERO,
    "guardia_prision":    ROL_GUARDIA_PRISION,
    "policia_rp":         ROL_POLICIA_CNPB,
}

# ── MAPA ESTUDIOS → ROL ──────────────────────────────────────────────────────
ESTUDIO_A_ROL = {
    "primaria":      ROL_PRIMARIA,
    "secundaria":    ROL_SECUNDARIA,
    "universitario": ROL_UNIVERSITARIO,
    "graduado":      ROL_GRADUADO,
}

# ── TODOS LOS ROLES ASIGNABLES (para quitar al resetear) ─────────────────────
TODOS_ROLES_RP = list(set([
    ROL_MUERTO, ROL_INFORMATICO, ROL_GRADUADO, ROL_ESTUDIANTE, ROL_MANTENIDO,
    ROL_EXTRANJERO, ROL_PRIMARIA, ROL_CRIMINAL, ROL_PRISIONERO, ROL_UNIVERSITARIO,
    ROL_SECUNDARIA, ROL_CIUDADANO, ROL_INDOCUMENTADO, ROL_HOMBRE, ROL_MUJER,
    ROL_PANADERO, ROL_MEDICO, ROL_FUNCIONARIO, ROL_QUIMICO, ROL_INGENIERO,
    ROL_PESCADERO, ROL_GANADERO, ROL_MAESTRO, ROL_VENDEDOR, ROL_BOMBERO,
    ROL_CIRUJANO, ROL_PRODUCTOR_EXEC, ROL_FANB, ROL_EJERCITO, ROL_SEBIN,
    ROL_ABOGADO, ROL_JEFE_PRENSA, ROL_EDITOR_NOTICIAS, ROL_CORRESPONSAL,
    ROL_REPORTERO, ROL_GUARDIA_PRISION, ROL_POLICIA_CNPB,
] + list(ROLES_SALARIO.values())))