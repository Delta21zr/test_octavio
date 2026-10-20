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

MÓDULO: ESQUEMA PRINCIPAL DE GRAPHQL (UNIFICACIÓN DE LOS 5 MICROSERVICIOS)
Archivo: schema.py
================================================================================
DESCRIPCIÓN GENERAL:
Actúa como el API Gateway GraphQL (Punto único de entrada según página 6 y 7 del
documento de arquitectura de Octavio). Unifica:

1. QUERIES (Consultas unificadas de los 5 microservicios):
   - 'UsuariosQueries' (Servicio 1: miPerfil, usuarios).
   - 'CatalogoQueries' (Servicio 2: hoteles, recursos(filtro), recurso(id)).
   - 'ReservacionesQueries' (Servicio 3: disponibilidad, misReservaciones, todasReservaciones, reservacion(id)).
   - 'PagosQueries' (Servicio 4: pago(reservacionId), misPagos, todosPagos).
   - 'NotificacionesQueries' (Servicio 5: historialNotificaciones, misNotificaciones).
   - 'reporte_contabilizacion' (Bitácora inmutable del modelo AAA).
   - 'metricas_saas' (Indicadores globales de transacciones, recaudación y seguridad).

2. MUTATIONS (Mutaciones unificadas de modificación de estado):
   - 'UsuariosMutations' (iniciarSesion, registrarUsuario).
   - 'CatalogoMutations' (crearRecurso, actualizarRecurso, eliminarRecurso).
   - 'ReservacionesMutations' (crearReservacion, modificarReservacion, cancelarReservacion).
   - 'PagosMutations' (pagarReservacion, reembolsarPago).
   - (Notificaciones no tiene mutaciones públicas: reacciona a eventos del bus).
================================================================================
"""

import sys
import os
from typing import List

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

import strawberry  # type: ignore
from strawberry.types import Info  # type: ignore

# Importación de los 5 Microservicios + Servicio de Reseñas (SOA)
from services.usuarios import UsuariosQueries, UsuariosMutations  # type: ignore
from services.catalogo import CatalogoQueries, CatalogoMutations  # type: ignore
from services.reservaciones import ReservacionesQueries, ReservacionesMutations  # type: ignore
from services.pagos import PagosQueries, PagosMutations  # type: ignore
from services.notificaciones import NotificacionesQueries, NotificacionesMutations  # type: ignore
from services.resenas import ResenasQueries, ResenasMutations  # type: ignore

from accounting import EventoAuditoria, MetricasSaaS, obtener_metricas_saas  # type: ignore
from data.db import ACCOUNTING_LOGS  # type: ignore
from security import requerir_autorizacion  # type: ignore


# ==============================================================================
# RAÍZ DE CONSULTAS (ROOT QUERY) - GATEWAY GRAPHQL
# ==============================================================================
@strawberry.type
class Query(
    UsuariosQueries,
    CatalogoQueries,
    ReservacionesQueries,
    PagosQueries,
    NotificacionesQueries,
    ResenasQueries
):
    """
    Gateway de lectura: hereda y agrupa todas las queries de los 5 microservicios
    más el módulo de Contabilización y Métricas SaaS del Modelo Triple A.
    """

    @strawberry.field
    def reporte_contabilizacion(self, info: Info) -> List[EventoAuditoria]:
        """
        CONSULTA: reporteContabilizacion (MODELO AAA - ACCOUNTING)
        Exclusivo para rol 'administrador'. Devuelve la bitácora cronológica
        de eventos de todos los microservicios persistida en MySQL.
        """
        requerir_autorizacion(info, ["administrador"])

        return [
            EventoAuditoria(
                id=strawberry.ID(log["id"]),
                timestamp=log["timestamp"],
                usuario_id=log.get("usuarioId", ""),
                usuario_nombre=log.get("usuarioNombre", ""),
                rol=log.get("rol", ""),
                servicio=log.get("servicio", ""),
                accion=log.get("accion", ""),
                estado=log.get("estado", ""),
                detalle=log.get("detalle", ""),
                monto=float(log.get("monto", 0.0))
            )
            for log in ACCOUNTING_LOGS
        ]

    @strawberry.field
    def metricas_saas(self, info: Info) -> MetricasSaaS:
        """
        CONSULTA: metricasSaas (INDICADORES DE RENDIMIENTO Y SEGURIDAD)
        Exclusivo para rol 'administrador'.
        """
        requerir_autorizacion(info, ["administrador"])
        return obtener_metricas_saas()


# ==============================================================================
# RAÍZ DE MUTACIONES (ROOT MUTATION) - GATEWAY GRAPHQL
# ==============================================================================
@strawberry.type
class Mutation(
    UsuariosMutations,
    CatalogoMutations,
    ReservacionesMutations,
    PagosMutations,
    NotificacionesMutations,
    ResenasMutations
):
    """
    Gateway de mutaciones: unifica todas las operaciones de modificación
    de Usuarios, Catálogo, Reservaciones, Pagos, Notificaciones y Reseñas.
    """
    pass


# ==============================================================================
# OBJETO SCHEMA FINAL EXPORTADO PARA FASTAPI
# ==============================================================================
schema = strawberry.Schema(query=Query, mutation=Mutation)