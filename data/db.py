# type: ignore
# pyright: reportMissingImports=false
# pyright: reportMissingTypeStubs=false
# pylint: skip-file
# flake8: noqa
"""
================================================================================
UNIVERSIDAD POLITÉCNICA DE DURANGO
Materia: Arquitectura de Software / Servicios Web / Inteligencia Artificial
Profesor: Florentino Octavio Mejía Rosales
Alumno: Salvador Rivera Delgado (Semestre 8 - Grupo B)

MÓDULO: CAPA DE PERSISTENCIA Y BASE DE DATOS MYSQL (XAMPP)
Archivo: data/db.py
================================================================================
ARQUITECTURA DE PERSISTENCIA HÍBRIDA (5 MICROSERVICIOS + MODELO AAA):
1. Base de Datos Relacional MySQL (XAMPP):
   - Motor MySQL ejecutándose en 'localhost:3306'.
   - Base de datos relacional: 'hotel_reservaciones'.
   - Administrable visualmente desde 'http://localhost/phpmyadmin'.
   - Tablas relacionales normalizadas para los 5 microservicios:
     * 'hoteles'        -> Sedes y destinos hoteleros.
     * 'usuarios'       -> Servicio 1: Usuarios (cuentas y roles).
     * 'recursos'       -> Servicio 2: Catálogo (habitaciones y tarifas).
     * 'reservaciones'  -> Servicio 3: Reservaciones (folios y fechas).
     * 'pagos'          -> Servicio 4: Pagos (comprobantes y reembolsos).
     * 'notificaciones' -> Servicio 5: Notificaciones (bitácora de correos y SMS).
     * 'auditoria'      -> Contabilización del Modelo AAA (Accounting).

2. Caché en Memoria de Alta Velocidad (High-Speed Cache):
   - Mantiene diccionarios en RAM sincronizados con MySQL.
   - Provee tolerancia a fallos: si MySQL no está encendido, el sistema opera en memoria.
================================================================================
"""

import sys
import os
import uuid
from datetime import datetime, timedelta

# Garantizar que la raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Conector MySQL nativo para Python
import pymysql  # type: ignore
import pymysql.cursors  # type: ignore


# ==============================================================================
# SECCIÓN 1: CONFIGURACIÓN DE CONEXIÓN A MYSQL (XAMPP / PHPMYADMIN)
# ==============================================================================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "hotel_reservaciones",
    "port": 3306,
    "charset": "utf8mb4",
    "autocommit": True
}

def get_mysql_conn():
    """
    Intenta abrir una conexión activa con el servidor MySQL de XAMPP.
    Si MySQL está apagado o no responde, retorna None permitiendo operar en memoria.
    """
    try:
        return pymysql.connect(**MYSQL_CONFIG)
    except Exception:
        return None


# ==============================================================================
# SECCIÓN 2: ESTRUCTURAS EN MEMORIA (CACHE RÁPIDO SINCRONIZADO)
# ==============================================================================
HOTELES_DB = {}          # Almacena hoteles (id_hotel -> datos)
USUARIOS_DB = {}         # Servicio 1: Usuarios (id_usuario -> datos)
RECURSOS_DB = {}         # Servicio 2: Catálogo (id_recurso -> datos)
RESERVACIONES_DB = {}    # Servicio 3: Reservaciones (id_reservacion -> datos)
PAGOS_DB = {}            # Servicio 4: Pagos (id_pago -> datos)
NOTIFICACIONES_DB = []   # Servicio 5: Notificaciones (lista secuencial)
ACCOUNTING_LOGS = []     # Modelo AAA: Bitácora contable de auditoría
RESENAS_DB = {}          # Microservicio de Reseñas / Interacciones Tienda Online (id_resena -> datos)


# ==============================================================================
# SECCIÓN 3: DATOS SEMILLA POR DEFECTO (SEED DATA)
# ==============================================================================

# 1. Sedes / Hoteles
HOTELES_SEMILLA = {
    "h-1": {
        "id": "h-1",
        "nombre": "Hotel Paraíso Playa",
        "ubicacion": "Cancún, Quintana Roo",
        "descripcion": "Resort frente al mar con acceso directo a playa privada, albercas y restaurante de mariscos.",
        "foto": "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80"
    },
    "h-2": {
        "id": "h-2",
        "nombre": "Hotel Paraíso Bosque Real",
        "ubicacion": "Mazamitla, Jalisco",
        "descripcion": "Cabañas de descanso rodeadas de bosque y naturaleza, con chimenea y fogateros.",
        "foto": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80"
    },
    "h-3": {
        "id": "h-3",
        "nombre": "Hotel Paraíso Centro",
        "ubicacion": "Guadalajara, Jalisco",
        "descripcion": "Hotel moderno en el corazón de la ciudad, ideal para viajes ejecutivos y eventos.",
        "foto": "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80"
    }
}

