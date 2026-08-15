"""
Cálculos de ingeniería fotovoltaica.
- Radiación: modelo de cielo despejado de Hottel + integración con API de PVGIS (opcional).
- Superficie inclinada: modelo isotrópico de Liu & Jordan.
- Producción: E = P_pico [kWp] x G_anual_inc [kWh/m2] x PR.
- Dimensionado de paneles, inversor, baterías y cableado según REBT ITC-BT-40.
"""
import json
import math
import urllib.request
from datetime import datetime

G_SC = 1367.0        # constante solar W/m2
G_STC = 1000.0       # irradiancia STC W/m2
T_STC = 25.0         # temperatura célula STC
ALBEDO = 0.2

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ---------------------------------------------------------------------------
# Geometría solar
# ---------------------------------------------------------------------------
def declinacion(dia):
    """Declinación solar (grados) para el día juliano del año."""
    return 23.45 * math.sin(math.radians(360.0 * (284 + dia) / 365.0))


def dia_medio_mes(mes):
    """Día juliano representativo de cada mes."""
    dias_acum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    return dias_acum[mes - 1] + 15


def radiacion_extraterrestre_horizontal(lat_deg, dia):
    """Irradiación extraterrestre diaria sobre superficie horizontal (kWh/m2·día)."""
    lat = math.radians(lat_deg)
    delta = math.radians(declinacion(dia))
    ws = math.acos(-math.tan(lat) * math.tan(delta))  # ángulo de salida/puesta
    ho = (24.0 / math.pi) * G_SC * (
        math.cos(lat) * math.cos(delta) * math.sin(ws) + ws * math.sin(lat) * math.sin(delta)
    )
    return ho / 1000.0  # kWh/m2·día


def _daylight_hours(lat_deg, dia):
    lat = math.radians(lat_deg)
    delta = math.radians(declinacion(dia))
    ws = math.acos(max(-1.0, min(1.0, -math.tan(lat) * math.tan(delta))))
    return 2.0 * math.degrees(ws) / 15.0


def horas_sol_equivalentes(lat_deg, mes=None, dia=None):
    """Horas de sol pico aproximadas para un mes (en torno a G=1000 W/m2)."""
    if dia is None:
        dia = dia_medio_mes(mes)
    return _daylight_hours(lat_deg, dia)


# ---------------------------------------------------------------------------
# Irradiancia de cielo despejado (Hottel)
# ---------------------------------------------------------------------------
def transparencia_hottel(altitud_msnm):
    """Coeficientes del modelo de Hottel según la altura sobre el nivel del mar."""
    z = max(0.0, min(altitud_msnm, 2500.0))
    if z <= 1000:
        a0, a1, k = 0.4237, 0.00821, 0.2711
    else:
        a0, a1, k = 0.1742, 0.00814, 0.3032
    a0 *= 0.95 * 1.02
    a1 *= 0.98
    k *= 1.02
    return a0, a1, k


def irradiancia_claro(lat_deg, altitud_msnm=0, dia=180, hora_utc=None):
    """Irradiancia directa + difusa (modelo Hottel) en W/m2. hora solar en horas decimales."""
    a0, a1, k = transparencia_hottel(altitud_msnm)
    lat = math.radians(lat_deg)
    delta = math.radians(declinacion(dia))
    ws = math.acos(max(-1.0, min(1.0, -math.tan(lat) * math.tan(delta))))
    hora = hora_utc if hora_utc is not None else 12.0
    w = math.radians(15.0 * (hora - 12.0))
    if abs(w) > ws:
        return 0.0
    cos_zen = math.sin(lat) * math.sin(delta) + math.cos(lat) * math.cos(delta) * math.cos(w)
    cos_zen = max(0.0, cos_zen)
    m = 1.0 / (cos_zen + 0.15 * (93.885 - math.degrees(math.acos(cos_zen))) ** -1.253)
    tb = a0 + a1 * math.exp(-k * m)
    td = 0.271 - 0.294 * tb
    gnh = G_SC * (1 + 0.033 * math.cos(math.radians(360.0 * dia / 365.0)))
    return gnh * cos_zen * (tb + td)


def irradiacion_clara_diaria(lat_deg, altitud_msnm=0, dia=180, paso=0.5):
    """Integración numérica de la irradiancia de Hottel sobre horizontal (kWh/m2·día)."""
    total = 0.0
    h = -1.5
    while h <= 24.0:
        g = irradiancia_claro(lat_deg, altitud_msnm, dia, h)
        total += g * paso
        h += paso
    return total / 1000.0


