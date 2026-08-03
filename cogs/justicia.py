"""
cogs/justicia.py — Sistema legal: abogados (de oficio y privados), pago de
honorarios, juicios contra el Estado (NPC) y juicios de roleplay entre
jugadores (con o sin NPCs de por medio).

Flujo típico:
1. Te detienen (arresto normal, control aleatorio, etc.)
2. `!abogados` — ves quién está disponible (defensores de oficio son GRATIS
   y siempre hay uno libre; los privados cuestan honorarios pero suben tu
   probabilidad de ganar el juicio).
3. `!contratar_abogado <nombre>` — lo contratas para tu caso actual.
4. `!juicio` — se celebra el juicio contra el Estado y se resuelve con un
   veredicto (absuelto / culpable), narrado por IA si hay una configurada.

Para disputas entre jugadores (o jugador vs NPC en un conflicto civil/penal
de rol, no una simple detención):
1. `!juicio_rp @acusado <motivo>` — abre el caso.
2. Ambas partes pueden usar `!alegato <texto>` para argumentar.
3. Un admin (o cualquiera de las partes tras haber al menos un alegato de
   cada lado) usa `!veredicto @acusado` para cerrar el caso con un fallo.
"""
import random
import time

import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils import ia

SYSTEM_JUEZ = (
    "Eres un juez venezolano ficticio en un servidor de roleplay de Discord. "
    "Escribes SIEMPRE en español, en 3 a 6 frases, con tono formal y serio de "
    "sala de tribunal. Debes: resumir brevemente el caso, valorar los alegatos "
    "de ambas partes y la calidad de la defensa, y terminar con un veredicto "
    "CLARO que empiece con la palabra 'CULPABLE' o 'INOCENTE' en mayúsculas. "
    "No inventes hechos que no estén en el caso descrito."
)


def _slug(nombre: str) -> str:
    return nombre.lower().replace(" ", "_")


async def _abogados_disponibles() -> list[tuple[str, dict]]:
    npcs = await db.all("npcs")
    return [(nid, n) for nid, n in npcs.items() if n.get("tipo") == "abogado" and not n.get("muerto")]


async def _get_abogado_choices(interaction: discord.Interaction, current: str):
    abogados = await _abogados_disponibles()
    out = []
    for nid, n in abogados:
        if current.lower() in n.get("nombre", "").lower():
            out.append(app_commands.Choice(name=n["nombre"][:100], value=nid))
    return out[:25]


