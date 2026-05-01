"""
╔══════════════════════════════════════════════════════════════════╗
║         SIMULADOR DE SISTEMAS ESTELARES Y EXOPLANETAS            ║
║         Física Avanzada — Generación Procedural Determinista     ║
╚══════════════════════════════════════════════════════════════════╝

USO:
    python simulador_estelar.py                    → Seed por defecto
    python simulador_estelar.py TRAPPIST-1         → Seed nombrada
    python simulador_estelar.py --seed MI_GALAXIA  → Flag explícito

La misma seed SIEMPRE produce el mismo sistema, sin importar cuántas veces
se ejecute o en qué máquina.
"""

import math
import random
import hashlib
import sys
from dataclasses import dataclass
from typing import Optional, List
import xml.etree.ElementTree as ET
import urllib.request
import gzip
import io

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES FÍSICAS (SI + Astronómicas)
# ══════════════════════════════════════════════════════════════════

class C:
    # Unidades astronómicas
    UA_A_KM              = 1.496e8          # 1 UA en km
    RADIO_SOLAR_UA       = 0.00465047       # Radio del Sol en UA
    MASA_TERRESTRE_SOLAR = 3.003e-6         # Masa de la Tierra en masas solares
    RADIO_TERRESTRE_KM   = 6371.0           # km

    # Físicas
    SIGMA                = 5.670e-8         # Stefan-Boltzmann (W m⁻² K⁻⁴)
    G                    = 6.674e-11        # Constante gravitacional (N m² kg⁻²)

    # Estelares de referencia (Sol)
    TEMP_SOL             = 5778.0           # K
    MASA_SOL_KG          = 1.989e30         # kg
    RADIO_SOL_KM         = 695700.0         # km
    LUM_SOL              = 3.828e26         # W

    # Termodinámicas
    ABS_ZERO             = -273.15          # °C → K offset

    # Zona Habitable (Kopparapu 2013, límites conservadores)
    ZH_INTERIOR          = 1.1             # Factor para límite interior
    ZH_EXTERIOR          = 0.53            # Factor para límite exterior
    LINEA_NIEVE          = 2.7             # Factor para línea de nieve

    # Referencia terrestre para ESI (Schulze-Makuch et al. 2011)
    ESI_T_REF            = 288.0           # K — temperatura media global Tierra
    ESI_RHO_REF          = 1.0             # densidad relativa normalizada
    ESI_VESC_REF         = 1.0             # velocidad de escape relativa normalizada
    ESI_R_REF            = 1.0             # radio en R⊕

    # Umbrales fisiológicos humanos para IHH
    IHH_ARMSTRONG        = 0.0618          # atm — por encima los fluidos corporales hierven
    IHH_TEMP_MIN_ABS     = -90.0           # °C — mínimo absoluto de supervivencia
    IHH_TEMP_MAX_ABS     = 150.0           # °C — máximo absoluto de supervivencia
    IHH_G_MIN            = 0.15            # g⊕ — colapso cardiovascular por debajo
    IHH_G_MAX            = 3.5             # g⊕ — colapso cardiovascular por encima


# ══════════════════════════════════════════════════════════════════
#  SISTEMA DE SEED DETERMINISTA
# ══════════════════════════════════════════════════════════════════

def derivar_rng(seed_maestra: str, *contexto) -> random.Random:
    """
    Crea un RNG completamente reproducible y AISLADO para cada componente.
    
    La clave es que cada planeta/luna tiene su propio RNG derivado de:
        seed_maestra + contexto (ej: "planeta_3", "luna_2_de_3")
    
    Así, agregar un planeta no corrompe la aleatoriedad de los demás.
    """
    token = seed_maestra + "_" + "_".join(str(c) for c in contexto)
    hash_bytes = hashlib.sha256(token.encode("utf-8")).digest()
    seed_int = int.from_bytes(hash_bytes[:8], "big")
    return random.Random(seed_int)


# ══════════════════════════════════════════════════════════════════
#  EVENTOS INTERESTELARES (DETERMINISTAS POR VIAJE)
# ══════════════════════════════════════════════════════════════════

@dataclass
class EventoEstelar:
    nombre: str
    descripcion: str
    categoria: str
    icono: str = "⚡"


# Catálogo completo de eventos clasificados por categorías
CATALOGO_EVENTOS: List[EventoEstelar] = [
    # ── 1. Fenómenos Astrofísicos Reales ──────────────────────────
    EventoEstelar(
        "Intersección con Planeta Errante",
        "Un planeta sin estrella emerge de la oscuridad. Los sensores infrarrojos "
        "leen su firma térmica a última hora. Podría servir de refugio de emergencia "
        "o ser un peligro de colisión.",
        "Astrofísico Real",
        "🪐"
    ),
    EventoEstelar(
        "Enjambre de Polvo Interestelar de Alta Densidad",
        "La nave atraviesa una nube densa de polvo y micrometeoritos. A velocidades "
        "relativistas, cada partícula impacta como una bala. Escudos deflectores "
        "activados y velocidad reducida para evitar erosión catastrófica.",
        "Astrofísico Real",
        "💥"
    ),
    EventoEstelar(
        "Impacto de Ráfaga de Rayos Gamma (GRB) Distante",
        "Un pulso de radiación ionizante procedente del colapso de una hipernova "
        "lejana inunda la nave. La electrónica no blindada sufre fallos en cascada; "
        "la tripulación debe refugiarse en el núcleo de la nave.",
        "Astrofísico Real",
        "💀"
    ),
    EventoEstelar(
        "Cruce de Nube de Oort Densa",
        "Al aproximarse al sistema de destino, la nave penetra una nube de Oort "
        "inusualmente poblada de cometas inactivos y cuerpos de hielo. Los sistemas "
        "automáticos ejecutan maniobras evasivas constantes.",
        "Astrofísico Real",
        "☄️"
    ),

    # ── 2. Física Teórica y Extrema ───────────────────────────────
    EventoEstelar(
        "Fluctuación de Cerebro de Boltzmann",
        "Una entidad autoconsciente surge espontáneamente por fluctuaciones cuánticas "
        "en el vacío. Interfiere los sensores con transmisiones ilógicas y paradojas "
        "matemáticas antes de disiparse por entropía.",
        "Física Teórica",
        "🧠"
    ),
    EventoEstelar(
        "Agujero Negro Primordial",
        "Una distorsión gravitacional masiva del tamaño de un átomo, remanente del "
        "Big Bang, altera bruscamente la trayectoria. Los detectores no registran "
        "radiación Hawking a tiempo.",
        "Física Teórica",
        "🕳️"
    ),
    EventoEstelar(
        "Encuentro con Cuerda Cósmica",
        "Un defecto topológico unidimensional en el espacio-tiempo provoca un efecto "
        "de lente gravitacional extremo. Las estrellas de fondo se duplican y el "
        "motor de curvatura se desestabiliza.",
        "Física Teórica",
        "🌀"
    ),
    EventoEstelar(
        "Condensado de Materia Oscura",
        "La nave queda atrapada temporalmente en un pozo gravitacional invisible. "
        "No se detecta masa bariónica, pero los motores experimentan una resistencia "
        "inercial inexplicable.",
        "Física Teórica",
        "🌌"
    ),

    # ── 3. Anómalos y Ficticios ────────────────────────────────────
    EventoEstelar(
        "Eco de Taquiones (Anomalía Causal)",
        "Los sensores detectan partículas superlumínicas viajando hacia atrás en el "
        "tiempo. La nave registra daños de un impacto minutos antes de que realmente "
        "ocurra, permitiendo una prevención temporal.",
        "Anómalo / Ficticio",
        "⏳"
    ),
    EventoEstelar(
        "Enjambre de Sondas Von Neumann",
        "Millones de máquinas autorreplicantes desmantelan un asteroide errante. "
        "Ignoran a la nave a menos que se interfiera con su ciclo de recolección.",
        "Anómalo / Ficticio",
        "🤖"
    ),
    EventoEstelar(
        "Escombros de Megaestructura",
        "La nave atraviesa un campo de restos de lo que parece ser un cilindro de "
        "O'Neill destruido o un segmento de una antigua Esfera de Dyson. Los materiales "
        "no coinciden con ninguna aleación conocida.",
        "Anómalo / Ficticio",
        "🏗️"
    ),
    EventoEstelar(
        "Burbuja de Falso Vacío",
        "Los instrumentos cuánticos alertan sobre la proximidad del decaimiento del "
        "estado de vacío local. Se ordena un salto de emergencia inmediato para evitar "
        "la desintegración de la materia a nivel subatómico.",
        "Anómalo / Ficticio",
        "💠"
    ),
]

