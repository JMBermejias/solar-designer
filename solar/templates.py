# Copyright (C) 2026 Enersolred
#
# Solar Designer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Plantillas de texto para contratos de mantenimiento de instalaciones fotovoltaicas.
"""

CLAUSULAS_BASE = [
    ("PRIMERA. OBJETO DEL CONTRATO",
     "El presente contrato tiene por objeto la prestación por parte de la EMPRESA de los servicios "
     "de mantenimiento preventivo, predictivo y correctivo de la instalación fotovoltaica descrita "
     "en el presupuesto contratado, así como la elaboración y custodia del libro de mantenimiento "
     "de la instalación en sus periodos trimestral, semestral y anual."),
    ("SEGUNDA. ALCANCE DE LOS TRABAJOS",
     "El mantenimiento incluye: revisión visual e inspección de módulos, estructura y cableado; "
     "limpieza de módulos; verificación de tensiones, corrientes y aislamiento; comprobación de "
     "inversor/es y protecciones; revisión del sistema de puesta a tierra; comprobación de "
     "conexiones y apriete de bornas; análisis termográfico de la instalación; y revisión de "
     "puntos de acceso y conexión a red cuando el alcance lo requiera."),
    ("TERCERA. PERIODICIDAD",
     "El servicio se prestará con la periodicidad pactada, realizándose una visita de "
     "mantenimiento preventivo con carácter trimestral, semestral o anual según lo contratado, "
     "y manteniendo actualizado el libro de mantenimiento tras cada visita."),
    ("CUARTA. DURACIÓN Y PRECIO",
     "El contrato tendrá la duración pactada, siendo prorrogable tácitamente por periodos anuales "
     "salvo preaviso de cualquiera de las partes con una antelación mínima de dos meses. El importe "
     "anual del servicio es el pactado en el presupuesto, IVA no incluido, que se facturará según "
     "la periodicidad acordada."),
    ("QUINTA. OBLIGACIONES DE LA EMPRESA",
     "La EMPRESA se obliga a realizar los trabajos con la diligencia profesional exigible, a "
     "cumplir la normativa vigente en materia de prevención de riesgos laborales, a comunicar por "
     "escrito cualquier incidencia relevante y a entregar los informes y el libro de mantenimiento "
     "actualizado tras cada visita."),
    ("SEXTA. OBLIGACIONES DEL CLIENTE",
     "El CLIENTE se obliga a permitir el acceso a la instalación en las fechas pactadas, a "
     "notificar cualquier anomalía detectada y a abonar las facturas en el plazo establecido."),
    ("SEPTIMA. RESPONSABILIDAD Y GARANTÍA",
     "La EMPRESA responderá de los daños causados por dolo o negligencia en la ejecución de los "
     "trabajos. Quedan excluidos los daños derivados de fuerza mayor, vandalismo, fenómenos "
     "meteorológicos extraordinarios o manipulación por personal ajeno."),
    ("OCTAVA. PROTECCIÓN DE DATOS",
     "Las partes se obligan al cumplimiento del Reglamento (UE) 2016/679 (RGPD) y de la Ley "
     "Orgánica 3/2018, de Protección de Datos Personales y garantía de los derechos digitales."),
    ("NOVENA. CONFIDENCIALIDAD",
     "Las partes se obligan a mantener la confidencialidad de la información técnica y comercial "
     "a la que tuvieran acceso con motivo de la ejecución del presente contrato."),
    ("DECIMA. RESOLUCIÓN",
     "Serán causa de resolución el incumplimiento grave de las obligaciones asumidas, el impago de "
     "tres periodos consecutivos, o la mutua voluntad de las partes manifestada por escrito con "
     "una antelación mínima de dos meses."),
    ("UNDECIMA. LEGISLACIÓN APLICABLE Y JURISDICCIÓN",
     "El presente contrato se regirá por la legislación española. Para la resolución de las "
     "controversias que pudieran surgir, las partes se someten a los Juzgados y Tribunales del "
     "domicilio del CLIENTE."),
]


def construir_contrato(cliente_nombre, empresa, importe, periodicidad, fecha_inicio,
                       fecha_fin, direccion_instalacion, extra_clausulas=None):
    intro = f"""En {empresa.get('ciudad', 'Madrid')}, a la fecha que consta en el presente documento,

REUNIDOS

De una parte, D./Dña. {cliente_nombre}, en su propio nombre y representación (en adelante, el
"CLIENTE"), con NIF que consta en la cabecera de este contrato.

De otra parte, {empresa.get('nombre', '')}, con CIF {empresa.get('cif', '')}, domicilio en
{empresa.get('direccion', '')}, representada por su administrador (en adelante, la "EMPRESA").

INTERVIENEN, ambas partes, con capacidad legal suficiente para otorgar el presente contrato, y a
tal efecto

EXPONEN

PRIMERO. Que la EMPRESA ha realizado la instalación fotovoltaica de autoconsumo ubicada en
{direccion_instalacion}, según el presupuesto de referencia del presente contrato.

SEGUNDO. Que el CLIENTE desea contratar el servicio de mantenimiento de dicha instalación.

TERCERO. Que la EMPRESA dispone de los medios técnicos y humanos necesarios para la prestación
de dicho servicio.

Por lo anterior, ambas partes otorgan el presente CONTRATO DE MANTENIMIENTO de acuerdo con las
siguientes CLAUSULAS:
"""
    clausulas = extra_clausulas or CLAUSULAS_BASE
    importe_txt = (f"IMPORTE: {importe} € IVA no incluido, con periodicidad de facturación "
                   f"{periodicidad}. VIGENCIA: desde {fecha_inicio} hasta {fecha_fin}.")
    return {"intro": intro, "importe_txt": importe_txt, "clausulas": clausulas}