# 2. Servicio 1: Usuarios
USUARIOS_SEMILLA = {
    "u-101": {
        "id": "u-101",
        "nombre": "Salvador Rivera (Admin)",
        "correo": "admin@hotel.com",
        "password": "123",
        "rol": "administrador",
        "creadoEn": "2026-01-15T09:00:00"
    },
    "u-102": {
        "id": "u-102",
        "nombre": "Juan Pérez (Cliente)",
        "correo": "juan@cliente.com",
        "password": "123",
        "rol": "cliente",
        "creadoEn": "2026-02-10T14:30:00"
    },
    "u-103": {
        "id": "u-103",
        "nombre": "María López (Cliente)",
        "correo": "maria@cliente.com",
        "password": "123",
        "rol": "cliente",
        "creadoEn": "2026-03-01T11:20:00"
    }
}

# 3. Servicio 2: Catálogo de Recursos
RECURSOS_SEMILLA = {
    "r-12": {
        "id": "r-12",
        "hotelId": "h-1",
        "nombre": "Suite Frente al Mar",
        "tipo": "HABITACION_LUJO",
        "capacidad": 4,
        "tarifa": 2500.0,
        "descripcion": "Cama King Size, jacuzzi privado, vista panorámica al mar y desayuno incluido.",
        "foto": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80"
    },
    "r-14": {
        "id": "r-14",
        "hotelId": "h-1",
        "nombre": "Habitación Doble Playa",
        "tipo": "HABITACION_DOBLE",
        "capacidad": 2,
        "tarifa": 1400.0,
        "descripcion": "Dos camas matrimoniales, aire acondicionado, balcón con vista parcial a la alberca.",
        "foto": "https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=800&q=80"
    },
    "r-20": {
        "id": "r-20",
        "hotelId": "h-1",
        "nombre": "Mesa Terraza Marítima",
        "tipo": "RESTAURANTE_MESA",
        "capacidad": 6,
        "tarifa": 500.0,
        "descripcion": "Mesa en terraza al aire libre con vista al atardecer frente a la playa.",
        "foto": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80"
    },
    "r-16": {
        "id": "r-16",
        "hotelId": "h-2",
        "nombre": "Cabaña Familiar Bosque",
        "tipo": "HABITACION_LUJO",
        "capacidad": 6,
        "tarifa": 3200.0,
        "descripcion": "Cabaña rústica de dos pisos con chimenea de leña, sala y vista a los pinos.",
        "foto": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80"
    },
    "r-18": {
        "id": "r-18",
        "hotelId": "h-2",
        "nombre": "Habitación Rústica Deluxe",
        "tipo": "HABITACION_DOBLE",
        "capacidad": 2,
        "tarifa": 1600.0,
        "descripcion": "Acabados en madera, cama Queen, calefacción y terraza privada.",
        "foto": "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80"
    },
    "r-25": {
        "id": "r-25",
        "hotelId": "h-3",
        "nombre": "Salón de Eventos Ejecutivo",
        "tipo": "SALON_EVENTOS",
        "capacidad": 50,
        "tarifa": 6500.0,
        "descripcion": "Espacio climatizado con proyector, audio y mobiliario para conferencias.",
        "foto": "https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=800&q=80"
    }
}

# 4. Servicio 3: Reservaciones
RESERVACIONES_SEMILLA = {
    "res-1": {
        "id": "res-1",
        "folio": "RES-2026-001",
        "usuarioId": "u-102",
        "recursoId": "r-12",
        "fechaInicio": "2026-10-18T15:00:00",
        "fechaFin": "2026-10-21T12:00:00",
        "personas": 2,
        "estado": "CONFIRMADA",
        "total": 7500.0,
        "creadoEn": "2026-10-01T10:00:00"
    },
    "res-2": {
        "id": "res-2",
        "folio": "RES-2026-002",
        "usuarioId": "u-103",
        "recursoId": "r-14",
        "fechaInicio": "2026-10-22T15:00:00",
        "fechaFin": "2026-10-24T12:00:00",
        "personas": 2,
        "estado": "PENDIENTE",
        "total": 2800.0,
        "creadoEn": "2026-10-02T16:20:00"
    }
}