# Pesos para la selección aleatoria (mayor peso = más frecuente)
PESOS_EVENTOS = [
    12,  # Planeta Errante
    14,  # Polvo Interestelar
    6,   # GRB
    10,  # Nube de Oort
    4,   # Cerebro de Boltzmann
    3,   # Agujero Negro Primordial
    5,   # Cuerda Cósmica
    5,   # Materia Oscura
    2,   # Eco de Taquiones
    3,   # Sondas Von Neumann
    2,   # Megaestructura
    1,   # Burbuja de Falso Vacío (muy raro)
]


def generar_cola_eventos(origen: str, destino: str) -> List[EventoEstelar]:
    """
    Genera la secuencia completa de eventos para el viaje origen→destino.
    La semilla depende de ambos nombres, por lo que es siempre idéntica.
    Retorna una lista con los eventos en el orden en que ocurrirán.
    """
    rng_viaje = derivar_rng(origen, destino, "eventos_viaje")
    num_eventos = rng_viaje.choices([0, 1, 2, 3], weights=[30, 40, 25, 5])[0]

    if num_eventos == 0:
        return []

    eventos_disponibles = list(range(len(CATALOGO_EVENTOS)))
    pesos = PESOS_EVENTOS[:]
    seleccionados = []

    for _ in range(num_eventos):
        total = sum(pesos[i] for i in eventos_disponibles)
        if total == 0:
            break
        umbral = rng_viaje.uniform(0, total)
        acumulado = 0
        elegido = None
        for idx in eventos_disponibles:
            acumulado += pesos[idx]
            if umbral <= acumulado:
                elegido = idx
                break
        if elegido is not None:
            seleccionados.append(CATALOGO_EVENTOS[elegido])
            eventos_disponibles.remove(elegido)

    return seleccionados


def mostrar_evento(evento: EventoEstelar, numero: int):
    """Muestra un evento individual durante el viaje."""
    print(f"\n  ── Etapa {numero} ──────────────────────────────────────────────")
    print(f"  {evento.icono}  {evento.nombre}")
    print(f"     [{evento.categoria}]")
    print(f"     {evento.descripcion}")


# ══════════════════════════════════════════════════════════════════
#  ESTRELLA
# ══════════════════════════════════════════════════════════════════

class Estrella:
    """
    Modelo estelar basado en secuencia principal (ZAMS).
    
    Relaciones de escala:
      Luminosidad: L ∝ M^3.5  (empírica, válida para 0.5–50 M☉)
      Radio:       R ∝ M^0.8
      Temperatura: T = T☉ · (L/L☉)^0.25 / (R/R☉)^0.5  (Stefan-Boltzmann)
    """
    def __init__(self, masa_solar: float):
        self.masa        = masa_solar                          # M☉
        self.luminosidad = masa_solar ** 3.5                   # L☉
        self.radio       = masa_solar ** 0.8                   # R☉

        # Temperatura efectiva via Stefan-Boltzmann: L = 4πR²σT⁴
        self.temperatura = C.TEMP_SOL * (self.luminosidad ** 0.25) / (self.radio ** 0.5)

        # Zonas orbitales (en UA)
        self.zona_hab_int = math.sqrt(self.luminosidad / C.ZH_INTERIOR)
        self.zona_hab_ext = math.sqrt(self.luminosidad / C.ZH_EXTERIOR)
        self.linea_nieve  = C.LINEA_NIEVE * math.sqrt(self.luminosidad)

    def clasificar(self) -> str:
        """Clasificación espectral simplificada (Morgan-Keenan)."""
        T = self.temperatura
        if   T >= 30000: return "O"
        elif T >= 10000: return "B"
        elif T >=  7500: return "A"
        elif T >=  6000: return "F"
        elif T >=  5200: return "G"
        elif T >=  3700: return "K"
        else:            return "M"

    def color_visual(self) -> str:
        clase = self.clasificar()
        colores = {"O": "Azul intenso", "B": "Azul-blanco",
                   "A": "Blanca",       "F": "Amarillo-blanco",
                   "G": "Amarilla",     "K": "Naranja", "M": "Roja"}
        return colores.get(clase, "Desconocido")


# ══════════════════════════════════════════════════════════════════
#  LUNA
# ══════════════════════════════════════════════════════════════════

@dataclass
class Luna:
    masa:  float   # M⊕
    radio: float   # R⊕
    tipo:  str

    @classmethod
    def desde_disco_acrecion(cls, masa_padre: float, rng: random.Random) -> "Luna":
        """Lunas regulares formadas en disco circunplanetario (heladas/rocosas, pequeñas)."""
        masa  = rng.uniform(1e-4, max(1e-4, masa_padre * 0.001))
        radio = masa ** 0.28
        return cls(masa=masa, radio=radio, tipo="Helada/Rocosa (Regular)")

    @classmethod
    def desde_impacto(cls, masa_padre: float, rng: random.Random) -> "Luna":
        """Lunas de impacto gigante o captura gravitacional (pueden ser masivas)."""
        masa  = rng.uniform(0.005, min(0.15, masa_padre * 0.12))
        radio = masa ** 0.28
        return cls(masa=masa, radio=radio, tipo="Rocosa (Impacto/Captura)")


# ══════════════════════════════════════════════════════════════════
#  PLANETA
# ══════════════════════════════════════════════════════════════════

