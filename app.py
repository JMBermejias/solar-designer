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

import json
import os
import re
import sys
import uuid
from datetime import date, datetime
import math

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, url_for)

import database
from solar import calculations as calc
from solar import pdf_engine


def _is_frozen():
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


if _is_frozen():
    BASE = sys._MEIPASS
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
DATOS = database.data_dir()
UPLOADS = os.path.join(DATOS, "uploads")
GENERATED = os.path.join(DATOS, "generated")
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(GENERATED, exist_ok=True)


def _web_dir():
    """Directorio con templates/ y static/ (fuente o instalado con pip)."""
    env = os.environ.get("SOLAR_APP_DIR")
    if env and os.path.isdir(env):
        return env
    share = os.path.join(sys.prefix, "share", "solar-designer")
    if os.path.isdir(os.path.join(share, "templates")):
        return share
    return BASE


WEB = _web_dir()

app = Flask(
    __name__,
    template_folder=os.path.join(WEB, "templates"),
    static_folder=os.path.join(WEB, "static"),
)
app.secret_key = os.environ.get("SOLAR_SECRET_KEY", "solar-designer-secret-2026")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

CATEGORIAS = {
    "panel": "Módulos fotovoltaicos",
    "inversor": "Inversores",
    "bateria": "Baterías y almacenamiento",
    "estructura": "Estructuras y soportes",
    "cable": "Cableado y conducciones",
    "proteccion": "Protecciones eléctricas",
    "monitorizacion": "Monitorización y medida",
    "accesorios": "Accesorios",
}
CATEGORIAS_HERR = ["medicion", "montaje", "inspeccion", "acceso", "seguridad", "otros"]
PERIODOS = ["trimestral", "semestral", "anual"]
TAREAS_MANT = {
    "trimestral": ["Limpieza de módulos fotovoltaicos", "Revisión visual de módulos y estructura",
                   "Comprobación de inversor/es y alarmas", "Verificación de cableado aparente"],
    "semestral": ["Apriete de bornas y conexiones", "Medida de tensiones y corrientes",
                  "Verificación de aislamiento", "Termografía de módulos", "Revisión de protecciones DC/AC"],
    "anual": ["Revisión completa de la instalación", "Comprobación de protecciones de interfaz",
              "Medida de puesta a tierra", "Revisión del cuadro de protecciones",
              "Revisión de estructura y fijaciones", "Informe anual y recomendaciones"],
}


def empresa():
    conn = database.get_db()
    fila = conn.execute("SELECT * FROM empresas ORDER BY activa DESC, id LIMIT 1").fetchone()
    conn.close()
    return dict(fila) if fila else {}


def guardar_imagen(file, prefijo):
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        ext = ".jpg"
    nombre = f"{prefijo}_{uuid.uuid4().hex[:8]}{ext}"
    file.save(os.path.join(UPLOADS, nombre))
    return nombre


def nuevo_numero(prefijo, tabla):
    conn = database.get_db()
    n = conn.execute(f"SELECT COUNT(*) AS c FROM {tabla}").fetchone()["c"] + 1
    conn.close()
    return f"{prefijo}-{datetime.now().year}-{n:04d}"


@app.context_processor
def inject_globals():
    return {"empresa": empresa(), "cat_materiales": CATEGORIAS, "cat_herr": CATEGORIAS_HERR,
            "periodos": PERIODOS, "meses": calc.MESES, "today": date.today().isoformat(),
            "TAREAS_MANT": TAREAS_MANT}


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    conn = database.get_db()
    ncli = conn.execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"]
    nproy = conn.execute("SELECT COUNT(*) c FROM proyectos").fetchone()["c"]
    nmat = conn.execute("SELECT COUNT(*) c FROM materiales").fetchone()["c"]
    npres = conn.execute("SELECT COUNT(*) c FROM presupuestos").fetchone()["c"]
    ncont = conn.execute("SELECT COUNT(*) c FROM contratos").fetchone()["c"]
    nmant = conn.execute("SELECT COUNT(*) c FROM mantenimiento WHERE estado='pendiente'").fetchone()["c"]
    proyectos = conn.execute(
        "SELECT p.*, c.nombre AS cliente FROM proyectos p LEFT JOIN clientes c ON c.id=p.cliente_id "
        "ORDER BY p.created_at DESC LIMIT 5").fetchall()
    pendientes = conn.execute(
        "SELECT m.*, p.nombre AS proyecto FROM mantenimiento m "
        "JOIN proyectos p ON p.id=m.proyecto_id WHERE m.estado='pendiente' "
        "ORDER BY m.fecha_programada ASC LIMIT 6").fetchall()
    conn.close()
    return render_template("dashboard.html", ncli=ncli, nproy=nproy, nmat=nmat, npres=npres,
                           ncont=ncont, nmant=nmant, proyectos=proyectos, pendientes=pendientes)


# ---------------------------------------------------------------------------
# Configuración de la empresa
# ---------------------------------------------------------------------------
@app.route("/config")
def config_view():
    return redirect(url_for("empresas"))


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------
@app.route("/empresas")
def empresas():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM empresas ORDER BY activa DESC, nombre").fetchall()]
    conn.close()
    return render_template("empresas.html", rows=rows)


@app.route("/empresas/guardar", methods=["POST"])
def empresa_guardar():
    f = request.form
    campos = ("nombre", "cif", "direccion", "ciudad", "telefono", "email", "web")
    vals = {c: f.get(c, "").strip() for c in campos}
    if not vals["nombre"]:
        flash("El nombre de la empresa es obligatorio.", "err")
        return redirect(url_for("empresas"))
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            f"UPDATE empresas SET {', '.join(c+'=?' for c in campos)} WHERE id=?",
            tuple(vals[c] for c in campos) + (f.get("id"),))
    else:
        cur = conn.execute(
            f"INSERT INTO empresas ({', '.join(campos)}) VALUES ({', '.join('?'*len(campos))})",
            tuple(vals[c] for c in campos))
        if conn.execute("SELECT COUNT(*) FROM empresas WHERE activa=1").fetchone()[0] == 0:
            conn.execute("UPDATE empresas SET activa=1 WHERE id=?", (cur.lastrowid,))
    conn.commit()
    conn.close()
    flash("Empresa guardada.", "ok")
    return redirect(url_for("empresas"))


