import json
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Directorio de datos (SQLite, uploads, PDFs).

    Se puede sobreescribir con la variable de entorno SOLAR_DATA_DIR
    (por ejemplo, un volumen persistente en Docker).
    """
    env = os.environ.get("SOLAR_DATA_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    path = os.path.join(BASE, "datos")
    os.makedirs(path, exist_ok=True)
    return path


DB_PATH = os.path.join(data_dir(), "solar.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    nif TEXT, direccion TEXT, cp TEXT, ciudad TEXT, provincia TEXT,
    telefono TEXT, email TEXT, contacto TEXT, notas TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS proveedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL, nif TEXT, direccion TEXT, cp TEXT, ciudad TEXT,
    telefono TEXT, email TEXT, contacto TEXT, web TEXT, notas TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS materiales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    nombre TEXT NOT NULL, marca TEXT, modelo TEXT, referencia TEXT,
    descripcion TEXT, ficha_url TEXT,
    precio_unitario REAL DEFAULT 0, iva REAL DEFAULT 21,
    unidad TEXT DEFAULT 'ud', stock REAL DEFAULT 0,
    garantia_anos INTEGER DEFAULT 2, vida_util_anos INTEGER DEFAULT 25,
    potencia_w REAL, eficiencia REAL,
    params TEXT DEFAULT '{}',
    imagen TEXT, proveedor_id INTEGER,
    FOREIGN KEY(proveedor_id) REFERENCES proveedores(id)
);
CREATE TABLE IF NOT EXISTS herramientas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL, categoria TEXT, descripcion TEXT,
    cantidad REAL DEFAULT 1, estado TEXT DEFAULT 'operativo',
    ubicacion TEXT, imagen TEXT, notas TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS proyectos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    nombre TEXT NOT NULL, direccion TEXT, cp TEXT, ciudad TEXT, provincia TEXT,
    lat REAL, lon REAL, altitud_msnm REAL DEFAULT 0,
    potencia_contratada REAL, tarifa TEXT,
    consumo_mensual TEXT DEFAULT '[]',
    consumo_anual_kwh REAL,
    tipo_cubierta TEXT, superficie_m2 REAL,
    orientacion_deg REAL DEFAULT 180, inclinacion_deg REAL DEFAULT 30,
    sombras TEXT DEFAULT 'sin sombras',
    autonomia_bateria_dias REAL DEFAULT 1,
    bateria_dod_pct REAL DEFAULT 80,
    bateria_tension_v REAL DEFAULT 48,
    inversion_subvencion REAL DEFAULT 0,
    inversion_estimada REAL DEFAULT 0,
    inversion_tasa_descuento_pct REAL DEFAULT 3.5,
    inversion_tasa_energia_pct REAL DEFAULT 2.5,
    inversion_vida_util REAL DEFAULT 25,
    inversion_costo_mantenimiento_pct REAL DEFAULT 0.5,
    imagen_fachada TEXT, imagen_plano TEXT, imagen_planta TEXT,
    imagen_extra1 TEXT, imagen_extra2 TEXT,
    notas TEXT, estado TEXT DEFAULT 'en diseño',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
CREATE TABLE IF NOT EXISTS proyecto_materiales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL,
    material_id INTEGER,
    partida TEXT, descripcion TEXT, categoria TEXT,
    cantidad REAL DEFAULT 1, precio_unitario REAL DEFAULT 0, iva REAL DEFAULT 21,
    FOREIGN KEY(proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE,
    FOREIGN KEY(material_id) REFERENCES materiales(id)
);
CREATE TABLE IF NOT EXISTS presupuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER,
    numero TEXT NOT NULL,
    fecha TEXT DEFAULT (date('now')),
    validez_dias INTEGER DEFAULT 30,
    descuento_global REAL DEFAULT 0,
    iva REAL DEFAULT 21,
    estado TEXT DEFAULT 'borrador',
    condiciones TEXT, notas TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
);
CREATE TABLE IF NOT EXISTS presupuesto_lineas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    presupuesto_id INTEGER NOT NULL,
    descripcion TEXT NOT NULL,
    tipo TEXT DEFAULT 'partida',
    material_id INTEGER,
    cantidad REAL DEFAULT 1, precio_unitario REAL DEFAULT 0, iva REAL DEFAULT 21,
    FOREIGN KEY(presupuesto_id) REFERENCES presupuestos(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS memorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL,
    numero TEXT NOT NULL,
    fecha TEXT DEFAULT (date('now')),
    version TEXT DEFAULT '01',
    contenido TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
);
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL,
    cliente_id INTEGER, proyecto_id INTEGER, presupuesto_id INTEGER,
    fecha TEXT DEFAULT (date('now')),
    fecha_inicio TEXT, fecha_fin TEXT,
    tipo TEXT DEFAULT 'mantenimiento',
    importe REAL, periodicidad TEXT DEFAULT 'anual',
    condiciones TEXT, clausulas TEXT DEFAULT '[]',
    firma_cliente TEXT, firma_empresa TEXT,
    estado TEXT DEFAULT 'borrador',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS mantenimiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL,
    contrato_id INTEGER,
    periodo TEXT NOT NULL,
    fecha_programada TEXT,
    fecha_realizado TEXT,
    tecnico TEXT, estado TEXT DEFAULT 'pendiente',
    tareas TEXT DEFAULT '[]',
    observaciones TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(proyecto_id) REFERENCES proyectos(id),
    FOREIGN KEY(contrato_id) REFERENCES contratos(id)
);
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY, valor TEXT
);
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    cif TEXT DEFAULT '',
    direccion TEXT DEFAULT '',
    ciudad TEXT DEFAULT '',
    telefono TEXT DEFAULT '',
    email TEXT DEFAULT '',
    web TEXT DEFAULT '',
    activa INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _migrar(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(proyectos)").fetchall()}
    if "bateria_dod_pct" not in cols:
        conn.execute("ALTER TABLE proyectos ADD COLUMN bateria_dod_pct REAL DEFAULT 80")
    if "bateria_tension_v" not in cols:
        conn.execute("ALTER TABLE proyectos ADD COLUMN bateria_tension_v REAL DEFAULT 48")
    for col, tipo, val in [
        ("inversion_subvencion", "REAL", 0),
        ("inversion_estimada", "REAL", 0),
        ("inversion_tasa_descuento_pct", "REAL", 3.5),
        ("inversion_tasa_energia_pct", "REAL", 2.5),
        ("inversion_vida_util", "REAL", 25),
        ("inversion_costo_mantenimiento_pct", "REAL", 0.5),
    ]:
        if col not in cols:
            conn.execute(f"ALTER TABLE proyectos ADD COLUMN {col} {tipo} DEFAULT {val}")


def _migrar_empresas(conn):
    """Convierte la antigua empresa única (config.empresa) en la tabla empresas."""
    if conn.execute("SELECT COUNT(*) FROM empresas").fetchone()[0] > 0:
        return
    datos = None
    fila = conn.execute("SELECT valor FROM config WHERE clave='empresa'").fetchone()
    if fila:
        try:
            datos = json.loads(fila["valor"])
        except Exception:
            datos = None
    if not datos:
        datos = {"nombre": "SolarTech Ingeniería S.L.", "cif": "B12345678",
                 "direccion": "C/ Solar 12, 28001 Madrid", "ciudad": "Madrid",
                 "telefono": "900 123 456", "email": "info@solartech.es",
                 "web": "www.solartech.es"}
    conn.execute(
        "INSERT INTO empresas (nombre, cif, direccion, ciudad, telefono, email, web, activa) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (datos.get("nombre", "Mi empresa"), datos.get("cif", ""),
         datos.get("direccion", ""), datos.get("ciudad", ""),
         datos.get("telefono", ""), datos.get("email", ""), datos.get("web", "")))


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    _migrar(conn)
    conn.commit()
    seed(conn)
    _migrar_empresas(conn)
    conn.commit()
    conn.close()


def seed(conn):
    cur = conn.cursor()
    if cur.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO config (clave, valor) VALUES (?, ?)",
            ("empresa",
             json.dumps({
                 "nombre": "SolarTech Ingeniería S.L.",
                 "cif": "B12345678",
                 "direccion": "C/ Solar 12, 28001 Madrid",
                 "telefono": "900 123 456",
                 "email": "info@solartech.es",
                 "web": "www.solartech.es",
             })),
        )
    if cur.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0] == 0:
        provs = [
            ("Silicon Valley Solar, S.A.", "B50000001", "Pol. Ind. Los Angeles",
             "50001", "Zaragoza", "976 100 100", "ventas@svsolar.es", "A. García"),
            ("Inverter Pro España", "B08000002", "Av. Barcelona 100", "08018",
             "Barcelona", "932 000 000", "info@inverterpro.es", "M. López"),
            ("Baterías Energía Plus", "A41000003", "Pol. Ind. Sevilla Este",
             "41020", "Sevilla", "954 200 200", "comercial@bateriasplus.es", "J. Ruiz"),
            ("Estructuras Solares Andaluzas", "B18000004", "C/ Metal 5", "18014",
             "Granada", "958 300 300", "ventas@esa.es", "L. Fernández"),
            ("Cableado y Protecciones Ibérica", "A28000005", "C/ Cobre 8", "28045",
             "Madrid", "910 400 400", "pedidos@cpi.es", "P. Navarro"),
        ]
        cur.executemany(
            "INSERT INTO proveedores (nombre, nif, direccion, cp, ciudad, telefono, email, contacto) "
            "VALUES (?,?,?,?,?,?,?,?)", provs)

    if cur.execute("SELECT COUNT(*) FROM materiales").fetchone()[0] == 0:
        mats = [
            # (categoria, nombre, marca, modelo, ref, desc, ficha, precio, iva, unidad, stock,
            #  garantia, vida, potencia_w, eficiencia, params, imagen, proveedor_id)
            ("panel", "Panel monocristalino 550W", "Trina Solar", "Titan 550",
             "TSM-550", "Panel PERC monocristalino 550W, media célula",
             "", 89.90, 21, "ud", 0, 15, 30, 550, 21.2, '{"vmp":"41,5 V","imp":"13,25 A","voc":"49,8 V","isc":"14,01 A","dim":"2278x1134x35 mm","peso":"27,5 kg"}', "", 1),
            ("panel", "Panel monocristalino 450W", "JA Solar", "JAM54S31",
             "JAM-450", "Panel monocristalino bifacial 450W",
             "", 72.50, 21, "ud", 0, 12, 30, 450, 20.7, '{"vmp":"40,9 V","voc":"49,5 V","dim":"1909x1134x30 mm","peso":"22,9 kg"}', "", 1),
            ("inversor", "Inversor híbrido monofásico 6kW", "Huawei", "SUN2000-6KTL",
             "SU-6KTL", "Inversor híbrido 6 kW, 2 MPPT, monofásico 230V",
             "", 1290.00, 21, "ud", 0, 10, 12, 6000, 98.4, '{"mppts":"2","max_entrada":"8500 W","tension":"100-1000 V"}', "", 2),
            ("inversor", "Inversor de cadena trifásico 15kW", "SolarEdge", "SE15K",
             "SE-15K", "Inversor trifásico 15 kW con optimizadores",
             "", 3450.00, 21, "ud", 0, 12, 15, 15000, 98.0, '{"fases":"3","max_entrada":"22500 W"}', "", 2),
            ("bateria", "Batería LFP 10,6 kWh", "BYD", "HVM 11.0",
             "BYD-HVM11", "Batería de litio hierro-fosfato apilable 10,6 kWh",
             "", 4850.00, 21, "ud", 0, 10, 15, 0, 0, '{"capacidad":"10,6 kWh","ciclos":"6000","tension":"204,8 V"}', "", 3),
            ("bateria", "Batería LFP 5,12 kWh", "Pylontech", "US5000",
             "PYL-US5", "Batería LFP 5,12 kWh con BMS integrado",
             "", 1750.00, 21, "ud", 0, 10, 15, 0, 0, '{"capacidad":"5,12 kWh","ciclos":"6000"}', "", 3),
            ("estructura", "Estructura coplanar aluminio 60º", "Estructuras Solares Andaluzas",
             "CO-60", "ESA-CO60", "Estructura coplanar de aluminio para cubierta inclinada, incluye soportes y fijaciones",
             "", 28.00, 21, "m2", 0, 10, 30, 0, 0, '{"material":"aluminio 6005-T5","inclinacion":"coplanar"}', "", 4),
            ("estructura", "Estructura cubierta plana inclinable 20-30º", "K2 Systems",
             "K2 SingleRail", "K2-SR", "Sistema de rail único para cubierta plana, inclinable 20-30º",
             "", 32.50, 21, "m2", 0, 10, 30, 0, 0, '{"material":"aluminio","inclinacion":"20-30º"}', "", 4),
            ("cable", "Cable solar PV 1x6mm² (metro)", "Top Cable", "H1Z2Z2-K 6",
             "H1Z2Z2-6", "Cable solar unipolar H1Z2Z2-K 6mm² negro",
             "", 0.85, 21, "m", 0, 2, 25, 0, 0, '{"tipo":"H1Z2Z2-K","seccion":"6 mm²"}', "", 5),
            ("cable", "Cable AC 3G6 (metro)", "Top Cable", "RZ1-K 0,6/1kV",
             "RZ1-3G6", "Cable RZ1-K 0,6/1kV 3G6 para CA",
             "", 2.20, 21, "m", 0, 2, 25, 0, 0, '{"tipo":"RZ1-K","seccion":"3G6 mm²"}', "", 5),
            ("proteccion", "Cuadro DC con fusibles y protección 1000V", "Schneider Electric",
             "DC Caja 1/2", "SE-CDC", "Cuadro DC con fusibles, portafusibles, protección sobretensiones",
             "", 145.00, 21, "ud", 0, 5, 20, 0, 0, '{"tension":"1000 V"}', "", 5),
            ("proteccion", "Protección sobretensiones tipo 2 AC", "Schneider Electric",
             "Acti9", "SE-AC", "Descargador de sobretensiones tipo 2 para CA",
             "", 62.00, 21, "ud", 0, 5, 20, 0, 0, '{"tipo":"2"}', "", 5),
            ("monitorizacion", "Medidor inteligente + gateway", "Huawei", "DTSU666",
             "HW-DTSU", "Contador inteligente trifásico con gateway de comunicaciones",
             "", 240.00, 21, "ud", 0, 5, 10, 0, 0, '{"comunicacion":"RS485/WiFi"}', "", 2),
            ("proteccion", "Interruptor automático magnetotérmico 40A", "Schneider Electric",
             "Acti9 C40", "SE-C40", "Magnetotérmico bipolar C40 6kA",
             "", 18.50, 21, "ud", 0, 5, 20, 0, 0, '{"curva":"C","in":"40 A"}', "", 5),
        ]
        cur.executemany(
            "INSERT INTO materiales (categoria, nombre, marca, modelo, referencia, descripcion, ficha_url, "
            "precio_unitario, iva, unidad, stock, garantia_anos, vida_util_anos, potencia_w, eficiencia, params, imagen, proveedor_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", mats)

    if cur.execute("SELECT COUNT(*) FROM herramientas").fetchone()[0] == 0:
        herr = [
            ("Multímetro digital", "medicion", "Medición de tensiones y continuidad en DC/AC", 2, "operativo", "Almacén 1"),
            ("Pinza amperimétrica", "medicion", "Medida de corriente sin contacto", 1, "operativo", "Almacén 1"),
            ("Taladro percutor", "montaje", "Perforación de cubierta y estructura", 2, "operativo", "Almacén 1"),
            ("Multifunción Dremel", "montaje", "Corte de perfiles de aluminio", 1, "operativo", "Almacén 1"),
            ("Crimpadora terminales MC4", "montaje", "Crimpeo de conectores MC4", 2, "operativo", "Maletín herramienta"),
            ("Cámara termográfica", "inspeccion", "Detección de puntos calientes en módulos", 1, "operativo", "Oficina"),
            ("Comprobador de aislamiento (megóhmetro)", "medicion", "Medida de aislamiento 1000V", 1, "operativo", "Almacén 1"),
            ("Plataforma elevadora", "acceso", "Acceso a cubiertas y trabajos en altura", 1, "alquiler", "Alquiler según obra"),
        ]
        cur.executemany(
            "INSERT INTO herramientas (nombre, categoria, descripcion, cantidad, estado, ubicacion) VALUES (?,?,?,?,?,?)",
            herr)

    if cur.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 0:
        cli = [
            ("Manuel García Pérez", "12345678A", "C/ Los Olivos 15", "18008", "Granada", "Granada",
             "600 111 222", "manuel.garcia@gmail.com", "Propietario"),
            ("Comunidad Los Prados", "G18000001", "Av. de Andalucía 24", "18014", "Granada", "Granada",
             "958 400 400", "admin@losprados.es", "Presidente: Laura Jiménez"),
            ("Almacenes del Sur S.L.", "B18900002", "C/ Industrial 3", "18100", "Armilla", "Granada",
             "958 500 500", "gerencia@almacenesdelsur.es", "Gerente: Carlos Ruiz"),
        ]
        cur.executemany(
            "INSERT INTO clientes (nombre, nif, direccion, cp, ciudad, provincia, telefono, email, contacto) "
            "VALUES (?,?,?,?,?,?,?,?,?)", cli)

    conn.commit()