class Planeta:
    # Tipos posibles — originales
    ROCOSO          = "Rocoso"
    GIGANTE_GASEOSO = "Gigante Gaseoso"
    GIGANTE_HELADO  = "Gigante Helado"
    JUPTER_CALIENTE = "Júpiter Caliente"
    SUPER_TIERRA    = "Super-Tierra"

    # Tipos nuevos — Terrestres
    SUBTIERRA       = "Subtierra"           # Masa < 0.5 M⊕  (análogo a Marte)
    MEGATIERRA      = "Megatierra"          # Sólido > 10 M⊕  (máximo rocoso)
    HIERRO          = "Planeta de Hierro"   # Núcleo metálico dominante, densísimo
    SIN_NUCLEO      = "Planeta sin Núcleo"  # Sin diferenciación interna, baja densidad

    # Tipos nuevos — Gaseosos
    MINI_NEPTUNO    = "Mini-Neptuno"        # El tipo más común en la galaxia (Kepler)
    CTONIANO        = "Planeta Ctónico"     # Núcleo desnudo de un gigante que perdió su atmósfera
    HINCHADO        = "Júpiter Hinchado"    # Puffy Planet: atmósfera expandida por irradiación

    # Etiquetas dinámicas — asignadas tras cálculos climáticos (no son tipos base)
    LAVA            = "Planeta de Lava"     # T_superficie > 1200°C
    OCEANO          = "Planeta Océano"      # Rocoso en ZH con alta fracción de agua
    HELADO          = "Planeta Helado"      # T_superficie < -80°C (no exterior a línea de nieve)
    DESIERTO        = "Planeta Desierto"    # Alta T + atmósfera tenue
    ANALOGO         = "Análogo Terrestre"   # ESI ≥ 90%

    # Conjunto de tipos "terrestres" para uso interno (ESI, IHH, vida, etc.)
    _TERRESTRES = None   # se inicializa como propiedad de clase abajo

    def __init__(self, distancia_ua: float, estrella: Estrella, rng: random.Random):
        self.distancia_original = distancia_ua
        self.distancia          = distancia_ua
        self.estrella           = estrella
        self.rng                = rng

        self.tipo         = ""
        self.masa         = 0.0        # M⊕
        self.radio        = 0.0        # R⊕
        self.gravedad     = 0.0        # g⊕ (relativa)
        self.radio_hill   = 0.0        # UA
        self.presion_atm  = 0.0        # atm
        self.atmosfera: dict[str, float] = {}
        self.temp_superficie = 0.0     # K
        self.prob_vida    = 0.0        # 0–100
        self.en_zona_hab  = False
        self.lunas: list[Luna] = []
        self.notas: list[str] = []

        # ── Nuevos índices ──────────────────────────────────────────
        self.esi  = 0.0   # Earth Similarity Index (0–100%)
        self.ihh  = 0.0   # Índice de Habitabilidad Humana (0–100%)

        self._formacion_primordial()
        self._calcular_estructura()

    # ── Helper: familia terrestre ─────────────────────────────────

    @property
    def _es_terrestre(self) -> bool:
        """True para cualquier tipo con superficie sólida (base o etiqueta dinámica)."""
        return self.tipo in (
            self.ROCOSO, self.SUPER_TIERRA, self.SUBTIERRA, self.MEGATIERRA,
            self.HIERRO, self.SIN_NUCLEO, self.CTONIANO,
            self.LAVA, self.OCEANO, self.HELADO, self.DESIERTO, self.ANALOGO,
        )

    # ── Formación ─────────────────────────────────────────────────

    def _formacion_primordial(self):
        """
        Composición según posición relativa a la línea de nieve.

        Interior a la línea de nieve → planetas rocosos/terrestres:
          < 0.5 M⊕  → Subtierra
          0.5–4.5   → Rocoso (+ variantes Hierro / Sin-Núcleo según RNG)
          4.5–10    → Super-Tierra
          > 10 M⊕   → Megatierra  (sólido masivo, no acretó suficiente gas)

        Exterior a la línea de nieve → planetas gaseosos/helados:
          nucleo < 4  → Mini-Neptuno  (el más común en la galaxia según Kepler)
          4–10        → Gigante Helado
          > 10        → Gigante Gaseoso
        """
        if self.distancia < self.estrella.linea_nieve:
            nucleo_masa = self.rng.uniform(0.1, 7.0)      # ampliado para incluir subtierras
            variante    = self.rng.random()                # decide entre sub-tipos rocosos

            if nucleo_masa < 0.5:
                # ── Subtierra (tipo Marte / Mercurio) ──────────────
                self.tipo = self.SUBTIERRA
                self.masa = nucleo_masa

            elif nucleo_masa > 5.5:
                # ── Megatierra (sólido masivo) ──────────────────────
                self.tipo = self.MEGATIERRA
                self.masa = self.rng.uniform(10.0, 20.0)

            elif nucleo_masa > 4.5:
                # ── Super-Tierra (igual que antes) ──────────────────
                self.tipo = self.SUPER_TIERRA
                self.masa = self.rng.uniform(4.5, 10.0)

            else:
                # ── Rocoso con posibles variantes mineralógicas ──────
                if variante < 0.15:
                    # Planeta de Hierro: núcleo metálico dominante
                    self.tipo = self.HIERRO
                    self.masa = nucleo_masa
                elif variante < 0.25:
                    # Planeta sin núcleo: baja densidad, sin diferenciación
                    self.tipo = self.SIN_NUCLEO
                    self.masa = nucleo_masa
                else:
                    self.tipo = self.ROCOSO
                    self.masa = nucleo_masa

        else:
            nucleo = self.rng.uniform(1.0, 22.0)
            if nucleo > 10.0:
                # ── Gigante Gaseoso (igual que antes) ───────────────
                self.tipo = self.GIGANTE_GASEOSO
                self.masa = self.rng.uniform(50.0, 600.0)
            elif nucleo > 4.0:
                # ── Gigante Helado (igual que antes) ────────────────
                self.tipo = self.GIGANTE_HELADO
                self.masa = self.rng.uniform(5.0, 30.0)
            else:
                # ── Mini-Neptuno (nuevo) — el más común en la galaxia
                self.tipo = self.MINI_NEPTUNO
                self.masa = self.rng.uniform(5.0, 20.0)

    def _calcular_estructura(self):
        """
        Radio, gravedad y radio de Hill.

        Relaciones masa-radio por familia:
          Rocoso/Super-Tierra: R ∝ M^0.274  (Fortney et al. 2007)
          Subtierra/Megatierra: misma ley (son extremos de la escala rocosa)
          Hierro: ~25% más denso → radio reducido un ~20%
          Sin núcleo: ~15% menos denso → radio ligeramente mayor
          Ctónico: núcleo desnudo metálico/rocoso → muy denso
          Gigante Helado / Mini-Neptuno: R ∝ M^0.35
          Gigante Gaseoso: logarítmico (degeneración de presión)
          Hinchado: como GG pero factor ×1.8 (expansión térmica)
        """
        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA,
                         self.SUBTIERRA, self.MEGATIERRA):
            self.radio = self.masa ** 0.274

        elif self.tipo == self.HIERRO:
            # Densidad ~1.4× la terrestre → radio ~20% menor a igual masa
            self.radio = (self.masa ** 0.274) * 0.80

        elif self.tipo == self.SIN_NUCLEO:
            # Baja densidad (sin diferenciación) → radio ~12% mayor
            self.radio = (self.masa ** 0.274) * 1.12

        elif self.tipo == self.CTONIANO:
            # Núcleo desnudo muy comprimido → aún más denso que Hierro
            self.radio = (self.masa ** 0.274) * 0.70

        elif self.tipo in (self.GIGANTE_HELADO, self.MINI_NEPTUNO):
            self.radio = self.masa ** 0.35

        elif self.tipo == self.GIGANTE_GASEOSO:
            self.radio = 10.0 + math.log10(max(1.0, self.masa / 100.0)) * 2.5

        elif self.tipo == self.HINCHADO:
            # Atmósfera expandida por irradiación → radio muy superior al esperado
            base = 10.0 + math.log10(max(1.0, self.masa / 100.0)) * 2.5
            self.radio = base * 1.8

        self.gravedad = self.masa / (self.radio ** 2)

        masa_solar = self.masa * C.MASA_TERRESTRE_SOLAR
        self.radio_hill = self.distancia * ((masa_solar / (3.0 * self.estrella.masa)) ** (1.0 / 3.0))

    # ── Termodinámica y Clima ──────────────────────────────────────

    def evolucionar_clima_y_vida(self):
        """
        Ejecutar DESPUÉS de la migración orbital.
        Calcula temperatura real, atmósfera, efecto invernadero,
        probabilidad de vida, ESI e IHH.
        """
        self.en_zona_hab = self.estrella.zona_hab_int <= self.distancia <= self.estrella.zona_hab_ext

        albedo = self._albedo_primordial()
        r_estelar_ua = self.estrella.radio * C.RADIO_SOLAR_UA
        temp_eq = (self.estrella.temperatura
                   * math.sqrt(r_estelar_ua / (2.0 * self.distancia))
                   * ((1.0 - albedo) ** 0.25))

        self._generar_atmosfera(temp_eq)
        delta_t = self._efecto_invernadero()
        self.temp_superficie = temp_eq + delta_t

        self._calcular_prob_vida()
        self._generar_lunas()

        # ── Calcular índices derivados ──
        self.esi = self._calcular_esi()
        self.ihh = self._calcular_ihh()

        # ── Etiquetas dinámicas (SIEMPRE al final, tras todos los cálculos) ──
        self._aplicar_etiquetas_dinamicas()

    def _aplicar_etiquetas_dinamicas(self):
        """
        Transforma el tipo planetario en una etiqueta descriptiva según los
        resultados climáticos calculados. Se ejecuta SIEMPRE al final de
        evolucionar_clima_y_vida(), cuando ESI/IHH/prob_vida ya están fijos.

        Prioridades (el primero que se activa gana):
          1. Planeta de Lava    → T_sup > 1200°C  (lava fundida en superficie)
          2. Análogo Terrestre  → ESI ≥ 90%        (el más cercano a la Tierra)
          3. Planeta Océano     → ZH + agua + RNG  (mundo acuático)
          4. Planeta Helado     → T_sup < −80°C    (congelado en superficie)
          5. Planeta Desierto   → T alta + P baja  (árido extremo)
        """
        # Solo aplica a tipos con superficie sólida (no gaseosos/helados)
        _TIPOS_BASE_SOLIDOS = (
            self.ROCOSO, self.SUPER_TIERRA, self.SUBTIERRA,
            self.MEGATIERRA, self.HIERRO, self.SIN_NUCLEO,
        )
        if self.tipo not in _TIPOS_BASE_SOLIDOS:
            return

        temp_c = self.temp_superficie + C.ABS_ZERO

        # ── 1. Planeta de Lava ──────────────────────────────────────
        # El basalto comienza a fundirse a ~700°C, superficie ígnea >900°C
        if temp_c > 900.0:
            self.tipo = self.LAVA
            self.notas.append(
                f"Temperatura ({temp_c:.0f}°C) supera fusión del basalto — superficie de lava fundida.")
            return

        # ── 2. Análogo Terrestre (ESI ≥ 90%) ───────────────────────
        # Etiqueta de máximo prestigio: ESI ya calculado con el tipo base
        if self.esi >= 90.0:
            self.tipo = self.ANALOGO
            self.notas.append(
                f"ESI = {self.esi:.1f}% — el mundo más parecido a la Tierra en este sistema.")
            return

        # ── 3. Planeta Océano ───────────────────────────────────────
        # Rocoso en ZH con temperatura líquida y probabilidad de agua alta
        if (self.en_zona_hab
                and 0.0 < temp_c < 100.0
                and self.prob_vida > 0.0
                and self.rng.random() < 0.30):
            self.tipo = self.OCEANO
            # Actualiza la atmósfera para reflejar un mundo oceánico
            self.atmosfera = {
                "Nitrógeno (N2)":        75.0,
                "Vapor de agua":         20.0,
                "Dióxido de Carbono (CO2)": 4.0,
                "Argón (Ar)":             1.0,
            }
            self.notas.append(
                "Alta fracción de agua superficial detectada — mundo de océano global.")
            return

        # ── 4. Planeta Helado ───────────────────────────────────────
        # Distinto del Gigante Helado: es un sólido con superficie congelada
        if temp_c < -80.0:
            self.tipo = self.HELADO
            self.notas.append(
                f"Temperatura ({temp_c:.0f}°C) — superficie cubierta de hielo permanente.")
            return

        # ── 5. Planeta Desierto ─────────────────────────────────────
        # Cálido + atmósfera demasiado tenue para retener agua
        if temp_c > 80.0 and self.presion_atm < 0.05:
            self.tipo = self.DESIERTO
            self.notas.append(
                "Alta temperatura y atmósfera tenue — mundo desierto sin agua superficial.")
            return

    def _albedo_primordial(self) -> float:
        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA,
                         self.SUBTIERRA, self.MEGATIERRA,
                         self.HIERRO, self.SIN_NUCLEO):
            return self.rng.uniform(0.10, 0.45)
        elif self.tipo == self.CTONIANO:
            # Núcleo oscuro y desnudo → albedo bajo
            return self.rng.uniform(0.05, 0.15)
        elif self.tipo in (self.GIGANTE_HELADO, self.MINI_NEPTUNO):
            return self.rng.uniform(0.40, 0.70)
        else:  # Gigante Gaseoso, Júpiter Caliente, Hinchado
            return self.rng.uniform(0.30, 0.65)

    def _generar_atmosfera(self, temp_eq: float):
        es_rocoso = self._es_terrestre

        if self.tipo == self.JUPTER_CALIENTE:
            self.presion_atm = self.rng.uniform(500.0, 2000.0)
            self.atmosfera = {"Hidrógeno (H2)": 85.0, "Helio (He)": 13.0, "Vapor de agua": 2.0}
            self.notas.append("Inflación atmosférica severa por irradiación estelar.")
            return

        if self.tipo == self.HINCHADO:
            # Igual que JC pero presión aún mayor y mucho vapor de agua
            self.presion_atm = self.rng.uniform(1000.0, 5000.0)
            self.atmosfera = {"Hidrógeno (H2)": 80.0, "Helio (He)": 12.0,
                              "Vapor de agua": 6.0, "Metano (CH4)": 2.0}
            self.notas.append("Radio inflado masivamente — densidad media muy baja (Puffy Planet).")
            return

        if self.tipo == self.GIGANTE_GASEOSO:
            self.presion_atm = 1000.0
            self.atmosfera = {"Hidrógeno (H2)": 89.0, "Helio (He)": 10.0, "Metano (CH4)": 1.0}
            return

        if self.tipo == self.GIGANTE_HELADO:
            self.presion_atm = 500.0
            self.atmosfera = {"Hidrógeno (H2)": 73.0, "Helio (He)": 15.0,
                              "Metano (CH4)": 8.0, "Amoníaco (NH3)": 4.0}
            return

        if self.tipo == self.MINI_NEPTUNO:
            # Atmósfera de hidrógeno/helio con más volátiles que un Helado
            self.presion_atm = self.rng.uniform(100.0, 800.0)
            self.atmosfera = {"Hidrógeno (H2)": 65.0, "Helio (He)": 20.0,
                              "Metano (CH4)": 10.0, "Amoníaco (NH3)": 5.0}
            return

        if self.tipo == self.CTONIANO:
            # Núcleo desnudo: atmósfera casi inexistente (evaporada) o exosfera residual
            if temp_eq > 400:
                self.presion_atm = 0.0
                self.atmosfera = {"Vacío (trazas)": 100.0}
                self.notas.append("Núcleo desnudo — atmósfera completamente evaporada por irradiación.")
            else:
                self.presion_atm = self.rng.uniform(0.0, 0.01)
                self.atmosfera = {"Silicatos (vapor)": 60.0, "Oxígeno (atómico)": 40.0}
                self.notas.append("Exosfera residual de silicatos evaporados.")
            return

        # ── A partir de aquí: tipos terrestres con superficie ────
        if temp_eq > 600 and self.gravedad < 0.4:
            self.presion_atm = 0.0
            self.atmosfera = {"Vacío (trazas)": 100.0}
            self.notas.append("Atmósfera evaporada por proximidad estelar (escape de Jeans).")
            return

        if temp_eq > 800 and self.gravedad < 0.8:
            self.presion_atm = 0.0
            self.atmosfera = {"Vacío (trazas)": 100.0}
            self.notas.append("Irradiación extrema — posible lava en superficie.")
            return

        # Subtierra: gravedad baja → atmósfera muy tenue
        if self.tipo == self.SUBTIERRA:
            base_presion = self.gravedad ** 2.0   # cae más rápido con poca grav.
            self.presion_atm = self.rng.uniform(0.0, 0.5) * base_presion
            co2 = self.rng.uniform(75.0, 95.0)
            n2  = 100.0 - co2 - self.rng.uniform(0.2, 1.0)
            self.atmosfera = {
                "Dióxido de Carbono (CO2)": round(co2, 1),
                "Nitrógeno (N2)": round(max(0, n2), 1),
            }
            return

        # Megatierra: gravedad alta → atmósfera muy densa y presión enorme
        if self.tipo == self.MEGATIERRA:
            base_presion = self.gravedad ** 1.5
            self.presion_atm = self.rng.uniform(10.0, 300.0) * base_presion
            co2 = self.rng.uniform(60.0, 92.0)
            n2  = 100.0 - co2 - self.rng.uniform(1.0, 4.0)
            self.atmosfera = {
                "Dióxido de Carbono (CO2)": round(co2, 1),
                "Nitrógeno (N2)": round(max(0, n2), 1),
            }
            self.notas.append("Masa elevada genera presión superficial extrema.")
            return

        # Hierro: volcanes de silicato activos → SO2 y CO2
        if self.tipo == self.HIERRO:
            base_presion = self.gravedad ** 1.5
            self.presion_atm = self.rng.uniform(0.001, 50.0) * base_presion
            co2 = self.rng.uniform(60.0, 88.0)
            so2 = self.rng.uniform(5.0, 20.0)
            n2  = max(0, 100.0 - co2 - so2)
            self.atmosfera = {
                "Dióxido de Carbono (CO2)": round(co2, 1),
                "Dióxido de Azufre (SO2)":  round(so2, 1),
                "Nitrógeno (N2)":            round(n2,  1),
            }
            return

        # Sin núcleo: composición más primitiva, más metano residual
        if self.tipo == self.SIN_NUCLEO:
            base_presion = self.gravedad ** 1.5
            self.presion_atm = self.rng.uniform(0.005, 80.0) * base_presion
            co2  = self.rng.uniform(60.0, 85.0)
            ch4  = self.rng.uniform(2.0, 10.0)
            n2   = max(0, 100.0 - co2 - ch4)
            self.atmosfera = {
                "Dióxido de Carbono (CO2)": round(co2, 1),
                "Metano (CH4)":             round(ch4, 1),
                "Nitrógeno (N2)":           round(n2,  1),
            }
            return

        # ── Rocoso / Super-Tierra: lógica original ────────────────
        base_presion = self.gravedad ** 1.5
        self.presion_atm = self.rng.uniform(0.005, 120.0) * base_presion

        co2  = self.rng.uniform(75.0, 96.0)
        n2   = 100.0 - co2 - self.rng.uniform(0.5, 2.0)
        self.atmosfera = {
            "Dióxido de Carbono (CO2)": round(co2, 1),
            "Nitrógeno (N2)": round(max(0, n2), 1),
        }

    def _efecto_invernadero(self) -> float:
        if self.presion_atm <= 0 or not self._es_terrestre:
            return 0.0

        delta_t = 0.0

        frac_co2 = self.atmosfera.get("Dióxido de Carbono (CO2)", 0.0) / 100.0
        p_co2_atm = frac_co2 * self.presion_atm

        if p_co2_atm > 1e-6:
            F_co2 = 5.35 * math.log(p_co2_atm / 0.0004 + 1.0)
            sensibilidad = 0.8 * math.log10(self.presion_atm + 1.5)
            delta_t += sensibilidad * F_co2

        frac_ch4 = self.atmosfera.get("Metano (CH4)", 0.0) / 100.0
        p_ch4_ppm = frac_ch4 * self.presion_atm * 1e6
        if p_ch4_ppm > 1.0:
            delta_t += 0.036 * math.sqrt(p_ch4_ppm)

        # SO2 también tiene efecto invernadero significativo (planetas de Hierro)
        frac_so2 = self.atmosfera.get("Dióxido de Azufre (SO2)", 0.0) / 100.0
        p_so2_atm = frac_so2 * self.presion_atm
        if p_so2_atm > 1e-6:
            delta_t += 3.0 * math.log(p_so2_atm / 0.0001 + 1.0)

        return min(delta_t, 600.0)

    def _calcular_prob_vida(self):
        if not self._es_terrestre or self.tipo in (self.CTONIANO,):
            self.prob_vida = 0.0
            return

        if self.presion_atm < 0.006:
            self.prob_vida = 0.0
            self.notas.append("Presión insuficiente para agua líquida en superficie.")
            return

        temp_c = self.temp_superficie + C.ABS_ZERO

        if not (0.0 < temp_c < 100.0):
            self.prob_vida = 0.0
            return

        t_optima = 15.0
        sigma_t  = 35.0
        score_t  = 100.0 * math.exp(-((temp_c - t_optima) ** 2) / (2 * sigma_t ** 2))
        score_g  = max(0.0, 100.0 - (abs(self.gravedad - 1.0) * 60.0))
        score_zh = 25.0 if self.en_zona_hab else 0.0

        if 0.5 <= self.presion_atm <= 5.0:
            score_p = 20.0
        elif 0.006 <= self.presion_atm < 0.5:
            score_p = 10.0
        elif self.presion_atm < 100.0:
            score_p = 5.0
        else:
            score_p = 2.0

        self.prob_vida = min(100.0, (score_t * 0.45) + (score_g * 0.25) + score_zh + score_p)

        if self.prob_vida > 55.0:
            self.atmosfera = {"Nitrógeno (N2)": 78.0, "Oxígeno (O2)": 21.0, "Argón (Ar)": 1.0}
            self.notas.append("Atmósfera oxidante — posible biosfera fotosintética activa.")
            self.prob_vida = min(100.0, self.prob_vida + self.rng.uniform(8.0, 18.0))

    # ══════════════════════════════════════════════════════════════
    #  ESI — EARTH SIMILARITY INDEX
    #  Schulze-Makuch et al. (2011), Astrobiology 11(10):1041-1052
    #  DOI: 10.1089/ast.2010.0592
    # ══════════════════════════════════════════════════════════════

    def _calcular_esi(self) -> float:
        """
        Índice de Similaridad Terrestre (ESI).
        
        Fórmula original (Schulze-Makuch et al. 2011):
            ESI_i = (1 - |x_i - x_0| / (x_i + x_0)) ^ (w_i / n)
            ESI   = ∏ ESI_i
        
        Donde x_i es el valor planetario, x_0 el terrestre de referencia,
        w_i el peso de sensibilidad y n el número de parámetros.
        
        Parámetros y pesos (ajustados para el modelo de este simulador):
          ┌─────────────────────────┬──────────┬───────────────────────┐
          │ Parámetro               │   w_i    │ Referencia (Tierra)   │
          ├─────────────────────────┼──────────┼───────────────────────┤
          │ Radio (R⊕)              │  0.57    │ 1.0 R⊕                │
          │ Densidad relativa       │  1.07    │ 1.0 (normalizada)     │
          │ Velocidad de escape     │  0.70    │ 1.0 (normalizada)     │
          │ Temperatura superficie  │  5.58    │ 288 K (15°C media)    │
          └─────────────────────────┴──────────┴───────────────────────┘
        
        El peso altísimo de la temperatura (5.58) refleja que incluso
        pequeñas desviaciones térmicas degradan el ESI drásticamente —
        Mars tiene ESI ~0.64 principalmente por su T_media de -60°C.
        
        Solo aplicable a cuerpos rocosos (ESI ~0 para gigantes gaseosos
        por convención del catálogo HEC).
        """
        # Todos los tipos terrestres son comparables con la Tierra
        # Los gaseosos retornan 0 por convención del catálogo HEC
        if not self._es_terrestre:
            return 0.0

        def esi_factor(x_p: float, x_0: float, w: float) -> float:
            """Factor de un parámetro individual."""
            if x_p + x_0 <= 0:
                return 0.0
            return (1.0 - abs(x_p - x_0) / (x_p + x_0)) ** w

        # Densidad relativa: ρ ∝ masa / radio³
        # (Normalizada contra Tierra = 1.0 → comparación relativa directa)
        rho_p   = self.masa / max(self.radio ** 3, 1e-9)

        # Velocidad de escape relativa: v_esc ∝ √(M/R)
        # (Tierra = 11.2 km/s → ratio v_p/v_Tierra = √(M_p·R_T / M_T·R_p))
        v_esc_p = math.sqrt(max(self.masa / self.radio, 1e-9))

        # Temperatura de superficie en Kelvin
        T_p = self.temp_superficie   # ya es en K

        esi = (esi_factor(self.radio,  C.ESI_R_REF,    0.57) *
               esi_factor(rho_p,       C.ESI_RHO_REF,  1.07) *
               esi_factor(v_esc_p,     C.ESI_VESC_REF, 0.70) *
               esi_factor(T_p,         C.ESI_T_REF,    5.58))

        return round(esi * 100.0, 1)

    # ══════════════════════════════════════════════════════════════
    #  IHH — ÍNDICE DE HABITABILIDAD HUMANA
    #  Basado en estándares NASA/ESA para misiones tripuladas y
    #  umbrales fisiológicos establecidos en la literatura médica
    #  espacial (Convertino & Feiveson 2016; Rayman et al. 2020).
    # ══════════════════════════════════════════════════════════════

    def _calcular_ihh(self) -> float:
        """
        Índice de Habitabilidad Humana (IHH).
        
        A diferencia del ESI (similaridad física pura), el IHH evalúa si
        un ser humano con tecnología de supervivencia básica (traje, filtros,
        presurización parcial) podría vivir de forma prolongada en el planeta.
        
        ── FILTROS ELIMINATORIOS (retornan 0% si se activan) ──────────────
        
          ① Punto de Armstrong (<0.0618 atm):
               Por debajo de esta presión, el agua corporal hierve a 37°C.
               Sin traje, muerte en ~15 segundos. Referencia: FAA-AM-68-10.
        
          ② Temperatura extrema (<-90°C o >150°C):
               Límites absolutos donde ningún material de aislamiento
               conocido protege suficientemente para operaciones prolongadas.
        
          ③ Gravedad incompatible (<0.15g o >3.5g):
               <0.15g → pérdida ósea y muscular irreversible en semanas.
               >3.5g  → colapso cardiovascular; el corazón no puede bombear
                        sangre al cerebro bajo esa carga.
        
        ── MÓDULOS DE PUNTUACIÓN (100 puntos totales) ─────────────────────
        
          [30 pts] Atmósfera respirable:
               Presión parcial de O2 (p_O2 = frac_O2 × P_total):
               • 0.16–0.30 atm → respirable sin equipo (+30 pts)
               • 0.10–0.16 atm → hipóxico, requiere máscara (+15 pts)
               • Presente pero fuera de rango → soporte parcial (+5 pts)
               • Sin O2 → traje completo (+0 pts)
        
          [25 pts] Temperatura de confort:
               Curva gaussiana centrada en 20°C (σ=20°C).
               Rango confortable sin traje especializado: -20°C a 45°C.
               Supervivencia con traje: -60°C a 60°C (+5 pts fijos).
        
          [20 pts] Presión atmosférica:
               • 0.70–1.40 atm → zona de confort humano (+20 pts)
               • 0.35–0.70 atm → tolerable con adaptación (+10 pts)
               • 1.40–3.00 atm → requiere equipo leve (+10 pts)
               • 3.00–5.00 atm → traje presurizado (+3 pts)
        
          [15 pts] Gravedad superficial:
               • 0.80–1.25 g → máximo confort fisiológico (+15 pts)
               • 0.50–0.80 g → adaptable en meses (ISS: 0g) (+8 pts)
               • 1.25–1.80 g → tolerable a largo plazo (+8 pts)
               • 0.30–0.50 g → problemas musculo-esqueléticos (+3 pts)
               • 1.80–2.50 g → problemas cardiovasculares (+3 pts)
        
          [10 pts] Radiación estelar según clase espectral:
               • G, F → espectro solar, UV manejable (+10 pts)
               • K    → candidatas prometedoras, menos UV (+8 pts)
               • M    → llamas estelares frecuentes, alta variabilidad (+3 pts)
               • A    → exceso UV, vida estelar corta (+2 pts)
               • O, B → radiación ionizante letal en superficie (+0 pts)
        """
        if not self._es_terrestre:
            return 0.0

        temp_c = self.temp_superficie + C.ABS_ZERO

        # ── Filtros Eliminatorios ──────────────────────────────────
        if self.presion_atm < C.IHH_ARMSTRONG:
            return 0.0
        if temp_c < C.IHH_TEMP_MIN_ABS or temp_c > C.IHH_TEMP_MAX_ABS:
            return 0.0
        if self.gravedad < C.IHH_G_MIN or self.gravedad > C.IHH_G_MAX:
            return 0.0

        score = 0.0

        # ── Módulo 1: Atmósfera Respirable (30 pts) ───────────────
        frac_o2    = self.atmosfera.get("Oxígeno (O2)", 0.0) / 100.0
        p_o2_atm   = frac_o2 * self.presion_atm   # presión parcial de O2

        if p_o2_atm > 0:
            if 0.16 <= p_o2_atm <= 0.30:
                score += 30.0   # Respirable sin equipo (21% O2 a 1 atm = 0.21 atm pO2)
            elif 0.10 <= p_o2_atm < 0.16 or 0.30 < p_o2_atm <= 0.50:
                score += 15.0   # Requiere máscara de oxígeno suplementario
            else:
                score += 5.0    # Presencia de O2 pero fuera de rango respirable
        # Sin O2: +0 pts (necesita traje completo de soporte vital)

        # ── Módulo 2: Temperatura (25 pts) ────────────────────────
        if -20.0 <= temp_c <= 45.0:
            # Curva gaussiana: máximo en 20°C, cae suavemente
            score += 25.0 * math.exp(-((temp_c - 20.0) ** 2) / (2 * 20.0 ** 2))
        elif -60.0 <= temp_c < -20.0 or 45.0 < temp_c <= 60.0:
            score += 5.0    # Supervivencia con traje de protección térmica

        # ── Módulo 3: Presión Atmosférica (20 pts) ────────────────
        if 0.70 <= self.presion_atm <= 1.40:
            score += 20.0   # Zona de confort (aviones presurizan a ~0.75 atm)
        elif 0.35 <= self.presion_atm < 0.70 or 1.40 < self.presion_atm <= 3.00:
            score += 10.0   # Requiere adaptación o equipo leve
        elif self.presion_atm <= 5.00:
            score += 3.0    # Traje presurizado necesario

        # ── Módulo 4: Gravedad (15 pts) ───────────────────────────
        if 0.80 <= self.gravedad <= 1.25:
            score += 15.0
        elif 0.50 <= self.gravedad < 0.80 or 1.25 < self.gravedad <= 1.80:
            score += 8.0
        elif 0.30 <= self.gravedad < 0.50 or 1.80 < self.gravedad <= 2.50:
            score += 3.0

        # ── Módulo 5: Radiación Estelar (10 pts) ──────────────────
        clase = self.estrella.clasificar()
        puntaje_radiacion = {"G": 10, "F": 10, "K": 8, "M": 3, "A": 2, "B": 0, "O": 0}
        score += puntaje_radiacion.get(clase, 0)

        return round(min(score, 100.0), 1)

    def _generar_lunas(self):
        token = getattr(self, "_seed_token", f"planeta_{self.distancia_original:.4f}")

        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA,
                         self.SUBTIERRA, self.MEGATIERRA,
                         self.HIERRO, self.SIN_NUCLEO):
            n = self.rng.choices([0, 1, 2], weights=[70, 24, 6])[0]
            # Subtierras raramente tienen lunas grandes
            if self.tipo == self.SUBTIERRA:
                n = self.rng.choices([0, 1], weights=[85, 15])[0]
            self.lunas = [Luna.desde_impacto(self.masa, derivar_rng(
                token, "luna_impacto", i)) for i in range(n)]

        elif self.tipo == self.CTONIANO:
            # Núcleo desnudo: perdió todas sus lunas por la migración/evaporación
            n = self.rng.choices([0, 1], weights=[90, 10])[0]
            self.lunas = [Luna.desde_impacto(self.masa, derivar_rng(
                token, "luna_impacto", i)) for i in range(n)]

        elif self.tipo in (self.GIGANTE_GASEOSO, self.JUPTER_CALIENTE):
            n = min(int(self.rng.uniform(4, self.masa * 0.15)), 95)
            self.lunas = [Luna.desde_disco_acrecion(self.masa, derivar_rng(
                token, "luna_disco", i)) for i in range(n)]

        elif self.tipo == self.HINCHADO:
            # Júpiter hinchado: órbitas internas inestables, pocas lunas
            n = self.rng.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]
            self.lunas = [Luna.desde_disco_acrecion(self.masa, derivar_rng(
                token, "luna_disco", i)) for i in range(n)]

        elif self.tipo in (self.GIGANTE_HELADO, self.MINI_NEPTUNO):
            n = min(int(self.rng.uniform(2, self.masa * 0.12)), 50)
            self.lunas = [Luna.desde_disco_acrecion(self.masa, derivar_rng(
                token, "luna_disco", i)) for i in range(n)]


