# Solar Designer

Aplicación de escritorio para planificación, cálculo y diseño de
instalaciones fotovoltaicas: proyectos, materiales, presupuestos, memorias
técnicas, contratos y mantenimiento, con generación de documentos en PDF
editable (AcroForm) según normativa española.

Se abre en una **ventana propia** (GTK/WebKit), sin depender del navegador.
También puede servir en el navegador con `solar --web`.

## Requisitos

- **Opción D (.deb, recomendada):** cualquier distribución basada en Debian.
- **Opción A (Docker):** cualquier sistema con Docker y Docker Compose.
- **Opción B (local):** Python 3.9 o superior.

## Opción A: Docker (recomendada)

```sh
docker compose up -d
# abre http://localhost:5000
```

Los datos (SQLite, subidas y PDFs) quedan en el volumen `solar_data`,
persistente entre reinicios.

## Opción B: instalación local automática

```sh
python install.py          # Linux/macOS: ./run.sh | Windows: run.bat
./run.sh                   # o run.bat en Windows
# abre http://127.0.0.1:5000
```

`install.py` crea un entorno virtual, instala las dependencias e inicializa
la base de datos con datos de ejemplo.

## Opción C: pip

```sh
pip install .
solar            # ventana nativa
solar --web      # o en el navegador
```

## Opción D: paquete .deb (cualquier distribución basada en Debian)

Válido para Debian, Ubuntu, Linux Mint, Zorin, Pop!_OS, etc. Un solo
comando instala el paquete, todas las dependencias del sistema (incluida
WebKit2GTK para la ventana nativa, eligiendo automáticamente el nombre
correcto del paquete según la distro) y crea una entrada **Solar Designer**
en el menú de aplicaciones con su icono:

```sh
python3 build_deb.py                # genera dist/solar-designer_1.2.0_all.deb
sudo apt install ./dist/solar-designer_1.2.0_all.deb
solar                               # abre la ventana nativa de la aplicación
```

Desde el escritorio: búscala como **Solar Designer** en el menú de
aplicaciones.

Si no hay ventana disponible (sin WebKit, sin pantalla), `solar` avisa y
sirve en el navegador automáticamente; o fuerza el navegador con
`solar --web`.

Los datos quedan en `/var/lib/solar-designer` (o en `~/.local/share/
solar-designer` si se ejecuta sin privilegios de escritura).

## Configuración

| Variable             | Descripción                                      |
|----------------------|--------------------------------------------------|
| `SOLAR_DATA_DIR`     | Directorio de datos (BD, uploads, PDFs)          |
| `SOLAR_APP_DIR`      | Directorio con `templates/` y `static/`          |
| `SOLAR_HOST`         | Host por defecto (`127.0.0.1`)                   |
| `SOLAR_PORT`         | Puerto por defecto (`5000`)                      |
| `SOLAR_SECRET_KEY`   | Clave secreta de sesión de Flask                 |

## Distribución en GitHub Releases

El repositorio incluye el workflow de GitHub Actions
`.github/workflows/build.yml`, que compila **automáticamente en cada push**
a `main` (o cuando creas una etiqueta `v*`) los ejecutables de Windows y
Linux, y los publica como una release:

- **Windows (runner windows-latest):** ejecutable standalone
  `SolarDesigner.exe` (PyInstaller) e instalador autoinstalable
  `solar-designer-<versión>-windows-setup.exe` (Inno Setup).
- **Linux (runner ubuntu-latest):** paquete `.deb` universal
  `solar-designer_<versión>_all.deb`.

Cada cambio que se sube a `main` genera una release nueva, sin necesidad
de tocar etiquetas. También puedes dispararlo manualmente desde la pestaña
*Actions* (`Build & Release` → *Run workflow*).

La versión se lee de `pyproject.toml`. Para asignar una versión, crea una
etiqueta y sube los ejecutables con el número correspondiente:

```sh
git tag v1.3.1
git push origin v1.3.1
```

Tras unos minutos aparecerá el release con los tres artefactos. Para
instalar en Linux:

```sh
sudo apt install ./solar-designer_1.3.1_all.deb
```

### Generar el instalador de Windows localmente

Si prefieres compilar en tu propia máquina con Windows:

```sh
pip install pyinstaller flask reportlab pywebview
python build_windows.py --version 1.3.1
```

Requiere [Inno Setup 6](https://jrsoftware.org/isdl.php) para generar el
instalador autoinstalable. Resultado:
- `dist/SolarDesigner.exe` - ejecutable portable
- `installer_output/solar-designer-1.3.1-windows-setup.exe` - instalador

## Estructura

```
app.py            Aplicación Flask (rutas web)
desktop.py        Interfaz nativa de escritorio (ventana, sin navegador)
database.py       SQLite, esquema y datos iniciales
solar/            Cálculos, normativa, plantillas y PDFs
templates/        Vistas HTML
static/           CSS y JS
install.py        Instalador local automático
install_debian.sh Instalador para distribuciones basadas en Debian
.github/         Workflow de GitHub Actions (build y release del .deb)
Dockerfile        Imagen de contenedor
docker-compose.yml  Orquestación Docker con volumen de datos
```

## Funcionalidades

- Gestión de clientes, proveedores, productos (catálogo de materiales) y
  herramientas, con añadir/modificar/eliminar.
- Empresas: catálogo de varias empresas propias (crear, editar, eliminar y
  elegir la activa que aparece en los PDFs).
- Proyectos con ubicación, consumo, orientación y cálculo de rendimiento
  (PVGIS, sistema, pérdidas y producción mensual).
- Presupuestos con partidas y baterías dimensionadas automáticamente.
- Memoria técnica, contrato y plan de mantenimiento en PDF editable.
- Simulador financiero (VAN, TIR, ROI) y dimensionado de baterías.

## Licencia

SolarDesigner es software libre: puedes redistribuirlo y/o modificarlo bajo
los términos de la GNU General Public License versión 3 (o cualquier versión
posterior). Ver el archivo [`LICENSE`](LICENSE) para los términos completos.

Desarrollado por **Enersolred** · https://enersolred.blogspot.com/
