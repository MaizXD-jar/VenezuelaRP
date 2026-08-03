"""
cogs/eventos_random.py — Eventos aleatorios expandidos:
robos, secuestros, fuego cruzado, atropellos, apuñalamientos,
objetos cayendo del bolsillo, hackeos, apagones, etc.
Probabilidades dependen del barrio y perfil del personaje.
"""
import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from utils import db
from utils.mapa import SECTORES, PELIGRO_EFECTOS

# ── IDs ───────────────────────────────────────────────────────────────────────
CH_POLICIA_AVISO = 1359320808526450780
ROL_POLICIA      = 1359320808526450780

# ── EVENTOS POR TIPO ──────────────────────────────────────────────────────────
EVENTOS_POSITIVOS = [
    ("💰", "Encuentras ${monto} en el suelo. ¡Alguien lo perdió!"),
    ("🎁", "Un vecino te regala comida. +$2 de suministros."),
    ("📱", "Encuentras un teléfono tirado. Puedes quedártelo o devolverlo."),
    ("🍗", "Un vendedor te da un bono: descuento del 50% en su próxima venta."),
    ("🏆", "Encuentras una joya en la calle. Vale ~$30."),
]

EVENTOS_NEUTROS = [
    ("🐕", "Un perro callejero te sigue un rato. Inofensivo."),
    ("📢", "Un vecino pone música a todo volumen. Ambiente ruidoso."),
    ("🌧️", "Empieza a llover. +10 min a los viajes."),
    ("🚧", "Hay obras en la calle. Paso lento."),
    ("🛵", "Un motorizado pasa volando casi rozándote."),
    ("🎊", "Hay una fiesta en una casa cercana."),
    ("📺", "Se anuncia cadena presidencial. Todo el país la ve."),
    ("☀️", "Calor extremo de 38°C. El cuerpo lo resiente."),
]

EVENTOS_NEGATIVOS = [
    {
        "id": "robo_rapido",
        "emoji": "🦹",
        "desc": "¡Te arrebatan el teléfono! Un ladrón te lo quitó corriendo.",
        "efecto": "robar_telefono",
        "prob_base": 0.03,
        "scaling_peligro": True,
    },
    {
        "id": "robo_dinero",
        "emoji": "💸",
        "desc": "Un malandrito te encañona. Pierde entre $5-$50.",
        "efecto": "robar_dinero",
        "prob_base": 0.02,
        "scaling_peligro": True,
    },
    {
        "id": "se_cae_dinero",
        "emoji": "💵",
        "desc": "Sin querer dejas caer ${monto} del bolsillo. ¡Cuidado!",
        "efecto": "perder_dinero",
        "prob_base": 0.04,
        "scaling_peligro": False,
    },
    {
        "id": "apunalamiento",
        "emoji": "🔪",
        "desc": "¡Un desconocido te apuñala! -{daño} HP.",
        "efecto": "daño_fisico",
        "prob_base": 0.008,
        "scaling_peligro": True,
        "min_peligro": 3,
    },
    {
        "id": "fuego_cruzado",
        "emoji": "💥",
        "desc": "¡Fuego cruzado entre bandas! Estás en medio. -{daño} HP.",
        "efecto": "daño_fisico_alto",
        "prob_base": 0.005,
        "scaling_peligro": True,
        "min_peligro": 4,
    },
    {
        "id": "secuestro",
        "emoji": "🚨",
        "desc": "¡Secuestro exprés! Te llevan en un carro por 30 minutos. Pierdes objetos.",
        "efecto": "secuestro_rapido",
        "prob_base": 0.003,
        "scaling_peligro": True,
        "min_peligro": 3,
    },
    {
        "id": "atropello",
        "emoji": "🚗",
        "desc": "¡Un carro te atropella! -{daño} HP. Estás en el suelo.",
        "efecto": "daño_fisico",
        "prob_base": 0.004,
        "scaling_peligro": False,
    },
    {
        "id": "hackeo_cuenta",
        "emoji": "💻",
        "desc": "¡Alguien hackea tu cuenta! Pierdes info de ubicación.",
        "efecto": "hackeo",
        "prob_base": 0.005,
        "scaling_peligro": False,
    },
    {
        "id": "muerte_subita",
        "emoji": "💀",
        "desc": "Fuego cruzado inesperado. Tu personaje cae en zona de guerra.",
        "efecto": "muerte",
        "prob_base": 0.001,
        "scaling_peligro": True,
        "min_peligro": 5,
    },
    {
        "id": "intento_robo_fallido",
        "emoji": "😅",
        "desc": "Alguien intentó robarte pero lograste escapar. Susto.",
        "efecto": "susto",
        "prob_base": 0.05,
        "scaling_peligro": True,
    },
    {
        "id": "detencion_policial",
        "emoji": "🚔",
        "desc": "La policía te detiene para un registro. Si tienes algo ilegal, te arrestan.",
        "efecto": "registro_policial",
        "prob_base": 0.015,
        "scaling_peligro": False,
    },
]