# ══════════════════════════════════════════════════════════════════
#  CATÁLOGO OEC (OPEN EXOPLANET CATALOGUE)
# ══════════════════════════════════════════════════════════════════

_OEC_CACHE = None

def _cargar_catalogo_oec():
    global _OEC_CACHE
    if _OEC_CACHE is not None:
        return
    
    import os
    print("\n  [INFO] Cargando Open Exoplanet Catalogue...")
    try:
        if os.path.exists("systems.xml"):
            tree = ET.parse("systems.xml")
            print("  [INFO] Se utilizó la versión local (offline) del catálogo.")
        else:
            url = "https://github.com/OpenExoplanetCatalogue/oec_gzip/raw/master/systems.xml.gz"
            print("  [INFO] Descargando Open Exoplanet Catalogue...")
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            response = urllib.request.urlopen(request)
            compressed_file = io.BytesIO(response.read())
            decompressed_file = gzip.GzipFile(fileobj=compressed_file)
            tree = ET.parse(decompressed_file)
            
        root = tree.getroot()
        
        sistemas_validos = []
        for system in root.findall('.//system'):
            name_elem = system.find('name')
            if name_elem is not None:
                system_name = name_elem.text
                star_elem = system.find('.//star')
                if star_elem is not None:
                    mass_elem = star_elem.find('mass')
                    if mass_elem is not None and mass_elem.text is not None:
                        try:
                            mass = float(mass_elem.text)
                            const_elem = system.find('constellation')
                            constellation = const_elem.text if const_elem is not None else "Desconocida"
                            sistemas_validos.append((system_name, mass, constellation))
                        except ValueError:
                            pass
        _OEC_CACHE = sistemas_validos
        print(f"  [INFO] Se cargaron {len(_OEC_CACHE)} sistemas del catálogo.")
    except Exception as e:
        print(f"  [ERROR] No se pudo acceder al catálogo OEC: {e}")
        _OEC_CACHE = []

