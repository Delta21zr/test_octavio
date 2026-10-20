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

MÓDULO: SERVICIO DE RESERVACIONES (SERVICIO 3 SEGÚN DOCUMENTO DE ARQUITECTURA)
Archivo: services/reservaciones.py
================================================================================
DESCRIPCIÓN GENERAL:
Este microservicio gestiona el ciclo de vida de las reservaciones hoteleras,
validación de disponibilidad, empalmes de fechas y reglas de negocio:

1. REQUERIMIENTOS SEGÚN EL DOCUMENTO DE OCTAVIO (Páginas 3, 4, 5, 7 y 8):
   - Función: Crea, modifica, consulta y cancela reservas; valida disponibilidad
     para evitar empalmes y aplica las reglas de negocio.
   - Entradas: usuarioId, recursoId, fechas de inicio y fin, número de personas.
   - Salidas: Reserva con folio y estado (PENDIENTE, CONFIRMADA, CANCELADA),
     disponibilidad; emisión de eventos 'ReservacionCreada' y 'ReservacionCancelada'.
   - REGLA CLAVE DE NEGOCIO (Página 8):
     "El estado de la reserva queda en PENDIENTE hasta que Pagos publica el
     evento PagoConfirmado, momento en que Reservaciones lo cambia a CONFIRMADO".

2. APLICACIÓN DEL MODELO TRIPLE A (AAA):
   - Autenticación: Verificación del token JWT.
   - Autorización: Ownership check (un cliente solo puede reservar a su propio
     nombre, ver y cancelar sus propias reservaciones; administradores tienen
     acceso global).
   - Contabilización: Trazabilidad y auditoría de cada operación en MySQL.
