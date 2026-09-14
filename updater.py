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
import os
import re
import shutil
import subprocess
import tempfile
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
        "assets": data.get("assets") or [],
    }


def _asset_deb(info):
    for a in info.get("assets") or []:
        if (a.get("name") or "").endswith(".deb"):
            return a.get("browser_download_url")
    return None


def instalar_actualizacion(timeout_descarga=120, timeout_install=240):
    """Descarga e instala la versión más reciente (Linux/.deb via pkexec).

    Devuelve un dict con ok, version, error, mensaje y, en algunos fallos,
    la ruta del .deb descargado para instalarlo a mano (sudo dpkg -i).
    """
    from version import __version__

    try:
        info = _ultima_version(8)
    except Exception:
        info = None
    if not info:
        return {"ok": False, "error": "consulta",
                "mensaje": "No se pudo consultar GitHub para descargar la actualización.",
                "ruta": None}

    nueva = info.get("version") or ""
    if _version_tupla(nueva) <= _version_tupla(__version__):
        return {"ok": False, "error": "al_dia",
                "mensaje": "Ya tienes la versión más reciente (%s)." % __version__,
                "ruta": None}

    deb_url = _asset_deb(info)
    if not deb_url:
        return {"ok": False, "error": "no_deb",
                "mensaje": "La release v%s no tiene paquete .deb para "
                           "descargar." % nueva, "ruta": None}

    ruta = None
    try:
        fd, ruta = tempfile.mkstemp(prefix="solar-designer-", suffix=".deb")
        os.close(fd)
        req = urllib.request.Request(deb_url,
                                     headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_descarga) as resp:
            with open(ruta, "wb") as f:
                shutil.copyfileobj(resp, f)
        if os.path.getsize(ruta) < 1000:
            try:
                os.remove(ruta)
            except Exception:
                pass
            return {"ok": False, "error": "descarga",
                    "mensaje": "El paquete descargado parece incompleto "
                               "(%s bytes)." % os.path.getsize(ruta), "ruta": None}
    except Exception as e:
        try:
            if ruta and os.path.exists(ruta):
                os.remove(ruta)
        except Exception:
            pass
        return {"ok": False, "error": "descarga",
                "mensaje": "Error al descargar el paquete: %s" % e, "ruta": None}

    instr = "Si no aparece el diálogo, instálalo manualmente con:\n" \
            "  sudo dpkg -i %s" % ruta
    try:
        proc = subprocess.run(
            ["pkexec", "dpkg", "-i", ruta],
            capture_output=True, text=True, timeout=timeout_install,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "sin_pkexec",
                "mensaje": "La instalación automática no está disponible "
                           "en este sistema (falta polkit/pkexec).\n\n%s" % instr,
                "ruta": ruta}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "instalacion",
                "mensaje": "La instalación tardó demasiado (posible "
                           "dialogo de contraseña sin respuesta).\n\n%s" % instr,
                "ruta": ruta}

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        return {"ok": False, "error": "instalacion",
                "mensaje": "La instalación falló (¿cancelaste la "
                           "contraseña?).\n\n%s" % instr +
                           ("\n\nError: %s" % stderr if stderr else ""),
                "ruta": ruta}

    try:
        os.remove(ruta)
    except Exception:
        pass
    return {"ok": True, "version": nueva,
            "mensaje": "Actualizado correctamente a la versión %s." % nueva,
            "ruta": None}


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