@app.route("/empresas/activar/<int:id>", methods=["POST"])
def empresa_activar(id):
    conn = database.get_db()
    if not conn.execute("SELECT id FROM empresas WHERE id=?", (id,)).fetchone():
        conn.close()
        abort(404)
    conn.execute("UPDATE empresas SET activa=0")
    conn.execute("UPDATE empresas SET activa=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Empresa activa actualizada.", "ok")
    return redirect(url_for("empresas"))


@app.route("/empresas/eliminar/<int:id>", methods=["POST"])
def empresa_eliminar(id):
    conn = database.get_db()
    if conn.execute("SELECT COUNT(*) FROM empresas").fetchone()[0] <= 1:
        conn.close()
        flash("No se puede eliminar la única empresa.", "err")
        return redirect(url_for("empresas"))
    fila = conn.execute("SELECT activa FROM empresas WHERE id=?", (id,)).fetchone()
    if not fila:
        conn.close()
        abort(404)
    conn.execute("DELETE FROM empresas WHERE id=?", (id,))
    if fila["activa"]:
        nxt = conn.execute("SELECT id FROM empresas ORDER BY id LIMIT 1").fetchone()
        if nxt:
            conn.execute("UPDATE empresas SET activa=1 WHERE id=?", (nxt["id"],))
    conn.commit()
    conn.close()
    flash("Empresa eliminada.", "ok")
    return redirect(url_for("empresas"))


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
@app.route("/clientes")
def clientes():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()]
    conn.close()
    return render_template("clientes.html", rows=rows)


@app.route("/clientes/guardar", methods=["POST"])
def cliente_guardar():
    f = request.form
    campos = ("nombre", "nif", "direccion", "cp", "ciudad", "provincia",
              "telefono", "email", "contacto", "notas")
    vals = {c: f.get(c, "") for c in campos}
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            f"UPDATE clientes SET {', '.join(c+'=?' for c in campos)} WHERE id=?",
            tuple(vals[c] for c in campos) + (f.get("id"),))
    else:
        conn.execute(
            f"INSERT INTO clientes ({', '.join(campos)}) VALUES ({', '.join('?'*len(campos))})",
            tuple(vals[c] for c in campos))
    conn.commit()
    conn.close()
    flash("Cliente guardado.", "ok")
    return redirect(url_for("clientes"))


@app.route("/clientes/eliminar/<int:id>", methods=["POST"])
def cliente_eliminar(id):
    conn = database.get_db()
    conn.execute("UPDATE proyectos SET cliente_id=NULL WHERE cliente_id=?", (id,))
    conn.execute("UPDATE contratos SET cliente_id=NULL WHERE cliente_id=?", (id,))
    conn.execute("DELETE FROM clientes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Cliente eliminado.", "ok")
    return redirect(url_for("clientes"))


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------
@app.route("/proveedores")
def proveedores():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()]
    conn.close()
    return render_template("proveedores.html", rows=rows)


@app.route("/proveedores/guardar", methods=["POST"])
def proveedor_guardar():
    f = request.form
    campos = ("nombre", "nif", "direccion", "cp", "ciudad", "telefono",
              "email", "contacto", "web", "notas")
    vals = {c: f.get(c, "") for c in campos}
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            f"UPDATE proveedores SET {', '.join(c+'=?' for c in campos)} WHERE id=?",
            tuple(vals[c] for c in campos) + (f.get("id"),))
    else:
        conn.execute(
            f"INSERT INTO proveedores ({', '.join(campos)}) VALUES ({', '.join('?'*len(campos))})",
            tuple(vals[c] for c in campos))
    conn.commit()
    conn.close()
    flash("Proveedor guardado.", "ok")
    return redirect(url_for("proveedores"))


@app.route("/proveedores/eliminar/<int:id>", methods=["POST"])
def proveedor_eliminar(id):
    conn = database.get_db()
    conn.execute("UPDATE materiales SET proveedor_id=NULL WHERE proveedor_id=?", (id,))
    conn.execute("DELETE FROM proveedores WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Proveedor eliminado.", "ok")
    return redirect(url_for("proveedores"))


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------
@app.route("/materiales")
def materiales():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT m.*, p.nombre AS proveedor FROM materiales m "
        "LEFT JOIN proveedores p ON p.id=m.proveedor_id ORDER BY m.categoria, m.nombre").fetchall()]
    provs = [dict(r) for r in conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()]
    conn.close()
    return render_template("materiales.html", rows=rows, provs=provs)


@app.route("/materiales/guardar", methods=["POST"])
def material_guardar():
    f = request.form
    img = guardar_imagen(request.files.get("imagen"), "mat")
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            "UPDATE materiales SET categoria=?, nombre=?, marca=?, modelo=?, referencia=?, "
            "descripcion=?, ficha_url=?, precio_unitario=?, iva=?, unidad=?, stock=?, "
            "garantia_anos=?, vida_util_anos=?, potencia_w=?, eficiencia=?, params=?, "
            "proveedor_id=? WHERE id=?",
            (f.get("categoria"), f.get("nombre"), f.get("marca"), f.get("modelo"),
             f.get("referencia"), f.get("descripcion"), f.get("ficha_url"),
             f.get("precio_unitario") or 0, f.get("iva") or 21, f.get("unidad") or "ud",
             f.get("stock") or 0, f.get("garantia_anos") or 2, f.get("vida_util_anos") or 25,
             f.get("potencia_w") or 0, f.get("eficiencia") or 0, f.get("params") or "{}",
             f.get("proveedor_id") or None, f.get("id")))
        if img:
            conn.execute("UPDATE materiales SET imagen=? WHERE id=?", (img, f.get("id")))
    else:
        cur = conn.execute(
            "INSERT INTO materiales (categoria, nombre, marca, modelo, referencia, descripcion, "
            "ficha_url, precio_unitario, iva, unidad, stock, garantia_anos, vida_util_anos, "
            "potencia_w, eficiencia, params, proveedor_id, imagen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f.get("categoria"), f.get("nombre"), f.get("marca"), f.get("modelo"),
             f.get("referencia"), f.get("descripcion"), f.get("ficha_url"),
             f.get("precio_unitario") or 0, f.get("iva") or 21, f.get("unidad") or "ud",
             f.get("stock") or 0, f.get("garantia_anos") or 2, f.get("vida_util_anos") or 25,
             f.get("potencia_w") or 0, f.get("eficiencia") or 0, f.get("params") or "{}",
             f.get("proveedor_id") or None, img))
    conn.commit()
    conn.close()
    flash("Producto guardado.", "ok")
    return redirect(url_for("materiales"))


