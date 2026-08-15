"""
Textos normativos aplicables a instalaciones fotovoltaicas en España
para incluir en memorias técnicas y contratos.
"""

NORMATIVA = [
    ("R.D. 244/2019, de 5 de abril",
     "Por el que se regulan las condiciones administrativas, técnicas y económicas del "
     "autoconsumo de energía eléctrica. Establece las modalidades de autoconsumo: con o sin "
     "excedentes, acogidas a compensación simplificada (b.1) o no acogidas (b.2), y la "
     "necesidad de inscribir la instalación en el registro de autoconsumo de la comunidad autónoma."),
    ("R.D. 1183/2020, de 29 de diciembre",
     "De acceso y conexión a las redes de transporte y distribución de energía eléctrica. "
     "Regula el procedimiento de acceso y conexión para instalaciones de generación, "
     "incluidos los requisitos de capacidad de acceso y los puntos de conexión."),
    ("R.D. 842/2002, de 2 de agosto (REBT)",
     "Reglamento Electrotécnico de Baja Tensión y sus instrucciones técnicas complementarias. "
     "Toda la parte eléctrica de la instalación, protecciones, cableado y puesta a tierra "
     "se proyecta conforme a este reglamento."),
    ("ITC-BT-40 del REBT",
     "Instrucción Técnica Complementaria específica de instalaciones generadoras de baja tensión. "
     "Aplica a los generadores fotovoltaicos conectados a la red: requisitos de seguridad, "
     "seccionamiento, protecciones de interfaz (50 Hz / 0,2 s; 51 Hz / 0,2 s; protección de "
     "mínima y máxima tensión y frecuencia), y verificación de la instalación."),
    ("Código Técnico de la Edificación (CTE), DB-HE 5",
     "Documento Básico de Ahorro de Energía, apartado HE-5 sobre contribución fotovoltaica "
     "mínima para edificios (autoconsumo en determinados usos: terciario, comercio, "
     "administrativo, etc.). Incluye requisitos de potencia mínima y de mantenimiento de "
     "las instalaciones."),
    ("R.D. 413/2014, de 6 de junio",
     "Regula la actividad de producción de energía eléctrica a partir de fuentes renovables, "
     "cogeneración y residuos, para instalaciones con régimen retributivo específico "
     "(si procede)."),
    ("R.D. 56/2016 (derogado)/ UNE-EN 62446",
     "Requisitos para la documentación, puesta en servicio e inspección de sistemas "
     "fotovoltaicos conectados a red. La instalación se documenta y verifica según la norma "
     "UNE-EN 62446-1: requisitos de documentación, marcado y comprobaciones de la instalación."),
    ("UNE 206007:2013",
     "Requisitos para instalaciones de sistemas de captación solar fotovoltaica para "
     "suministro eléctrico autónomo (aplicable a las partes aisladas de red)."),
    ("R.D. 513/2017",
     "Reglamento de instalaciones de protección contra incendios (RIPCI), aplicable en la "
     "medida que la instalación forma parte del edificio y se exige su mantenimiento."),
    ("Ley 24/2013, de 26 de diciembre, del Sector Eléctrico",
     "Marco regulatorio general del sector eléctrico; derechos y obligaciones de los "
     "autoconsumidores y productores de energía renovable."),
    ("R.D. 647/2020, de 7 de julio",
     "Regula la facturación electrónica y el contrato de suministro; actualiza los "
     "contratos de acceso y el proceso de cambio de suministrador."),
    ("Real Decreto 1110/2007",
     "Reglamento unificado de puntos de medida del sistema eléctrico, aplicable a los "
     "equipos de medida de la instalación (contadores bidireccionales)."),
    ("UNE-EN 50618 / UNE-HD 60364",
     "Cables solares (H1Z2Z2-K) y reglas generales para instalaciones eléctricas de baja "
     "tensión en edificios."),
]

CTE_ELECTRICIDAD = """La instalación proyectada se adecúa a lo dispuesto en el Reglamento
Electrotécnico para Baja Tensión (RD 842/2002), y en particular a su ITC-BT-40, así como a la
normativa de acceso y conexión vigente y al Real Decreto 244/2019 en materia de autoconsumo."""

OBJETO_MEMORIA = """El presente documento constituye la Memoria Técnica de Diseño de la instalación
fotovoltaica de autoconsumo objeto del proyecto. En él se describen los datos de partida, el
dimensionalo de la instalación, los resultados de producción energética esperada, las partidas
que componen la instalación, así como la normativa aplicable y las prescripciones técnicas y de
mantenimiento que deben observarse para el correcto funcionamiento de la misma."""


def obtener_normativa():
    return NORMATIVA
