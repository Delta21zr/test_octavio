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

MÓDULO: CONTABILIZACIÓN Y AUDITORÍA (ACCOUNTING - MODELO AAA)
Archivo: accounting.py
================================================================================
DESCRIPCIÓN GENERAL:
Este módulo implementa el tercer pilar del Modelo de Seguridad AAA:
3. CONTABILIZACIÓN / RENDICIÓN DE CUENTAS (Accounting) para los 5 microservicios:
- Servicio 1: Usuarios (Login, Registro, Sesiones)
- Servicio 2: Catálogo (Altas, Bajas y Modificación de recursos y tarifas)
- Servicio 3: Reservaciones (Creación, Modificación, Cancelación)
- Servicio 4: Pagos (Cobros, Comprobantes, Reembolsos)
- Servicio 5: Notificaciones (Despacho de correos y SMS ante eventos del Bus)

Responsabilidades:
- Registro cronológico e inmutable de eventos operacionales y de seguridad.
- Trazabilidad completa de acciones (quién hizo qué, a qué hora y con qué resultado).
- Persistencia de los eventos en la tabla 'auditoria' de MySQL en XAMPP.
- Cálculo de métricas e indicadores de negocio en tiempo real.
================================================================================
"""

import sys
import os
import uuid
from datetime import datetime
from typing import List, Optional

# Garantizar que la raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strawberry  # type: ignore
from data.db import (  # type: ignore
    ACCOUNTING_LOGS,
    RESERVACIONES_DB,
    USUARIOS_DB,
    PAGOS_DB,
    NOTIFICACIONES_DB
)

# TIPOS GRAPHQL PARA CONTABILIZACIÓN Y AUDITORÍA 

@strawberry.type
class EventoAuditoria:
    """
    Representa un registro de auditoría individual del modelo AAA.
    """
    id: strawberry.ID         # ID único del evento (ej: 'log-1a2b3c4d')
    timestamp: str           # Fecha y hora exacta de la acción (ISO)
    usuario_id: str          # ID del usuario que ejecutó la acción
    usuario_nombre: str      # Nombre legible del usuario
    rol: str                 # Rol con el que actuó (administrador / cliente / sistema)
    servicio: str            # Servicio invocado ('Usuarios', 'Catálogo', 'Reservaciones', 'Pagos', 'Notificaciones')
    accion: str              # Acción realizada (LOGIN_EXITOSO, CREAR_RECURSO, PAGO_APROBADO, etc.)
    estado: str              # Resultado de la operación: 'EXITO', 'FALLIDO', 'DENEGADO'
    detalle: str             # Descripción explicativa del evento
    monto: float             # Monto económico asociado (si aplica)


@strawberry.type
class MetricasSaaS:
    """
    Métricas cuantitativas del sistema generadas a partir de la bitácora contable.
    """
    total_transacciones: int          # Cantidad total de operaciones auditadas
    total_reservado: float            # Suma acumulada de ingresos reservados (MXN)
    total_usuarios: int               # Total de usuarios registrados
    total_reservaciones_activas: int  # Cantidad de reservaciones vigentes
    intentos_bloqueados: int          # Intentos de acceso denegados por seguridad AAA
    total_pagos_aprobados: int        # Pagos confirmados con pasarela
    total_monto_cobrado: float        # Monto efectivamente recaudado en pagos
    total_notificaciones_enviadas: int # Avisos emitidos por el bus de mensajes


def registrar_evento(
    usuario_id: str,
    usuario_nombre: str,
    rol: str,
    servicio: str,
    accion: str,
    estado: str,
    detalle: str,
    monto: float = 0.0
) -> EventoAuditoria:
    """
    3. CONTABILIZACIÓN (Triple A - Accounting):
    Registra de forma inmutable cada operación de los servicios web para auditoría,
    trazabilidad y rendición de cuentas.
    
    Inserta el evento tanto en la memoria RAM como en la tabla 'auditoria' de MySQL en XAMPP.
    """
    log_id = f"log-{uuid.uuid4().hex[:8]}"
    fecha_actual = datetime.now().isoformat()
    
    nuevo_log = {
        "id": log_id,
        "timestamp": fecha_actual,
        "usuarioId": usuario_id,
        "usuarioNombre": usuario_nombre,
        "rol": rol,
        "servicio": servicio,
        "accion": accion,
        "estado": estado,
        "detalle": detalle,
        "monto": float(monto)
    }
    
    # Insertar al inicio de la lista en memoria (orden descendente)
    ACCOUNTING_LOGS.insert(0, nuevo_log)
    
    # Persistir en la tabla 'auditoria' de MySQL en XAMPP
    try:
        from data.db import guardar_evento_auditoria_db  # type: ignore
        guardar_evento_auditoria_db(nuevo_log)
    except Exception:
        pass
    
    # Salida por consola para seguimiento de desarrollo
    print(f"[CONTABILIZACION AAA] {fecha_actual} | {servicio} | {accion} | {estado} | Usuario: {usuario_id} ({rol}) | {detalle}")
    
    return EventoAuditoria(
        id=strawberry.ID(log_id),
        timestamp=fecha_actual,
        usuario_id=usuario_id,
        usuario_nombre=usuario_nombre,
        rol=rol,
        servicio=servicio,
        accion=accion,
        estado=estado,
        detalle=detalle,
        monto=float(monto)
    )


def obtener_metricas_saas() -> MetricasSaaS:
    """
    Calcula dinámicamente las métricas de rendimiento y seguridad del sistema
    a partir de las estructuras de datos y la bitácora contable.
    """
    total_trans = len(ACCOUNTING_LOGS)
    
    # Sumar montos de reservaciones activas
    total_monto = sum(
        float(r.get("total", 0.0))
        for r in RESERVACIONES_DB.values()
        if r.get("estado") != "CANCELADA"
    )
    
    # Contar intentos bloqueados por seguridad AAA
    bloqueados = sum(
        1 for ev in ACCOUNTING_LOGS
        if ev.get("estado") in ("DENEGADO", "FALLIDO")
    )
    
    # Reservaciones activas
    activas = sum(
        1 for r in RESERVACIONES_DB.values()
        if r.get("estado") in ("CONFIRMADA", "PENDIENTE")
    )

    # Métricas de pagos
    pagos_aprobados = [p for p in PAGOS_DB.values() if p.get("estado") == "APROBADO"]
    total_pagos_count = len(pagos_aprobados)
    total_cobrado = sum(float(p.get("monto", 0.0)) for p in pagos_aprobados)

    # Notificaciones enviadas
    total_notifs = len(NOTIFICACIONES_DB)
    
    return MetricasSaaS(
        total_transacciones=total_trans,
        total_reservado=round(total_monto, 2),
        total_usuarios=len(USUARIOS_DB),
        total_reservaciones_activas=activas,
        intentos_bloqueados=bloqueados,
        total_pagos_aprobados=total_pagos_count,
        total_monto_cobrado=round(total_cobrado, 2),
        total_notificaciones_enviadas=total_notifs
    )