@app.route("/materiales/eliminar/<int:id>", methods=["POST"])
def material_eliminar(id):
    conn = database.get_db()
    conn.execute("UPDATE proyecto_materiales SET material_id=NULL WHERE material_id=?", (id,))
    conn.execute("UPDATE presupuesto_lineas SET material_id=NULL WHERE material_id=?", (id,))
    conn.execute("DELETE FROM materiales WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Producto eliminado.", "ok")
    return redirect(url_for("materiales"))


@app.route("/materiales/<int:id>/duplicar", methods=["POST"])
def material_duplicar(id):
    conn = database.get_db()
    m = conn.execute("SELECT * FROM materiales WHERE id=?", (id,)).fetchone()
    if m:
        conn.execute(
            "INSERT INTO materiales (categoria, nombre, marca, modelo, referencia, descripcion, "
            "ficha_url, precio_unitario, iva, unidad, stock, garantia_anos, vida_util_anos, "
            "potencia_w, eficiencia, params, imagen, proveedor_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["categoria"], m["nombre"] + " (copia)", m["marca"], m["modelo"], m["referencia"],
             m["descripcion"], m["ficha_url"], m["precio_unitario"], m["iva"], m["unidad"],
             m["stock"], m["garantia_anos"], m["vida_util_anos"], m["potencia_w"],
             m["eficiencia"], m["params"], m["imagen"], m["proveedor_id"]))
    conn.commit()
    conn.close()
    flash("Producto duplicado.", "ok")
    return redirect(url_for("materiales"))


# ---------------------------------------------------------------------------
# Productos (alias de Materiales)
# ---------------------------------------------------------------------------
@app.route("/productos")
def productos():
    return materiales()


@app.route("/productos/guardar", methods=["POST"])
def producto_guardar():
    return material_guardar()


@app.route("/productos/eliminar/<int:id>", methods=["POST"])
def producto_eliminar(id):
    return material_eliminar(id)


@app.route("/productos/<int:id>/duplicar", methods=["POST"])
def producto_duplicar(id):
    return material_duplicar(id)


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------
@app.route("/herramientas")
def herramientas():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM herramientas ORDER BY categoria, nombre").fetchall()]
    conn.close()
    return render_template("herramientas.html", rows=rows)


@app.route("/herramientas/guardar", methods=["POST"])
def herramienta_guardar():
    f = request.form
    img = guardar_imagen(request.files.get("imagen"), "herr")
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            "UPDATE herramientas SET nombre=?, categoria=?, descripcion=?, cantidad=?, "
            "estado=?, ubicacion=?, notas=? WHERE id=?",
            (f.get("nombre"), f.get("categoria"), f.get("descripcion"),
             f.get("cantidad") or 1, f.get("estado") or "operativo",
             f.get("ubicacion"), f.get("notas"), f.get("id")))
        if img:
            conn.execute("UPDATE herramientas SET imagen=? WHERE id=?", (img, f.get("id")))
    else:
        cur = conn.execute(
            "INSERT INTO herramientas (nombre, categoria, descripcion, cantidad, estado, ubicacion, notas, imagen) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (f.get("nombre"), f.get("categoria"), f.get("descripcion"),
             f.get("cantidad") or 1, f.get("estado") or "operativo",
             f.get("ubicacion"), f.get("notas"), img))
    conn.commit()
    conn.close()
    flash("Herramienta guardada.", "ok")
    return redirect(url_for("herramientas"))


@app.route("/herramientas/eliminar/<int:id>", methods=["POST"])
def herramienta_eliminar(id):
    conn = database.get_db()
    conn.execute("DELETE FROM herramientas WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Herramienta eliminada.", "ok")
    return redirect(url_for("herramientas"))


# ---------------------------------------------------------------------------
# Proyectos
# ---------------------------------------------------------------------------
@app.route("/proyectos")
def proyectos():
    conn = database.get_db()
    rows = conn.execute(
        "SELECT p.*, c.nombre AS cliente, "
        "(SELECT COUNT(*) FROM proyecto_materiales pm WHERE pm.proyecto_id=p.id) AS nmats "
        "FROM proyectos p LEFT JOIN clientes c ON c.id=p.cliente_id "
        "ORDER BY p.created_at DESC").fetchall()
    conn.close()
    return render_template("proyectos.html", rows=rows)


def _consumo_form(f):
    lista = []
    total = f.get("consumo_total") or "0"
    for i in range(12):
        v = f.get(f"consumo_{i}")
        if v is None or v == "":
            if f.get("distribuir_total"):
                v = float(total or 0) / 12.0
            else:
                v = 0
        try:
            lista.append(float(v))
        except (TypeError, ValueError):
            lista.append(0.0)
    return json.dumps(lista)