# ── EVENTOS DE MERCADO NEGRO PETARE ──────────────────────────────────────────
EVENTOS_MERCADO_NEGRO = [
    ("🔫", "¡Tiroteo en el mercado negro! Todos a cubierto. -{daño} HP a quienes estén."),
    ("🦹", "Un carterista actúa en el mercado."),
    ("🚔", "¡REDADA! La policía entra al mercado. Todos los presentes son sospechosos."),
    ("💣", "Alguien lanza un petardo. Pánico y confusión."),
    ("🔪", "Ajuste de cuentas entre bandas en el mercado."),
    ("💊", "Se ofrece mercancía dudosa. ¿Compras?"),
    ("🧨", "Explosión a dos calles. Humo y pánico."),
]

# ── EVENTOS DE ELECCIONES ─────────────────────────────────────────────────────
EVENTOS_ELECCIONES = [
    "🗳️ Marcha electoral bloquea la autopista. +30 min de viaje.",
    "📣 Propaganda política en todas partes. Ambiente muy tenso.",
    "⚠️ Guarimbas en el barrio. Zona intransitable por 1 hora.",
    "🔴 Colectivos en motorizados patrullando. Mucho cuidado.",
    "📢 Cadena nacional obligatoria. Cortan señal de TV e internet por 2h.",
    "🚨 Enfrentamientos entre opositores y chavistas en la plaza.",
    "🔥 Queman cauchos en la calle. Humo negro visible.",
]