# 5. Servicio 4: Pagos
PAGOS_SEMILLA = {
    "pag-1": {
        "id": "pag-1",
        "reservacionId": "res-1",
        "usuarioId": "u-102",
        "monto": 7500.0,
        "metodoPago": "TARJETA_CREDITO",
        "estado": "APROBADO",
        "comprobante": "PAG-2026-A101",
        "fecha": "2026-10-01T10:05:00"
    }
}

# 6. Servicio 5: Notificaciones
NOTIFICACIONES_SEMILLA = [
    {
        "id": "notif-1",
        "usuarioId": "u-102",
        "canal": "EMAIL",
        "destinatario": "juan@cliente.com",
        "asunto": "Confirmación de Reservación RES-2026-001",
        "mensaje": "Estimado Juan Pérez, tu reservación en Suite Frente al Mar ha sido confirmada con éxito. Pago procesado: $7,500.00 MXN.",
        "eventoOrigen": "PagoConfirmado",
        "fechaEnvio": "2026-10-01T10:06:00",
        "estado": "ENVIADO"
    },
    {
        "id": "notif-2",
        "usuarioId": "u-103",
        "canal": "SMS",
        "destinatario": "maria@cliente.com",
        "asunto": "Reservación Pendiente de Pago RES-2026-002",
        "mensaje": "Hola María López, tu reservación RES-2026-002 está registrada. Por favor realiza tu pago para confirmarla.",
        "eventoOrigen": "ReservacionCreada",
        "fechaEnvio": "2026-10-02T16:21:00",
        "estado": "ENVIADO"
    }
]

# 7. Modelo Triple A: Bitácora de Auditoría
ACCOUNTING_LOGS_SEMILLA = [
    {
        "id": "log-001",
        "timestamp": "2026-10-05T07:00:00",
        "usuarioId": "u-101",
        "usuarioNombre": "Salvador Rivera (Admin)",
        "rol": "administrador",
        "servicio": "Usuarios",
        "accion": "LOGIN_EXITOSO",
        "estado": "EXITO",
        "detalle": "Inicio de sesión con emisión de token JWT",
        "monto": 0.0
    },
    {
        "id": "log-002",
        "timestamp": "2026-10-05T07:15:00",
        "usuarioId": "u-102",
        "usuarioNombre": "Juan Pérez (Cliente)",
        "rol": "cliente",
        "servicio": "Reservaciones",
        "accion": "CREAR_RESERVACION",
        "estado": "EXITO",
        "detalle": "Generación de Folio RES-2026-001 para Suite Frente al Mar (3 noches)",
        "monto": 7500.0
    },
    {
        "id": "log-003",
        "timestamp": "2026-10-05T07:16:00",
        "usuarioId": "u-102",
        "usuarioNombre": "Juan Pérez (Cliente)",
        "rol": "cliente",
        "servicio": "Pagos",
        "accion": "PAGO_APROBADO",
        "estado": "EXITO",
        "detalle": "Cobro procesado mediante TARJETA_CREDITO. Comprobante PAG-2026-A101",
        "monto": 7500.0
    },
    {
        "id": "log-004",
        "timestamp": "2026-10-05T07:16:05",
        "usuarioId": "u-102",
        "usuarioNombre": "Juan Pérez (Cliente)",
        "rol": "cliente",
        "servicio": "Notificaciones",
        "accion": "NOTIFICACION_ENVIADA",
        "estado": "EXITO",
        "detalle": "Email enviado a juan@cliente.com por evento PagoConfirmado",
        "monto": 0.0
    }
]

# 6. Servicio Externo: Reseñas / Calificaciones (Tienda Online Alan)
RESENAS_SEMILLA = {
    "rev-1": {
        "id": "rev-1",
        "recursoId": "r-12",
        "usuarioId": "u-102",
        "usuarioNombre": "Juan Pérez",
        "reservacionId": "res-1",
        "calificacion": 5,
        "titulo": "¡Experiencia inolvidable frente al mar!",
        "comentario": "La suite tiene una vista impresionante, el jacuzzi privado es excelente y la atención de primera.",
        "fecha": "2026-10-18T16:00:00",
        "servicioExterno": "Tienda Online Alan (Interactions)",
        "reviewIdExterno": "rev-ext-101"
    },
    "rev-2": {
        "id": "rev-2",
        "recursoId": "r-16",
        "usuarioId": "u-103",
        "usuarioNombre": "María López",
        "reservacionId": "res-2",
        "calificacion": 5,
        "titulo": "Cabaña perfecta para descansar",
        "comentario": "El bosque y la chimenea hacen que la estancia sea mágica. Muy recomendado para familias.",
        "fecha": "2026-10-19T11:30:00",
        "servicioExterno": "Tienda Online Alan (Interactions)",
        "reviewIdExterno": "rev-ext-102"
    }
}