@app.route("/proyectos/nuevo", methods=["GET", "POST"])
@app.route("/proyectos/<int:pid>/editar", methods=["GET", "POST"])
def proyecto_form(pid=None):
    conn = database.get_db()
    clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    proy = None
    if pid:
        proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
        if not proy:
            abort(404)
    conn.close()

    if request.method == "POST":
        f = request.form
        if f.get("lat") and f.get("lon"):
            lat, lon = float(f["lat"]), float(f["lon"])
        else:
            lat, lon = 37.0, -3.6
        if f.get("consumo_total") and not any(f.get(f"consumo_{i}") for i in range(12)):
            f_distribuir = True
        else:
            f_distribuir = False

        imagenes = {}
        for campo in ("imagen_fachada", "imagen_plano", "imagen_planta", "imagen_extra1", "imagen_extra2"):
            img = guardar_imagen(request.files.get(campo), campo.replace("imagen_", "img"))
            if img:
                imagenes[campo] = img

        vals = {
            "cliente_id": f.get("cliente_id") or None,
            "nombre": f.get("nombre") or "Proyecto sin nombre",
            "direccion": f.get("direccion", ""), "cp": f.get("cp", ""),
            "ciudad": f.get("ciudad", ""), "provincia": f.get("provincia", ""),
            "lat": lat, "lon": lon, "altitud_msnm": f.get("altitud_msnm") or 0,
            "potencia_contratada": f.get("potencia_contratada") or 0,
            "tarifa": f.get("tarifa", ""),
            "consumo_mensual": _consumo_form(f),
            "consumo_anual_kwh": sum(json.loads(_consumo_form(f))),
            "tipo_cubierta": f.get("tipo_cubierta", ""),
            "superficie_m2": f.get("superficie_m2") or 0,
            "orientacion_deg": f.get("orientacion_deg") or 180,
            "inclinacion_deg": f.get("inclinacion_deg") or 30,
            "sombras": f.get("sombras", "sin sombras"),
            "autonomia_bateria_dias": f.get("autonomia_bateria_dias") or 0,
            "bateria_dod_pct": f.get("bateria_dod_pct") or 80,
            "bateria_tension_v": f.get("bateria_tension_v") or 48,
            "inversion_subvencion": f.get("inversion_subvencion") or 0,
            "inversion_estimada": f.get("inversion_estimada") or 0,
            "inversion_tasa_descuento_pct": f.get("inversion_tasa_descuento_pct") or 3.5,
            "inversion_tasa_energia_pct": f.get("inversion_tasa_energia_pct") or 2.5,
            "inversion_vida_util": f.get("inversion_vida_util") or 25,
            "inversion_costo_mantenimiento_pct": f.get("inversion_costo_mantenimiento_pct") or 0.5,
            "notas": f.get("notas", ""),
            "estado": f.get("estado", "en diseño"),
        }
        # doble llamada a _consumo_form para evitar divergencia
        vals["consumo_mensual"] = _consumo_form(f)
        vals["consumo_anual_kwh"] = sum(json.loads(vals["consumo_mensual"]))

        conn = database.get_db()
        if pid:
            conn.execute(
                "UPDATE proyectos SET cliente_id=?, nombre=?, direccion=?, cp=?, ciudad=?, "
                "provincia=?, lat=?, lon=?, altitud_msnm=?, potencia_contratada=?, tarifa=?, "
                "consumo_mensual=?, consumo_anual_kwh=?, tipo_cubierta=?, superficie_m2=?, "
                "orientacion_deg=?, inclinacion_deg=?, sombras=?, autonomia_bateria_dias=?, "
                "bateria_dod_pct=?, bateria_tension_v=?, inversion_subvencion=?, "
                "inversion_estimada=?, "
                "inversion_tasa_descuento_pct=?, inversion_tasa_energia_pct=?, "
                "inversion_vida_util=?, inversion_costo_mantenimiento_pct=?, "
                "notas=?, estado=? WHERE id=?",
                tuple(vals[k] for k in ("cliente_id", "nombre", "direccion", "cp", "ciudad",
                                        "provincia", "lat", "lon", "altitud_msnm",
                                        "potencia_contratada", "tarifa", "consumo_mensual",
                                        "consumo_anual_kwh", "tipo_cubierta", "superficie_m2",
                                        "orientacion_deg", "inclinacion_deg", "sombras",
                                        "autonomia_bateria_dias", "bateria_dod_pct",
                                        "bateria_tension_v", "inversion_subvencion",
                                        "inversion_estimada",
                                        "inversion_tasa_descuento_pct", "inversion_tasa_energia_pct",
                                        "inversion_vida_util", "inversion_costo_mantenimiento_pct",
                                        "notas", "estado")) + (pid,))
            for campo, img in imagenes.items():
                conn.execute(f"UPDATE proyectos SET {campo}=? WHERE id=?", (img, pid))
            nid = pid
        else:
            cur = conn.execute(
                "INSERT INTO proyectos (cliente_id, nombre, direccion, cp, ciudad, provincia, "
                "lat, lon, altitud_msnm, potencia_contratada, tarifa, consumo_mensual, "
                "consumo_anual_kwh, tipo_cubierta, superficie_m2, orientacion_deg, "
                "inclinacion_deg, sombras, autonomia_bateria_dias, bateria_dod_pct, "
                "bateria_tension_v, inversion_subvencion, inversion_estimada, "
                "inversion_tasa_descuento_pct, "
                "inversion_tasa_energia_pct, inversion_vida_util, "
                "inversion_costo_mantenimiento_pct, notas, estado, "
                "imagen_fachada, imagen_plano, imagen_planta, imagen_extra1, imagen_extra2) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                tuple(vals[k] for k in ("cliente_id", "nombre", "direccion", "cp", "ciudad",
                                        "provincia", "lat", "lon", "altitud_msnm",
                                        "potencia_contratada", "tarifa", "consumo_mensual",
                                        "consumo_anual_kwh", "tipo_cubierta", "superficie_m2",
                                        "orientacion_deg", "inclinacion_deg", "sombras",
                                        "autonomia_bateria_dias", "bateria_dod_pct",
                                        "bateria_tension_v", "inversion_subvencion",
                                        "inversion_estimada",
                                        "inversion_tasa_descuento_pct", "inversion_tasa_energia_pct",
                                        "inversion_vida_util", "inversion_costo_mantenimiento_pct",
                                        "notas", "estado")) +
                tuple(imagenes.get(k) for k in ("imagen_fachada", "imagen_plano",
                                                "imagen_planta", "imagen_extra1", "imagen_extra2")))
            nid = cur.lastrowid
        conn.commit()
        conn.close()
        flash("Proyecto guardado.", "ok")
        return redirect(url_for("proyecto_detalle", pid=nid))

    consumo = []
    if proy:
        try:
            consumo = json.loads(proy["consumo_mensual"] or "[]")
        except Exception:
            consumo = []
    return render_template("proyecto_form.html", proy=proy, clientes=clientes, consumo=consumo)


