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

"""Comprobación de actualizaciones frente al repositorio GitHub.

Consulta la última release publicada en
https://github.com/JMBermejias/solar-designer y compara su versión con la
instalada. Los resultados se guardan en caché durante unos minutos para no
agotar la cuota de la API y para que la comprobación al abrir la aplicación
sea inmediata. Si no hay conexión a internet se devuelve un estado neutro
("sin disponible") sin bloquear la interfaz.
"""

import json
import re
import time
import urllib.parse
import urllib.request
import webbrowser

REPO = "JMBermejias/solar-designer"
API_URL = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASE_URL = "https://github.com/%s/releases" % REPO
CACHE_TTL = 15 * 60  # 15 minutos
_CACHE = {"ts": 0.0, "datos": None}

USER_AGENT = "solar-designer"


def _version_tupla(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0, 0, 0)


def _ultima_version(timeout):
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tag = (data.get("tag_name") or "").lstrip("v")
    return {
        "version": tag,
        "tag": data.get("tag_name") or "v" + tag,
        "url": data.get("html_url") or RELEASE_URL,
        "notas": (data.get("body") or "").strip(),
        "publicado": data.get("published_at"),
    }


def comprobar_actualizacion(timeout=6):
    """Devuelve un dict con la situación de actualización.

    Campos: disponible (bool), actual (instalada), nueva, url, notas, error.
    """
    from version import __version__

    ahora = time.time()
    if _CACHE["datos"] is not None and ahora - _CACHE["ts"] < CACHE_TTL:
        info = _CACHE["datos"]
    else:
        try:
            info = _ultima_version(timeout)
            _CACHE["ts"] = ahora
            _CACHE["datos"] = info
        except Exception:
            info = None

    if not info:
        return {"disponible": False, "error": "sin_conexion",
                "actual": __version__, "nueva": None, "url": RELEASE_URL,
                "notas": None}

    disponible = _version_tupla(info["version"]) > _version_tupla(__version__)
    return {"disponible": disponible,
            "error": None,
            "actual": __version__,
            "nueva": info["version"],
            "url": info["url"],
            "notas": info.get("notas")}


def abrir_release(url=None):
    """Abre la página de releases en el navegador del sistema.

    Solo acepta URLs del repositorio solar-designer para evitar abrir
    direcciones arbitrarias; cualquier otra se ignora y se usa la genérica.
    """
    destino = RELEASE_URL
    if url:
        try:
            u = urllib.parse.urlparse(url)
            if (u.scheme in ("http", "https") and u.netloc == "github.com"
                    and u.path.startswith("/%s" % REPO)):
                destino = url
        except Exception:
            destino = RELEASE_URL
    return webbrowser.open(destino)