class Justicia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _caso_activo(self, user_id: int) -> dict:
        caso = await db.get("casos_legales", str(user_id))
        if not caso or caso.get("estado") == "cerrado":
            caso = {
                "acusado_id": str(user_id),
                "abogado_id": None,
                "pagado": False,
                "estado": "activo",
                "tipo": "estado",
                "acusador_id": None,
                "motivo": None,
                "alegatos": [],
                "veredicto": None,
                "creado_ts": time.time(),
            }
            await db.set("casos_legales", str(user_id), caso)
        return caso

    # ── !abogados ─────────────────────────────────────────────────────────────
    @commands.command(name="abogados")
    async def abogados_cmd(self, ctx):
        abogados = await _abogados_disponibles()
        if not abogados:
            return await ctx.send(
                "❌ Todavía no hay abogados registrados. Un admin puede usar `/crear_npcs_ejemplo`."
            )
        embed = discord.Embed(title="⚖️ Abogados disponibles", color=discord.Color.dark_gold())
        publicos = [(nid, n) for nid, n in abogados if n.get("categoria") == "publico"]
        privados = [(nid, n) for nid, n in abogados if n.get("categoria") != "publico"]
        if publicos:
            embed.add_field(
                name="🆓 Defensores de oficio (gratis)",
                value="\n".join(f"**{n['nombre']}** — nivel {n.get('nivel','?')}/10" for _, n in publicos),
                inline=False
            )
        if privados:
            embed.add_field(
                name="💰 Abogados privados (de pago)",
                value="\n".join(f"**{n['nombre']}** — ${n.get('tarifa',0):,.2f} — nivel {n.get('nivel','?')}/10" for _, n in privados),
                inline=False
            )
        embed.set_footer(text="!contratar_abogado <nombre> — un nivel más alto sube tus probabilidades en el juicio")
        await ctx.send(embed=embed)

    # ── !contratar_abogado ────────────────────────────────────────────────────
    @commands.command(name="contratar_abogado")
    async def contratar_abogado(self, ctx, *, nombre: str):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        abogados = await _abogados_disponibles()
        match = next((n for _, n in abogados if nombre.lower() in n.get("nombre", "").lower()), None)
        nid = next((i for i, n in abogados if nombre.lower() in n.get("nombre", "").lower()), None)
        if not match:
            return await ctx.send(f"❌ No encontré ningún abogado llamado `{nombre}`. Usa `!abogados` para ver la lista.")

        tarifa = match.get("tarifa", 0)
        if tarifa > 0:
            dinero = datos.get("dinero", 0)
            if dinero < tarifa:
                return await ctx.send(f"❌ **{match['nombre']}** cobra ${tarifa:,.2f} de honorarios. Tienes ${dinero:,.2f}.")
            await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - tarifa, 2)})

        caso = await self._caso_activo(ctx.author.id)
        caso["abogado_id"] = nid
        caso["pagado"] = tarifa > 0
        await db.set("casos_legales", str(ctx.author.id), caso)

        gratis_txt = "de oficio, sin costo" if tarifa == 0 else f"por ${tarifa:,.2f}"
        await ctx.send(embed=discord.Embed(
            description=f"⚖️ Contrataste a **{match['nombre']}** ({gratis_txt}) para tu caso.\n"
                        f"Nivel de defensa: {match.get('nivel','?')}/10.",
            color=discord.Color.green()
        ))

    # ── !hablar_abogado ───────────────────────────────────────────────────────
    @commands.command(name="hablar_abogado")
    async def hablar_abogado(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        caso = await self._caso_activo(ctx.author.id)
        if not caso.get("abogado_id"):
            abogados = await _abogados_disponibles()
            publicos = [(nid, n) for nid, n in abogados if n.get("categoria") == "publico"]
            if not publicos:
                return await ctx.send("❌ No hay defensores de oficio disponibles ahora mismo. Pídele a un admin `/crear_npcs_ejemplo`.")
            nid, abogado = random.choice(publicos)
            caso["abogado_id"] = nid
            caso["pagado"] = False
            await db.set("casos_legales", str(ctx.author.id), caso)
        else:
            abogado = await db.get("npcs", caso["abogado_id"])

        arrestos = await db.get("arrestos", str(ctx.author.id)) or []
        razon = arrestos[-1]["razon"] if arrestos else "sin cargos claros todavía"

        fallback = (
            f"*{abogado['nombre']} revisa tus papeles.* \"Con base en '{razon}', vamos a pelear esto en el juicio. "
            f"No digas nada más sin mí presente. Usa `!juicio` cuando estés listo.\""
        )
        texto = fallback
        if ia.hay_ia():
            prompt = (
                f"Eres {abogado['nombre']}, abogado ({abogado.get('categoria','publico')}, nivel "
                f"{abogado.get('nivel','?')}/10) hablando con tu cliente detenido por: {razon}. "
                f"Dale un consejo legal breve y en personaje, en 2-3 frases, en español."
            )
            ia_texto, _ = await ia.generar("Eres un abogado venezolano de ficción dando consejo legal breve.", prompt, max_tokens=150)
            texto = ia_texto or fallback

        embed = discord.Embed(description=texto, color=discord.Color.dark_gold())
        embed.set_author(name=f"⚖️ {abogado['nombre']}")
        await ctx.send(embed=embed)

    # ── !juicio (contra el Estado, por tu propia detención) ─────────────────────
    @commands.command(name="juicio")
    async def juicio(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not datos.get("arrestado"):
            return await ctx.send("❌ No estás arrestado ni tienes un caso pendiente contra el Estado.")

        caso = await self._caso_activo(ctx.author.id)
        abogado = await db.get("npcs", caso["abogado_id"]) if caso.get("abogado_id") else None
        nivel_abogado = abogado.get("nivel", 2) if abogado else 1  # sin abogado, te defiendes solo (mal)

        arrestos = await db.get("arrestos", str(ctx.author.id)) or []
        razon = arrestos[-1]["razon"] if arrestos else "cargos sin especificar"
        agravante = any(p in razon.lower() for p in ["arma", "droga", "asesinato", "homicidio", "secuestro"])

        prob_absolucion = 0.12 + nivel_abogado * 0.055 - (0.10 if agravante else 0)
        prob_absolucion = max(0.03, min(0.90, prob_absolucion))
        absuelto = random.random() < prob_absolucion

        prompt = (
            f"Caso: el Estado venezolano acusa a {datos.get('nombre','?')} de: {razon}. "
            f"Su defensa la lleva {abogado['nombre'] if abogado else 'él mismo, sin abogado'} "
            f"(nivel de defensa {nivel_abogado}/10). "
            f"El resultado YA está decidido: {'INOCENTE' if absuelto else 'CULPABLE'}. "
            f"Narra el veredicto de forma coherente con ese resultado."
        )
        veredicto_texto = None
        if ia.hay_ia():
            veredicto_texto, _ = await ia.generar(SYSTEM_JUEZ, prompt, max_tokens=250)
        if not veredicto_texto:
            veredicto_texto = (
                f"El tribunal, tras revisar el caso de {datos.get('nombre','?')} por '{razon}', dictamina: "
                + ("INOCENTE. Falta de pruebas suficientes para condenar." if absuelto
                   else "CULPABLE. Se dicta sentencia conforme a la ley.")
            )

        caso["estado"] = "cerrado"
        caso["veredicto"] = "inocente" if absuelto else "culpable"
        await db.set("casos_legales", str(ctx.author.id), caso)
        try:
            from cogs.noticias_ia import registrar_evento
            await registrar_evento("veredicto",
                f"Un tribunal declaró {'inocente' if absuelto else 'culpable'} a {datos.get('nombre','?')} por: {razon}.")
        except Exception:
            pass

        if absuelto:
            barrio_origen = datos.get("barrio", "distrito-capital")
            await db.update("personajes", str(ctx.author.id), {
                "arrestado": False, "ubicacion": barrio_origen, "canal_actual": None,
            })
        # Si es culpable, se queda arrestado (un admin decide cuándo cumplió condena con !liberar).

        embed = discord.Embed(
            title="⚖️ Veredicto" + (" — INOCENTE ✅" if absuelto else " — CULPABLE ❌"),
            description=veredicto_texto[:4000],
            color=discord.Color.green() if absuelto else discord.Color.dark_red()
        )
        embed.add_field(name="Defensa", value=abogado["nombre"] if abogado else "Sin abogado (defensa propia)", inline=True)
        embed.add_field(name="Cargos", value=razon, inline=True)
        await ctx.send(embed=embed)

    # ── !juicio_rp — disputa entre jugadores (o jugador vs NPC) ─────────────────
    @commands.command(name="juicio_rp")
    async def juicio_rp(self, ctx, acusado: discord.Member, *, motivo: str):
        datos_acc = await db.get("personajes", str(ctx.author.id))
        datos_acu = await db.get("personajes", str(acusado.id))
        if not datos_acc or not datos_acu:
            return await ctx.send("❌ Ambas partes necesitan personaje.")

        caso = {
            "acusado_id": str(acusado.id),
            "acusador_id": str(ctx.author.id),
            "abogado_id": None,
            "pagado": False,
            "estado": "activo",
            "tipo": "civil_rp",
            "motivo": motivo,
            "alegatos": [],
            "veredicto": None,
            "creado_ts": time.time(),
        }
        await db.set("casos_legales", str(acusado.id), caso)

        embed = discord.Embed(
            title="⚖️ Nuevo caso de roleplay",
            description=(
                f"**Acusador:** {datos_acc['nombre']}\n"
                f"**Acusado:** {datos_acu['nombre']}\n"
                f"**Motivo:** {motivo}\n\n"
                f"Ambas partes pueden usar `!alegato <texto>` para argumentar y `!contratar_abogado` "
                f"para representación legal. Un admin (o cualquiera de las partes cuando ambas hayan "
                f"presentado al menos un alegato) cierra el caso con `!veredicto @{acusado.display_name}`."
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)
        try:
            await acusado.send(f"⚖️ **{datos_acc['nombre']}** abrió un caso de roleplay contra ti. Motivo: {motivo}")
        except Exception:
            pass

    # ── !alegato ──────────────────────────────────────────────────────────────
    @commands.command(name="alegato")
    async def alegato(self, ctx, *, texto: str):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        # Buscar un caso donde el autor sea acusado o acusador
        todos = await db.all("casos_legales")
        caso_id, caso = None, None
        for cid, c in todos.items():
            if c.get("estado") != "activo":
                continue
            if str(ctx.author.id) in (c.get("acusado_id"), c.get("acusador_id")):
                caso_id, caso = cid, c
                break
        if not caso:
            return await ctx.send("❌ No tienes ningún caso activo. Ábrelo con `!juicio_rp` o espera a que te acusen.")

        caso.setdefault("alegatos", []).append({"autor": str(ctx.author.id), "nombre": datos["nombre"], "texto": texto[:500]})
        await db.set("casos_legales", caso_id, caso)
        await ctx.send(embed=discord.Embed(
            description=f"📝 **{datos['nombre']}** presenta su alegato:\n> {texto[:500]}",
            color=discord.Color.dark_grey()
        ))

    # ── !veredicto ────────────────────────────────────────────────────────────
    @commands.command(name="veredicto")
    async def veredicto(self, ctx, acusado: discord.Member):
        caso = await db.get("casos_legales", str(acusado.id))
        if not caso or caso.get("estado") != "activo" or caso.get("tipo") != "civil_rp":
            return await ctx.send("❌ No hay ningún caso de roleplay activo para esa persona.")

        es_admin = ctx.author.guild_permissions.manage_guild
        es_parte = str(ctx.author.id) in (caso.get("acusado_id"), caso.get("acusador_id"))
        alegatos = caso.get("alegatos", [])
        autores = {a["autor"] for a in alegatos}
        ambas_partes_hablaron = caso.get("acusador_id") in autores and caso.get("acusado_id") in autores

        if not es_admin and not (es_parte and ambas_partes_hablaron):
            return await ctx.send(
                "❌ Solo un admin puede cerrar el caso ya mismo. Si eres parte del caso, espera a que "
                "ambos lados hayan presentado al menos un `!alegato`."
            )

        datos_acu = await db.get("personajes", caso["acusado_id"])
        datos_acc = await db.get("personajes", caso["acusador_id"]) if caso.get("acusador_id") else None

        abogado_acu = await db.get("npcs", caso["abogado_id"]) if caso.get("abogado_id") else None
        nivel_defensa = abogado_acu.get("nivel", 2) if abogado_acu else 2

        alegatos_txt = "\n".join(f"- {a['nombre']}: {a['texto']}" for a in alegatos) or "(sin alegatos presentados)"
        prob_culpable = max(0.10, min(0.90, 0.55 - nivel_defensa * 0.03 + 0.03 * len(alegatos_txt.splitlines())))
        culpable = random.random() < prob_culpable

        prompt = (
            f"Caso civil/penal de rol. Acusador: {datos_acc['nombre'] if datos_acc else 'el Estado'}. "
            f"Acusado: {datos_acu['nombre']}. Motivo: {caso.get('motivo','?')}.\n"
            f"Alegatos presentados:\n{alegatos_txt}\n"
            f"El resultado YA está decidido: {'CULPABLE' if culpable else 'INOCENTE'}. Narra el veredicto "
            f"de forma coherente con los alegatos y ese resultado."
        )
        veredicto_texto = None
        if ia.hay_ia():
            veredicto_texto, _ = await ia.generar(SYSTEM_JUEZ, prompt, max_tokens=250)
        if not veredicto_texto:
            veredicto_texto = (
                f"Visto el caso contra {datos_acu['nombre']} por '{caso.get('motivo','?')}': "
                + ("CULPABLE. Se ordena una sanción proporcional." if culpable
                   else "INOCENTE. No hay pruebas suficientes.")
            )

        caso["estado"] = "cerrado"
        caso["veredicto"] = "culpable" if culpable else "inocente"
        await db.set("casos_legales", caso["acusado_id"], caso)
        try:
            from cogs.noticias_ia import registrar_evento
            await registrar_evento("veredicto_rp",
                f"Caso de rol contra {datos_acu['nombre']} ({caso.get('motivo','?')}) resuelto como {'culpable' if culpable else 'inocente'}.")
        except Exception:
            pass

        embed = discord.Embed(
            title="⚖️ Veredicto del caso" + (" — CULPABLE ❌" if culpable else " — INOCENTE ✅"),
            description=veredicto_texto[:4000],
            color=discord.Color.dark_red() if culpable else discord.Color.green()
        )
        embed.set_footer(text=f"Caso: {caso.get('motivo','?')}")
        await ctx.send(embed=embed)

    # ── !mi_caso ──────────────────────────────────────────────────────────────
    @commands.command(name="mi_caso")
    async def mi_caso(self, ctx):
        caso = await db.get("casos_legales", str(ctx.author.id))
        if not caso:
            return await ctx.send("ℹ️ No tienes ningún caso legal registrado.")
        abogado = await db.get("npcs", caso["abogado_id"]) if caso.get("abogado_id") else None
        embed = discord.Embed(title="⚖️ Tu caso legal", color=discord.Color.dark_gold())
        embed.add_field(name="Estado", value=caso.get("estado", "?"), inline=True)
        embed.add_field(name="Tipo", value=caso.get("tipo", "?"), inline=True)
        embed.add_field(name="Abogado", value=abogado["nombre"] if abogado else "Ninguno contratado", inline=True)
        if caso.get("motivo"):
            embed.add_field(name="Motivo", value=caso["motivo"], inline=False)
        if caso.get("veredicto"):
            embed.add_field(name="Veredicto", value=caso["veredicto"].title(), inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Justicia(bot))