def obtener_estrella_oec(nombre_seed: str, rng: random.Random) -> tuple:
    # ── El Sol siempre está disponible ──
    if nombre_seed.upper() == "SOL":
        return ("Sol", 1.0, "Sistema Solar")

    _cargar_catalogo_oec()

    if not _OEC_CACHE:
        return nombre_seed, rng.uniform(0.6, 1.5), "Desconocida"

    for sys_name, mass, const in _OEC_CACHE:
        if sys_name.upper() == nombre_seed.upper():
            return sys_name, mass, const
            
    print(f"  [INFO] Sistema '{nombre_seed}' no encontrado en OEC. Eligiendo uno al azar deterministamente...")
    return rng.choice(_OEC_CACHE)

def obtener_sistema_aleatorio_oec() -> str:
    _cargar_catalogo_oec()
    if _OEC_CACHE:
        return random.choice(_OEC_CACHE)[0]
    return "SOL-442"


# ══════════════════════════════════════════════════════════════════
#  SISTEMA ESTELAR
# ══════════════════════════════════════════════════════════════════

class SistemaEstelar:
    """
    Genera un sistema estelar completo de forma determinista a partir de una seed.
    
    Pipeline de simulación:
      1. Formación estelar
      2. Acreción primordial (distribución Bode + margen de Hill)
      3. Migración planetaria dinámica (Júpiteres Calientes)
      4. Eliminación de órbitas inestables
      5. Evolución termoclimática + ESI + IHH
    """

    def __init__(self, seed: str = "SOL-442"):
        self.seed = seed
        self.rng_sistema = derivar_rng(seed, "sistema")
        self.planetas: list[Planeta] = []
        self.constelacion = "Desconocida"
        self._generar()

    def _generar(self):
        # ── 1. Estrella ──
        nombre_real, masa_estelar, constellation = obtener_estrella_oec(self.seed, self.rng_sistema)
        self.seed = nombre_real
        self.estrella = Estrella(masa_estelar)
        self.constelacion = constellation

        # ── 2. Acreción de Protoplanetas ──
        dist = self.rng_sistema.uniform(0.25, 0.65)
        idx  = 0
        while dist < 40.0:
            rng_planeta = derivar_rng(self.seed, "planeta", idx)
            p = Planeta(dist, self.estrella, rng_planeta)
            p._seed_token = f"{self.seed}_planeta_{idx}"
            self.planetas.append(p)
            idx += 1

            margen_hill = p.radio_hill * rng_planeta.uniform(3.5, 8.0)
            salto_bode  = dist * rng_planeta.uniform(1.4, 2.1)
            dist = max(dist + margen_hill, salto_bode)

        # ── 3. Migración Planetaria ──
        rng_mig = derivar_rng(self.seed, "migracion")
        for p in self.planetas:
            if p.tipo == Planeta.GIGANTE_GASEOSO and rng_mig.random() < 0.28:
                p.distancia = rng_mig.uniform(0.04, 0.45)
                p.tipo = Planeta.JUPTER_CALIENTE
                p.notas.append(f"Migró desde {p.distancia_original:.2f} UA durante la formación del sistema.")

                # ── Sub-mutación A: Planeta Ctónico ─────────────────
                # Si orbita extremadamente cerca, la irradiación evapora
                # toda la atmósfera y queda solo el núcleo desnudo.
                if p.distancia < 0.10 and rng_mig.random() < 0.38:
                    masa_nucleo = rng_mig.uniform(2.0, 15.0)   # núcleo rocoso/metálico
                    p.tipo = Planeta.CTONIANO
                    p.masa = masa_nucleo
                    p._calcular_estructura()   # recalcular radio/gravedad con nueva masa
                    p.notas.append(
                        "Atmósfera gigante evaporada por irradiación extrema — núcleo desnudo (Ctónico).")

                # ── Sub-mutación B: Júpiter Hinchado (Puffy) ────────
                # Irradiación intensa infla la atmósfera → radio enorme,
                # densidad media muy baja (algunos flotan en agua).
                elif p.distancia < 0.20 and p.masa < 200.0 and rng_mig.random() < 0.40:
                    p.tipo = Planeta.HINCHADO
                    p._calcular_estructura()   # recalcular radio con factor hinchado ×1.8
                    p.notas.append(
                        "Irradiación estelar extrema infla la atmósfera — densidad media muy baja (Puffy Planet).")

        # ── 4. Estabilidad Orbital (Criterio de Hill) ──
        self.planetas.sort(key=lambda x: x.distancia)
        supervivientes = [self.planetas[0]]
        for p in self.planetas[1:]:
            ultimo = supervivientes[-1]
            separacion_minima = (ultimo.radio_hill + p.radio_hill) * 3.0
            if (p.distancia - ultimo.distancia) >= separacion_minima:
                supervivientes.append(p)
        self.planetas = supervivientes

        # ── 5. Termodinámica, Vida, ESI e IHH ──
        for p in self.planetas:
            p.evolucionar_clima_y_vida()

    # ── Renderizado ────────────────────────────────────────────────

    def renderizar(self):
        ancho = 72
        print("\n" + "═" * ancho)
        print("🌌  SIMULADOR DE SISTEMAS ESTELARES Y EXOPLANETAS".center(ancho))
        print(f"    Sistema / Estrella: {self.seed}  |  Origen: Catálogo Real (OEC)".center(ancho))
        print("═" * ancho)

        e = self.estrella
        print(f"\n  ☀  ESTRELLA: {self.seed}  —  Clase {e.clasificar()} ({e.color_visual()})")
        print(f"     Constelación:  {self.constelacion} 🌌")
        print(f"     Masa:          {e.masa:.3f} M☉")
        print(f"     Luminosidad:   {e.luminosidad:.4f} L☉")
        print(f"     Radio:         {e.radio:.3f} R☉")
        print(f"     Temperatura:   {e.temperatura:.0f} K")
        print(f"     Zona Habitable:{e.zona_hab_int:.2f} – {e.zona_hab_ext:.2f} UA")
        print(f"     Línea de Nieve:{e.linea_nieve:.2f} UA")
        print()

        for i, p in enumerate(self.planetas, 1):
            self._renderizar_planeta(i, p)

        print("\n" + "═" * ancho)
        print(f"  {len(self.planetas)} planetas generados | Seed: «{self.seed}»")
        print("═" * ancho + "\n")

    @staticmethod
    def _barra_progreso(valor: float, maximo: float = 100.0, ancho: int = 20) -> str:
        """Genera una barra de progreso ASCII proporcional al valor."""
        llenos = int((valor / maximo) * ancho)
        vacios = ancho - llenos
        return f"[{'█' * llenos}{'░' * vacios}]"

    @staticmethod
    def _clasificar_esi(esi: float) -> str:
        """
        Clasificación cualitativa del ESI según Planetary Habitability Laboratory (UPR):
          > 0.95  → Gemela terrestre
          0.80–0.95 → Análoga terrestre cercana
          0.60–0.80 → Análoga terrestre moderada
          0.40–0.60 → Análoga terrestre lejana
          < 0.40  → Mundo diferente
        """
        if esi >= 95:   return "Gemela terrestre 🌍"
        elif esi >= 80: return "Análoga cercana 🌏"
        elif esi >= 60: return "Análoga moderada 🌑"
        elif esi >= 40: return "Análoga lejana 🪨"
        else:           return "Mundo diferente ❄️"

    @staticmethod
    def _clasificar_ihh(ihh: float) -> str:
        """
        Niveles de habitabilidad humana:
          > 80  → Habitable sin equipo especializado
          60–80 → Habitable con traje/máscara
          40–60 → Habitable con colonia presurizada
          20–40 → Supervivencia de corto plazo con tecnología avanzada
          < 20  → Inhabitable para humanos
        """
        if ihh >= 80:   return "Habitable directamente ✅"
        elif ihh >= 60: return "Con traje/máscara 🪖"
        elif ihh >= 40: return "Colonia presurizada 🏗️"
        elif ihh >= 20: return "Supervivencia limitada ⚠️"
        else:           return "Inhabitable para humanos ❌"

    def _renderizar_planeta(self, idx: int, p: Planeta):
        ancho = 72

        # ── Ícono por tipo ──────────────────────────────────────────
        if p.tipo == Planeta.ANALOGO:
            icono = "🌍"
        elif p.tipo == Planeta.OCEANO:
            icono = "🌊"
        elif p.tipo == Planeta.LAVA:
            icono = "🌋"
        elif p.tipo == Planeta.HELADO:
            icono = "🧊"
        elif p.tipo == Planeta.DESIERTO:
            icono = "🏜️"
        elif "Oxígeno (O2)" in p.atmosfera:
            icono = "🌍"
        elif p.tipo == Planeta.ROCOSO:
            icono = "🪨"
        elif p.tipo == Planeta.SUBTIERRA:
            icono = "🔴"   # análogo a Marte: pequeño y rojizo
        elif p.tipo == Planeta.SUPER_TIERRA:
            icono = "🌑"
        elif p.tipo == Planeta.MEGATIERRA:
            icono = "⬛"   # masivo y oscuro
        elif p.tipo == Planeta.HIERRO:
            icono = "⚙️"   # metálico
        elif p.tipo == Planeta.SIN_NUCLEO:
            icono = "🟤"   # primitivo, sin diferenciación
        elif p.tipo == Planeta.JUPTER_CALIENTE:
            icono = "🔥"
        elif p.tipo == Planeta.HINCHADO:
            icono = "🎈"   # inflado, liviano
        elif p.tipo == Planeta.CTONIANO:
            icono = "💀"   # núcleo desnudo
        elif p.tipo == Planeta.GIGANTE_GASEOSO:
            icono = "💨"
        elif p.tipo == Planeta.MINI_NEPTUNO:
            icono = "🔵"   # azul como Neptuno pero pequeño
        else:
            icono = "🧊"   # Gigante Helado u otro

        temp_c = p.temp_superficie + C.ABS_ZERO
        sufijo = chr(97 + idx) if idx <= 25 else str(idx)
        nombre_planeta = f"{self.seed} {sufijo}"

        print("─" * ancho)
        print(f" {icono}  {nombre_planeta}  ─  {p.tipo.upper()}", end="")
        if p.en_zona_hab and p._es_terrestre:
            print("  ✦ ZONA HABITABLE", end="")
        print()

        print(f"     Órbita:        {p.distancia:.3f} UA", end="")
        if p.distancia_original != p.distancia:
            print(f"  (migró de {p.distancia_original:.2f} UA)", end="")
        print()
        print(f"     Masa:          {p.masa:.2f} M⊕   |   Radio: {p.radio:.2f} R⊕   |   g: {p.gravedad:.2f} g⊕")
        print(f"     Temperatura:   {temp_c:.1f} °C")
        print(f"     Presión:       {p.presion_atm:.3f} atm")

        gases = " · ".join([f"{k}: {v:.1f}%" for k, v in p.atmosfera.items()])
        print(f"     Atmósfera:     {gases}")

        print(f"     Satélites:     {len(p.lunas)}", end="")
        if p.lunas:
            masas_lunas = [f"{l.masa:.4f}M⊕" for l in p.lunas[:3]]
            if len(p.lunas) > 3:
                masas_lunas.append(f"…+{len(p.lunas)-3} más")
            print(f"  ({', '.join(masas_lunas)})", end="")
        print()

        # ── Sección de índices (todos los tipos con superficie sólida) ──
        if p._es_terrestre:
            print()

            # Prob. de Vida (existente)
            if p.prob_vida > 55:
                ind_vida = "🟢"
            elif p.prob_vida > 15:
                ind_vida = "🟡"
            else:
                ind_vida = "🔴"
            barra_vida = self._barra_progreso(p.prob_vida)
            print(f"     {ind_vida} Prob. Vida:  {p.prob_vida:5.1f}%  {barra_vida}")

            # ESI — Earth Similarity Index
            if p.esi > 0:
                if p.esi >= 80:
                    ind_esi = "🟢"
                elif p.esi >= 50:
                    ind_esi = "🟡"
                else:
                    ind_esi = "🔴"
                barra_esi = self._barra_progreso(p.esi)
                desc_esi  = self._clasificar_esi(p.esi)
                print(f"     {ind_esi} ESI:         {p.esi:5.1f}%  {barra_esi}  {desc_esi}")
            else:
                print(f"     ⚫ ESI:           N/A  (no aplicable a este tipo)")

            # IHH — Índice de Habitabilidad Humana
            if p.ihh > 0:
                if p.ihh >= 60:
                    ind_ihh = "🟢"
                elif p.ihh >= 30:
                    ind_ihh = "🟡"
                else:
                    ind_ihh = "🔴"
                barra_ihh = self._barra_progreso(p.ihh)
                desc_ihh  = self._clasificar_ihh(p.ihh)
                print(f"     {ind_ihh} IHH:         {p.ihh:5.1f}%  {barra_ihh}  {desc_ihh}")
            else:
                print(f"     ❌ IHH:           0.0%  {'[░░░░░░░░░░░░░░░░░░░░]'}  Inhabitable para humanos ❌")

        for nota in p.notas:
            print(f"     ⚠  {nota}")

        print()