@app.route("/proyectos/<int:pid>")
def proyecto_detalle(pid):
    conn = database.get_db()
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
    if not proy:
        abort(404)
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?",
                           (proy["cliente_id"],)).fetchone() if proy["cliente_id"] else None
    materiales = conn.execute("SELECT * FROM materiales ORDER BY categoria, nombre").fetchall()
    lineas = conn.execute("SELECT * FROM proyecto_materiales WHERE proyecto_id=?", (pid,)).fetchall()
    presupuestos = conn.execute(
        "SELECT * FROM presupuestos WHERE proyecto_id=? ORDER BY created_at DESC", (pid,)).fetchall()
    memorias = conn.execute(
        "SELECT * FROM memorias WHERE proyecto_id=? ORDER BY created_at DESC", (pid,)).fetchall()
    contratos = conn.execute(
        "SELECT * FROM contratos WHERE proyecto_id=? ORDER BY created_at DESC", (pid,)).fetchall()
    mant = conn.execute(
        "SELECT * FROM mantenimiento WHERE proyecto_id=? ORDER BY fecha_programada DESC", (pid,)).fetchall()
    conn.close()
    try:
        consumo = json.loads(proy["consumo_mensual"] or "[]")
    except Exception:
        consumo = []
    inversion_total = sum(float(l["cantidad"] or 0) * float(l["precio_unitario"] or 0)
                          for l in lineas)
    if float(proy["inversion_estimada"] or 0) > 0:
        inversion_total = float(proy["inversion_estimada"])
    if inversion_total <= 0:
        pre = calc.calcular_proyecto(dict(proy))
        inversion_total = pre["potencia_pico_kw"] * 950.0
        if pre.get("bateria"):
            inversion_total += pre["bateria"]["n_modulos"] * 1750.0
    res = calc.calcular_proyecto(dict(proy), inversion_total=inversion_total)
    return render_template("proyecto_detalle.html", p=proy, cliente=cliente, materiales=materiales,
                           lineas=lineas, presupuestos=presupuestos, memorias=memorias,
                           contratos=contratos, mant=mant, consumo=consumo, res=res)


@app.route("/proyectos/<int:pid>/materiales", methods=["POST"])
def proyecto_add_material(pid):
    f = request.form
    conn = database.get_db()
    if f.get("material_id"):
        mat = conn.execute("SELECT * FROM materiales WHERE id=?", (f.get("material_id"),)).fetchone()
        if mat:
            conn.execute(
                "INSERT INTO proyecto_materiales (proyecto_id, material_id, partida, descripcion, "
                "categoria, cantidad, precio_unitario, iva) VALUES (?,?,?,?,?,?,?,?)",
                (pid, mat["id"], mat["categoria"], mat["nombre"], mat["categoria"],
                 f.get("cantidad") or 1, mat["precio_unitario"], mat["iva"]))
    else:
        conn.execute(
            "INSERT INTO proyecto_materiales (proyecto_id, partida, descripcion, categoria, "
            "cantidad, precio_unitario, iva) VALUES (?,?,?,?,?,?,?)",
            (pid, f.get("partida"), f.get("descripcion"), f.get("categoria"),
             f.get("cantidad") or 1, f.get("precio_unitario") or 0, f.get("iva") or 21))
    conn.commit()
    conn.close()
    return redirect(url_for("proyecto_detalle", pid=pid))


@app.route("/proyectos/<int:pid>/materiales/<int:lid>/eliminar", methods=["POST"])
def proyecto_del_material(pid, lid):
    conn = database.get_db()
    conn.execute("DELETE FROM proyecto_materiales WHERE id=? AND proyecto_id=?", (lid, pid))
    conn.commit()
    conn.close()
    return redirect(url_for("proyecto_detalle", pid=pid))


@app.route("/proyectos/eliminar/<int:pid>", methods=["POST"])
def proyecto_eliminar(pid):
    conn = database.get_db()
    conn.execute("DELETE FROM presupuesto_lineas WHERE presupuesto_id IN "
                 "(SELECT id FROM presupuestos WHERE proyecto_id=?)", (pid,))
    conn.execute("DELETE FROM presupuestos WHERE proyecto_id=?", (pid,))
    conn.execute("DELETE FROM memorias WHERE proyecto_id=?", (pid,))
    conn.execute("DELETE FROM mantenimiento WHERE proyecto_id=?", (pid,))
    conn.execute("DELETE FROM contratos WHERE proyecto_id=?", (pid,))
    conn.execute("DELETE FROM proyecto_materiales WHERE proyecto_id=?", (pid,))
    conn.execute("DELETE FROM proyectos WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Proyecto eliminado.", "ok")
    return redirect(url_for("proyectos"))


# ---------------------------------------------------------------------------
# Presupuestos
# ---------------------------------------------------------------------------
def _bateria_auto(conn, proy, preid):
    """Añade la partida de batería dimensionada a un presupuesto recién creado."""
    import json as _json
    try:
        consumo_mensual = _json.loads(proy["consumo_mensual"] or "[]")
    except Exception:
        consumo_mensual = []
    consumo_anual = sum(consumo_mensual) or float(proy["consumo_anual_kwh"] or 0)
    bat = calc.dimensionar_bateria(
        consumo_anual / 365.0,
        autonomia_dias=float(proy["autonomia_bateria_dias"] or 0),
        dod_pct=float(proy["bateria_dod_pct"] or 80),
        tension_v=float(proy["bateria_tension_v"] or 48))
    if not bat:
        return None

    def _capacidad(material):
        try:
            params = _json.loads(material["params"] or "{}")
            cap = str(params.get("capacidad", ""))
            return float(cap.replace(",", ".").replace("kWh", "").strip())
        except Exception:
            return 0.0

    mod = None
    for m in conn.execute(
            "SELECT * FROM materiales WHERE categoria='bateria' ORDER BY precio_unitario"):
        if _capacidad(m) > 0:
            mod = m
            break
    if not mod:
        return None
    cap_mod = _capacidad(mod)
    n = max(1, math.ceil(bat["capacidad_total_kwh"] / cap_mod)) if cap_mod > 0 else 1
    cap_instalada = round(n * cap_mod, 1)
    desc = (f"{mod['nombre']} - banco de {cap_instalada} kWh "
            f"({n} ud, {bat['autonomia_dias']:g} dia(s) de autonomia, DOD {bat['dod_pct']:g}%)")
    conn.execute(
        "INSERT INTO presupuesto_lineas (presupuesto_id, descripcion, tipo, material_id, "
        "cantidad, precio_unitario, iva) VALUES (?,?,?,?,?,?,?)",
        (preid, desc, "material", mod["id"], n, mod["precio_unitario"], mod["iva"]))
    return n


@app.route("/presupuestos")
def presupuestos():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT pr.*, p.nombre AS proyecto, c.nombre AS cliente, "
        "(SELECT ROUND(SUM(l.cantidad*l.precio_unitario*(1+0.0)),2) FROM presupuesto_lineas l "
        "WHERE l.presupuesto_id=pr.id) AS total_bruto "
        "FROM presupuestos pr JOIN proyectos p ON p.id=pr.proyecto_id "
        "LEFT JOIN clientes c ON c.id=p.cliente_id ORDER BY pr.created_at DESC").fetchall()]
    conn.close()
    return render_template("presupuestos.html", rows=rows)