class EventosRandom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.modo_elecciones = False
        self.evento_loop.start()

    def start_tasks(self):
        if not self.evento_loop.is_running():
            self.evento_loop.start()

    @tasks.loop(minutes=15)
    async def evento_loop(self):
        """Genera eventos aleatorios para personajes activos."""
        personajes = await db.all("personajes")
        for uid, datos in personajes.items():
            if datos.get("muerto") or datos.get("en_viaje") or datos.get("arrestado"):
                continue

            sector_key = datos.get("ubicacion", "")
            if not sector_key or sector_key not in SECTORES:
                continue

            sec_info = SECTORES[sector_key]
            peligro = sec_info.get("peligro", 1)

            # Probabilidad base de que algo pase: 15% base + peligro
            prob_evento = 0.10 + peligro * 0.03
            if random.random() > prob_evento:
                continue

            # Elegir tipo de evento
            roll = random.random()
            if roll < 0.25:
                await self._evento_positivo(uid, datos, sec_info)
            elif roll < 0.50:
                await self._evento_neutro(uid, datos, sec_info)
            else:
                await self._evento_negativo(uid, datos, sec_info, peligro)

    async def _evento_positivo(self, uid: str, datos: dict, sec_info: dict):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        member = guild.get_member(int(uid))
        if not member:
            return

        emoji, desc = random.choice(EVENTOS_POSITIVOS)
        monto = round(random.uniform(1, 20), 2)
        desc = desc.replace("{monto}", str(monto))

        ganancia = 0
        if "💰" in emoji or "🏆" in emoji:
            ganancia = monto if "💰" in emoji else 30.0
            await db.update("personajes", uid, {"dinero": round(datos.get("dinero", 0) + ganancia, 2)})

        canal_nombre = datos.get("canal_actual", "")
        canal = discord.utils.get(guild.text_channels, name=canal_nombre)
        if canal:
            embed = discord.Embed(description=f"{emoji} {member.mention} — {desc}", color=0x2ECC71)
            embed.set_footer(text="Evento aleatorio")
            await canal.send(embed=embed)

    async def _evento_neutro(self, uid: str, datos: dict, sec_info: dict):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        emoji, desc = random.choice(EVENTOS_NEUTROS)
        canal_nombre = datos.get("canal_actual", "")
        canal = discord.utils.get(guild.text_channels, name=canal_nombre)
        if canal and random.random() < 0.3:  # No siempre pingear en neutros
            embed = discord.Embed(description=f"{emoji} {desc}", color=0x95A5A6)
            embed.set_footer(text=f"📍 {canal_nombre}")
            await canal.send(embed=embed)

    async def _evento_negativo(self, uid: str, datos: dict, sec_info: dict, peligro: int):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        member = guild.get_member(int(uid))
        if not member:
            return

        # Filtrar eventos por peligro mínimo
        posibles = [e for e in EVENTOS_NEGATIVOS
                    if peligro >= e.get("min_peligro", 0)]
        if not posibles:
            return

        # Elegir por probabilidad
        total = sum(e["prob_base"] * (peligro if e.get("scaling_peligro") else 1) for e in posibles)
        rand = random.uniform(0, total)
        acum = 0
        evento = posibles[-1]
        for e in posibles:
            p = e["prob_base"] * (peligro if e.get("scaling_peligro") else 1)
            acum += p
            if rand <= acum:
                evento = e
                break

        efecto = evento["efecto"]
        desc = evento["desc"]
        emoji = evento["emoji"]
        stats = datos.get("stats", {})
        hp = stats.get("hp", 100)
        inventario = datos.get("inventario", {})
        dinero = datos.get("dinero", 0)
        canal_nombre = datos.get("canal_actual", "")
        canal = discord.utils.get(guild.text_channels, name=canal_nombre)

        # Aplicar efectos
        if efecto == "daño_fisico":
            daño = random.randint(5, 25)
            stats["hp"] = max(0, hp - daño)
            desc = desc.replace("{daño}", str(daño))
            await db.update("personajes", uid, {"stats": stats})

        elif efecto == "daño_fisico_alto":
            daño = random.randint(20, 60)
            stats["hp"] = max(0, hp - daño)
            desc = desc.replace("{daño}", str(daño))
            await db.update("personajes", uid, {"stats": stats})

        elif efecto == "robar_dinero":
            monto = round(random.uniform(5, min(50, dinero)), 2) if dinero > 5 else 0
            if monto > 0:
                await db.update("personajes", uid, {"dinero": round(dinero - monto, 2)})
                desc += f" Perdiste **${monto:.2f}**."

        elif efecto == "robar_telefono":
            tiene_tel = any("telefono" in k or "smartphone" in k for k in inventario)
            if tiene_tel:
                tel_key = next((k for k in inventario if "telefono" in k or "smartphone" in k), None)
                if tel_key:
                    inventario[tel_key] = max(0, inventario[tel_key] - 1)
                    if inventario[tel_key] == 0:
                        del inventario[tel_key]
                    await db.update("personajes", uid, {"inventario": inventario})
            else:
                desc = "Alguien intentó arrebatarte el teléfono, pero no tienes. Escape rápido."

        elif efecto == "perder_dinero":
            monto = round(random.uniform(1, min(20, dinero)) , 2) if dinero > 1 else 0
            if monto > 0:
                await db.update("personajes", uid, {"dinero": round(dinero - monto, 2)})
                desc = desc.replace("{monto}", str(monto))

        elif efecto == "secuestro_rapido":
            # Secuestro exprés: pierdes dinero y te retrasas
            monto = round(dinero * random.uniform(0.05, 0.20), 2)
            await db.update("personajes", uid, {
                "dinero": round(dinero - monto, 2),
                "en_viaje": True,
            })
            desc += f" Perdiste ${monto:.2f} y quedaste inmovilizado 30 min."
            await asyncio.sleep(1800)
            await db.update("personajes", uid, {"en_viaje": False})

        elif efecto == "hackeo":
            try:
                await member.send(f"💻 ¡Tu ubicación y datos de cuenta fueron comprometidos por un hackeo!")
            except:
                pass

        elif efecto == "registro_policial":
            # Verificar si tiene objetos ilegales
            objetos_ilegales = [k for k in inventario if any(
                x in k.lower() for x in ["arma", "pistola", "rifle", "droga", "cocaina", "heroin"]
            )]
            if objetos_ilegales:
                desc = f"🚔 La policía te detiene y encuentra **{', '.join(objetos_ilegales[:2])}** en tu inventario. Arrestado."
                await db.update("personajes", uid, {
                    "arrestado": True,
                    "ubicacion": "prision-yare",
                })
                ch_pol = guild.get_channel(CH_POLICIA_AVISO)
                if ch_pol:
                    await ch_pol.send(f"🚨 {member.mention} fue detenido en registro policial. Objetos ilegales encontrados.")
            else:
                desc = "🚔 La policía te detiene y registra. Todo en orden. Te dejan ir."

        elif efecto == "susto":
            pass  # Solo visual

        elif efecto == "muerte":
            from bot import CH_MUERTOS
            stats["hp"] = 0
            await db.update("personajes", uid, {"stats": stats, "muerto": True, "causa_muerte": "Fuego cruzado"})
            ch_muertos = guild.get_channel(CH_MUERTOS)
            if ch_muertos:
                embed_muerte = discord.Embed(
                    title="💀 PERSONAJE FALLECIDO",
                    description=f"**{datos.get('nombre','?')}** cayó en fuego cruzado.",
                    color=0x000000
                )
                embed_muerte.add_field(name="Causa", value="Fuego cruzado — evento aleatorio")
                await ch_muertos.send(embed_muerte)

        # Enviar mensaje al canal
        if canal:
            color = 0xE74C3C if efecto not in ("susto", "registro_policial") else 0xF39C12
            embed = discord.Embed(
                description=f"{emoji} {member.mention} — {desc}",
                color=color
            )
            embed.set_footer(text=f"Evento en {canal_nombre} | Peligro zona: {'⚠️'*peligro}")
            await canal.send(embed=embed)

    # ── MERCADO NEGRO PETARE ESPECIAL ─────────────────────────────────────────
    @tasks.loop(minutes=30)
    async def evento_mercado_negro(self):
        for guild in self.bot.guilds:
            canal = discord.utils.get(guild.text_channels, name="mercado-negro-petare")
            if not canal:
                continue
            if random.random() > 0.40:  # 40% chance cada 30 min
                continue
            emoji, msg = random.choice(EVENTOS_MERCADO_NEGRO)
            daño = random.randint(10, 30)
            msg = msg.replace("{daño}", str(daño))
            embed = discord.Embed(
                title=f"{emoji} EVENTO EN EL MERCADO NEGRO",
                description=msg,
                color=0x8B0000
            )
            await canal.send("@here", embed=embed)

            # Aplicar daño a quienes estén ahí
            personajes = await db.all("personajes")
            for uid, datos in personajes.items():
                if datos.get("canal_actual") == "mercado-negro-petare" and not datos.get("muerto"):
                    stats = datos.get("stats", {})
                    if "tiroteo" in msg.lower() or "fuego" in msg.lower():
                        stats["hp"] = max(0, stats.get("hp", 100) - daño)
                        await db.update("personajes", uid, {"stats": stats})

    # ── ELECCIONES ────────────────────────────────────────────────────────────
    @commands.command(name="elecciones")
    async def toggle_elecciones(self, ctx):
        """[ADMIN] Activa/desactiva modo elecciones."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        self.modo_elecciones = not self.modo_elecciones
        if self.modo_elecciones:
            # Anunciar en todos los sectores de Caracas
            for sector_key, sec in SECTORES.items():
                if sec.get("ciudad") != "caracas":
                    continue
                canales = list(sec.get("canales", {}).keys())
                if not canales:
                    continue
                canal = discord.utils.get(ctx.guild.text_channels, name=canales[0])
                if canal:
                    embed = discord.Embed(
                        title="🗳️ PERÍODO ELECTORAL",
                        description=random.choice(EVENTOS_ELECCIONES),
                        color=0xFFD700
                    )
                    await canal.send(embed=embed)
        await ctx.send(f"Modo elecciones: **{'ACTIVADO 🗳️' if self.modo_elecciones else 'DESACTIVADO ✅'}**")

    # ── EVENTO MANUAL ADMIN ───────────────────────────────────────────────────
    @commands.command(name="evento")
    async def evento_manual(self, ctx):
        """[ADMIN] Crea un evento personalizado."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        await ctx.send_modal(EventoModal())

    # ── CLIMA ─────────────────────────────────────────────────────────────────
    @commands.command(name="clima")
    async def clima(self, ctx):
        climas = [
            ("☀️", "Soleado y caluroso. ~33°C. Beber agua."),
            ("🌧️", "Lluvia fuerte. +10 min a viajes. Cuidado con el asfalto."),
            ("⛈️", "Tormenta eléctrica. Viajes muy arriesgados. Posible apagón."),
            ("🌤️", "Parcialmente nublado. Temperatura agradable ~27°C."),
            ("🌫️", "Neblina en las montañas. Visibilidad reducida."),
            ("🔥", "Calor extremo 40°C. Sin luz + calor = peligro real."),
        ]
        emoji, desc = random.choice(climas)
        embed = discord.Embed(title=f"{emoji} Clima en Venezuela", description=desc, color=0x3498DB)
        await ctx.send(embed=embed)