# ==============================================================================
# SECCIÓN 4: INICIALIZADOR: VERIFICACIÓN, CREACIÓN Y SINCRONIZACIÓN DE TABLAS
# ==============================================================================

def inicializar_base_de_datos():
    """
    Función de arranque del subsistema de datos para los 5 microservicios + Reseñas:
    1. Carga los datos semilla en las estructuras en memoria RAM.
    2. Conecta con el motor MySQL en XAMPP.
    3. Crea tablas si no existen.
    4. Puebla semillas si las tablas están vacías.
    5. Carga datos de MySQL hacia los diccionarios de memoria RAM.
    """
    global HOTELES_DB, USUARIOS_DB, RECURSOS_DB, RESERVACIONES_DB, PAGOS_DB, NOTIFICACIONES_DB, ACCOUNTING_LOGS, RESENAS_DB

    # Paso 1: Carga inmediata en memoria para disponibilidad garantizada
    HOTELES_DB.update(HOTELES_SEMILLA)
    USUARIOS_DB.update(USUARIOS_SEMILLA)
    RECURSOS_DB.update(RECURSOS_SEMILLA)
    RESERVACIONES_DB.update(RESERVACIONES_SEMILLA)
    PAGOS_DB.update(PAGOS_SEMILLA)
    RESENAS_DB.update(RESENAS_SEMILLA)
    NOTIFICACIONES_DB.clear()
    NOTIFICACIONES_DB.extend(NOTIFICACIONES_SEMILLA)
    ACCOUNTING_LOGS.extend(ACCOUNTING_LOGS_SEMILLA)

    # Paso 2: Intentar conexión con MySQL
    conn = get_mysql_conn()
    if not conn:
        print("[AVISO] MySQL de XAMPP no disponible. Operando en memoria (fallback seguro).")
        return

    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # ----------------------------------------------------------------------
        # CREACIÓN DE TABLAS RELACIONALES (DDL)
        # ----------------------------------------------------------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS hoteles (
            id VARCHAR(50) PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            ubicacion VARCHAR(100),
            descripcion TEXT,
            foto VARCHAR(255)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id VARCHAR(50) PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            correo VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            rol VARCHAR(20) DEFAULT 'cliente',
            creadoEn VARCHAR(50)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS recursos (
            id VARCHAR(50) PRIMARY KEY,
            hotelId VARCHAR(50),
            nombre VARCHAR(100) NOT NULL,
            tipo VARCHAR(50) NOT NULL,
            capacidad INT DEFAULT 2,
            tarifa DECIMAL(10,2) NOT NULL,
            descripcion TEXT,
            foto VARCHAR(255)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS reservaciones (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(50) UNIQUE NOT NULL,
            usuarioId VARCHAR(50) NOT NULL,
            recursoId VARCHAR(50) NOT NULL,
            fechaInicio VARCHAR(50) NOT NULL,
            fechaFin VARCHAR(50) NOT NULL,
            personas INT DEFAULT 1,
            estado VARCHAR(20) DEFAULT 'PENDIENTE',
            total DECIMAL(10,2) NOT NULL,
            creadoEn VARCHAR(50)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id VARCHAR(50) PRIMARY KEY,
            reservacionId VARCHAR(50) NOT NULL,
            usuarioId VARCHAR(50) NOT NULL,
            monto DECIMAL(10,2) NOT NULL,
            metodoPago VARCHAR(50) NOT NULL,
            estado VARCHAR(20) DEFAULT 'APROBADO',
            comprobante VARCHAR(50) UNIQUE NOT NULL,
            fecha VARCHAR(50) NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id VARCHAR(50) PRIMARY KEY,
            usuarioId VARCHAR(50) NOT NULL,
            canal VARCHAR(20) DEFAULT 'EMAIL',
            destinatario VARCHAR(100) NOT NULL,
            asunto VARCHAR(150) NOT NULL,
            mensaje TEXT NOT NULL,
            eventoOrigen VARCHAR(50) NOT NULL,
            fechaEnvio VARCHAR(50) NOT NULL,
            estado VARCHAR(20) DEFAULT 'ENVIADO'
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id VARCHAR(50) PRIMARY KEY,
            timestamp VARCHAR(50) NOT NULL,
            usuarioId VARCHAR(50),
            usuarioNombre VARCHAR(100),
            rol VARCHAR(50),
            servicio VARCHAR(50),
            accion VARCHAR(100),
            estado VARCHAR(20),
            monto DECIMAL(10,2) DEFAULT 0.0,
            detalle TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS resenas (
            id VARCHAR(50) PRIMARY KEY,
            recursoId VARCHAR(50) NOT NULL,
            usuarioId VARCHAR(50) NOT NULL,
            usuarioNombre VARCHAR(100),
            reservacionId VARCHAR(50),
            calificacion INT DEFAULT 5,
            titulo VARCHAR(150),
            comentario TEXT,
            fecha VARCHAR(50),
            servicioExterno VARCHAR(100),
            reviewIdExterno VARCHAR(100)
        );
        """)

        # ----------------------------------------------------------------------
        # POBLACIÓN DE DATOS SEMILLA (DML)
        # ----------------------------------------------------------------------
        cur.execute("SELECT COUNT(*) AS total FROM hoteles")
        if cur.fetchone()["total"] == 0:
            for h in HOTELES_SEMILLA.values():
                cur.execute(
                    "INSERT INTO hoteles (id, nombre, ubicacion, descripcion, foto) VALUES (%s, %s, %s, %s, %s)",
                    (h["id"], h["nombre"], h["ubicacion"], h["descripcion"], h["foto"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM usuarios")
        if cur.fetchone()["total"] == 0:
            for u in USUARIOS_SEMILLA.values():
                cur.execute(
                    "INSERT INTO usuarios (id, nombre, correo, password, rol, creadoEn) VALUES (%s, %s, %s, %s, %s, %s)",
                    (u["id"], u["nombre"], u["correo"], u["password"], u["rol"], u["creadoEn"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM recursos")
        if cur.fetchone()["total"] == 0:
            for r in RECURSOS_SEMILLA.values():
                cur.execute(
                    "INSERT INTO recursos (id, hotelId, nombre, tipo, capacidad, tarifa, descripcion, foto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (r["id"], r.get("hotelId", "h-1"), r["nombre"], r["tipo"], r["capacidad"], r["tarifa"], r["descripcion"], r["foto"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM reservaciones")
        if cur.fetchone()["total"] == 0:
            for res in RESERVACIONES_SEMILLA.values():
                cur.execute(
                    "INSERT INTO reservaciones (id, folio, usuarioId, recursoId, fechaInicio, fechaFin, personas, estado, total, creadoEn) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (res["id"], res["folio"], res["usuarioId"], res["recursoId"], res["fechaInicio"], res["fechaFin"], res["personas"], res["estado"], res["total"], res["creadoEn"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM pagos")
        if cur.fetchone()["total"] == 0:
            for p in PAGOS_SEMILLA.values():
                cur.execute(
                    "INSERT INTO pagos (id, reservacionId, usuarioId, monto, metodoPago, estado, comprobante, fecha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (p["id"], p["reservacionId"], p["usuarioId"], p["monto"], p["metodoPago"], p["estado"], p["comprobante"], p["fecha"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM notificaciones")
        if cur.fetchone()["total"] == 0:
            for n in NOTIFICACIONES_SEMILLA:
                cur.execute(
                    "INSERT INTO notificaciones (id, usuarioId, canal, destinatario, asunto, mensaje, eventoOrigen, fechaEnvio, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (n["id"], n["usuarioId"], n["canal"], n["destinatario"], n["asunto"], n["mensaje"], n["eventoOrigen"], n["fechaEnvio"], n["estado"])
                )

        cur.execute("SELECT COUNT(*) AS total FROM auditoria")
        if cur.fetchone()["total"] == 0:
            for ev in ACCOUNTING_LOGS_SEMILLA:
                cur.execute(
                    "INSERT INTO auditoria (id, timestamp, usuarioId, usuarioNombre, rol, servicio, accion, estado, monto, detalle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (ev["id"], ev["timestamp"], ev["usuarioId"], ev["usuarioNombre"], ev["rol"], ev["servicio"], ev["accion"], ev["estado"], ev["monto"], ev["detalle"])
                )

        # ----------------------------------------------------------------------
        # LECTURA Y SINCRONIZACIÓN CON LA MEMORIA RAM
        # ----------------------------------------------------------------------
        cur.execute("SELECT * FROM hoteles")
        HOTELES_DB.clear()
        for row in cur.fetchall():
            HOTELES_DB[row["id"]] = row

        cur.execute("SELECT * FROM usuarios")
        USUARIOS_DB.clear()
        for row in cur.fetchall():
            USUARIOS_DB[row["id"]] = row

        cur.execute("SELECT * FROM recursos")
        RECURSOS_DB.clear()
        for row in cur.fetchall():
            row["tarifa"] = float(row["tarifa"])
            RECURSOS_DB[row["id"]] = row

        cur.execute("SELECT * FROM reservaciones")
        RESERVACIONES_DB.clear()
        for row in cur.fetchall():
            row["total"] = float(row["total"])
            RESERVACIONES_DB[row["id"]] = row

        cur.execute("SELECT * FROM pagos")
        PAGOS_DB.clear()
        for row in cur.fetchall():
            row["monto"] = float(row["monto"])
            PAGOS_DB[row["id"]] = row

        cur.execute("SELECT * FROM notificaciones ORDER BY fechaEnvio DESC")
        NOTIFICACIONES_DB.clear()
        for row in cur.fetchall():
            NOTIFICACIONES_DB.append(row)

        cur.execute("SELECT * FROM auditoria ORDER BY timestamp ASC")
        ACCOUNTING_LOGS.clear()
        for row in cur.fetchall():
            row["monto"] = float(row["monto"])
            ACCOUNTING_LOGS.append(row)

        # Sincronización de Reseñas (Interacciones con Tienda Online)
        cur.execute("SELECT * FROM resenas ORDER BY fecha DESC")
        resenas_filas = cur.fetchall()
        if resenas_filas:
            RESENAS_DB.clear()
            for row in resenas_filas:
                row["calificacion"] = int(row["calificacion"])
                RESENAS_DB[row["id"]] = row
        else:
            for r in RESENAS_SEMILLA.values():
                cur.execute(
                    """INSERT INTO resenas (id, recursoId, usuarioId, usuarioNombre, reservacionId, calificacion, titulo, comentario, fecha, servicioExterno, reviewIdExterno)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (r["id"], r["recursoId"], r["usuarioId"], r.get("usuarioNombre", ""), r.get("reservacionId", ""), r["calificacion"], r["titulo"], r["comentario"], r["fecha"], r.get("servicioExterno", ""), r.get("reviewIdExterno", ""))
                )
            conn.commit()

        print("[OK] Sincronizado exitosamente con MySQL (XAMPP phpMyAdmin) -> Base de datos: hotel_reservaciones")
        conn.close()

    except Exception as e:
        print(f"[ERROR al sincronizar con MySQL]: {e}. Continuando con datos en memoria.")


# ==============================================================================
# SECCIÓN 5: OPERACIONES DE PERSISTENCIA DIRECTA (CRUD MYSQL)
# ==============================================================================

def guardar_usuario_db(u: dict):
    USUARIOS_DB[u["id"]] = u
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO usuarios (id, nombre, correo, password, rol, creadoEn) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE nombre=%s, password=%s, rol=%s",
                    (u["id"], u["nombre"], u["correo"], u["password"], u["rol"], u.get("creadoEn", ""), u["nombre"], u["password"], u["rol"])
                )
            conn.commit()
            conn.close()
            print(f"[MySQL OK] Usuario '{u.get('correo')}' guardado exitosamente en tabla 'usuarios' (BD: 'hotel_reservaciones').")
        except Exception as e:
            print(f"[MySQL] Error al guardar usuario: {e}")
    else:
        print(f"[MySQL ALERTA] No se pudo conectar a MySQL (XAMPP). El usuario '{u.get('correo')}' solo se guardó en memoria.")


