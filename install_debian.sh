#!/bin/sh
# Solar Designer - instalador para cualquier distribución basada en Debian
# (Debian, Ubuntu, Mint, Zorin, Pop!_OS, Kali, etc.)
#
# Uso:
#   python3 build_deb.py          # genera el .deb (opcional, ya incluido)
#   ./install_debian.sh           # instala paquete + dependencias

set -e
cd "$(dirname "$0")"

DEB=$(ls dist/solar-designer_*.deb 2>/dev/null | sort -V | tail -1)
if [ -z "$DEB" ]; then
    echo "No se encuentra ningún .deb en dist/."
    echo "Ejecuta primero:  python3 build_deb.py"
    exit 1
fi

echo "=================================================="
echo " Solar Designer - instalador Debian"
echo "=================================================="
echo " Paquete : $DEB"
echo

if [ "$(id -u)" -ne 0 ]; then
    echo "Se pedirá contraseña de administrador (sudo) para instalar."
    echo
fi

# apt resuelve e instala automáticamente python3, python3-venv, python3-pip,
# python3-gi y GTK3. Flask, ReportLab y pywebview se instalan en el postinst
# (sistema o venv propio), por lo que no hace falta que estén en los repos.
sudo apt-get update
sudo apt-get install -y "$DEB"

# WebKit2GTK para la ventana nativa (nombre cambia según la distribución:
# gir1.2-webkit2-4.1 en Debian 12+/Ubuntu 23.10+, gir1.2-webkit2-4.0 antes).
if ! dpkg -s gir1.2-webkit2-4.1 >/dev/null 2>&1 && \
   ! dpkg -s gir1.2-webkit2-4.0 >/dev/null 2>&1; then
    if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
        sudo apt-get install -y gir1.2-webkit2-4.1
    elif apt-cache show gir1.2-webkit2-4.0 >/dev/null 2>&1; then
        sudo apt-get install -y gir1.2-webkit2-4.0
    else
        echo
        echo "Aviso: no se encontró WebKit2GTK en los repositorios."
        echo "La ventana nativa no estará disponible; usa 'solar --web'."
    fi
fi

echo
echo "=================================================="
echo " Instalación completada."
echo " Para abrir la aplicación:    solar"
echo "   (ventana propia, sin navegador)"
echo " Alternativa en navegador:    solar --web"
echo "=================================================="
