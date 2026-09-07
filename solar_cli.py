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

"""Punto de entrada CLI de Solar Designer.

Comandos:
    solar                abre la aplicación en una ventana nativa (sin navegador)
    solar --web          sirve la aplicación para el navegador
    solar --host 0.0.0.0 --port 5000
    solar --help
    solar init           inicializa la base de datos y directorios
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _is_frozen():
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _open_browser(host, port):
    import webbrowser
    webbrowser.open(f"http://{host}:{port}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        return init_db()

    import argparse
    parser = argparse.ArgumentParser(prog="solar", description="Solar Designer - diseño fotovoltaico")
    parser.add_argument("--host", default=os.environ.get("SOLAR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SOLAR_PORT", "5000")))
    parser.add_argument("--web", action="store_true",
                        help="servir en el navegador en vez de abrir la ventana nativa")
    parser.add_argument("--no-browser", action="store_true",
                        help="no abrir el navegador automáticamente")
    parser.add_argument("--debug", action="store_true", help="modo depuración de Flask")
    args = parser.parse_args()

    if _is_frozen() or args.web:
        import app
        if not args.no_browser:
            import threading
            threading.Timer(1.5, _open_browser, args=[args.host, args.port]).start()
        app.run_server(args.host, args.port, args.debug)
        return

    import desktop
    if not desktop.abrir_ventana(args.host, args.port, args.debug):
        import app
        if not args.no_browser:
            import threading
            threading.Timer(1.5, _open_browser, args=[args.host, args.port]).start()
        app.run_server(args.host, args.port, args.debug)


def init_db():
    import database
    database.init_db()
    from app import UPLOADS, GENERATED
    os.makedirs(UPLOADS, exist_ok=True)
    os.makedirs(GENERATED, exist_ok=True)
    print("Solar Designer inicializado.")
    print("  Datos:    ", database.data_dir())
    print("  Subidas:  ", UPLOADS)
    print("  PDFs:     ", GENERATED)


if __name__ == "__main__":
    main()