@app.route("/presupuestos/nuevo", methods=["GET", "POST"])
def presupuesto_nuevo():
    if request.method == "POST":
        f = request.form
        pid = f.get("proyecto_id")
        numero = nuevo_numero("P", "presupuestos")
        conn = database.get_db()
        cur = conn.execute(
            "INSERT INTO presupuestos (proyecto_id, numero, fecha, validez_dias, descuento_global, "
            "iva, estado, condiciones, notas) VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, numero, f.get("fecha") or date.today().isoformat(), f.get("validez_dias") or 30,
             f.get("descuento_global") or 0, f.get("iva") or 21, f.get("estado") or "borrador",
             f.get("condiciones"), f.get("notas")))
        preid = cur.lastrowid
        # Copia las partidas del proyecto
        mats = conn.execute("SELECT * FROM proyecto_materiales WHERE proyecto_id=? ORDER BY id", (pid,)).fetchall()
        for m in mats:
            conn.execute(
                "INSERT INTO presupuesto_lineas (presupuesto_id, descripcion, tipo, material_id, "
                "cantidad, precio_unitario, iva) VALUES (?,?,?,?,?,?,?)",
                (preid, m["descripcion"], "material" if m["material_id"] else "partida",
                 m["material_id"], m["cantidad"], m["precio_unitario"], m["iva"]))
        # Añade automáticamente la batería dimensionada si el proyecto la lleva
        proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
        if proy and float(proy["autonomia_bateria_dias"] or 0) > 0:
            _bateria_auto(conn, proy, preid)
        conn.commit()
        conn.close()
        flash(f"Presupuesto {numero} creado a partir del proyecto.", "ok")
        return redirect(url_for("presupuestos"))
    conn = database.get_db()
    proyectos = conn.execute("SELECT p.*, c.nombre AS cliente FROM proyectos p "
                             "LEFT JOIN clientes c ON c.id=p.cliente_id "
                             "ORDER BY p.created_at DESC").fetchall()
    conn.close()
    return render_template("presupuesto_form.html", proyectos=proyectos)


@app.route("/presupuestos/<int:pid>")
def presupuesto_detalle(pid):
    conn = database.get_db()
    pre = conn.execute("SELECT * FROM presupuestos WHERE id=?", (pid,)).fetchone()
    if not pre:
        abort(404)
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pre["proyecto_id"],)).fetchone()
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?",
                           (proy["cliente_id"],)).fetchone() if proy["cliente_id"] else None
    lineas = conn.execute("SELECT * FROM presupuesto_lineas WHERE presupuesto_id=?", (pid,)).fetchall()
    conn.close()
    return render_template("presupuesto_detalle.html", pre=pre, proy=proy, cliente=cliente, lineas=lineas)


@app.route("/presupuestos/<int:pid>/lineas", methods=["POST"])
def presupuesto_add_linea(pid):
    f = request.form
    conn = database.get_db()
    conn.execute(
        "INSERT INTO presupuesto_lineas (presupuesto_id, descripcion, tipo, material_id, "
        "cantidad, precio_unitario, iva) VALUES (?,?,?,?,?,?,?)",
        (pid, f.get("descripcion"), f.get("tipo") or "partida", f.get("material_id") or None,
         f.get("cantidad") or 1, f.get("precio_unitario") or 0, f.get("iva") or 21))
    conn.commit()
    conn.close()
    return redirect(url_for("presupuesto_detalle", pid=pid))


@app.route("/presupuestos/<int:pid>/actualizar", methods=["POST"])
def presupuesto_actualizar(pid):
    f = request.form
    conn = database.get_db()
    conn.execute(
        "UPDATE presupuestos SET validez_dias=?, descuento_global=?, iva=?, estado=?, "
        "condiciones=?, notas=? WHERE id=?",
        (f.get("validez_dias") or 30, f.get("descuento_global") or 0, f.get("iva") or 21,
         f.get("estado") or "borrador", f.get("condiciones"), f.get("notas"), pid))
    conn.commit()
    conn.close()
    flash("Presupuesto actualizado.", "ok")
    return redirect(url_for("presupuesto_detalle", pid=pid))


@app.route("/presupuestos/<int:pid>/eliminar", methods=["POST"])
def presupuesto_eliminar(pid):
    conn = database.get_db()
    conn.execute("DELETE FROM presupuestos WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Presupuesto eliminado.", "ok")
    return redirect(url_for("presupuestos"))


@app.route("/presupuestos/<int:pid>/pdf")
def presupuesto_pdf(pid):
    conn = database.get_db()
    pre = conn.execute("SELECT * FROM presupuestos WHERE id=?", (pid,)).fetchone()
    if not pre:
        conn.close()
        abort(404)
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pre["proyecto_id"],)).fetchone()
    if not proy:
        conn.close()
        abort(404)
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?",
                           (proy["cliente_id"],)).fetchone() if proy["cliente_id"] else None
    lineas = conn.execute("SELECT * FROM presupuesto_lineas WHERE presupuesto_id=?", (pid,)).fetchall()
    conn.close()
    proy = dict(proy)
    res = calc.calcular_proyecto(proy)
    proy["potencia_pico_kw"] = res["potencia_pico_kw"]
    ruta = os.path.join(GENERATED, f"presupuesto_{pid}.pdf")
    pdf_engine.generar_presupuesto(ruta, dict(pre), [dict(l) for l in lineas],
                                   proy, dict(cliente) if cliente else {}, empresa())
    return send_file(ruta, as_attachment=True, download_name=f"presupuesto_{pre['numero']}.pdf")


# ---------------------------------------------------------------------------
# Memorias
# ---------------------------------------------------------------------------
@app.route("/memorias")
def memorias():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT m.*, p.nombre AS proyecto FROM memorias m "
        "JOIN proyectos p ON p.id=m.proyecto_id ORDER BY m.created_at DESC").fetchall()]
    proyectos = [dict(r) for r in conn.execute("SELECT * FROM proyectos ORDER BY nombre").fetchall()]
    conn.close()
    return render_template("memorias.html", rows=rows, proyectos=proyectos)


