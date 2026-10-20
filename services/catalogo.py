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

MÓDULO: SERVICIO DE CATÁLOGO (SERVICIO 2 SEGÚN DOCUMENTO DE ARQUITECTURA)
Archivo: services/catalogo.py
================================================================================
DESCRIPCIÓN GENERAL:
Este microservicio gestiona el inventario de recursos reservables (habitaciones de
lujo, dobles, cabañas, salones de eventos y mesas de restaurante) y sedes hoteleras:

1. REQUERIMIENTOS SEGÚN EL DOCUMENTO DE OCTAVIO (Páginas 3 y 4):
   - Cliente (Consulta):
     * Poder consultar la disponibilidad y catálogo buscando por tipo, capacidad y precio.
   - Administración (Staff / Gerentes):
     * Administrar el inventario, subir fotos y definir las tarifas vigentes.
   - Entradas: Datos del recurso, filtros de búsqueda (tipo, capacidad, precio).
   - Salidas: Lista o detalle de recursos, tarifa vigente.

2. APLICACIÓN DEL MODELO TRIPLE A (AAA):
   - Autenticación: Consultas públicas para huéspedes; Mutaciones protegidas por JWT.
   - Autorización (RBAC):
     * Solo usuarios con rol 'administrador' pueden crear, modificar o eliminar recursos.
     * Si un 'cliente' intenta mutar el catálogo, se bloquea con HTTP 403 Forbidden.
   - Contabilización (Accounting):
     * Cada creación, actualización o eliminación se audita de inmediato en MySQL.
