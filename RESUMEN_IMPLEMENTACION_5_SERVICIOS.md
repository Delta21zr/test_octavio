# 📋 Resumen Completo de Implementación: Los 5 Microservicios, Bus de Mensajes (ESB) y Modelo Triple A

**Universidad Politécnica de Durango**  
**Materia:** Inteligencia Artificial / Arquitectura Orientada a Servicios (SOA / SaaS)  
**Docente:** Florentino Octavio Mejía Rosales  
**Alumno:** Salvador Rivera Delgado (Grupo B - Semestre 8)  
**Proyecto:** Sistema de Reservaciones Hoteleras con Base de Datos MySQL (XAMPP)

---

## 🎯 1. ¿Qué se solicitó y cuál era la situación inicial?

El proyecto contaba inicialmente con **2 servicios** (`Usuarios` y `Reservaciones`, teniendo los recursos del catálogo mezclados).  
A partir del documento oficial del **"Sistema de reservaciones"** (10 páginas del profesor Octavio), se solicitó incorporar **los otros 3 servicios restantes** para completar la arquitectura de microservicios:
1. **Servicio de Catálogo** (antes no estaba formalmente separado como microservicio independiente).
2. **Servicio de Pagos** (nuevo).
3. **Servicio de Notificaciones** (nuevo).
4. El **Bus de Mensajes Empresarial (ESB / Broker Pub/Sub)** para la comunicación asíncrona entre servicios.

---

## 🛠️ 2. Resumen de Archivos Creados y Modificados