# ══════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA — VIAJE POR ETAPAS
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import string

    # ── Seed inicial ──────────────────────────────────────────────
    seed = "SOL-442"
    args = sys.argv[1:]
    if "--seed" in args:
        idx = args.index("--seed")
        if idx + 1 < len(args):
            seed = args[idx + 1]
    elif args:
        seed = args[0]

    # ── Primer sistema (sin viaje previo) ─────────────────────────
    print(f"\n  Usando seed: «{seed}»\n")
    sistema = SistemaEstelar(seed=seed)
    sistema.renderizar()
    current_seed = seed

    # Estado de viaje: None si estamos en una estrella, tuple si en tránsito
    transit = None  # (destino, cola_eventos) o None

    while True:
        # ── Cabecera de estado ────────────────────────────────────
        if transit:
            destino, eventos_pendientes = transit
            print("\n" + "═" * 72)
            print(f"  🚀 EN TRÁNSITO: {current_seed} → {destino}".center(72))
            print(f"  Quedan {len(eventos_pendientes)} etapa(s) del viaje.".center(72))
            print("═" * 72)
            print(" 1. Avanzar una etapa del viaje interestelar")
            print(" 2. Abortar viaje y elegir otro destino")
            print(" 3. Salir de la simulación")
            print("═" * 72)
        else:
            print("\n" + "═" * 72)
            print(f"  📍 EN ÓRBITA alrededor de {current_seed}".center(72))
            print("═" * 72)
            print(" 1. Viajar a un sistema estelar aleatorio")
            print(" 2. Ingresar el nombre de una estrella específica")
            print(" 3. Salir de la simulación")
            print("═" * 72)

        opcion = input("\nSelecciona una opción: ").strip()

        # ── Opción 3: Salir ────────────────────────────────────────
        if opcion == "3":
            print("\n  Cerrando sistema de navegación. ¡Hasta la próxima exploración!\n")
            break

        # ── LÓGICA SI ESTAMOS EN TRÁNSITO ────────────────────────
        if transit:
            destino, cola = transit
            if opcion == "1":
                # Avanzar una etapa
                if not cola:
                    # Llegada: ya no quedaban eventos, así que llegamos
                    print("\n  🌟 Saliendo del viaje... ¡Has llegado a tu destino!\n")
                    current_seed = destino
                    transit = None
                    sistema = SistemaEstelar(seed=current_seed)
                    sistema.renderizar()
                else:
                    evento = cola.pop(0)
                    etapa_num = len(cola) + 1  # para mostrar el número correcto
                    mostrar_evento(evento, etapa_num)
                    if not cola:
                        # Último evento consumido, pero aún no llegamos:
                        # el viaje continúa. El jugador debe pulsar otra
                        # vez "1" para la etapa final (vacía) y llegar.
                        print("\n  ⚡ Último evento superado. El camino está despejado.")
                        print("     Pulsa 1 de nuevo para completar el viaje y llegar al destino.")
            elif opcion == "2":
                # Abortar viaje
                print(f"\n  ⛔ Viaje abortado. Permanecés en {current_seed}.")
                transit = None
            else:
                print("\n⚠️  Opción no reconocida.")
            continue

        # ── LÓGICA SI ESTAMOS EN UNA ESTRELLA ─────────────────────
        if opcion == "1":
            nuevo_destino = obtener_sistema_aleatorio_oec()
        elif opcion == "2":
            nuevo_destino = input("Ingresa el nombre del sistema estelar (ej. TRAPPIST-1): ").strip()
            if not nuevo_destino:
                print("⚠️  No ingresaste ningún nombre. Operación cancelada.")
                continue
        else:
            print("\n⚠️  Opción no reconocida. Por favor ingresa 1, 2 o 3.")
            continue

        # Si el destino es el mismo sistema, no hay viaje
        if nuevo_destino == current_seed:
            print(f"\n  ⚠️  Ya te encuentras en {current_seed}. No se realiza ningún viaje.")
            continue

        # ── Iniciar nuevo viaje ───────────────────────────────────
        cola = generar_cola_eventos(current_seed, nuevo_destino)
        if not cola:
            # Viaje directo sin eventos
            print(f"\n  ✨ El trayecto de {current_seed} a {nuevo_destino} es tranquilo.")
            print(f"     Sin incidentes. Llegada inmediata.\n")
            current_seed = nuevo_destino
            sistema = SistemaEstelar(seed=current_seed)
            sistema.renderizar()
        else:
            # Hay eventos: entramos en tránsito y mostramos el primer evento
            transit = (nuevo_destino, cola)
            print(f"\n  🚀 Iniciando viaje de {current_seed} a {nuevo_destino}...\n")
            evento = cola.pop(0)
            mostrar_evento(evento, 1)
            if not cola:
                print("\n  ⚡ Último evento superado. El camino está despejado.")
                print("     Pulsa 1 de nuevo para completar el viaje y llegar al destino.")