================================================================================
"""

import sys
import os
import uuid
from datetime import datetime
from typing import Optional, List

# Garantizar que la raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strawberry  # type: ignore
from strawberry.types import Info  # type: ignore

from data.db import (  # type: ignore
    RECURSOS_DB,
    HOTELES_DB,
    RESERVACIONES_DB,
    PAGOS_DB,
    guardar_recurso_db,
    eliminar_recurso_db
)
from security import requerir_autenticacion, requerir_autorizacion  # type: ignore
from accounting import registrar_evento  # type: ignore
from event_bus import (  # type: ignore
    event_bus,
    EVENTO_RECURSO_CREADO,
    EVENTO_RECURSO_ACTUALIZADO,
    EVENTO_RECURSO_ELIMINADO
)


# ==============================================================================
# TIPOS GRAPHQL PARA CATÁLOGO Y ESTADÍSTICAS POR HOTEL / SUCURSAL
# ==============================================================================

@strawberry.type
class Hotel:
    """
    Representa una sede o sucursal de la cadena hotelera 'Hotel Paraíso'.
    """
    id: strawberry.ID
    nombre: str
    ubicacion: str
    descripcion: str
    foto: str
    capacidad_total: Optional[int] = 0
    total_habitaciones: Optional[int] = 0
    disponibles_hoy: Optional[int] = 0
    ocupadas_hoy: Optional[int] = 0
    tasa_ocupacion: Optional[float] = 0.0


@strawberry.type
class EstadisticasHotel:
    """
    Estadísticas operacionales y de capacidad exclusivas de una sucursal hotelera.
    """
    hotel_id: strawberry.ID
    nombre: str
    ubicacion: str
    descripcion: str
    foto: str
    capacidad_total_personas: int
    total_habitaciones: int
    habitaciones_disponibles_hoy: int
    habitaciones_ocupadas: int
    habitaciones_pendientes: int
    tasa_ocupacion: float
    total_ingresos: float


@strawberry.type
class RecursoDisponibilidadHotel:
    """
    Reporte de disponibilidad de una habitación o espacio en un rango de fechas.
    """
    recurso: 'Recurso'
    disponible: bool
    motivo: str
    reserva_folio: Optional[str] = None
    reserva_estado: Optional[str] = None


@strawberry.type
class Recurso:
    """
    Representa un recurso reservable (habitación, cabaña, mesa o salón).
    """
    id: strawberry.ID
    nombre: str
    tipo: str
    capacidad: int
    tarifa: float
    descripcion: str
    foto: str
    hotel_id: Optional[str] = "h-1"


@strawberry.input
class FiltroRecursosInput:
    """
    Filtros de búsqueda especificados en la página 4 y 7 del documento.
    """
    hotel_id: Optional[strawberry.ID] = None
    tipo: Optional[str] = None
    max_tarifa: Optional[float] = None
    min_capacidad: Optional[int] = None


@strawberry.input
class CrearRecursoInput:
    """
    Entrada para dar de alta un recurso en el catálogo (solo administradores).
    """
    nombre: str
    tipo: str
    capacidad: int
    tarifa: float
    descripcion: str
    foto: str
    hotel_id: Optional[str] = "h-1"


@strawberry.input
class ActualizarRecursoInput:
    """
    Entrada para modificar tarifas, fotos o características de un recurso.
    """
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    capacidad: Optional[int] = None
    tarifa: Optional[float] = None
    descripcion: Optional[str] = None
    foto: Optional[str] = None
    hotel_id: Optional[str] = None


# ==============================================================================
# FUNCIONES AUXILIARES DE CÁLCULO DE CAPACIDAD Y ESTADÍSTICAS POR SUCURSAL
# ==============================================================================

def calcular_metricas_sucursal(hotel_id: str) -> dict:
    """
    Calcula en tiempo real la capacidad de personas, total de habitaciones,
    habitaciones ocupadas vs disponibles y facturación para una sucursal específica.
    """
    try:
        from services.reservaciones import liberar_reservaciones_expiradas  # type: ignore
        liberar_reservaciones_expiradas()
    except Exception:
        pass

    hoy = datetime.now().date()
    recursos_hotel = [r for r in RECURSOS_DB.values() if r.get("hotelId") == hotel_id]
    total_hab = len(recursos_hotel)
    cap_personas = sum(int(r.get("capacidad", 1)) for r in recursos_hotel)

    ocupadas_set = set()
    pendientes_set = set()
    recursos_ids = {r["id"] for r in recursos_hotel}

    for res in RESERVACIONES_DB.values():
        if res.get("recursoId") in recursos_ids:
            estado = res.get("estado")
            if estado in ("CONFIRMADA", "PENDIENTE"):
                try:
                    f_ini = datetime.fromisoformat(res["fechaInicio"].replace("Z", "")).date()
                    f_fin = datetime.fromisoformat(res["fechaFin"].replace("Z", "")).date()
                    if f_ini <= hoy <= f_fin:
                        if estado == "CONFIRMADA":
                            ocupadas_set.add(res["recursoId"])
                        elif estado == "PENDIENTE":
                            pendientes_set.add(res["recursoId"])
                except Exception:
                    continue

    ocupadas_count = len(ocupadas_set)
    pendientes_count = len(pendientes_set - ocupadas_set)
    disponibles_count = max(0, total_hab - (ocupadas_count + pendientes_count))
    tasa_ocupacion = round(((ocupadas_count + pendientes_count) / total_hab) * 100, 1) if total_hab > 0 else 0.0

    # Total ingresos de esta sucursal
    total_ingresos = 0.0
    for p in PAGOS_DB.values():
        if p.get("estado") == "APROBADO":
            res_pago = RESERVACIONES_DB.get(p.get("reservacionId"))
            if res_pago and res_pago.get("recursoId") in recursos_ids:
                total_ingresos += float(p.get("monto", 0.0))

    return {
        "capacidad_total_personas": cap_personas,
        "total_habitaciones": total_hab,
        "habitaciones_disponibles_hoy": disponibles_count,
        "habitaciones_ocupadas": ocupadas_count,
        "habitaciones_pendientes": pendientes_count,
        "tasa_ocupacion": tasa_ocupacion,
        "total_ingresos": round(total_ingresos, 2)
    }


# ==============================================================================
# QUERIES DEL SERVICIO DE CATÁLOGO (PÁGINA 7 DEL DOCUMENTO)
# ==============================================================================

@strawberry.type
class CatalogoQueries:
    """
    Consultas GraphQL del Servicio de Catálogo:
    - hoteles: Sedes y destinos de la cadena con su capacidad y disponibilidad en vivo.
    - estadisticasHoteles: Reporte de ocupación y capacidad por cada sucursal.
    - estadisticaHotel(hotelId): Métricas en tiempo real de una sucursal específica.
    - disponibilidadHotel(hotelId, desde, hasta): Verificación habitación por habitación.
    - recursos(filtro): Búsqueda con filtros (tipo, capacidad, precio, hotel).
    - recurso(id): Detalle individual de una habitación o espacio.
    """

    @strawberry.field
    def hoteles(self) -> List[Hotel]:
        """
        CONSULTA PÚBLICA: hoteles
        Retorna la lista de hoteles con su capacidad y disponibilidad hoy calculadas.
        """
        resultado = []
        for h in HOTELES_DB.values():
            m = calcular_metricas_sucursal(h["id"])
            resultado.append(Hotel(
                id=strawberry.ID(h["id"]),
                nombre=h["nombre"],
                ubicacion=h.get("ubicacion", ""),
                descripcion=h.get("descripcion", ""),
                foto=h.get("foto", ""),
                capacidad_total=m["capacidad_total_personas"],
                total_habitaciones=m["total_habitaciones"],
                disponibles_hoy=m["habitaciones_disponibles_hoy"],
                ocupadas_hoy=m["habitaciones_ocupadas"] + m["habitaciones_pendientes"],
                tasa_ocupacion=m["tasa_ocupacion"]
            ))
        return resultado

    @strawberry.field
    def estadisticas_hoteles(self) -> List[EstadisticasHotel]:
        """
        CONSULTA: estadisticasHoteles
        Devuelve el balance completo de capacidad, disponibilidad e ingresos por sucursal.
        """
        lista = []
        for h in HOTELES_DB.values():
            m = calcular_metricas_sucursal(h["id"])
            lista.append(EstadisticasHotel(
                hotel_id=strawberry.ID(h["id"]),
                nombre=h["nombre"],
                ubicacion=h.get("ubicacion", ""),
                descripcion=h.get("descripcion", ""),
                foto=h.get("foto", ""),
                capacidad_total_personas=m["capacidad_total_personas"],
                total_habitaciones=m["total_habitaciones"],
                habitaciones_disponibles_hoy=m["habitaciones_disponibles_hoy"],
                habitaciones_ocupadas=m["habitaciones_ocupadas"],
                habitaciones_pendientes=m["habitaciones_pendientes"],
                tasa_ocupacion=m["tasa_ocupacion"],
                total_ingresos=m["total_ingresos"]
            ))
        return lista

    @strawberry.field
    def estadistica_hotel(self, hotel_id: strawberry.ID) -> Optional[EstadisticasHotel]:
        """
        CONSULTA: estadisticaHotel(hotelId)
        Detalle estadístico y capacidad de una sucursal en particular.
        """
        h = HOTELES_DB.get(str(hotel_id))
        if not h:
            return None
        m = calcular_metricas_sucursal(str(hotel_id))
        return EstadisticasHotel(
            hotel_id=strawberry.ID(h["id"]),
            nombre=h["nombre"],
            ubicacion=h.get("ubicacion", ""),
            descripcion=h.get("descripcion", ""),
            foto=h.get("foto", ""),
            capacidad_total_personas=m["capacidad_total_personas"],
            total_habitaciones=m["total_habitaciones"],
            habitaciones_disponibles_hoy=m["habitaciones_disponibles_hoy"],
            habitaciones_ocupadas=m["habitaciones_ocupadas"],
            habitaciones_pendientes=m["habitaciones_pendientes"],
            tasa_ocupacion=m["tasa_ocupacion"],
            total_ingresos=m["total_ingresos"]
        )

    @strawberry.field
    def disponibilidad_hotel(
        self,
        hotel_id: strawberry.ID,
        desde: str,
        hasta: str
    ) -> List[RecursoDisponibilidadHotel]:
        """
        CONSULTA PÚBLICA: disponibilidadHotel(hotelId, desde, hasta)
        Inspecciona todas las habitaciones de una sucursal en un rango de fechas
        e informa cuáles están disponibles y cuáles ocupadas para reservar.
        """
        try:
            from services.reservaciones import verificar_traslape, liberar_reservaciones_expiradas  # type: ignore
            liberar_reservaciones_expiradas()
        except Exception:
            pass

        hid = str(hotel_id)
        recursos_sucursal = [r for r in RECURSOS_DB.values() if r.get("hotelId") == hid]
        resultado = []

        for r_data in recursos_sucursal:
            hay_empalme = False
            folio_asoc = None
            estado_asoc = None

            try:
                from services.reservaciones import verificar_traslape  # type: ignore
                hay_empalme = verificar_traslape(r_data["id"], desde, hasta)
            except Exception:
                hay_empalme = False

            if hay_empalme:
                # Buscar folio y estado de la reserva conflictiva
                for res in RESERVACIONES_DB.values():
                    if res["recursoId"] == r_data["id"] and res["estado"] in ("CONFIRMADA", "PENDIENTE"):
                        folio_asoc = res.get("folio")
                        estado_asoc = res.get("estado")
                        break

            rec_obj = Recurso(
                id=strawberry.ID(r_data["id"]),
                nombre=r_data["nombre"],
                tipo=r_data["tipo"],
                capacidad=int(r_data["capacidad"]),
                tarifa=float(r_data["tarifa"]),
                descripcion=r_data.get("descripcion", ""),
                foto=r_data.get("foto", ""),
                hotel_id=r_data.get("hotelId", "h-1")
            )

            motivo = "Disponible para las fechas seleccionadas" if not hay_empalme else (
                f"Reservada ({folio_asoc})" if estado_asoc == "CONFIRMADA" else f"En proceso de pago ({folio_asoc})"
            )

            resultado.append(RecursoDisponibilidadHotel(
                recurso=rec_obj,
                disponible=not hay_empalme,
                motivo=motivo,
                reserva_folio=folio_asoc,
                reserva_estado=estado_asoc
            ))

        return resultado

    @strawberry.field
    def recursos(
        self,
        filtro: Optional[FiltroRecursosInput] = None,
        hotel_id: Optional[strawberry.ID] = None,
        tipo: Optional[str] = None,
        max_tarifa: Optional[float] = None,
        min_capacidad: Optional[int] = None
    ) -> List[Recurso]:
        """
        CONSULTA PÚBLICA: recursos(filtro)
        Permite a los huéspedes buscar habitaciones y espacios según sus requerimientos.
        """
        items = list(RECURSOS_DB.values())

        # Consolidar filtros ya sea que vengan por el objeto o parámetros sueltos
        f_hotel = filtro.hotel_id if filtro and filtro.hotel_id else hotel_id
        f_tipo = filtro.tipo if filtro and filtro.tipo else tipo
        f_max = filtro.max_tarifa if filtro and filtro.max_tarifa else max_tarifa
        f_min = filtro.min_capacidad if filtro and filtro.min_capacidad else min_capacidad

        if f_hotel and str(f_hotel) != "TODOS":
            items = [r for r in items if r.get("hotelId") == str(f_hotel)]
        if f_tipo and str(f_tipo) != "TODOS":
            items = [r for r in items if r.get("tipo") == str(f_tipo)]
        if f_max is not None:
            items = [r for r in items if float(r.get("tarifa", 0.0)) <= float(f_max)]
        if f_min is not None:
            items = [r for r in items if int(r.get("capacidad", 1)) >= int(f_min)]

        return [
            Recurso(
                id=strawberry.ID(r["id"]),
                nombre=r["nombre"],
                tipo=r["tipo"],
                capacidad=int(r["capacidad"]),
                tarifa=float(r["tarifa"]),
                descripcion=r.get("descripcion", ""),
                foto=r.get("foto", ""),
                hotel_id=r.get("hotelId", "h-1")
            )
            for r in items
        ]

    @strawberry.field
    def recurso(self, id: strawberry.ID) -> Optional[Recurso]:
        """
        CONSULTA PÚBLICA: recurso(id)
        Devuelve el detalle y tarifa vigente de un recurso reservable específico.
        """
        r = RECURSOS_DB.get(str(id))
        if not r:
            return None
        return Recurso(
            id=strawberry.ID(r["id"]),
            nombre=r["nombre"],
            tipo=r["tipo"],
            capacidad=int(r["capacidad"]),
            tarifa=float(r["tarifa"]),
            descripcion=r.get("descripcion", ""),
            foto=r.get("foto", ""),
            hotel_id=r.get("hotelId", "h-1")
        )


# ==============================================================================
# MUTATIONS DEL SERVICIO DE CATÁLOGO (PÁGINA 7 DEL DOCUMENTO)
# ==============================================================================

@strawberry.type
class CatalogoMutations:
    """
    Mutaciones GraphQL del Servicio de Catálogo:
    - crearRecurso: Alta de nuevas habitaciones (solo administradores).
    - actualizarRecurso: Modificar tarifas o inventario (solo administradores).
    - eliminarRecurso: Baja de recursos (solo administradores).
    """

    @strawberry.mutation
    def crear_recurso(self, info: Info, input: CrearRecursoInput) -> Recurso:
        """
        MUTATION: crearRecurso
        Seguridad AAA:
        1. Autenticación JWT.
        2. Autorización RBAC: Exige rol 'administrador'. Si es cliente -> 403 Forbidden.
        3. Contabilización: Audita el alta en MySQL.
        """
        user_jwt = requerir_autorizacion(info, ["administrador"])
        admin_id = user_jwt.get("sub", "")
        admin_nombre = user_jwt.get("nombre", "")

        nuevo_id = f"r-{uuid.uuid4().hex[:4]}"
        recurso_dict = {
            "id": nuevo_id,
            "hotelId": input.hotel_id or "h-1",
            "nombre": input.nombre,
            "tipo": input.tipo,
            "capacidad": input.capacidad,
            "tarifa": float(input.tarifa),
            "descripcion": input.descripcion,
            "foto": input.foto
        }

        RECURSOS_DB[nuevo_id] = recurso_dict
        try:
            guardar_recurso_db(recurso_dict)
        except Exception:
            pass

        # Publicar evento en el Bus de Mensajes
        event_bus.publicar(EVENTO_RECURSO_CREADO, recurso_dict)

        # Contabilización AAA
        registrar_evento(
            usuario_id=admin_id,
            usuario_nombre=admin_nombre,
            rol="administrador",
            servicio="Catálogo",
            accion="CREAR_RECURSO",
            estado="EXITO",
            detalle=f"Administrador agregó recurso '{input.nombre}' ({input.tipo}) con tarifa ${input.tarifa:,.2f} MXN",
            monto=float(input.tarifa)
        )

        return Recurso(
            id=strawberry.ID(nuevo_id),
            nombre=recurso_dict["nombre"],
            tipo=recurso_dict["tipo"],
            capacidad=recurso_dict["capacidad"],
            tarifa=recurso_dict["tarifa"],
            descripcion=recurso_dict["descripcion"],
            foto=recurso_dict["foto"],
            hotel_id=recurso_dict["hotelId"]
        )

    @strawberry.mutation
    def actualizar_recurso(self, info: Info, id: strawberry.ID, input: ActualizarRecursoInput) -> Recurso:
        """
        MUTATION: actualizarRecurso
        Permite a la gerencia ajustar tarifas, cupos o fotos.
        Seguridad: Requiere rol 'administrador'.
        """
        user_jwt = requerir_autorizacion(info, ["administrador"])
        admin_id = user_jwt.get("sub", "")
        admin_nombre = user_jwt.get("nombre", "")

        rec_id = str(id)
        if rec_id not in RECURSOS_DB:
            raise ValueError(f"Recurso con ID '{id}' no encontrado en el catálogo.")

        r = RECURSOS_DB[rec_id]
        if input.nombre is not None: r["nombre"] = input.nombre
        if input.tipo is not None: r["tipo"] = input.tipo
        if input.capacidad is not None: r["capacidad"] = input.capacidad
        if input.tarifa is not None: r["tarifa"] = float(input.tarifa)
        if input.descripcion is not None: r["descripcion"] = input.descripcion
        if input.foto is not None: r["foto"] = input.foto
        if input.hotel_id is not None: r["hotelId"] = input.hotel_id

        try:
            guardar_recurso_db(r)
        except Exception:
            pass

        event_bus.publicar(EVENTO_RECURSO_ACTUALIZADO, r)

        registrar_evento(
            usuario_id=admin_id,
            usuario_nombre=admin_nombre,
            rol="administrador",
            servicio="Catálogo",
            accion="ACTUALIZAR_RECURSO",
            estado="EXITO",
            detalle=f"Administrador actualizó datos del recurso '{r['nombre']}' (ID: {rec_id})",
            monto=float(r.get("tarifa", 0.0))
        )

        return Recurso(
            id=strawberry.ID(r["id"]),
            nombre=r["nombre"],
            tipo=r["tipo"],
            capacidad=r["capacidad"],
            tarifa=float(r["tarifa"]),
            descripcion=r.get("descripcion", ""),
            foto=r.get("foto", ""),
            hotel_id=r.get("hotelId", "h-1")
        )

    @strawberry.mutation
    def eliminar_recurso(self, info: Info, id: strawberry.ID) -> bool:
        """
        MUTATION: eliminarRecurso
        Retira una habitación o espacio del inventario.
        Seguridad: Requiere rol 'administrador'.
        """
        user_jwt = requerir_autorizacion(info, ["administrador"])
        admin_id = user_jwt.get("sub", "")
        admin_nombre = user_jwt.get("nombre", "")

        rec_id = str(id)
        if rec_id not in RECURSOS_DB:
            raise ValueError(f"Recurso con ID '{id}' no encontrado.")

        nombre_rec = RECURSOS_DB[rec_id]["nombre"]
        try:
            eliminar_recurso_db(rec_id)
        except Exception:
            pass

        event_bus.publicar(EVENTO_RECURSO_ELIMINADO, {"id": rec_id, "nombre": nombre_rec})

        registrar_evento(
            usuario_id=admin_id,
            usuario_nombre=admin_nombre,
            rol="administrador",
            servicio="Catálogo",
            accion="ELIMINAR_RECURSO",
            estado="EXITO",
            detalle=f"Administrador retiró recurso '{nombre_rec}' (ID: {rec_id}) del inventario"
        )

        return True
