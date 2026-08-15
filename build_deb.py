#!/usr/bin/env python3
"""Genera el paquete .deb de Solar Designer sin depender de dpkg-deb.

Uso:
    python3 build_deb.py            -> dist/solar-designer_1.1.0_all.deb
    python3 build_deb.py --version 1.2.0
"""

import argparse
import hashlib
import io
import os
import tarfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PACKAGE = "solar-designer"
MAINTAINER = "SolarTech Ingenieria S.L. <info@solartech.es>"

# Dependencias mínimas del sistema: python, venv/pip, GTK3, sus bindings y
# WebKit2GTK para la ventana nativa. El nombre del paquete webkit cambia
# según la distro (4.1 en Debian 12+/Ubuntu 23.10+, 4.0 en el resto), por lo
# que se declara como alternativa: apt instala la primera disponible.
# Flask/ReportLab/pywebview se instalan en postinst (sistema o venv propio),
# de modo que el .deb funciona en cualquier Debian/Ubuntu.
DEPENDS = ("python3, python3-venv, python3-pip, python3-gi, gir1.2-gtk-3.0, "
           "gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0")

CONTROL = """Package: {pkg}
Version: {version}
Architecture: all
Maintainer: {maintainer}
Installed-Size: {size}
Depends: {depends}
Section: web
Priority: optional
Homepage: https://www.solartech.es
Description: Diseno fotovoltaico en una ventana propia
 Genera proyectos, presupuestos, memorias tecnicas, contratos y planes
 de mantenimiento de instalaciones fotovoltaicas, con documentos PDF
 editables (AcroForm) segun normativa espanola. Aplicacion de escritorio
 con interfaz nativa (GTK/WebKit); tambien sirve en el navegador con
 'solar --web'.
"""
POSTINST = """#!/bin/sh
set -e
case "$1" in
  configure)
    mkdir -p /var/lib/solar-designer

    # Dependencias de Python: si el sistema ya tiene flask+reportlab se usan;
    # si no, se instalan en un venv propio con pip (vale para cualquier
    # Debian/Ubuntu aunque los repos no tengan versiones suficientes).
    PY=python3
    if ! python3 -c "import flask, reportlab, webview" 2>/dev/null; then
        if [ ! -x /usr/lib/solar-designer/venv/bin/python ]; then
            python3 -m venv --system-site-packages /usr/lib/solar-designer/venv
        fi
        /usr/lib/solar-designer/venv/bin/pip install --quiet \\
            --disable-pip-version-check "flask>=2.2" "reportlab>=3.6" \\
            "pywebview>=4.4" || true
        if [ -x /usr/lib/solar-designer/venv/bin/python ]; then
            PY=/usr/lib/solar-designer/venv/bin/python
        fi
    fi

    SOLAR_DATA_DIR=/var/lib/solar-designer "$PY" \\
        /usr/lib/solar-designer/solar_cli.py init || true
    chown -R root:root /var/lib/solar-designer 2>/dev/null || true
    ;;
esac
exit 0
"""

WRAPPER_SOLAR = """#!/bin/sh
# Python: el del venv si postinst lo creó; si no, el del sistema.
if [ -x /usr/lib/solar-designer/venv/bin/python ]; then
    PY=/usr/lib/solar-designer/venv/bin/python
else
    PY=python3
fi
# Directorio de datos: /var/lib/solar-designer si es escribible;
# si no (usuario sin privilegios), directorio de datos del usuario.
if [ -z "${SOLAR_DATA_DIR:-}" ]; then
    if [ -d /var/lib/solar-designer ] && [ -w /var/lib/solar-designer ]; then
        export SOLAR_DATA_DIR=/var/lib/solar-designer
    else
        export SOLAR_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/solar-designer"
    fi
fi
export SOLAR_APP_DIR=/usr/share/solar-designer
exec "$PY" /usr/lib/solar-designer/solar_cli.py "$@"
"""

WRAPPER_INIT = """#!/bin/sh
if [ -x /usr/lib/solar-designer/venv/bin/python ]; then
    PY=/usr/lib/solar-designer/venv/bin/python
else
    PY=python3
fi
if [ -z "${SOLAR_DATA_DIR:-}" ]; then
    if [ -d /var/lib/solar-designer ] && [ -w /var/lib/solar-designer ]; then
        export SOLAR_DATA_DIR=/var/lib/solar-designer
    else
        export SOLAR_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/solar-designer"
    fi
fi
export SOLAR_APP_DIR=/usr/share/solar-designer
exec "$PY" /usr/lib/solar-designer/solar_cli.py init
"""


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_tree():
    """Devuelve {ruta_relativa_en_el_paquete: ruta_origen} y permisos."""
    files = {}
    lib = os.path.join(ROOT, "usr-lib")
    os.makedirs(lib, exist_ok=True)
    # copia de los módulos a un árbol limpio
    for f in ("app.py", "database.py", "desktop.py", "solar_cli.py"):
        src = os.path.join(ROOT, f)
        dst = os.path.join(lib, f)
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            fo.write(fi.read())
        files["usr/lib/solar-designer/" + f] = dst
    for f in os.listdir(os.path.join(ROOT, "solar")):
        if f.endswith(".py"):
            src = os.path.join(ROOT, "solar", f)
            dst = os.path.join(lib, "solar_" + f)
            with open(src, "rb") as fi, open(dst, "wb") as fo:
                fo.write(fi.read())
            files["usr/lib/solar-designer/solar/" + f] = dst
    for t in sorted(os.listdir(os.path.join(ROOT, "templates"))):
        src = os.path.join(ROOT, "templates", t)
        files["usr/share/solar-designer/templates/" + t] = src
    for s in ("static/css/style.css", "static/js/app.js"):
        files["usr/share/solar-designer/" + s] = os.path.join(ROOT, s)
    # icono y lanzador de menú
    files["usr/share/icons/hicolor/scalable/apps/solar-designer.svg"] = \
        os.path.join(ROOT, "assets", "solar-designer.svg")
    files["usr/share/applications/solar-designer.desktop"] = \
        os.path.join(ROOT, "assets", "solar-designer.desktop")
    return files