# ---------------------------------------------------------------------------
# Estimación mensual de irradiación (aprox. Península / Baleares / Canarias)
# ---------------------------------------------------------------------------
def perfil_mensual_peninsula(lat_deg):
    """Perfil mensual de irradiación horizontal estimado (kWh/m2/día) a partir de la
    latitud y valores de referencia para España (datos típicos de PVGIS/PIEs)."""
    base = [2.3, 3.2, 4.4, 5.4, 6.3, 7.0, 7.3, 6.5, 5.1, 3.6, 2.6, 2.1]
    # Corrección por latitud (a mayor latitud, inviernos más suaves en sur)
    factor = 1.0 + (37.0 - lat_deg) * 0.008
    return [round(b * max(0.75, factor), 2) for b in base]


DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def radiacion_mensual_estimada(lat_deg, altitud_msnm=0, tipo="pais"):
    """Devuelve lista de 12 irradiaciones diarias (kWh/m2·día) sobre horizontal."""
    perfil = perfil_mensual_peninsula(lat_deg)
    # Corrección ligera por altitud (mayor irradiancia a mayor altura)
    fac_alt = 1.0 + max(0.0, altitud_msnm) / 3000.0
    out = [round(min(9.0, v * fac_alt), 2) for v in perfil]
    return out


# ---------------------------------------------------------------------------
# Superficie inclinada (Liu & Jordan, modelo isotrópico)
# ---------------------------------------------------------------------------
def radiacion_inclinada(gh_mensual_kwh_m2_dia, lat_deg, inclinacion_deg, orientacion_deg=180):
    """Irradiación diaria sobre superficie inclinada (kWh/m2·día) — Liu & Jordan."""
    beta = math.radians(inclinacion_deg)
    gama = math.radians(orientacion_deg - 180.0)  # azimut de la superficie (0 = sur en hemisferio N)
    lat = math.radians(lat_deg)

    out = []
    for mes in range(1, 13):
        dia = dia_medio_mes(mes)
        delta = math.radians(declinacion(dia))
        ws = math.acos(max(-1.0, min(1.0, -math.tan(lat) * math.tan(delta))))
        cos_theta = (
            math.sin(delta) * math.sin(lat) * math.cos(beta)
            - math.sin(delta) * math.cos(lat) * math.sin(beta) * math.cos(gama)
            + math.cos(delta) * math.cos(lat) * math.cos(beta) * math.sin(ws)
            + math.cos(delta) * math.sin(lat) * math.sin(beta) * math.cos(gama) * math.sin(ws)
            + math.cos(delta) * math.sin(beta) * math.sin(gama) * (math.sin(ws) * math.cos(ws) + ws)
        )
        if ws > 0 and math.sin(ws) > 0:
            rb = cos_theta / (math.cos(lat) * math.cos(delta) * math.sin(ws) + ws * math.sin(lat) * math.sin(delta))
            rb = max(0.0, rb)
        else:
            rb = 1.0
        # Factor difuso isotrópico
        kd = 0.35  # fracción difusa típica (~35%)
        rd = (1.0 + math.cos(beta)) / 2.0
        rr = ALBEDO * (1.0 - math.cos(beta)) / 2.0
        gh = gh_mensual_kwh_m2_dia[mes - 1]
        gi = gh * ((1.0 - kd) * rb + kd * rd + rr)
        out.append(round(gi, 2))
    return out


# ---------------------------------------------------------------------------
# PVGIS (opcional, requiere internet)
# ---------------------------------------------------------------------------
_pvgis_cache = {}