| Archivo | Tipo de Cambio | Descripción del Trabajo Realizado |
|---|---|---|
| [`event_bus.py`](file:///c:/xampp/htdocs/Octavio/event_bus.py) | **Creado** | Implementación del **Bus de Mensajes / Broker asíncrono** (RabbitMQ/Kafka en memoria) con patrón Pub/Sub. Gestiona eventos: `ReservacionCreada`, `PagoConfirmado`, `ReservacionCancelada` y `PagoReembolsado`. |
| [`services/catalogo.py`](file:///c:/xampp/htdocs/Octavio/services/catalogo.py) | **Creado** | **Servicio 2 (Catálogo):** Gestiona inventario de habitaciones, suites, salones y tarifas. Expone queries `recursos(filtro)`, `recurso(id)` y mutaciones protegidas para admin (`crearRecurso`, `actualizarRecurso`, `eliminarRecurso`). Aplica control RBAC con bloqueo 403 a clientes. |
| [`services/pagos.py`](file:///c:/xampp/htdocs/Octavio/services/pagos.py) | **Creado** | **Servicio 4 (Pagos):** Pasarela de pagos externa simulada (Tarjeta, PayPal, SPEI). Emite comprobantes `PAG-2026-XXXX`, publica evento `PagoConfirmado` en el bus y procesa reembolsos de estancias canceladas. |
| [`services/notificaciones.py`](file:///c:/xampp/htdocs/Octavio/services/notificaciones.py) | **Creado** | **Servicio 5 (Notificaciones):** Despacha correos electrónicos y SMS automáticos. **No tiene mutaciones públicas:** se activa 100% como consumidor de eventos del Bus de Mensajes. Permite consultar `historialNotificaciones` (admin) y `misNotificaciones` (cliente). |
| [`services/reservaciones.py`](file:///c:/xampp/htdocs/Octavio/services/reservaciones.py) | **Actualizado** | Se desacopló del catálogo; ahora las reservaciones **nacen en estado `PENDIENTE`** (según página 8 del PDF) y cambian a **`CONFIRMADA`** automáticamente al recibir el evento `PagoConfirmado` del Bus. Al cancelarse, emite `ReservacionCancelada`. |
| [`schema.py`](file:///c:/xampp/htdocs/Octavio/schema.py) | **Actualizado** | Actúa como el **API Gateway GraphQL unificado**. Hereda las queries y mutations de los 5 microservicios (`Usuarios`, `Catálogo`, `Reservaciones`, `Pagos`, `Notificaciones`) más el módulo de Contabilización AAA. |
| [`data/db.py`](file:///c:/xampp/htdocs/Octavio/data/db.py) | **Actualizado** | Persistencia híbrida en MySQL (XAMPP phpMyAdmin) y memoria RAM. Se agregaron las tablas relacionales y diccionarios para `pagos` y `notificaciones`, funciones CRUD completas y datos semilla. |
| [`database.sql`](file:///c:/xampp/htdocs/Octavio/database.sql) | **Actualizado** | Script SQL DDL/DML con las 7 tablas del sistema: `hoteles`, `usuarios`, `recursos`, `reservaciones`, `pagos`, `notificaciones` y `auditoria`. |
| [`accounting.py`](file:///c:/xampp/htdocs/Octavio/accounting.py) | **Actualizado** | Módulo de **Contabilización (Accounting - Triple A)** adaptado para auditar eventos operacionales y financieros de los 5 microservicios en MySQL, calculando métricas SaaS en tiempo real. |
| [`static/index.html`](file:///c:/xampp/htdocs/Octavio/static/index.html) | **Actualizado** | Interfaz web interactiva con: Centro de Notificaciones con badge 🔔, Pasarela de Pagos 💳, botón de Admin para agregar habitaciones al Catálogo ➕, y **Panel SOA & Triple A** con el diagrama oficial de la página 6 del PDF. |
| [`static/app.js`](file:///c:/xampp/htdocs/Octavio/static/app.js) | **Actualizado** | Lógica en JavaScript para interactuar con todas las operaciones GraphQL de los 5 microservicios, modal de pago, campanita de notificaciones en vivo y pruebas de seguridad RBAC. |
| [`static/style.css`](file:///c:/xampp/htdocs/Octavio/static/style.css) | **Actualizado** | Estilos visuales para las tarjetas de recursos, badges de estado (`PENDIENTE`, `CONFIRMADA`, `CANCELADA`), selector de métodos de pago y el diagrama de bloques SOA. |
| [`test_services.py`](file:///c:/xampp/htdocs/Octavio/test_services.py) | **Actualizado** | Suite de pruebas automatizadas que valida integralmente en consola el funcionamiento de los 5 microservicios, el paso de mensajes asíncronos y la auditoría Triple A (**100% de pruebas aprobadas**). |
| [`GUIA_PRESENTACION_TRIPLE_A.md`](file:///c:/xampp/htdocs/Octavio/GUIA_PRESENTACION_TRIPLE_A.md) | **Actualizado** | Guía de exposición para la revisión con el profesor Octavio, guión paso a paso y explicación teórica de SOA, SaaS y Triple A. |

---

## 🧩 3. Detalle de los 5 Microservicios Implementados

### 1. Servicio de Usuarios (`services/usuarios.py`)
- **Responsabilidad:** Registro, autenticación y emisión de identidad digital.
- **Operaciones:** `iniciarSesion`, `registrarUsuario`, `miPerfil`, `usuarios`.
- **Triple A:** Emite tokens **JWT** (`HS256`). Define roles `cliente` y `administrador`.

### 2. Servicio de Catálogo (`services/catalogo.py`)
- **Responsabilidad:** Administrar los recursos reservables (habitaciones de lujo, dobles, mesas de restaurante, salones de conferencias) y tarifas vigentes.
- **Operaciones:**
  * `recursos(filtro, hotelId, tipo, maxTarifa, minCapacidad)`: Consulta pública con filtros dinámicos.
  * `recurso(id)`: Consulta individual de amenidades y tarifa.
  * `crearRecurso(input)`: Alta de nuevas habitaciones (solo administradores).
  * `actualizarRecurso(id, input)`: Modificación de precios/inventario (solo admin).
  * `eliminarRecurso(id)`: Retiro de habitaciones (solo admin).
- **Triple A:** Control de acceso por roles (**RBAC**). Si un cliente intenta crear o editar un recurso, el sistema arroja **error 403 Forbidden** y audita el intento.

### 3. Servicio de Reservaciones (`services/reservaciones.py`)
- **Responsabilidad:** Ciclo de vida de las reservaciones, cálculo de noches/tarifas y control de empalmes.
- **Operaciones:**
  * `disponibilidad(recursoId, desde, hasta)`: Comprobación de traslapes en tiempo real.
  * `crearReservacion(input)`: Crea la reserva en estado inicial **`PENDIENTE`** y publica el evento `ReservacionCreada`.
  * `modificarReservacion(id, input)`: Ajusta fechas y huéspedes.
  * `cancelarReservacion(id)`: Anula la estancia y publica `ReservacionCancelada`.
  * `misReservaciones`, `todasReservaciones`: Vistas filtradas por propiedad o rol.
- **Regla Clave (Pág 8):** Permanece en `PENDIENTE` hasta recibir el evento `PagoConfirmado` desde el Bus de Mensajes, momento en que cambia a **`CONFIRMADA`**.

### 4. Servicio de Pagos (`services/pagos.py`)
- **Responsabilidad:** Cobro de anticipos o totales mediante pasarela de pagos simulada (Tarjeta de Crédito, PayPal, Transferencia SPEI) y reembolsos.
- **Operaciones:**
  * `pagarReservacion(input)`: Cobra el monto, emite comprobante oficial `PAG-2026-XXXX`, cambia el estado del pago a `APROBADO` y publica el evento `PagoConfirmado` en el Bus.
  * `pago(reservacionId)`: Consulta del comprobante y estado de liquidación de una reserva.
  * `reembolsarPago(pagoId, motivo)`: Emite reintegro de fondos y publica `PagoReembolsado`.
  * `misPagos`, `todosPagos`: Historial de cobros.
- **Triple A:** Valida pertenencia de la reserva (**Ownership Check**) para impedir pagar reservas ajenas, y audita los montos recaudados en MySQL.

### 5. Servicio de Notificaciones (`services/notificaciones.py`)
- **Responsabilidad:** Envío de correos electrónicos y SMS automáticos al reaccionar a eventos asíncronos del bus.
- **Endpoints Públicos:** **Ninguna mutación pública** (cumpliendo al 100% con la tabla de la página 7 del PDF: *"Ninguna; se activa por eventos"*).
- **Operaciones de Lectura:**
  * `historialNotificaciones`: Exclusivo para administradores (auditoría de envíos).
  * `misNotificaciones`: Bandeja de entrada personal del huésped en sesión.
- **Reacción a Eventos del Bus:**
  * Ante `ReservacionCreada` ➔ Envía correo con el folio registrado en espera de pago.
  * Ante `PagoConfirmado` ➔ Envía correo con comprobante de pago y confirmación oficial.
  * Ante `ReservacionCancelada` ➔ Envía correo informando la cancelación de la estancia.
  * Ante `PagoReembolsado` ➔ Envía SMS con folio de reintegro monetario.

---

## 🔄 4. Arquitectura de Comunicación Asíncrona (Bus de Mensajes)

Implementado en [`event_bus.py`](file:///c:/xampp/htdocs/Octavio/event_bus.py) según el diagrama de la **página 6** del documento de Octavio:

```text
               ┌────────────────────────┐
               │  Cliente Web / Móvil   │
               └───────────┬────────────┘
                           │ (POST /graphql)
                           ▼
               ┌────────────────────────┐
               │   API Gateway GraphQL  │
               └───────────┬────────────┘
                           │
       ┌───────────────┬───┴───────────┬───────────────┐
       ▼               ▼               ▼               ▼
 ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
 │ Usuarios  │   │ Catálogo  │   │Reservas   │   │   Pagos   │
 └───────────┘   └───────────┘   └─────┬─────┘   └─────┬─────┘
                                       │               │
                                       ▼               ▼
                        ┌─────────────────────────────────────┐
                        │ Bus de Mensajes Empresarial (ESB)   │
                        │ Broker: RabbitMQ / Apache Kafka     │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼ (Eventos asíncronos)
                                ┌─────────────────────┐
                                │   Notificaciones    │
                                │   (Email y SMS)     │
                                └─────────────────────┘
```

---

## 🧪 5. Resultados de Pruebas Automatizadas

Al ejecutar `python test_services.py` en la consola del proyecto:

```text
===========================================================================
EJECUTANDO PRUEBAS DE LOS 5 MICROSERVICIOS (ARQUITECTURA SOA / SAAS)
===========================================================================
[OK] 1. Servicio de Usuarios: Token JWT emitido para Administrador
[OK] 2. Servicio de Usuarios: Token JWT emitido para Cliente (Juan)
[OK] 3. Servicio de Catálogo: Consulta filtrada retornó recursos de lujo
[OK] 4. Servicio de Catálogo: Admin dio de alta nuevo recurso (ID: r-07ff)
[OK] 5. Control de Acceso Catálogo: Intento de cliente denegado -> Error 403 Forbidden
[OK] 6. Servicio de Reservaciones: Folio creado en estado inicial 'PENDIENTE'
[OK] 7. Servicio de Pagos: Cobro aprobado ($16,500.00 MXN) | Comprobante: PAG-2026-XXXX
[OK] 8. Integración Asíncrona (ESB): Reserva cambió a 'CONFIRMADA' tras PagoConfirmado
[OK] 9. Servicio de Notificaciones: Cliente recibió avisos automáticos vía Bus de Mensajes
[OK] 10. Flujo Completo: Cancelación detonó reembolso en Pagos y aviso en Notificaciones
[OK] 11. Modelo Triple A: 120 eventos registrados en la tabla 'auditoria' de MySQL.
===========================================================================
[EXITO TOTAL] LOS 5 MICROSERVICIOS Y EL MODELO TRIPLE A FUNCIONAN AL 100%
===========================================================================
```

---

## 🚀 6. ¿Cómo presentarlo o probarlo?

1. **Iniciar el servidor:**  
   Haz doble clic en `iniciar_servidor.bat` o ejecuta en consola:
   ```bash
   python main.py
   ```
2. **Abrir en el navegador:**
   - Interfaz Web: `http://localhost:8000`
   - GraphiQL Console: `http://localhost:8000/graphql`
   - phpMyAdmin: `http://localhost/phpmyadmin` (Base de datos: `hotel_reservaciones`)
3. **Puntos clave a mostrar al profesor:**
   - **Catálogo:** Filtros por destino/tipo y botón de administrador para dar de alta recursos.
   - **Reservación:** Reservar y mostrar cómo nace en **`PENDIENTE`**.
   - **Pago:** Presionar **`💳 Pagar Ahora`**, liquidar en la pasarela y ver cómo la reservación cambia inmediatamente a **`CONFIRMADA`** con comprobante `PAG-2026-XXXX`.
   - **Notificaciones:** Clic en la campanita 🔔 para ver los correos y SMS automáticos disparados por el bus.
   - **Panel SOA & Triple A:** Clic en **`🛡️ Panel SOA & AAA (Profesor)`** para ver el diagrama de arquitectura, validación de JWT, bloqueo 403 (RBAC) y la bitácora contable en MySQL.