def obtener_usuario_mysql(correo_o_id: str):
    """
    Consulta directamente a MySQL para encontrar un usuario por correo o ID.
    Garantiza que cualquier usuario creado manualmente en phpMyAdmin sea accesible al instante.
    """
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM usuarios WHERE LOWER(correo) = %s OR id = %s LIMIT 1",
                    (correo_o_id.strip().lower(), correo_o_id.strip())
                )
                row = cur.fetchone()
                if row:
                    USUARIOS_DB[row["id"]] = row
                    conn.close()
                    return row
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al buscar usuario: {e}")

    # Fallback a memoria
    c_limpio = correo_o_id.strip().lower()
    return next((u for u in USUARIOS_DB.values() if u["correo"].lower() == c_limpio or u["id"] == correo_o_id), None)


def guardar_recurso_db(r: dict):
    RECURSOS_DB[r["id"]] = r
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO recursos (id, hotelId, nombre, tipo, capacidad, tarifa, descripcion, foto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE hotelId=%s, nombre=%s, tipo=%s, capacidad=%s, tarifa=%s, descripcion=%s, foto=%s",
                    (r["id"], r.get("hotelId", "h-1"), r["nombre"], r["tipo"], r["capacidad"], r["tarifa"], r.get("descripcion", ""), r.get("foto", ""), r.get("hotelId", "h-1"), r["nombre"], r["tipo"], r["capacidad"], r["tarifa"], r.get("descripcion", ""), r.get("foto", ""))
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al guardar recurso: {e}")


def eliminar_recurso_db(recurso_id: str):
    if recurso_id in RECURSOS_DB:
        del RECURSOS_DB[recurso_id]
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM recursos WHERE id=%s", (recurso_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al eliminar recurso: {e}")