def pvgis_mensual(lat, lon, inclinacion=30, orientacion=180, pvtech="crystSi",
                  peakpower=1.0, loss=14, temperature="30"):
    """
    Consulta la API de PVGIS (JRC, Comisión Europea).
    Devuelve dict con irradiacion_mensual_inc (12), produccion_mensual (kWh/kWp)
    y produccion_anual o None si falla la conexión.
    """
    clave = (round(lat, 4), round(lon, 4), inclinacion, orientacion)
    if clave in _pvgis_cache:
        return _pvgis_cache[clave]

    # PVGIS usa aspect en [-180,180]: 0 = sur, negativo = este, positivo = oeste.
    # La app usa orientación 0-360 con 180 = sur.
    asp = (float(orientacion) - 180.0) % 360.0
    if asp > 180.0:
        asp -= 360.0

    url = ("https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat={lat}&lon={lon}"
           "&angle={ang}&aspect={asp}&pvtechchoice={pv}&peakpower={pp}"
           "&loss={loss}&outputformat=json&mountingplace={mount}"
           "&trackingtype=0").format(
        lat=lat, lon=lon, ang=inclinacion, asp=round(asp, 2), pv=pvtech,
        pp=peakpower, loss=loss, mount="free" if temperature == "30" else "roof")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SolarDesigner/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    outs = data.get("outputs", {})
    mensual = (outs.get("monthly") or {}).get("fixed") or []
    if not mensual:
        return None
    irr_inc = [round(float(m["H(i)_m"]) / 30.0, 2) if m.get("H(i)_m") else 0 for m in mensual]
    prod = [round(float(m["E_m"]), 1) for m in mensual]
    anual = round(float((outs.get("totals") or {}).get("fixed", {}).get("E_y") or sum(prod)), 1)
    res = {
        "irr_mensual_inc": irr_inc,
        "prod_mensual_kwh_kwp": prod,
        "prod_anual_kwh_kwp": anual,
        "fuente": "PVGIS JRC",
    }
    _pvgis_cache[clave] = res
    return res


# ---------------------------------------------------------------------------
# Dimensionado
# ---------------------------------------------------------------------------
def dimensionar_consumo(consumo_mensual_kwh, horas_sol_pico_mensual, fraccion_cubrir=1.0,
                        dias_autonomia=1.0, tiene_bateria=False):
    """Dimensiona la potencia pico necesaria para cubrir un % del consumo."""
    an = sum(consumo_mensual_kwh)
    hsp_anual = sum(horas_sol_pico_mensual)
    potencia_kw = (an * fraccion_cubrir) / max(0.1, hsp_anual * 0.85)
    return {
        "consumo_anual": round(an),
        "potencia_pico": round(potencia_kw, 2),
        "energia_diaria": round(an / 365.0, 1),
        "capacidad_bateria_kwh": round(an / 365.0 * dias_autonomia / 0.9, 1) if tiene_bateria else 0.0,
    }


def num_paneles(potencia_kw, potencia_panel_w):
    return max(1, math.ceil(potencia_kw * 1000.0 / max(1, potencia_panel_w)))


def area_paneles(num, dimensiones="2278x1134"):
    try:
        a, b = dimensiones.split("x")
        sup = (float(a) * float(b)) / 1e6
    except Exception:
        sup = 1.95
    return num * sup


def dimensionar_inversor(potencia_pico_kw, ratio=1.15, fases=1):
    """Potencia nominal de inversor recomendada (ratio I/V típico 1.0-1.3)."""
    pot = potencia_pico_kw / ratio
    pot = math.ceil(pot * 2) / 2.0  # redondeo a 0,5 kW
    return round(pot, 2)