def stage_files(files):
    """Copia todos los ficheros a un árbol de stage y devuelve la raíz."""
    stage = os.path.join(ROOT, "build", "stage")
    if os.path.isdir(stage):
        import shutil
        shutil.rmtree(stage)
    for rel, src in files.items():
        dst = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            fo.write(fi.read())
    return stage


def make_tar(stage, member_paths, modes, prefix=""):
    """Crea un control.tar.gz/data.tar.gz en memoria."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tf:
        for rel, mode in sorted(zip(member_paths, modes)):
            p = os.path.join(stage, rel)
            ti = tf.gettarinfo(p, arcname=prefix + rel)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            ti.mode = mode
            ti.mtime = 0
            if ti.isdir():
                tf.addfile(ti)
            else:
                with open(p, "rb") as f:
                    tf.addfile(ti, f)
    return buf.getvalue()


def ar_member(name, data, mode=0o100644):
    """Cabecera ar de 60 bytes + datos (alineados a par)."""
    hdr = "%s/%-15s" % (name, " ")          # 16 bytes, nombre con '/'
    hdr = hdr[:16]
    mtime, uid, gid = "0", "0", "0"
    size = str(len(data))
    mode_s = "%06o" % mode
    header = (hdr + mtime.rjust(12) + uid.rjust(6) + gid.rjust(6) +
              mode_s.rjust(8) + size.rjust(10) + "`\n").encode()
    payload = data
    if len(payload) % 2:
        payload += b"\n"
    return header + payload


def build_deb(version):
    files = build_tree()
    stage = stage_files(files)
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)

    # control.tar.gz
    control_dir = os.path.join(ROOT, "build", "control")
    if os.path.isdir(control_dir):
        import shutil
        shutil.rmtree(control_dir)
    os.makedirs(control_dir)

    total = sum(os.path.getsize(s) for s in files.values())
    control_content = CONTROL.format(pkg=PACKAGE, version=version,
                                     maintainer=MAINTAINER,
                                     size=max(1, total // 1024),
                                     depends=DEPENDS)
    with open(os.path.join(control_dir, "control"), "w") as f:
        f.write(control_content)

    md5s = "\n".join("%s  %s" % (md5(src), rel)
                     for rel, src in sorted(files.items())) + "\n"
    with open(os.path.join(control_dir, "md5sums"), "w") as f:
        f.write(md5s)

    postinst = os.path.join(control_dir, "postinst")
    with open(postinst, "w") as f:
        f.write(POSTINST)

    control_tar = make_tar(control_dir, ["control", "md5sums", "postinst"],
                           [0o100644, 0o100644, 0o100755], prefix="./")

    # wrappers
    for rel in ("usr/bin/solar", "usr/bin/solar-init"):
        dst = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w") as f:
            f.write(WRAPPER_SOLAR if rel.endswith("solar") else WRAPPER_INIT)
        os.chmod(dst, 0o755)

    # data.tar.gz (directorios intermedios con 0755)
    data_members = []
    seen_dirs = set()
    for rel in sorted(files) + ["usr/bin/solar", "usr/bin/solar-init"]:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            if d not in seen_dirs:
                seen_dirs.add(d)
                os.makedirs(os.path.join(stage, d), exist_ok=True)
                data_members.append((d, 0o40755))
        data_members.append((rel, 0o100644 if not rel.startswith("usr/bin") else 0o100755))
    data_tar = make_tar(stage, [m[0] for m in data_members], [m[1] for m in data_members])

    deb = (ar_member("debian-binary", b"2.0\n", 0o100644) +
           ar_member("control.tar.gz", control_tar, 0o100644) +
           ar_member("data.tar.gz", data_tar, 0o100644))

    out = os.path.join(out_dir, "%s_%s_all.deb" % (PACKAGE, version))
    with open(out, "wb") as f:
        f.write(b"!<arch>\n" + deb)
    print("Paquete generado:", out)
    print("Ficheros:", len(files), "- Tamano:", len(deb), "bytes")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera el .deb de Solar Designer")
    parser.add_argument("--version", default="1.1.0")
    args = parser.parse_args()
    build_deb(args.version)
