#!/usr/bin/env python3
"""
Solar Designer - instalador automático multiplataforma.

Uso:
    python install.py            instalación completa (venv + dependencias + BD)
    python install.py --port 5000   elegir puerto
    python install.py --host 0.0.0.0  escuchar en todas las interfaces

Genera:
    - venv/                 entorno virtual con las dependencias
    - run.sh (Linux/macOS) y run.bat (Windows) para arrancar
    - Base de datos inicial con datos de ejemplo
"""

import argparse
import os
import subprocess
import sys
import venv

ROOT = os.path.dirname(os.path.abspath(__file__))


def python_cmd(bin_dir, name="python"):
    if os.name == "nt":
        return os.path.join(bin_dir, name + ".exe")
    return os.path.join(bin_dir, name)


def run(cmd, cwd=None):
    print("  >", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd or ROOT)


def main():
    parser = argparse.ArgumentParser(prog="install", description="Instalador de Solar Designer")
    parser.add_argument("--host", default="127.0.0.1", help="host por defecto")
    parser.add_argument("--port", type=int, default=5000, help="puerto por defecto")
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        print("Se necesita Python 3.9 o superior.")
        sys.exit(1)

    print("=" * 60)
    print("Solar Designer - instalador automático")
    print("=" * 60)
    print("Directorio de instalación:", ROOT)

    venv_dir = os.path.join(ROOT, "venv")
    print("\n[1/4] Creando entorno virtual en venv/ ...")
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    py = python_cmd(os.path.join(venv_dir, "bin") if os.name != "nt" else os.path.join(venv_dir, "Scripts"))

    print("\n[2/4] Instalando dependencias (Flask, ReportLab) ...")
    run([py, "-m", "pip", "install", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", "-e", ROOT])

    print("\n[3/4] Inicializando base de datos y directorios ...")
    run([py, "-c", "import solar_cli; solar_cli.init_db()"])

    # Launchers
    print("\n[4/4] Creando lanzadores ...")
    if os.name == "nt":
        launcher = os.path.join(ROOT, "run.bat")
        with open(launcher, "w", encoding="utf-8") as f:
            f.write('@echo off\r\n')
            f.write('cd /d "%~dp0"\r\n')
            f.write(f'call venv\\Scripts\\python solar_cli.py --host {args.host} --port {args.port}\r\n')
    else:
        launcher = os.path.join(ROOT, "run.sh")
        with open(launcher, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
            f.write('cd "$(dirname "$0")"\n')
            f.write(f'exec venv/bin/python solar_cli.py --host {args.host} --port {args.port}\n')
        os.chmod(launcher, 0o755)

    print("\n" + "=" * 60)
    print("Instalación completada.")
    print("Para arrancar la aplicación:")
    if os.name == "nt":
        print("    run.bat")
    else:
        print("    ./run.sh")
    print(f"Luego abre:  http://{args.host}:{args.port}")
    print("=" * 60)


if __name__ == "__main__":
    main()