def guardar_reservacion_db(res: dict):
    RESERVACIONES_DB[res["id"]] = res
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO reservaciones (id, folio, usuarioId, recursoId, fechaInicio, fechaFin, personas, estado, total, creadoEn) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (res["id"], res["folio"], res["usuarioId"], res["recursoId"], res["fechaInicio"], res["fechaFin"], res["personas"], res["estado"], res["total"], res.get("creadoEn", ""))
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al guardar reservacion: {e}")


def actualizar_estado_reservacion_db(res_id: str, nuevo_estado: str):
    if res_id in RESERVACIONES_DB:
        RESERVACIONES_DB[res_id]["estado"] = nuevo_estado
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reservaciones SET estado=%s WHERE id=%s",
                    (nuevo_estado, res_id)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al actualizar reservacion: {e}")


def eliminar_reservacion_db(res_id: str):
    """
    Elimina permanentemente una reservación tanto de la memoria como de MySQL.
    También remueve pagos asociados para mantener la integridad referencial.
    """
    if res_id in RESERVACIONES_DB:
        del RESERVACIONES_DB[res_id]

    # Eliminar pagos asociados en memoria
    pagos_a_borrar = [p_id for p_id, p in list(PAGOS_DB.items()) if p.get("reservacionId") == res_id]
    for p_id in pagos_a_borrar:
        del PAGOS_DB[p_id]

    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM pagos WHERE reservacionId=%s", (res_id,))
                cur.execute("DELETE FROM reservaciones WHERE id=%s", (res_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al eliminar reservacion: {e}")


def guardar_pago_db(p: dict):
    PAGOS_DB[p["id"]] = p
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO pagos (id, reservacionId, usuarioId, monto, metodoPago, estado, comprobante, fecha, transaction_ref, order_id, receipt_number, refund_token) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        p["id"],
                        p["reservacionId"],
                        p["usuarioId"],
                        p["monto"],
                        p["metodoPago"],
                        p["estado"],
                        p["comprobante"],
                        p["fecha"],
                        p.get("transaction_ref"),
                        p.get("order_id"),
                        p.get("receipt_number"),
                        p.get("refund_token")
                    )
                )
            conn.commit()
            conn.close()
        except Exception:
            # Fallback en caso de que alguna columna no exista en esquemas antiguos
            try:
                conn_fb = get_mysql_conn()
                if conn_fb:
                    with conn_fb.cursor() as cur_fb:
                        cur_fb.execute(
                            "INSERT INTO pagos (id, reservacionId, usuarioId, monto, metodoPago, estado, comprobante, fecha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (p["id"], p["reservacionId"], p["usuarioId"], p["monto"], p["metodoPago"], p["estado"], p["comprobante"], p["fecha"])
                        )
                    conn_fb.commit()
                    conn_fb.close()
            except Exception as e2:
                print(f"[MySQL] Error al guardar pago: {e2}")


