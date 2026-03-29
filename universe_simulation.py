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
from dataclasses import dataclass, field
from typing import Optional

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES FÍSICAS (SI + Astronómicas)
# ══════════════════════════════════════════════════════════════════

class C:
    # Unidades astronómicas
    UA_A_KM             = 1.496e8          # 1 UA en km
    RADIO_SOLAR_UA      = 0.00465047       # Radio del Sol en UA
    MASA_TERRESTRE_SOLAR = 3.003e-6        # Masa de la Tierra en masas solares
    RADIO_TERRESTRE_KM  = 6371.0           # km

    # Físicas
    SIGMA               = 5.670e-8         # Stefan-Boltzmann (W m⁻² K⁻⁴)
    G                   = 6.674e-11        # Constante gravitacional (N m² kg⁻²)

    # Estelares de referencia (Sol)
    TEMP_SOL            = 5778.0           # K
    MASA_SOL_KG         = 1.989e30         # kg
    RADIO_SOL_KM        = 695700.0         # km
    LUM_SOL             = 3.828e26         # W

    # Termodinámicas
    ABS_ZERO            = -273.15          # °C → K offset

    # Zona Habitable (Kopparapu 2013, límites conservadores)
    ZH_INTERIOR         = 1.1              # Factor para límite interior
    ZH_EXTERIOR         = 0.53             # Factor para límite exterior
    LINEA_NIEVE         = 2.7              # Factor para línea de nieve


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
        # T = T☉ · (L☉/L_rel · R_rel²)^-0.25 simplificado con relaciones de escala:
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
        # Similar a Tierra-Luna: la Luna es ~1.2% de la masa terrestre
        masa  = rng.uniform(0.005, min(0.15, masa_padre * 0.12))
        radio = masa ** 0.28
        return cls(masa=masa, radio=radio, tipo="Rocosa (Impacto/Captura)")


# ══════════════════════════════════════════════════════════════════
#  PLANETA
# ══════════════════════════════════════════════════════════════════