class EventoModal(discord.ui.Modal, title="Crear Evento"):
    titulo = discord.ui.TextInput(label="Título del evento")
    descripcion = discord.ui.TextInput(label="Descripción", style=discord.TextStyle.long)
    canal_nombre = discord.ui.TextInput(label="Canal donde ocurre (nombre exacto)")
    duracion = discord.ui.TextInput(label="Duración en minutos (0 = permanente)", placeholder="30")

    async def on_submit(self, interaction: discord.Interaction):
        canal = discord.utils.get(interaction.guild.text_channels, name=self.canal_nombre.value.lower().replace(" ","-"))
        try: dur = int(self.duracion.value)
        except: dur = 0
        embed = discord.Embed(
            title=f"⚡ EVENTO: {self.titulo.value}",
            description=self.descripcion.value,
            color=0xF39C12
        )
        embed.set_footer(text=f"Admin: {interaction.user.display_name} | Duración: {'indefinida' if dur==0 else f'{dur}min'}")
        if canal:
            await canal.send("@here", embed=embed)
            await interaction.response.send_message(f"✅ Enviado a {canal.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Canal no encontrado.", ephemeral=True)
        if dur > 0:
            await asyncio.sleep(dur*60)
            if canal:
                await canal.send(embed=discord.Embed(title=f"⏰ Evento finalizado: {self.titulo.value}", color=0x95A5A6))


async def setup(bot):
    await bot.add_cog(EventosRandom(bot))