================================================================================
"""

import sys
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

# Garantizar que la raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strawberry  # type: ignore
from strawberry.types import Info  # type: ignore

from data.db import (  # type: ignore
    RESERVACIONES_DB,
    RECURSOS_DB,
    USUARIOS_DB,
    HOTELES_DB,
    obtener_usuario_mysql,
    guardar_reservacion_db,
    actualizar_estado_reservacion_db,
    eliminar_reservacion_db
)
from security import (  # type: ignore
    requerir_autenticacion,
    requerir_autorizacion,
    obtener_usuario_actual
)
from accounting import registrar_evento  # type: ignore
from event_bus import (  # type: ignore
    event_bus,
    EVENTO_RESERVACION_CREADA,
    EVENTO_RESERVACION_CANCELADA,
    EVENTO_PAGO_CONFIRMADO
)
from services.catalogo import Recurso, Hotel  # type: ignore


# ==============================================================================
# ENUMERACIONES Y TIPOS GRAPHQL PARA RESERVACIONES
# ==============================================================================

@strawberry.enum
class EstadoReservacion(Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


@strawberry.type
class Reservacion:
    """
    Representa una reservación formal emitida con folio oficial.
    """
    id: strawberry.ID
    folio: str
    usuario_id: strawberry.ID
    usuario_nombre: Optional[str] = None
    usuario_correo: Optional[str] = None
    recurso: Recurso
    fecha_inicio: str
    fecha_fin: str
    personas: int
    estado: EstadoReservacion
    total: float
    creado_en: str


@strawberry.type
class ResultadoOperacionReserva:
    exito: bool
    mensaje: str
    id: Optional[str] = None
    folio: Optional[str] = None


@strawberry.input
class CrearReservacionInput:
    """
    Estructura de entrada según la página 9 del documento de Octavio.
    """
    usuario_id: strawberry.ID
    recurso_id: strawberry.ID
    fecha_inicio: str
    fecha_fin: str
    personas: int


@strawberry.input
class ModificarReservacionInput:
    """
    Entrada para mutación modificarReservacion (Página 7).
    """
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    personas: Optional[int] = None


# ==============================================================================
# FUNCIONES AUXILIARES DE LÓGICA DE NEGOCIO Y LIBERACIÓN DE 15 MINUTOS
# ==============================================================================

def liberar_reservaciones_expiradas() -> int:
    """
    REGLA DE NEGOCIO:
    Si una reservación permanece en estado 'PENDIENTE' por más de 15 minutos sin ser pagada,
    se anula/cancela automáticamente y la habitación se libera de inmediato para otros clientes.
    """
    ahora = datetime.now()
    expiradas = 0
    for res_id, res in list(RESERVACIONES_DB.items()):
        if res.get("estado") == "PENDIENTE":
            creado_str = res.get("creadoEn", "")
            try:
                creado_dt = datetime.fromisoformat(creado_str.replace("Z", ""))
                diferencia = ahora - creado_dt
                if diferencia.total_seconds() >= (15 * 60):  # 15 minutos cumplidos
                    res["estado"] = "CANCELADA"
                    try:
                        actualizar_estado_reservacion_db(res_id, "CANCELADA")
                    except Exception:
                        pass

                    # Publicar cancelación por tiempo agotado al bus de eventos
                    event_bus.publicar(EVENTO_RESERVACION_CANCELADA, {
                        "reservacionId": res_id,
                        "folio": res.get("folio", ""),
                        "usuarioId": res.get("usuarioId", ""),
                        "total": res.get("total", 0.0),
                        "motivo": "EXPIRACION_15_MINUTOS"
                    })

                    # Registrar en bitácora contable AAA
                    registrar_evento(
                        usuario_id=res.get("usuarioId", "sistema"),
                        usuario_nombre="Sistema (Liberación Automática 15 min)",
                        rol="sistema",
                        servicio="Reservaciones",
                        accion="LIBERAR_RESERVA_EXPIRADA_15MIN",
                        estado="EXITO",
                        detalle=f"Folio {res.get('folio')} liberado automáticamente: Transcurrieron más de 15 minutos en estado PENDIENTE sin recibir pago. Habitación liberada.",
                        monto=res.get("total", 0.0)
                    )
                    expiradas += 1
            except Exception:
                continue
    return expiradas


def calcular_dias_o_noches(fecha_inicio: str, fecha_fin: str) -> int:
    try:
        f_ini = datetime.fromisoformat(fecha_inicio.replace("Z", ""))
        f_fin = datetime.fromisoformat(fecha_fin.replace("Z", ""))
        dias = (f_fin.date() - f_ini.date()).days
        return max(1, dias)
    except Exception:
        return 1


def verificar_traslape(recurso_id: str, f_ini_str: str, f_fin_str: str, excluir_res_id: Optional[str] = None) -> bool:
    """
    Algoritmo de detección de empalmes entre rangos de fechas:
    Existe conflicto si: (Nueva_Llegada < Salida_Existente) Y (Nueva_Salida > Llegada_Existente).
    Primero libera cualquier reservación pendiente que haya superado los 15 minutos.
    """
    liberar_reservaciones_expiradas()
    try:
        nueva_ini = datetime.fromisoformat(f_ini_str.replace("Z", ""))
        nueva_fin = datetime.fromisoformat(f_fin_str.replace("Z", ""))
    except Exception:
        return False

    for res_id, res in RESERVACIONES_DB.items():
        if excluir_res_id and res_id == excluir_res_id:
            continue
        if res["recursoId"] == recurso_id and res["estado"] in ("CONFIRMADA", "PENDIENTE"):
            try:
                exist_ini = datetime.fromisoformat(res["fechaInicio"].replace("Z", ""))
                exist_fin = datetime.fromisoformat(res["fechaFin"].replace("Z", ""))
                if nueva_ini < exist_fin and nueva_fin > exist_ini:
                    return True
            except Exception:
                continue
    return False


def formatear_reservacion(res_data: dict) -> Reservacion:
    rec_data = RECURSOS_DB.get(res_data["recursoId"], {
        "id": res_data["recursoId"],
        "nombre": "Recurso general",
        "tipo": "GENERAL",
        "capacidad": 1,
        "tarifa": 0.0,
        "descripcion": "",
        "foto": "",
        "hotelId": "h-1"
    })
    
    uid = str(res_data.get("usuarioId", ""))
    user_info = USUARIOS_DB.get(uid) or obtener_usuario_mysql(uid) or {}
    user_nombre = user_info.get("nombre", f"Huésped ({uid})")
    user_correo = user_info.get("correo", "")

    return Reservacion(
        id=strawberry.ID(res_data["id"]),
        folio=res_data["folio"],
        usuario_id=strawberry.ID(res_data["usuarioId"]),
        usuario_nombre=user_nombre,
        usuario_correo=user_correo,
        recurso=Recurso(
            id=strawberry.ID(rec_data["id"]),
            nombre=rec_data["nombre"],
            tipo=rec_data["tipo"],
            capacidad=int(rec_data["capacidad"]),
            tarifa=float(rec_data["tarifa"]),
            descripcion=rec_data.get("descripcion", ""),
            foto=rec_data.get("foto", ""),
            hotel_id=rec_data.get("hotelId", "h-1")
        ),
        fecha_inicio=res_data["fechaInicio"],
        fecha_fin=res_data["fechaFin"],
        personas=int(res_data["personas"]),
        estado=EstadoReservacion[res_data["estado"]],
        total=float(res_data["total"]),
        creado_en=res_data.get("creadoEn", "")
    )


# ==============================================================================
# QUERIES DEL SERVICIO DE RESERVACIONES (PÁGINA 7 DEL DOCUMENTO)
# ==============================================================================

@strawberry.type
class ReservacionesQueries:
    """
    Consultas GraphQL del Servicio de Reservaciones:
    - disponibilidad(recursoId, desde, hasta): Valida si hay traslape.
    - misReservaciones: Reservas del usuario en sesión.
    - todasReservaciones: Vista general para administradores.
    - reservacion(id): Detalle individual protegido.
    """

    @strawberry.field
    def disponibilidad(self, recurso_id: strawberry.ID, desde: str, hasta: str) -> bool:
        """
        CONSULTA PÚBLICA: disponibilidad(recursoId, desde, hasta)
        Comprueba en tiempo real si el recurso está libre en el rango especificado.
        """
        liberar_reservaciones_expiradas()
        hay_empalme = verificar_traslape(str(recurso_id), desde, hasta)
        return not hay_empalme

    @strawberry.field
    def mis_reservaciones(self, info: Info) -> List[Reservacion]:
        """
        CONSULTA: misReservaciones
        Devuelve únicamente las reservaciones pertenecientes al huésped en sesión.
        """
        liberar_reservaciones_expiradas()
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub")
        
        reservas = [
            formatear_reservacion(r)
            for r in RESERVACIONES_DB.values()
            if r["usuarioId"] == user_id
        ]

        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=user_jwt.get("nombre", ""),
            rol=user_jwt.get("rol", ""),
            servicio="Reservaciones",
            accion="MIS_RESERVACIONES",
            estado="EXITO",
            detalle=f"Consulta de historial propio ({len(reservas)} reservaciones encontradas)"
        )

        return reservas

    @strawberry.field
    def todas_reservaciones(self, info: Info, estado: Optional[str] = None) -> List[Reservacion]:
        """
        CONSULTA: todasReservaciones
        Vista global para gerencia. Exige rol 'administrador'.
        Permite segmentar por estado: 'PENDIENTE', 'CONFIRMADA', 'CANCELADA'.
        """
        liberar_reservaciones_expiradas()
        admin_jwt = requerir_autorizacion(info, ["administrador"])
        
        lista = list(RESERVACIONES_DB.values())
        if estado and estado != "TODAS":
            lista = [r for r in lista if r["estado"] == estado]

        registrar_evento(
            usuario_id=admin_jwt.get("sub", ""),
            usuario_nombre=admin_jwt.get("nombre", ""),
            rol=admin_jwt.get("rol", ""),
            servicio="Reservaciones",
            accion="LISTAR_TODAS_RESERVACIONES",
            estado="EXITO",
            detalle=f"Administrador consultó reservas (filtro: {estado or 'TODAS'}, {len(lista)} registros)"
        )

        return [formatear_reservacion(r) for r in lista]

    @strawberry.field
    def reservacion(self, info: Info, id: strawberry.ID) -> Optional[Reservacion]:
        """
        CONSULTA: reservacion(id)
        Detalle individual. Control de propiedad estricto (huésped o admin).
        """
        user_jwt = requerir_autenticacion(info)
        res_data = RESERVACIONES_DB.get(str(id))
        if not res_data:
            return None

        user_id = user_jwt.get("sub")
        rol = user_jwt.get("rol")

        if rol != "administrador" and res_data["usuarioId"] != user_id:
            registrar_evento(
                usuario_id=user_id,
                usuario_nombre=user_jwt.get("nombre", ""),
                rol=rol,
                servicio="Reservaciones",
                accion="ACCESO_DENEGADO_RESERVA",
                estado="DENEGADO",
                detalle=f"Intento no autorizado de consultar reserva {id} de otro cliente"
            )
            raise PermissionError("Autorización denegada: No tienes permiso para ver esta reservación ajena.")

        return formatear_reservacion(res_data)


# ==============================================================================
# MUTATIONS DEL SERVICIO DE RESERVACIONES (PÁGINA 7 DEL DOCUMENTO)
# ==============================================================================

@strawberry.type
class ReservacionesMutations:
    """
    Mutaciones GraphQL del Servicio de Reservaciones:
    - crearReservacion: Registra en estado PENDIENTE y emite 'ReservacionCreada'.
    - modificarReservacion: Ajusta fechas y aforo de una reserva propia.
    - cancelarReservacion: Anula la reserva y emite 'ReservacionCancelada'.
    """

    @strawberry.mutation
    def crear_reservacion(self, info: Info, input: CrearReservacionInput) -> Reservacion:
        """
        MUTATION: crearReservacion
        Genera la reservación inicial. Según la especificación del documento de Octavio:
        - Nace con estado 'PENDIENTE'.
        - Emite el evento asíncrono 'ReservacionCreada' al bus de mensajes.
        - Notificaciones avisa al cliente con su folio para proceder al pago.
        - Cuando el servicio de Pagos confirme el cobro, cambiará a 'CONFIRMADA'.
        """
        # 1. Autenticación
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub")
        rol = user_jwt.get("rol")
        nombre_usuario = user_jwt.get("nombre", "")

        # 2. Control de Autorización (prevención de suplantación)
        if rol != "administrador" and str(input.usuario_id) != user_id:
            registrar_evento(
                usuario_id=user_id,
                usuario_nombre=nombre_usuario,
                rol=rol,
                servicio="Reservaciones",
                accion="INTENTO_SUPLANTACION_RESERVA",
                estado="DENEGADO",
                detalle=f"Cliente intentó crear reserva a nombre de otro usuario ({input.usuario_id})"
            )
            raise PermissionError("Autorización denegada: Un cliente solo puede reservar a su propio nombre.")

        recurso_id = str(input.recurso_id)
        recurso = RECURSOS_DB.get(recurso_id)
        if not recurso:
            raise ValueError(f"La habitación o espacio con ID '{recurso_id}' no existe.")

        if input.personas > recurso["capacidad"]:
            raise ValueError(f"El espacio seleccionado solo tiene capacidad máxima de {recurso['capacidad']} personas.")

        if verificar_traslape(recurso_id, input.fecha_inicio, input.fecha_fin):
            registrar_evento(
                usuario_id=user_id,
                usuario_nombre=nombre_usuario,
                rol=rol,
                servicio="Reservaciones",
                accion="CONFLICTO_DISPONIBILIDAD",
                estado="FALLIDO",
                detalle=f"Intento de reservación fallido: Recurso {recurso_id} ocupado en las fechas solicitadas."
            )
            raise ValueError("El recurso seleccionado ya no se encuentra disponible en las fechas solicitadas.")

        noches = calcular_dias_o_noches(input.fecha_inicio, input.fecha_fin)
        costo_total = round(noches * float(recurso["tarifa"]), 2)

        res_id = f"res-{uuid.uuid4().hex[:6]}"
        folio = f"RES-2026-{uuid.uuid4().hex[:4].upper()}"
        creado_en = datetime.now().isoformat()

        # Estado inicial PENDIENTE según página 8 del documento
        nueva_res = {
            "id": res_id,
            "folio": folio,
            "usuarioId": str(input.usuario_id),
            "recursoId": recurso_id,
            "fechaInicio": input.fecha_inicio,
            "fechaFin": input.fecha_fin,
            "personas": input.personas,
            "estado": "PENDIENTE",
            "total": costo_total,
            "creadoEn": creado_en
        }

        RESERVACIONES_DB[res_id] = nueva_res
        try:
            guardar_reservacion_db(nueva_res)
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # PUBLICAR EVENTO EN EL BUS DE MENSAJES (BROKER ASÍNCRONO)
        # ----------------------------------------------------------------------
        event_bus.publicar(EVENTO_RESERVACION_CREADA, {
            "reservacionId": res_id,
            "folio": folio,
            "usuarioId": str(input.usuario_id),
            "recursoId": recurso_id,
            "recursoNombre": recurso["nombre"],
            "total": costo_total,
            "fechaInicio": input.fecha_inicio,
            "fechaFin": input.fecha_fin
        })

        # Contabilización AAA
        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=nombre_usuario,
            rol=rol,
            servicio="Reservaciones",
            accion="CREAR_RESERVACION",
            estado="EXITO",
            detalle=f"Folio {folio} registrado en estado PENDIENTE para {recurso['nombre']}. Noches: {noches}. Total: ${costo_total:,.2f} MXN",
            monto=costo_total
        )

        return formatear_reservacion(nueva_res)

    @strawberry.mutation
    def modificar_reservacion(self, info: Info, id: strawberry.ID, input: ModificarReservacionInput) -> Reservacion:
        """
        MUTATION: modificarReservacion (Página 7)
        Permite actualizar fechas o personas de una reserva vigente.
        """
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub")
        rol = user_jwt.get("rol")
        nombre_usuario = user_jwt.get("nombre", "")

        res_id = str(id)
        res = RESERVACIONES_DB.get(res_id)
        if not res:
            raise ValueError(f"Reservación '{res_id}' no encontrada.")

        if rol != "administrador" and res["usuarioId"] != user_id:
            raise PermissionError("Autorización denegada: No puedes modificar reservaciones ajenas.")

        if res["estado"] == "CANCELADA":
            raise ValueError("No se puede modificar una reservación cancelada.")

        nueva_ini = input.fecha_inicio or res["fechaInicio"]
        nueva_fin = input.fecha_fin or res["fechaFin"]

        if verificar_traslape(res["recursoId"], nueva_ini, nueva_fin, excluir_res_id=res_id):
            raise ValueError("Las nuevas fechas colisionan con otra reservación activa.")

        res["fechaInicio"] = nueva_ini
        res["fechaFin"] = nueva_fin
        if input.personas is not None:
            res["personas"] = input.personas

        # Recalcular costo
        rec = RECURSOS_DB.get(res["recursoId"])
        if rec:
            noches = calcular_dias_o_noches(nueva_ini, nueva_fin)
            res["total"] = round(noches * float(rec["tarifa"]), 2)

        try:
            guardar_reservacion_db(res)
        except Exception:
            pass

        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=nombre_usuario,
            rol=rol,
            servicio="Reservaciones",
            accion="MODIFICAR_RESERVACION",
            estado="EXITO",
            detalle=f"Reservación {res['folio']} modificada. Nuevo rango: {nueva_ini} a {nueva_fin}. Total: ${res['total']:,.2f} MXN",
            monto=res["total"]
        )

        return formatear_reservacion(res)

    @strawberry.mutation
    def cancelar_reservacion(self, info: Info, id: strawberry.ID) -> Reservacion:
        """
        MUTATION: cancelarReservacion
        Anula una estancia. Dispara 'ReservacionCancelada' por el bus de mensajes,
        lo que detona reembolso en Pagos y aviso por Notificaciones.
        """
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub")
        rol = user_jwt.get("rol")
        nombre_usuario = user_jwt.get("nombre", "")

        res_id = str(id)
        res_data = RESERVACIONES_DB.get(res_id)
        if not res_data:
            raise ValueError(f"Reservación con ID '{id}' no encontrada.")

        # Control de Autorización / Ownership Check
        if rol != "administrador" and res_data["usuarioId"] != user_id:
            registrar_evento(
                usuario_id=user_id,
                usuario_nombre=nombre_usuario,
                rol=rol,
                servicio="Reservaciones",
                accion="CANCELACION_NO_AUTORIZADA",
                estado="DENEGADO",
                detalle=f"Cliente intentó cancelar reserva ajena '{res_data['folio']}' de usuario {res_data['usuarioId']}"
            )
            raise PermissionError("Autorización denegada: Solo el titular de la reserva o un administrador pueden cancelarla.")

        if res_data["estado"] == "CANCELADA":
            return formatear_reservacion(res_data)

        res_data["estado"] = "CANCELADA"
        try:
            actualizar_estado_reservacion_db(res_id, "CANCELADA")
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # PUBLICAR EVENTO EN EL BUS DE MENSAJES
        # ----------------------------------------------------------------------
        event_bus.publicar(EVENTO_RESERVACION_CANCELADA, {
            "reservacionId": res_id,
            "folio": res_data["folio"],
            "usuarioId": res_data["usuarioId"],
            "total": res_data["total"]
        })

        # Contabilización AAA
        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=nombre_usuario,
            rol=rol,
            servicio="Reservaciones",
            accion="CANCELAR_RESERVACION",
            estado="EXITO",
            detalle=f"Folio {res_data['folio']} cancelado por {nombre_usuario} ({rol}). Evento publicado al Bus.",
            monto=res_data["total"]
        )

        return formatear_reservacion(res_data)

    @strawberry.mutation
    def liberar_reservacion_expirada(self, info: Info, id: strawberry.ID) -> Reservacion:
        """
        MUTATION: liberarReservacionExpirada
        Permite anular/liberar inmediatamente una reservación que esté en estado PENDIENTE.
        Permite al titular o a un administrador liberar la habitación si el pago no se concretará
        o si se agotó el límite de tiempo de 15 minutos.
        """
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub", "")
        rol = user_jwt.get("rol", "")
        nombre_usuario = user_jwt.get("nombre", "")

        res_id = str(id)
        res_data = RESERVACIONES_DB.get(res_id)
        if not res_data:
            raise ValueError(f"Reservación '{id}' no encontrada.")

        if rol != "administrador" and res_data["usuarioId"] != user_id:
            raise PermissionError("Autorización denegada: Solo el titular o un administrador pueden liberar la reserva.")

        if res_data["estado"] != "PENDIENTE":
            raise ValueError(f"Solo se pueden liberar reservaciones en estado PENDIENTE. Estado actual: '{res_data['estado']}'.")

        res_data["estado"] = "CANCELADA"
        try:
            actualizar_estado_reservacion_db(res_id, "CANCELADA")
        except Exception:
            pass

        # Publicar evento de cancelación
        event_bus.publicar(EVENTO_RESERVACION_CANCELADA, {
            "reservacionId": res_id,
            "folio": res_data["folio"],
            "usuarioId": res_data["usuarioId"],
            "total": res_data["total"],
            "motivo": "LIBERACION_PENDIENTE_15MIN"
        })

        # Registrar en auditoría AAA
        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=nombre_usuario,
            rol=rol,
            servicio="Reservaciones",
            accion="LIBERAR_RESERVACION_PENDIENTE",
            estado="EXITO",
            detalle=f"Habitación liberada: Folio {res_data['folio']} cancelado desde estado PENDIENTE por {nombre_usuario} ({rol}). Habitación disponible.",
            monto=res_data["total"]
        )

        return formatear_reservacion(res_data)

    @strawberry.mutation
    def eliminar_reservacion(self, info: Info, id: strawberry.ID) -> ResultadoOperacionReserva:
        """
        MUTATION: eliminarReservacion
        Elimina definitivamente una reservación de la base de datos MySQL y la memoria.
        Permite al administrador o al cliente depurar reservaciones canceladas o de prueba.
        """
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub", "")
        rol = user_jwt.get("rol", "")
        nombre_usuario = user_jwt.get("nombre", "")

        res_id = str(id)
        res_data = RESERVACIONES_DB.get(res_id)
        if not res_data:
            eliminar_reservacion_db(res_id)
            return ResultadoOperacionReserva(exito=True, mensaje=f"Reservación '{id}' eliminada.", id=res_id)

        # Control de Autorización / Ownership Check
        if rol != "administrador" and res_data["usuarioId"] != user_id:
            registrar_evento(
                usuario_id=user_id,
                usuario_nombre=nombre_usuario,
                rol=rol,
                servicio="Reservaciones",
                accion="ELIMINACION_NO_AUTORIZADA",
                estado="DENEGADO",
                detalle=f"Usuario intentó eliminar reserva ajena '{res_data['folio']}' de {res_data['usuarioId']}"
            )
            raise PermissionError("Autorización denegada: Solo el titular de la reserva o un administrador pueden eliminarla.")

        folio = res_data.get("folio", res_id)
        monto = float(res_data.get("total", 0.0))

        eliminar_reservacion_db(res_id)

        # Contabilización AAA
        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=nombre_usuario,
            rol=rol,
            servicio="Reservaciones",
            accion="ELIMINAR_RESERVACION",
            estado="EXITO",
            detalle=f"Reservación folio {folio} eliminada definitivamente de MySQL por {nombre_usuario} ({rol}).",
            monto=monto
        )

        return ResultadoOperacionReserva(
            exito=True,
            mensaje=f"Reservación {folio} eliminada exitosamente de la base de datos.",
            id=res_id,
            folio=folio
        )



# ==============================================================================
# CONSUMIDOR DEL EVENTO 'PagoConfirmado' EN EL BUS DE MENSAJES (PÁGINA 8)
# ==============================================================================
def manejar_evento_pago_confirmado(evento_dict: dict):
    """
    Regla de la página 8 del documento de Octavio:
    "El estado de la reserva queda en PENDIENTE hasta que Pagos publica el
    evento PagoConfirmado, momento en que Reservaciones lo cambia a CONFIRMADO"
    """
    datos = evento_dict.get("datos", {})
    res_id = datos.get("reservacionId")
    if not res_id:
        return

    res = RESERVACIONES_DB.get(res_id)
    if res and res["estado"] == "PENDIENTE":
        res["estado"] = "CONFIRMADA"
        try:
            actualizar_estado_reservacion_db(res_id, "CONFIRMADA")
        except Exception:
            pass

        print(f"[SERVICIO DE RESERVACIONES] >> Reserva {res['folio']} actualizada a 'CONFIRMADA' tras recibir evento PagoConfirmado")

        registrar_evento(
            usuario_id=res["usuarioId"],
            usuario_nombre="Sistema",
            rol="sistema",
            servicio="Reservaciones",
            accion="CONFIRMAR_RESERVACION_POR_PAGO",
            estado="EXITO",
            detalle=f"Reserva {res['folio']} promovida automáticamente a CONFIRMADA por recepción de PagoConfirmado",
            monto=res["total"]
        )

# Suscribir handler al bus de mensajes
event_bus.suscribir(EVENTO_PAGO_CONFIRMADO, manejar_evento_pago_confirmado)
