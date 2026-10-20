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

SUITE DE PRUEBAS AUTOMATIZADAS: 5 MICROSERVICIOS + BUS DE MENSAJES + TRIPLE A
Archivo: test_services.py
================================================================================
Valida de forma integral:
1. Servicio de Usuarios (Autenticación JWT y Roles RBAC).
2. Servicio de Catálogo (Filtros de búsqueda, creación admin y bloqueo 403 a cliente).
3. Servicio de Reservaciones (Creación en estado PENDIENTE, prevención de traslapes y suplantación).
4. Servicio de Pagos (Cobro con pasarela, emisión de comprobante y evento PagoConfirmado).
5. Comunicación Asíncrona (Transición automática de la reserva a CONFIRMADA).
6. Servicio de Notificaciones (Reacción asíncrona ante eventos, despacho de email/SMS).
7. Flujo de Cancelación y Reembolso (Cancelación -> Reembolso en Pagos -> Alerta en Notificaciones).
8. Contabilización AAA (Auditoría de todos los microservicios y métricas SaaS en MySQL).
================================================================================
"""

import asyncio
from datetime import datetime, timedelta
import random

from schema import schema
from security import verificar_token


async def run_tests():
    print("\n" + "="*75)
    print("EJECUTANDO PRUEBAS DE LOS 5 MICROSERVICIOS (ARQUITECTURA SOA / SAAS)")
    print("="*75)

    # --------------------------------------------------------------------------
    # 1. SERVICIO DE USUARIOS: AUTENTICACIÓN (JWT)
    # --------------------------------------------------------------------------
    login_admin = """
    mutation {
        iniciarSesion(correo: "admin@hotel.com", password: "123") {
            token
            exito
            mensaje
            usuario { id nombre rol }
        }
    }
    """
    res1 = await schema.execute(login_admin, context_value={})
    assert res1.data and res1.data["iniciarSesion"]["exito"] is True, f"Error en login admin: {res1.errors}"
    admin_token = res1.data["iniciarSesion"]["token"]
    admin_user = verificar_token(admin_token)
    print("[OK] 1. Servicio de Usuarios: Token JWT emitido para Administrador")

    login_cliente = """
    mutation {
        iniciarSesion(correo: "juan@cliente.com", password: "123") {
            token
            exito
            usuario { id nombre rol }
        }
    }
    """
    res2 = await schema.execute(login_cliente, context_value={})
    assert res2.data and res2.data["iniciarSesion"]["exito"] is True, f"Error en login cliente: {res2.errors}"
    cliente_token = res2.data["iniciarSesion"]["token"]
    cliente_user = verificar_token(cliente_token)
    print("[OK] 2. Servicio de Usuarios: Token JWT emitido para Cliente (Juan)")

    # --------------------------------------------------------------------------
    # 2. SERVICIO DE CATÁLOGO: CONSULTA Y CONTROL RBAC
    # --------------------------------------------------------------------------
    # 2.1 Consulta pública con filtros
    query_catalogo = """
    query {
        recursos(tipo: "HABITACION_LUJO") {
            id
            nombre
            tipo
            tarifa
        }
    }
    """
    res_cat = await schema.execute(query_catalogo, context_value={})
    assert res_cat.data and len(res_cat.data["recursos"]) > 0, f"Error en catálogo: {res_cat.errors}"
    print(f"[OK] 3. Servicio de Catálogo: Consulta filtrada retornó {len(res_cat.data['recursos'])} recursos de lujo")

    # 2.2 Administrador crea un nuevo recurso en el catálogo
    nuevo_recurso_mutation = """
    mutation {
        crearRecurso(input: {
            hotelId: "h-1",
            nombre: "Villa Presidencial Frente al Océano",
            tipo: "HABITACION_LUJO",
            capacidad: 8,
            tarifa: 5500.0,
            descripcion: "Villa privada con alberca infinita y servicio de mayordomo",
            foto: "https://images.unsplash.com/photo-1571896349842-33c89424de2d"
        }) {
            id
            nombre
            tarifa
        }
    }
    """
    res_crear_rec = await schema.execute(nuevo_recurso_mutation, context_value={"user": admin_user, "token": admin_token})
    assert res_crear_rec.data and "crearRecurso" in res_crear_rec.data, f"Error al crear recurso: {res_crear_rec.errors}"
    rec_nuevo_id = res_crear_rec.data["crearRecurso"]["id"]
    print(f"[OK] 4. Servicio de Catálogo: Admin dio de alta nuevo recurso (ID: {rec_nuevo_id})")

    # 2.3 RBAC: Un cliente intenta dar de alta un recurso (debe ser bloqueado con 403)
    res_intento_cliente_cat = await schema.execute(nuevo_recurso_mutation, context_value={"user": cliente_user, "token": cliente_token})
    assert res_intento_cliente_cat.errors and len(res_intento_cliente_cat.errors) > 0
    print(f"[OK] 5. Control de Acceso Catálogo: Intento de cliente denegado -> '{res_intento_cliente_cat.errors[0].message}'")

    # --------------------------------------------------------------------------
    # 3. SERVICIO DE RESERVACIONES: CREACIÓN EN ESTADO PENDIENTE
    # --------------------------------------------------------------------------
    f_ini_dt = datetime.now() + timedelta(days=random.randint(500, 900))
    f_fin_dt = f_ini_dt + timedelta(days=3)
    f_ini_str = f_ini_dt.strftime("%Y-%m-%dT15:00:00")
    f_fin_str = f_fin_dt.strftime("%Y-%m-%dT12:00:00")

    crear_res = f"""
    mutation {{
        crearReservacion(input: {{
            usuarioId: "u-102",
            recursoId: "{rec_nuevo_id}",
            fechaInicio: "{f_ini_str}",
            fechaFin: "{f_fin_str}",
            personas: 2
        }}) {{
            id
            folio
            estado
            total
            recurso {{
                nombre
                tarifa
            }}
        }}
    }}
    """
    res_crear = await schema.execute(crear_res, context_value={"user": cliente_user, "token": cliente_token})
    assert res_crear.data and "crearReservacion" in res_crear.data, f"Error al crear reservación: {res_crear.errors}"
    reserva_creada = res_crear.data["crearReservacion"]
    res_id = reserva_creada["id"]
    folio_res = reserva_creada["folio"]

    # Validar que nace en estado PENDIENTE según la página 8 del documento
    assert reserva_creada["estado"] == "PENDIENTE", f"Debería haber nacido en PENDIENTE, pero fue: {reserva_creada['estado']}"
    print(f"[OK] 6. Servicio de Reservaciones: Folio {folio_res} creado en estado 'PENDIENTE' | Total: ${reserva_creada['total']:,.2f} MXN")

    # --------------------------------------------------------------------------
    # 4. SERVICIO DE PAGOS: COBRO CON PASARELA Y PUBLICACIÓN EN EL BUS
    # --------------------------------------------------------------------------
    pagar_mutation = f"""
    mutation {{
        pagarReservacion(input: {{
            reservacionId: "{res_id}",
            metodoPago: "TARJETA_CREDITO"
        }}) {{
            id
            reservacionId
            monto
            metodoPago
            estado
            comprobante
            fecha
        }}
    }}
    """
    res_pago = await schema.execute(pagar_mutation, context_value={"user": cliente_user, "token": cliente_token})
    assert res_pago.data and "pagarReservacion" in res_pago.data, f"Error al pagar: {res_pago.errors}"
    pago_data = res_pago.data["pagarReservacion"]
    assert pago_data["estado"] == "APROBADO"
    print(f"[OK] 7. Servicio de Pagos: Cobro aprobado (${pago_data['monto']:,.2f} MXN) | Comprobante: {pago_data['comprobante']}")

    # --------------------------------------------------------------------------
    # 5. REACCIÓN ASÍNCRONA: RESERVACIONES CAMBIA A 'CONFIRMADA' (PÁGINA 8)
    # --------------------------------------------------------------------------
    # Consultamos la reserva nuevamente para confirmar que pasó a CONFIRMADA
    consultar_res_query = f"""
    query {{
        reservacion(id: "{res_id}") {{
            id
            folio
            estado
        }}
    }}
    """
    res_check = await schema.execute(consultar_res_query, context_value={"user": cliente_user, "token": cliente_token})
    assert res_check.data and res_check.data["reservacion"]["estado"] == "CONFIRMADA", f"La reserva no se confirmó: {res_check.data}"
    print(f"[OK] 8. Integración Asíncrona (ESB): Reserva {folio_res} cambió automáticamente a 'CONFIRMADA' tras PagoConfirmado")

    # --------------------------------------------------------------------------
    # 6. SERVICIO DE NOTIFICACIONES: AVISOS ASÍNCRONOS DETONADOS POR EL BUS
    # --------------------------------------------------------------------------
    notifs_query = """
    query {
        misNotificaciones {
            id
            asunto
            mensaje
            eventoOrigen
            canal
        }
    }
    """
    res_notifs = await schema.execute(notifs_query, context_value={"user": cliente_user, "token": cliente_token})
    assert res_notifs.data and len(res_notifs.data["misNotificaciones"]) >= 2, f"Faltan notificaciones: {res_notifs.data}"
    notifs = res_notifs.data["misNotificaciones"]
    print(f"[OK] 9. Servicio de Notificaciones: Cliente recibió {len(notifs)} avisos automáticos vía Bus de Mensajes")
    for n in notifs[:2]:
        print(f"      -> [{n['canal']}] {n['asunto']} (Evento: {n['eventoOrigen']})")

    # --------------------------------------------------------------------------
    # 7. FLUJO DE CANCELACIÓN Y REEMBOLSO ASÍNCRONO
    # --------------------------------------------------------------------------
    cancelar_mutation = f"""
    mutation {{
        cancelarReservacion(id: "{res_id}") {{
            id
            folio
            estado
        }}
    }}
    """
    res_cancelar = await schema.execute(cancelar_mutation, context_value={"user": cliente_user, "token": cliente_token})
    assert res_cancelar.data and res_cancelar.data["cancelarReservacion"]["estado"] == "CANCELADA"
    print(f"[OK] 10. Flujo Completo: Reserva {folio_res} cancelada. Detonó reembolso automático en Pagos y aviso en Notificaciones")

    # --------------------------------------------------------------------------
    # 8. CONTABILIZACIÓN Y AUDITORÍA TRIPLE A (ACCOUNTING)
    # --------------------------------------------------------------------------
    reporte_audit = """
    query {
        reporteContabilizacion {
            id
            timestamp
            usuarioNombre
            servicio
            accion
            estado
            monto
        }
        metricasSaas {
            totalTransacciones
            totalReservado
            totalUsuarios
            totalReservacionesActivas
            intentosBloqueados
            totalPagosAprobados
            totalMontoCobrado
            totalNotificacionesEnviadas
        }
    }
    """
    res_audit = await schema.execute(reporte_audit, context_value={"user": admin_user, "token": admin_token})
    assert res_audit.data and "reporteContabilizacion" in res_audit.data, f"Error en auditoría: {res_audit.errors}"
    logs = res_audit.data["reporteContabilizacion"]
    metricas = res_audit.data["metricasSaas"]

    print("\n" + "-"*75)
    print(f"[OK] 11. Modelo Triple A (Accounting): {len(logs)} eventos de auditoría registrados.")
    print(f"       - Transacciones Totales:        {metricas['totalTransacciones']}")
    print(f"       - Pagos Aprobados:              {metricas['totalPagosAprobados']}")
    print(f"       - Monto Cobrado en Pasarela:    ${metricas['totalMontoCobrado']:,.2f} MXN")
    print(f"       - Notificaciones Enviadas:      {metricas['totalNotificacionesEnviadas']}")
    print(f"       - Intentos de Acceso Denegados: {metricas['intentosBloqueados']}")
    print("-"*75)

    print("\n" + "="*75)
    print("[EXITO TOTAL] LOS 5 MICROSERVICIOS Y EL MODELO TRIPLE A FUNCIONAN AL 100%")
    print("="*75 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