def actualizar_estado_pago_db(pago_id: str, nuevo_estado: str, refund_token: str = None):
    if pago_id in PAGOS_DB:
        PAGOS_DB[pago_id]["estado"] = nuevo_estado
        if refund_token:
            PAGOS_DB[pago_id]["refund_token"] = refund_token
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                if refund_token:
                    cur.execute(
                        "UPDATE pagos SET estado=%s, refund_token=%s WHERE id=%s",
                        (nuevo_estado, refund_token, pago_id)
                    )
                else:
                    cur.execute(
                        "UPDATE pagos SET estado=%s WHERE id=%s",
                        (nuevo_estado, pago_id)
                    )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al actualizar estado del pago: {e}")


def guardar_notificacion_db(n: dict):
    NOTIFICACIONES_DB.insert(0, n)
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO notificaciones (id, usuarioId, canal, destinatario, asunto, mensaje, eventoOrigen, fechaEnvio, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (n["id"], n["usuarioId"], n["canal"], n["destinatario"], n["asunto"], n["mensaje"], n["eventoOrigen"], n["fechaEnvio"], n["estado"])
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al guardar notificacion: {e}")


def eliminar_notificacion_db(notif_id: str, usuario_id: str = None) -> bool:
    """
    Elimina una notificación específica tanto de la memoria como de MySQL.
    Si se pasa usuario_id, garantiza que pertenezca estrictamente a ese usuario.
    """
    global NOTIFICACIONES_DB
    inicial = len(NOTIFICACIONES_DB)
    if usuario_id:
        NOTIFICACIONES_DB = [n for n in NOTIFICACIONES_DB if not (n["id"] == notif_id and n.get("usuarioId") == usuario_id)]
    else:
        NOTIFICACIONES_DB = [n for n in NOTIFICACIONES_DB if n["id"] != notif_id]

    eliminado = len(NOTIFICACIONES_DB) < inicial

    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                if usuario_id:
                    cur.execute("DELETE FROM notificaciones WHERE id=%s AND usuarioId=%s", (notif_id, usuario_id))
                else:
                    cur.execute("DELETE FROM notificaciones WHERE id=%s", (notif_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al eliminar notificacion: {e}")

    return eliminado


def limpiar_notificaciones_db(usuario_id: str) -> int:
    """
    Limpia ÚNICAMENTE las notificaciones del usuario especificado.
    NUNCA borra notificaciones de otros usuarios o clientes.
    """
    global NOTIFICACIONES_DB
    inicial = len(NOTIFICACIONES_DB)
    NOTIFICACIONES_DB = [n for n in NOTIFICACIONES_DB if n.get("usuarioId") != usuario_id]
    eliminadas = inicial - len(NOTIFICACIONES_DB)

    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM notificaciones WHERE usuarioId=%s", (usuario_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al limpiar notificaciones: {e}")

    return eliminadas


def limpiar_todas_notificaciones_db() -> int:
    """
    Elimina todas las notificaciones registradas (Historial global para administradores).
    Sincroniza tanto en memoria RAM como en la base de datos MySQL (XAMPP).
    """
    global NOTIFICACIONES_DB
    inicial = len(NOTIFICACIONES_DB)
    NOTIFICACIONES_DB.clear()

    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM notificaciones")
            conn.commit()
            conn.close()
            print(f"[MySQL OK] Se vaciaron todas las notificaciones ({inicial} eliminadas).")
        except Exception as e:
            print(f"[MySQL] Error al vaciar todas las notificaciones: {e}")

    return inicial


def guardar_evento_auditoria_db(ev: dict):
    ACCOUNTING_LOGS.append(ev)
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auditoria (id, timestamp, usuarioId, usuarioNombre, rol, servicio, accion, estado, monto, detalle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (ev["id"], ev["timestamp"], ev.get("usuarioId", ""), ev.get("usuarioNombre", ""), ev.get("rol", ""), ev.get("servicio", ""), ev.get("accion", ""), ev.get("estado", ""), ev.get("monto", 0.0), ev.get("detalle", ""))
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al guardar auditoria: {e}")


def guardar_resena_db(r: dict):
    """Guarda una reseña tanto en memoria RAM como en la tabla resenas de MySQL."""
    RESENAS_DB[r["id"]] = r
    conn = get_mysql_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO resenas (id, recursoId, usuarioId, usuarioNombre, reservacionId, calificacion, titulo, comentario, fecha, servicioExterno, reviewIdExterno) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        r["id"],
                        r["recursoId"],
                        r["usuarioId"],
                        r.get("usuarioNombre", "Huésped"),
                        r.get("reservacionId", ""),
                        int(r["calificacion"]),
                        r.get("titulo", ""),
                        r.get("comentario", ""),
                        r["fecha"],
                        r.get("servicioExterno", "Tienda Online Alan"),
                        r.get("reviewIdExterno", "")
                    )
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MySQL] Error al guardar reseña: {e}")


def obtener_resenas_db(recurso_id: str = None) -> list:
    """Retorna las reseñas filtradas por habitación/recurso o todas si no se especifica."""
    if recurso_id:
        return [r for r in RESENAS_DB.values() if r.get("recursoId") == recurso_id]
    return list(RESENAS_DB.values())


# Inicialización al importar
inicializar_base_de_datos()