@app.route("/memorias/nueva", methods=["POST"])
def memoria_nueva():
    f = request.form
    pid = f.get("proyecto_id")
    conn = database.get_db()
    numero = nuevo_numero("M", "memorias")
    cur = conn.execute(
        "INSERT INTO memorias (proyecto_id, numero, fecha, version) VALUES (?,?,?,?)",
        (pid, numero, f.get("fecha") or date.today().isoformat(), f.get("version") or "01"))
    conn.commit()
    conn.close()
    flash(f"Memoria {numero} creada.", "ok")
    return redirect(url_for("memorias"))


@app.route("/memorias/<int:mid>/pdf")
def memoria_pdf(mid):
    conn = database.get_db()
    mem = conn.execute("SELECT * FROM memorias WHERE id=?", (mid,)).fetchone()
    if not mem:
        conn.close()
        abort(404)
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (mem["proyecto_id"],)).fetchone()
    if not proy:
        conn.close()
        abort(404)
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?",
                           (proy["cliente_id"],)).fetchone() if proy["cliente_id"] else None
    lineas = conn.execute("SELECT * FROM proyecto_materiales WHERE proyecto_id=?",
                          (proy["id"],)).fetchall()
    conn.close()
    inversion_total = sum(float(l["cantidad"] or 0) * float(l["precio_unitario"] or 0)
                          for l in lineas)
    if float(proy["inversion_estimada"] or 0) > 0:
        inversion_total = float(proy["inversion_estimada"])
    if inversion_total <= 0:
        inversion_total = calc.calcular_proyecto(dict(proy))["potencia_pico_kw"] * 950.0
    res = calc.calcular_proyecto(dict(proy), inversion_total=inversion_total)
    ruta = os.path.join(GENERATED, f"memoria_{mid}.pdf")
    pdf_engine.generar_memoria(ruta, dict(mem), dict(proy), res, empresa(),
                               dict(cliente) if cliente else None)
    return send_file(ruta, as_attachment=True, download_name=f"memoria_{mem['numero']}.pdf")


@app.route("/memorias/<int:mid>/eliminar", methods=["POST"])
def memoria_eliminar(mid):
    conn = database.get_db()
    conn.execute("DELETE FROM memorias WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    flash("Memoria eliminada.", "ok")
    return redirect(url_for("memorias"))


# ---------------------------------------------------------------------------
# Contratos
# ---------------------------------------------------------------------------
@app.route("/contratos")
def contratos():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT ct.*, c.nombre AS cliente, p.nombre AS proyecto, pr.numero AS presupuesto "
        "FROM contratos ct LEFT JOIN clientes c ON c.id=ct.cliente_id "
        "LEFT JOIN proyectos p ON p.id=ct.proyecto_id "
        "LEFT JOIN presupuestos pr ON pr.id=ct.presupuesto_id "
        "ORDER BY ct.created_at DESC").fetchall()]
    conn.close()
    return render_template("contratos.html", rows=rows)


@app.route("/contratos/nuevo", methods=["GET", "POST"])
def contrato_nuevo():
    conn = database.get_db()
    if request.method == "POST":
        f = request.form
        pid = f.get("proyecto_id")
        proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
        cliente_id = f.get("cliente_id") or proy["cliente_id"]
        preid = f.get("presupuesto_id") or None
        numero = nuevo_numero("C", "contratos")
        cur = conn.execute(
            "INSERT INTO contratos (numero, cliente_id, proyecto_id, presupuesto_id, fecha, "
            "fecha_inicio, fecha_fin, tipo, importe, periodicidad, condiciones, clausulas, "
            "firma_cliente, firma_empresa, estado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (numero, cliente_id, pid, preid, f.get("fecha") or date.today().isoformat(),
             f.get("fecha_inicio"), f.get("fecha_fin"), f.get("tipo") or "mantenimiento",
             f.get("importe") or 0, f.get("periodicidad") or "anual",
             f.get("condiciones"), f.get("clausulas") or "[]",
             f.get("firma_cliente"), f.get("firma_empresa"), f.get("estado") or "borrador"))
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        flash(f"Contrato {numero} creado.", "ok")
        return redirect(url_for("contratos"))

    proyectos = conn.execute("SELECT p.*, c.nombre AS cliente FROM proyectos p "
                             "LEFT JOIN clientes c ON c.id=p.cliente_id "
                             "ORDER BY p.created_at DESC").fetchall()
    clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    presupuestos = conn.execute("SELECT * FROM presupuestos ORDER BY numero").fetchall()
    conn.close()
    return render_template("contrato_form.html", proyectos=proyectos, clientes=clientes,
                           presupuestos=presupuestos)


@app.route("/contratos/<int:cid>")
def contrato_detalle(cid):
    conn = database.get_db()
    ct = conn.execute("SELECT * FROM contratos WHERE id=?", (cid,)).fetchone()
    if not ct:
        abort(404)
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (ct["cliente_id"],)).fetchone() if ct["cliente_id"] else None
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (ct["proyecto_id"],)).fetchone() if ct["proyecto_id"] else None
    pre = conn.execute("SELECT * FROM presupuestos WHERE id=?", (ct["presupuesto_id"],)).fetchone() if ct["presupuesto_id"] else None
    conn.close()
    return render_template("contrato_detalle.html", ct=ct, cliente=cliente, proy=proy, pre=pre)


@app.route("/contratos/<int:cid>/pdf")
def contrato_pdf(cid):
    conn = database.get_db()
    ct = conn.execute("SELECT * FROM contratos WHERE id=?", (cid,)).fetchone()
    if not ct:
        conn.close()
        abort(404)
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?",
                           (ct["cliente_id"],)).fetchone() if ct["cliente_id"] else None
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?",
                        (ct["proyecto_id"],)).fetchone() if ct["proyecto_id"] else None
    conn.close()
    ruta = os.path.join(GENERATED, f"contrato_{cid}.pdf")
    pdf_engine.generar_contrato(ruta, dict(ct), dict(cliente) if cliente else {},
                                dict(proy) if proy else {}, empresa())
    return send_file(ruta, as_attachment=True, download_name=f"contrato_{ct['numero']}.pdf")


