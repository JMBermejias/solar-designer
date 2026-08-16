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

"""Interfaz nativa de escritorio (pywebview) para Solar Designer.

Arranca el servidor Flask en un hilo en segundo plano y abre una ventana
propia de la aplicación con la interfaz embebida, sin depender del
navegador. Si no se puede abrir la ventana (falta pywebview o GTK/WebKit2,
o no hay pantalla), devuelve False y detiene su servidor para que el
llamante pueda servir en el navegador.
"""

import os
import socket
import threading
import time
import urllib.request

TITULO = "Solar Designer - Ingeniería Fotovoltaica"
ANCHO, ALTO = 1280, 820


class _Servidor:
    def __init__(self, host, port, debug):
        from werkzeug.serving import make_server
        import app as appmod
        appmod.database.init_db()
        self._server = make_server(host, port, appmod.app, threaded=True)

    def arrancar(self):
        self._server.serve_forever()

    def detener(self):
        self._server.shutdown()


def _puerto_libre(puerto):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", puerto))
        return puerto
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _esperar_servidor(url):
    for _ in range(100):
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def abrir_ventana(host="127.0.0.1", port=5000, debug=False):
    """Abre la ventana nativa. Devuelve True si se abrió, False si no."""
    port = _puerto_libre(port)
    url = "http://%s:%d/" % (host, port)

    try:
        import webview
    except Exception as e:
        print("No se pudo cargar la interfaz nativa: %s" % e)
        print("Falta pywebview o sus dependencias (python3-gi, GTK y WebKit2).")
        print("Ejecuta 'solar --web' para usar el navegador en su lugar.")
        return False

    srv = _Servidor(host, port, debug)
    t = threading.Thread(target=srv.arrancar, daemon=True)
    t.start()
    _esperar_servidor(url)

    try:
        webview.create_window(TITULO, url, width=ANCHO, height=ALTO,
                              min_size=(900, 600))
        webview.start()
    except Exception as e:
        print("No se pudo abrir la ventana nativa: %s" % e)
        srv.detener()
        print("Ejecuta 'solar --web' para usar el navegador en su lugar.")
        return False
    return True


if __name__ == "__main__":
    abrir_ventana()
