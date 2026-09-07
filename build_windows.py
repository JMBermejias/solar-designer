#!/usr/bin/env python3
# Copyright (C) 2026 Enersolred
#
# Solar Designer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Genera un ejecutable .exe standalone de Solar Designer para Windows
usando PyInstaller, y opcionalmente un instalador .exe con Inno Setup.

Uso:
    pip install pyinstaller
    python build_windows.py [--version X.Y.Z]

Resultados:
    - ejecutable:       dist/SolarDesigner.exe
    - instalador:       installer_output/solar-designer-X.Y.Z-windows-setup.exe
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
INSTALLER_OUT = os.path.join(ROOT, "installer_output")
INNO_SCRIPT = os.path.join(ROOT, "installer.iss")

# Rutas típicas de Inno Setup 6
INNO_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
]


def default_version():
    try:
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
            m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "1.0.0"


def find_iscc():
    for p in INNO_PATHS:
        if os.path.isfile(p):
            return p
    # Buscar en PATH
    iscc = shutil.which("ISCC.exe")
    return iscc


def run(cmd, cwd=None):
    print("  >", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd or ROOT)


def clean():
    for d in [DIST, BUILD, INSTALLER_OUT]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    for f in ["SolarDesigner.spec"]:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            os.remove(p)


def main():
    parser = argparse.ArgumentParser(description="Build Windows de Solar Designer")
    parser.add_argument("--version", default=default_version(),
                        help="Versión a empaquetar (por defecto, la de pyproject.toml)")
    parser.add_argument("--no-installer", action="store_true",
                        help="Solo generar el .exe standalone, sin instalador")
    args = parser.parse_args()
    version = args.version

    print("=" * 60)
    print("Solar Designer - Build Windows (.exe)")
    print("=" * 60)

    # 1. Limpiar builds anteriores
    print("\n[1/5] Limpiando builds anteriores...")
    clean()

    # 2. Verificar PyInstaller
    print("\n[2/5] Verificando PyInstaller...")
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__} encontrado.")
    except ImportError:
        print("  Instalando PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 3. Construir .exe
    print("\n[3/5] Construyendo ejecutable...")
    datas = []
    for folder in ["templates", "static", "solar", "assets"]:
        src = os.path.join(ROOT, folder)
        if os.path.isdir(src):
            datas.append(f"--add-data={src};{folder}")

    hidden_imports = [
        "--hidden-import=flask",
        "--hidden-import=jinja2",
        "--hidden-import=werkzeug",
        "--hidden-import=reportlab",
        "--hidden-import=reportlab.lib",
        "--hidden-import=reportlab.pdfbase",
        "--hidden-import=reportlab.pdfgen",
        "--hidden-import=sqlite3",
        "--hidden-import=app",
        "--hidden-import=database",
        "--hidden-import=desktop",
        "--hidden-import=solar_cli",
        "--hidden-import=solar.calculations",
        "--hidden-import=solar.pdf_engine",
        "--hidden-import=solar.normativa",
        "--hidden-import=solar.templates",
        "--hidden-import=webview",
    ]

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=SolarDesigner",
        "--onefile",
        "--noconsole",
        "--icon=assets/solar-designer.ico" if os.path.isfile(os.path.join(ROOT, "assets", "solar-designer.ico")) else "",
        *datas,
        *hidden_imports,
        "--clean",
        "solar_cli.py",
    ]
    pyinstaller_cmd = [c for c in pyinstaller_cmd if c]

    run(pyinstaller_cmd, cwd=ROOT)

    exe_path = os.path.join(DIST, "SolarDesigner.exe")
    if not os.path.isfile(exe_path):
        print("\n  ERROR: No se generó el ejecutable.")
        sys.exit(1)

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n  Ejecutable: {exe_path}")
    print(f"  Tamaño: {size_mb:.1f} MB")

    # 4. Compilar instalador con Inno Setup
    if args.no_installer:
        print("\n[4/5] Omitido (--no-installer).")
    else:
        print("\n[4/5] Compilando instalador con Inno Setup...")
        iscc = find_iscc()
        if not iscc:
            print("\n  AVISO: Inno Setup no está instalado.")
            print("  Descárgalo en https://jrsoftware.org/isdl.php")
            print("  y ejecuta: ISCC.exe installer.iss")
        else:
            if not os.path.isfile(INNO_SCRIPT):
                print(f"  ERROR: No existe {INNO_SCRIPT}")
                sys.exit(1)
            os.makedirs(INSTALLER_OUT, exist_ok=True)
            # Definir la versión al compilar sin modificar el .iss
            run([iscc, "/DMyAppVersion={}".format(version), INNO_SCRIPT], cwd=ROOT)
            setup_name = "solar-designer-{}-windows-setup.exe".format(version)
            setup_path = os.path.join(INSTALLER_OUT, setup_name)
            if os.path.isfile(setup_path):
                ssize = os.path.getsize(setup_path) / (1024 * 1024)
                print(f"\n  Instalador: {setup_path}")
                print(f"  Tamaño: {ssize:.1f} MB")
            else:
                print(f"\n  AVISO: No se encontró {setup_path}.")
                print("  Revisa la salida de ISCC y la configuración [OutputBaseFilename].")

    # 5. Resumen
    print("\n[5/5] RESUMEN:")
    print(f"  Ejecutable standalone: dist\\SolarDesigner.exe")
    if not args.no_installer:
        print(f"  Instalador:             installer_output\\solar-designer-{version}-windows-setup.exe")
    print("=" * 60)


if __name__ == "__main__":
    main()