@app.route("/contratos/<int:cid>/eliminar", methods=["POST"])
def contrato_eliminar(cid):
    conn = database.get_db()
    conn.execute("DELETE FROM contratos WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    flash("Contrato eliminado.", "ok")
    return redirect(url_for("contratos"))


# ---------------------------------------------------------------------------
# Mantenimiento
# ---------------------------------------------------------------------------
@app.route("/mantenimiento")
def mantenimiento():
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT m.*, p.nombre AS proyecto, c.nombre AS cliente FROM mantenimiento m "
        "JOIN proyectos p ON p.id=m.proyecto_id "
        "LEFT JOIN clientes c ON c.id=p.cliente_id ORDER BY m.fecha_programada DESC").fetchall()]
    proyectos = [dict(r) for r in conn.execute("SELECT * FROM proyectos ORDER BY nombre").fetchall()]
    conn.close()
    return render_template("mantenimiento.html", rows=rows, proyectos=proyectos)


@app.route("/mantenimiento/guardar", methods=["POST"])
def mant_guardar():
    f = request.form
    conn = database.get_db()
    if f.get("id"):
        conn.execute(
            "UPDATE mantenimiento SET proyecto_id=?, periodo=?, fecha_programada=?, "
            "fecha_realizado=?, tecnico=?, estado=?, tareas=?, observaciones=? WHERE id=?",
            (f.get("proyecto_id"), f.get("periodo"), f.get("fecha_programada"),
             f.get("fecha_realizado"), f.get("tecnico"), f.get("estado"),
             f.get("tareas") or "[]", f.get("observaciones"), f.get("id")))
    else:
        conn.execute(
            "INSERT INTO mantenimiento (proyecto_id, contrato_id, periodo, fecha_programada, "
            "fecha_realizado, tecnico, estado, tareas, observaciones) VALUES (?,?,?,?,?,?,?,?,?)",
            (f.get("proyecto_id"), f.get("contrato_id") or None, f.get("periodo"),
             f.get("fecha_programada"), f.get("fecha_realizado"), f.get("tecnico"),
             f.get("estado") or "pendiente", f.get("tareas") or "[]", f.get("observaciones")))
    conn.commit()
    conn.close()
    flash("Registro de mantenimiento guardado.", "ok")
    return redirect(url_for("mantenimiento"))


@app.route("/mantenimiento/<int:mid>/eliminar", methods=["POST"])
def mant_eliminar(mid):
    conn = database.get_db()
    conn.execute("DELETE FROM mantenimiento WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    flash("Registro eliminado.", "ok")
    return redirect(url_for("mantenimiento"))


@app.route("/mantenimiento/<int:mid>/pdf")
def mant_pdf(mid):
    conn = database.get_db()
    reg = conn.execute("SELECT * FROM mantenimiento WHERE id=?", (mid,)).fetchone()
    if not reg:
        conn.close()
        abort(404)
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (reg["proyecto_id"],)).fetchone()
    if not proy:
        conn.close()
        abort(404)
    conn.close()
    ruta = os.path.join(GENERATED, f"mantenimiento_{mid}.pdf")
    pdf_engine.generar_informe_mantenimiento(ruta, dict(reg), dict(proy), empresa())
    return send_file(ruta, as_attachment=True, download_name=f"informe_mantenimiento_{mid}.pdf")


@app.route("/mantenimiento/libro", methods=["POST"])
def mant_libro_form():
    pid = request.form.get("proyecto_id")
    if not pid:
        flash("Selecciona un proyecto.", "err")
        return redirect(url_for("mantenimiento"))
    return mant_libro(int(pid))


@app.route("/mantenimiento/<int:pid>/libro")
def mant_libro(pid):
    conn = database.get_db()
    proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
    if not proy:
        conn.close()
        abort(404)
    registros = conn.execute(
        "SELECT * FROM mantenimiento WHERE proyecto_id=? ORDER BY fecha_realizado", (pid,)).fetchall()
    contrato = conn.execute(
        "SELECT * FROM contratos WHERE proyecto_id=? LIMIT 1", (pid,)).fetchone()
    conn.close()
    ruta = os.path.join(GENERATED, f"libro_{pid}.pdf")
    pdf_engine.generar_libro_mantenimiento(ruta, dict(proy), [dict(r) for r in registros],
                                           empresa(), dict(contrato) if contrato else None)
    return send_file(ruta, as_attachment=True, download_name=f"libro_mantenimiento_{proy['nombre']}.pdf")


# ---------------------------------------------------------------------------
# Recursos / herramientas online
# ---------------------------------------------------------------------------
@app.route("/recursos")
def recursos():
    return render_template("recursos.html")


@app.route("/recursos/pvgis")
def recursos_pvgis():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    incl = request.args.get("incl", 30, type=float)
    asp = request.args.get("asp", 180, type=int)
    datos = None
    if lat is not None and lon is not None:
        datos = calc.pvgis_mensual(lat, lon, incl, asp)
    return render_template("recursos_pvgis.html", datos=datos, lat=lat, lon=lon,
                           incl=incl, asp=asp, meses=calc.MESES)


@app.route("/recursos/calculadora")
def recursos_calculadora():
    return render_template("recursos_calculadora.html", meses=calc.MESES)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@app.route("/uploads/<path:nombre>")
def uploads(nombre):
    return send_from_directory(UPLOADS, nombre)


@app.route("/api/consumo")
def api_consumo():
    """Estimación del consumo eléctrico anual según plantilla (orientativa)."""
    tipo = request.args.get("tipo", "vivienda")
    personas = request.args.get("personas", 2, type=int)
    m2 = request.args.get("m2", 80, type=int)
    if tipo == "vivienda":
        an = 2500 + personas * 800 + m2 * 5
    elif tipo == "nave":
        an = m2 * 12
    else:
        an = 4000 + m2 * 8
    return jsonify({"anual": an})


def run_server(host=None, port=None, debug=False):
    """Inicia la BD y sirve la aplicación en el host/puerto indicados."""
    host = host or os.environ.get("SOLAR_HOST", "127.0.0.1")
    port = port or int(os.environ.get("SOLAR_PORT", "5000"))
    database.init_db()
    app.run(debug=debug, host=host, port=port, threaded=True)


def main():
    """Punto de entrada CLI: `solar` o `solar --host --port --debug`."""
    import argparse
    parser = argparse.ArgumentParser(prog="solar", description="Solar Designer - aplicación de diseño fotovoltaico")
    parser.add_argument("--host", default=os.environ.get("SOLAR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SOLAR_PORT", "5000")))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.debug)


if __name__ == "__main__":
    main()