class Planeta:
    # Tipos posibles
    ROCOSO          = "Rocoso"
    GIGANTE_GASEOSO = "Gigante Gaseoso"
    GIGANTE_HELADO  = "Gigante Helado"
    JUPTER_CALIENTE = "Júpiter Caliente"
    SUPER_TIERRA    = "Super-Tierra"

    def __init__(self, distancia_ua: float, estrella: Estrella, rng: random.Random):
        self.distancia_original = distancia_ua
        self.distancia          = distancia_ua
        self.estrella           = estrella
        self.rng                = rng

        # Resultado de cálculos (se llenan en métodos siguientes)
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

        self._formacion_primordial()
        self._calcular_estructura()

    # ── Formación ─────────────────────────────────────────────────

    def _formacion_primordial(self):
        """Composición según posición relativa a la línea de nieve."""
        if self.distancia < self.estrella.linea_nieve:
            nucleo_masa = self.rng.uniform(0.5, 6.0)
            if nucleo_masa > 4.5:
                self.tipo = self.SUPER_TIERRA
                self.masa = self.rng.uniform(4.5, 10.0)
            else:
                self.tipo = self.ROCOSO
                self.masa = nucleo_masa
        else:
            nucleo = self.rng.uniform(1.0, 22.0)
            if nucleo > 10.0:
                self.tipo = self.GIGANTE_GASEOSO
                self.masa = self.rng.uniform(50.0, 600.0)
            else:
                self.tipo = self.GIGANTE_HELADO
                self.masa = self.rng.uniform(5.0, 30.0)

    def _calcular_estructura(self):
        """Radio, gravedad y radio de Hill."""
        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA):
            # Relación masa-radio para planetas sólidos (Seager et al.)
            self.radio = self.masa ** 0.274
        elif self.tipo == self.GIGANTE_HELADO:
            self.radio = self.masa ** 0.35
        elif self.tipo == self.GIGANTE_GASEOSO:
            # Los gigantes gaseosos son más compresibles: radio no crece linealmente
            self.radio = 10.0 + math.log10(max(1.0, self.masa / 100.0)) * 2.5

        self.gravedad = self.masa / (self.radio ** 2)  # g relativa a la Tierra

        # Radio de Hill: zona de influencia gravitacional
        masa_solar = self.masa * C.MASA_TERRESTRE_SOLAR
        self.radio_hill = self.distancia * ((masa_solar / (3.0 * self.estrella.masa)) ** (1.0 / 3.0))

    # ── Termodinámica y Clima ──────────────────────────────────────

    def evolucionar_clima_y_vida(self):
        """
        Ejecutar DESPUÉS de la migración orbital.
        Calcula temperatura real, atmósfera, efecto invernadero y probabilidad de vida.
        """
        self.en_zona_hab = self.estrella.zona_hab_int <= self.distancia <= self.estrella.zona_hab_ext

        # ── 1. Temperatura de equilibrio (cuerpo negro sin atmósfera) ──
        #   T_eq = T_estrella · √(R_estrella_UA / 2·d) · (1-A)^0.25
        #   donde R_estrella_UA = radio estelar en UA (factor geométrico correcto)
        albedo = self._albedo_primordial()
        r_estelar_ua = self.estrella.radio * C.RADIO_SOLAR_UA
        temp_eq = (self.estrella.temperatura
                   * math.sqrt(r_estelar_ua / (2.0 * self.distancia))
                   * ((1.0 - albedo) ** 0.25))

        # ── 2. Atmósfera ──
        self._generar_atmosfera(temp_eq)

        # ── 3. Efecto invernadero (modelo de capas ópticas) ──
        delta_t = self._efecto_invernadero()
        self.temp_superficie = temp_eq + delta_t

        # ── 4. Probabilidad de vida ──
        self._calcular_prob_vida()

        # ── 5. Lunas ──
        self._generar_lunas()

    def _albedo_primordial(self) -> float:
        """Albedo según tipo: rocoso más oscuro, gaseosos más brillantes."""
        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA):
            return self.rng.uniform(0.10, 0.45)   # De tipo Mercurio a tipo Venus sin nubes
        elif self.tipo == self.GIGANTE_HELADO:
            return self.rng.uniform(0.40, 0.70)   # Alta reflectividad de hielo
        else:  # Gaseoso / Júpiter Caliente
            return self.rng.uniform(0.30, 0.65)

    def _generar_atmosfera(self, temp_eq: float):
        """
        Generación atmosférica física:
        - El escape de Jeans purga atmósferas en planetas calientes y poco masivos.
        - Planetas masivos retienen H2/He primordial.
        - La desgasificación volcánica domina en rocosos masivos y fríos.
        """
        es_rocoso = self.tipo in (self.ROCOSO, self.SUPER_TIERRA)

        if self.tipo == self.JUPTER_CALIENTE:
            self.presion_atm = self.rng.uniform(500.0, 2000.0)
            self.atmosfera = {"Hidrógeno (H2)": 85.0, "Helio (He)": 13.0, "Vapor de agua": 2.0}
            self.notas.append("Inflación atmosférica severa por irradiación estelar.")
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

        # ── Planetas Rocosos / Super-Tierras ──
        # Escape de Jeans simplificado: velocidad térmica vs velocidad de escape
        #   Si T_eq > 600K y gravedad < 0.4: la atmósfera se evapora
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

        # Presión determinada por geología + masa
        base_presion = self.gravedad ** 1.5  # Gravedad alta → retiene más gas
        self.presion_atm = self.rng.uniform(0.005, 120.0) * base_presion

        # Composición volcánica base (pre-vida)
        co2  = self.rng.uniform(75.0, 96.0)
        n2   = 100.0 - co2 - self.rng.uniform(0.5, 2.0)
        self.atmosfera = {
            "Dióxido de Carbono (CO2)": round(co2, 1),
            "Nitrógeno (N2)": round(max(0, n2), 1),
        }

    def _efecto_invernadero(self) -> float:
        """
        Modelo de efecto invernadero por capas ópticas.
        
        Basado en la aproximación de forzamiento radiativo:
            ΔT ≈ λ · F  donde λ es la sensibilidad climática y F el forzamiento.
        
        Para CO2:  F_CO2 = 5.35 · ln(p_CO2 / p_ref)   [W/m²]
        Para CH4:  F_CH4 ≈ 0.036 · √(p_CH4)           [W/m²]
        La sensibilidad λ ≈ 0.8 K/(W/m²) para terrestre, mayor a alta presión.
        """
        if self.presion_atm <= 0 or self.tipo not in (self.ROCOSO, self.SUPER_TIERRA):
            return 0.0

        delta_t = 0.0

        # Contribución CO2
        frac_co2 = self.atmosfera.get("Dióxido de Carbono (CO2)", 0.0) / 100.0
        p_co2_atm = frac_co2 * self.presion_atm   # presión parcial de CO2

        if p_co2_atm > 1e-6:
            # Venus tiene ~92 atm de CO2 → +460°C de invernadero
            F_co2 = 5.35 * math.log(p_co2_atm / 0.0004 + 1.0)
            sensibilidad = 0.8 * math.log10(self.presion_atm + 1.5)
            delta_t += sensibilidad * F_co2

        # Contribución CH4 (si aplica)
        frac_ch4 = self.atmosfera.get("Metano (CH4)", 0.0) / 100.0
        p_ch4_ppm = frac_ch4 * self.presion_atm * 1e6
        if p_ch4_ppm > 1.0:
            delta_t += 0.036 * math.sqrt(p_ch4_ppm)

        # Cap físico: no puede ser mayor que ~600K (punto de fuga terrestre)
        return min(delta_t, 600.0)

    def _calcular_prob_vida(self):
        """
        Índice de habitabilidad basado en:
        - Temperatura en rango de agua líquida (0-100°C)
        - Presión suficiente para agua líquida (>0.006 atm)
        - Gravedad compatible con bioquímica (0.3–2.5 g)
        - Zona habitable orbital
        """
        if self.tipo not in (self.ROCOSO, self.SUPER_TIERRA):
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

        # Score de temperatura: óptimo en 10-30°C (Tierra ~15°C media)
        t_optima = 15.0
        sigma_t  = 35.0   # desviación estándar de tolerancia
        score_t  = 100.0 * math.exp(-((temp_c - t_optima) ** 2) / (2 * sigma_t ** 2))

        # Score de gravedad: óptimo en 1.0 g
        score_g = max(0.0, 100.0 - (abs(self.gravedad - 1.0) * 60.0))

        # Score de zona habitable orbital
        score_zh = 25.0 if self.en_zona_hab else 0.0

        # Score de presión: óptima entre 0.5 y 5 atm
        if 0.5 <= self.presion_atm <= 5.0:
            score_p = 20.0
        elif 0.006 <= self.presion_atm < 0.5:
            score_p = 10.0
        elif self.presion_atm < 100.0:
            score_p = 5.0
        else:
            score_p = 2.0  # Presiones extremas tipo Venus

        self.prob_vida = min(100.0, (score_t * 0.45) + (score_g * 0.25) + score_zh + score_p)

        # Evolución atmosférica por vida fotosintética
        if self.prob_vida > 55.0:
            self.atmosfera = {"Nitrógeno (N2)": 78.0, "Oxígeno (O2)": 21.0, "Argón (Ar)": 1.0}
            self.notas.append("Atmósfera oxidante — posible biosfera fotosintética activa.")
            self.prob_vida = min(100.0, self.prob_vida + self.rng.uniform(8.0, 18.0))

    def _generar_lunas(self):
        """
        Formación de satélites naturales:
        - Rocosos: impactos gigantes (raros) → 0-2 lunas masivas.
        - Gigantes: disco de acreción circunplanetario → múltiples lunas pequeñas.
        
        Usa self._seed_token (inyectado por SistemaEstelar) para determinismo total.
        """
        token = getattr(self, "_seed_token", f"planeta_{self.distancia_original:.4f}")

        if self.tipo in (self.ROCOSO, self.SUPER_TIERRA):
            n = self.rng.choices([0, 1, 2], weights=[70, 24, 6])[0]
            self.lunas = [Luna.desde_impacto(self.masa, derivar_rng(
                token, "luna_impacto", i)) for i in range(n)]

        elif self.tipo in (self.GIGANTE_GASEOSO, self.JUPTER_CALIENTE):
            n = min(int(self.rng.uniform(4, self.masa * 0.15)), 95)
            self.lunas = [Luna.desde_disco_acrecion(self.masa, derivar_rng(
                token, "luna_disco", i)) for i in range(n)]

        elif self.tipo == self.GIGANTE_HELADO:
            n = min(int(self.rng.uniform(2, self.masa * 0.12)), 50)
            self.lunas = [Luna.desde_disco_acrecion(self.masa, derivar_rng(
                token, "luna_disco", i)) for i in range(n)]


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
      5. Evolución termoclimática
    """

    def __init__(self, seed: str = "SOL-442"):
        self.seed = seed
        self.rng_sistema = derivar_rng(seed, "sistema")
        self.planetas: list[Planeta] = []
        self._generar()

    def _generar(self):
        # ── 1. Estrella ──
        masa_estelar = self.rng_sistema.uniform(0.6, 1.5)
        self.estrella = Estrella(masa_estelar)

        # ── 2. Acreción de Protoplanetas ──
        dist = self.rng_sistema.uniform(0.25, 0.65)
        idx  = 0
        while dist < 40.0:
            rng_planeta = derivar_rng(self.seed, "planeta", idx)
            p = Planeta(dist, self.estrella, rng_planeta)
            p._seed_token = f"{self.seed}_planeta_{idx}"   # token determinista para lunas
            self.planetas.append(p)
            idx += 1

            # Separación orbital: Ley de Titius-Bode estocástica + estabilidad de Hill
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

        # ── 4. Estabilidad Orbital (Criterio de Hill) ──
        self.planetas.sort(key=lambda x: x.distancia)
        supervivientes = [self.planetas[0]]
        for p in self.planetas[1:]:
            ultimo = supervivientes[-1]
            separacion_minima = (ultimo.radio_hill + p.radio_hill) * 3.0
            if (p.distancia - ultimo.distancia) >= separacion_minima:
                supervivientes.append(p)
        self.planetas = supervivientes

        # ── 5. Termodinámica y Vida ──
        for p in self.planetas:
            p.evolucionar_clima_y_vida()

    # ── Renderizado ────────────────────────────────────────────────

    def renderizar(self):
        ancho = 72
        print("\n" + "═" * ancho)
        print("🌌  SIMULADOR DE SISTEMAS ESTELARES Y EXOPLANETAS".center(ancho))
        print(f"    Seed: «{self.seed}»".center(ancho))
        print("═" * ancho)

        # Estrella
        e = self.estrella
        print(f"\n  ☀  ESTRELLA  —  Clase {e.clasificar()} ({e.color_visual()})")
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

    def _renderizar_planeta(self, idx: int, p: Planeta):
        ancho = 72

        # Ícono según tipo y habitabilidad
        if "Oxígeno (O2)" in p.atmosfera:
            icono = "🌍"
        elif p.tipo == Planeta.ROCOSO:
            icono = "🪨"
        elif p.tipo == Planeta.SUPER_TIERRA:
            icono = "🌑"
        elif p.tipo == Planeta.JUPTER_CALIENTE:
            icono = "🔥"
        elif p.tipo == Planeta.GIGANTE_GASEOSO:
            icono = "💨"
        else:
            icono = "🧊"

        temp_c = p.temp_superficie + C.ABS_ZERO

        print("─" * ancho)
        print(f" {icono}  PLANETA {idx}  ─  {p.tipo.upper()}", end="")
        if p.en_zona_hab and p.tipo in (Planeta.ROCOSO, Planeta.SUPER_TIERRA):
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

        if p.tipo in (Planeta.ROCOSO, Planeta.SUPER_TIERRA):
            if p.prob_vida > 55:
                ind = "🟢"
            elif p.prob_vida > 15:
                ind = "🟡"
            else:
                ind = "🔴"
            print(f"     {ind} Prob. Vida:  {p.prob_vida:.1f}%")

        for nota in p.notas:
            print(f"     ⚠  {nota}")

        print()


# ══════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Lectura de seed desde argumentos de línea de comandos
    seed = "SOL-442"  # Seed por defecto

    args = sys.argv[1:]
    if "--seed" in args:
        idx = args.index("--seed")
        if idx + 1 < len(args):
            seed = args[idx + 1]
    elif args:
        seed = args[0]

    print(f"\n  Usando seed: «{seed}»")
    print("  (Pasa otra seed como argumento para explorar otro sistema)\n")

    sistema = SistemaEstelar(seed=seed)
    sistema.renderizar()