def calcular_inversion(inversion_total, ahorro_anual, vida_util=25,
                       tasa_descuento_pct=3.5, tasa_energia_pct=2.5,
                       costo_mantenimiento_pct=0.5, subvencion=0, capacidad_kw=0):
    """Estudio de rentabilidad de la inversión fotovoltaica.

    Indicadores clásicos: retorno simple, retorno descontado, VAN, TIR y ROI.
    El ahorro anual crece con la tasa de subida de la energía (compuesta).
    """
    if not inversion_total or inversion_total <= 0:
        return None
    inv_total = float(inversion_total)
    inv_neta = max(0.0, inv_total - float(subvencion or 0))
    ahorro = float(ahorro_anual or 0)
    vida = max(1, int(vida_util or 25))
    t = float(tasa_descuento_pct or 3.5) / 100.0
    e = float(tasa_energia_pct or 2.5) / 100.0
    om = inv_total * float(costo_mantenimiento_pct or 0.5) / 100.0

    def flujo_anio(anio):
        return ahorro * (1.0 + e) ** (anio - 1) - om

    def van_para(r):
        v = -inv_neta
        for anio in range(1, vida + 1):
            v += flujo_anio(anio) / (1.0 + r) ** anio
        return v

    flujos = []
    acum = -inv_neta
    acum_desc = -inv_neta
    van = -inv_neta
    payback = None
    payback_desc = None
    for anio in range(1, vida + 1):
        f = flujo_anio(anio)
        f_desc = f / (1.0 + t) ** anio
        prev = acum
        acum += f
        van += f_desc
        prev_desc = acum_desc
        acum_desc += f_desc
        flujos.append({
            "anio": anio,
            "ahorro": round(f + om, 2),
            "om": round(om, 2),
            "flujo": round(f, 2),
            "acumulado": round(acum, 2),
        })
        if payback is None and acum >= 0:
            payback = anio - 1 + (-prev) / f
        if payback_desc is None and acum_desc >= 0:
            payback_desc = anio - 1 + (-prev_desc) / f_desc

    # TIR: raíz de VAN(r)=0 por bisección
    tir = None
    if van_para(0.0) > 0:
        lo, hi = 0.0, 1.0
        if van_para(hi) < 0:
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if van_para(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            tir = (lo + hi) / 2.0
        else:
            tir = 1.0

    ahorro_acumulado = round(sum(f["flujo"] for f in flujos), 0)
    roi_total = round(ahorro_acumulado / inv_neta * 100.0, 1) if inv_neta > 0 else 0.0

    return {
        "inversion_total": round(inv_total, 0),
        "subvencion": round(float(subvencion or 0), 0),
        "inversion_neta": round(inv_neta, 0),
        "ahorro_anual_eur": round(ahorro, 0),
        "costo_mantenimiento_anual": round(om, 0),
        "vida_util": vida,
        "tasa_descuento_pct": round(t * 100.0, 2),
        "tasa_energia_pct": round(e * 100.0, 2),
        "payback_anos": round(payback, 1) if payback else None,
        "payback_descontado_anos": round(payback_desc, 1) if payback_desc else None,
        "van_eur": round(van, 0),
        "tir_pct": round(tir * 100.0, 1) if tir is not None else None,
        "roi_total_pct": roi_total,
        "ahorro_acumulado_eur": ahorro_acumulado,
        "flujos": flujos,
    }


# Módulo de batería de litio de referencia para el dimensionado
MODULO_BATERIA_KWH = 5.12
MODULO_BATERIA_VOLT = 48


def dimensionar_bateria(consumo_diario_kwh, autonomia_dias=1, dod_pct=80,
                        tension_v=48, eficiencia_inv=0.90, modulo_kwh=None):
    """Dimensiona un banco de baterías de litio (LFP) para respaldo/autoconsumo.

    - energia_diaria: consumo medio diario en kWh.
    - autonomia_dias: días de respaldo (0 = sin batería).
    - dod_pct: profundidad de descarga máxima permitida (%). LFP ≈ 80-90%.
    - eficiencia_inv: rendimiento del camino inversor/batería.
    - modulo_kwh: capacidad del módulo comercial usado (por defecto 5,12 kWh).
    Devuelve dict o None si no aplica.
    """
    if not autonomia_dias or autonomia_dias <= 0:
        return None
    energia_diaria = max(0.0, float(consumo_diario_kwh or 0))
    if energia_diaria <= 0:
        return None
    dod = max(0.1, float(dod_pct or 80) / 100.0)
    modulo = float(modulo_kwh or MODULO_BATERIA_KWH)

    capacidad_util_kwh = energia_diaria * float(autonomia_dias) / eficiencia_inv
    capacidad_total_kwh = capacidad_util_kwh / dod
    n_modulos = max(1, math.ceil(capacidad_total_kwh / modulo))
    capacidad_instalada = n_modulos * modulo

    return {
        "autonomia_dias": float(autonomia_dias),
        "dod_pct": float(dod_pct or 80),
        "tension_v": float(tension_v or 48),
        "consumo_diario_kwh": round(energia_diaria, 1),
        "capacidad_util_kwh": round(capacidad_util_kwh, 1),
        "capacidad_total_kwh": round(capacidad_total_kwh, 1),
        "capacidad_ah": round(capacidad_total_kwh * 1000.0 / max(1.0, tension_v or 48), 0),
        "modulo_kwh": modulo,
        "n_modulos": n_modulos,
        "capacidad_instalada_kwh": round(capacidad_instalada, 1),
        "energia_util_diaria_kwh": round(capacidad_instalada * dod, 1),
    }


def calcular_proyecto(proyecto, inversion_total=0):
    """Cálculo completo de un proyecto. Devuelve dict con resultados."""
    lat = float(proyecto.get("lat") or 37.0)
    lon = float(proyecto.get("lon") or -3.6)
    alt = float(proyecto.get("altitud_msnm") or 0)
    incl = float(proyecto.get("inclinacion_deg") or 30)
    ori = float(proyecto.get("orientacion_deg") or 180)

    consumo = proyecto.get("consumo_mensual") or []
    if isinstance(consumo, str):
        try:
            consumo = json.loads(consumo)
        except Exception:
            consumo = []

    # 1) PVGIS si es posible (datos reales de radiación del JRC)
    irr_hor = radiacion_mensual_estimada(lat, alt)
    pvgis = pvgis_mensual(lat, lon, incl, ori)
    if pvgis:
        irr_inc = pvgis["irr_mensual_inc"]
        hsp = [min(7.5, round(i, 1)) for i in irr_inc]
        fuente_radiacion = "PVGIS (JRC, datos reales)"
    else:
        irr_inc = radiacion_inclinada(irr_hor, lat, incl, ori)
        hsp = [round(min(7.0, max(1.0, i / 0.8)), 1) for i in irr_inc]
        fuente_radiacion = "Modelo estimado (Hottel + Liu & Jordan)"

    irr_inc_anual = sum(irr_inc[m] * DIAS_MES[m] for m in range(12))
    rad_hor_anual = sum(irr_hor[m] * DIAS_MES[m] for m in range(12))
    factor_opt = round(irr_inc_anual / max(0.1, rad_hor_anual), 2) if rad_hor_anual else 1.0

    consumo_anual = sum(consumo) if consumo else 0
    produccion_anual_kwh_kwp = pvgis["prod_anual_kwh_kwp"] if pvgis else round(irr_inc_anual * 0.80, 1)

    bateria = dimensionar_bateria(
        consumo_anual / 365.0,
        autonomia_dias=float(proyecto.get("autonomia_bateria_dias") or 0),
        dod_pct=float(proyecto.get("bateria_dod_pct") or 80),
        tension_v=float(proyecto.get("bateria_tension_v") or 48))

    # 2) Dimensionado de paneles (modelo de panel por defecto)
    panel_potencia_w = float(proyecto.get("panel_potencia_w") or 550)
    potencia_pico_kw = round((consumo_anual / max(0.1, produccion_anual_kwh_kwp))
                            if consumo_anual else 5.0, 2)
    n_paneles = num_paneles(potencia_pico_kw, panel_potencia_w)
    superficie = area_paneles(n_paneles)
    inv_pot = dimensionar_inversor(potencia_pico_kw)

    produccion_anual = round(potencia_pico_kw * produccion_anual_kwh_kwp, 0)
    ahorro_estimado = round(consumo_anual * 0.14, 0) if consumo_anual else 0
    co2_anual = round(produccion_anual * 0.35, 0)
    cobertura = round(produccion_anual / max(1, consumo_anual) * 100, 1) if consumo_anual else 0

    pr_estimado = 0.80 if not pvgis else round(produccion_anual_kwh_kwp /
                                               max(0.1, irr_inc_anual), 2)

    return {
        "fuente_radiacion": fuente_radiacion,
        "pvgis_online": bool(pvgis),
        "irr_horizontal_mensual": irr_hor,
        "irr_inclinada_mensual": irr_inc,
        "irr_horizontal_anual": round(rad_hor_anual, 1),
        "irr_inclinada_anual": round(irr_inc_anual, 1),
        "factor_optimizacion": factor_opt,
        "hsp_mensual": hsp,
        "consumo_anual_kwh": round(consumo_anual),
        "potencia_pico_kw": potencia_pico_kw,
        "n_paneles": n_paneles,
        "panel_potencia_w": panel_potencia_w,
        "superficie_necesaria_m2": round(superficie, 1),
        "potencia_inversor_kw": inv_pot,
        "produccion_anual_kwh": produccion_anual,
        "produccion_anual_kwh_kwp": produccion_anual_kwh_kwp,
        "ahorro_estimado_eur": ahorro_estimado,
        "co2_anual_kg": co2_anual,
        "cobertura_consumo_pct": cobertura,
        "pr_estimado": pr_estimado,
        "bateria": bateria,
        "inversion": calcular_inversion(
            inversion_total,
            ahorro_estimado,
            vida_util=float(proyecto.get("inversion_vida_util") or 25),
            tasa_descuento_pct=float(proyecto.get("inversion_tasa_descuento_pct") or 3.5),
            tasa_energia_pct=float(proyecto.get("inversion_tasa_energia_pct") or 2.5),
            costo_mantenimiento_pct=float(proyecto.get("inversion_costo_mantenimiento_pct") or 0.5),
            subvencion=float(proyecto.get("inversion_subvencion") or 0)),
    }


def resumen_mensual(mensual_kwh_m2, label="kWh/m²"):
    """Convierte lista mensual a texto para PDFs."""
    return ", ".join(f"{MESES[i][:3]}: {v} {label}" for i, v in enumerate(mensual_kwh_m2))
