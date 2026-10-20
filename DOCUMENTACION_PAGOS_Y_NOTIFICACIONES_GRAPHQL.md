# DOCUMENTACIÓN TÉCNICA: SERVICIOS DE PAGOS Y NOTIFICACIONES EN GRAPHQL
## Sistema de Gestión y Reservaciones Hoteleras — "Hoteles Paraíso"
**Proyecto Universitario de Arquitectura de Software y Microservicios**  
**Alumno:** Salvador Rivera  
**Profesor:** Florentino Octavio Mejía Rosales  
**Tecnologías Principales:** Python 3.13, FastAPI, Strawberry GraphQL, MySQL (XAMPP phpMyAdmin), Bus de Eventos Asíncrono (EDA), Vanilla JavaScript, CSS3.

---

## 1. INTRODUCCIÓN Y ARQUITECTURA GENERAL

El sistema está estructurado bajo una **Arquitectura Orientada a Servicios (SOA / Microservicios)** desacoplada a través de un **Bus de Eventos (Event-Driven Architecture - EDA)** y expuesta de manera unificada mediante una **API GraphQL** construida con **Strawberry** y **FastAPI**.

La persistencia de datos reside en el motor relacional **MySQL (XAMPP)** en la base de datos `hotel_reservaciones`.

```
                    ┌────────────────────────────────────────────────────────┐
                    │            NAVEGADOR CLIENTE (Frontend Web)            │
                    │   Vanilla JS (app.js) • Fetch API • Token JWT Bearer   │
                    └───────────────────────────┬────────────────────────────┘
                                                │ HTTP POST /graphql
                                                ▼
                    ┌────────────────────────────────────────────────────────┐
                    │               API GATEWAY / GRAPHQL ENGINE             │
                    │           (FastAPI + Strawberry GraphQL Router)        │
                    │       Validación de Token JWT • Contexto de Seguridad  │
                    └───────┬────────────────────────────┬───────────────────┘
                            │                            │
             ┌──────────────┴──────────────┐      ┌──────┴──────────────────────┐
             │ SERVICIO 4: PAGOS           │      │ SERVICIO 5: NOTIFICACIONES  │
             │ (Accounting / Pasarela AAA) │      │ (Email / SMS Dispatcher)    │
             └──────────────┬──────────────┘      └──────────────┬──────────────┘
                            │                                    ▲
                            │ Publica Evento                     │ Escucha Evento
                            ▼                                    │
    ╔═════════════════════════════════════════════════════════════════════════════╗
    ║                     BUS DE EVENTOS (EventBus Pub/Sub)                       ║
    ║   Eventos: "PagoConfirmado", "ReservacionCancelada", "PagoReembolsado"      ║
    ╚═════════════════════════════════════════════════════════════════════════════╝
                            │                                    │
                            ▼                                    ▼
    ╔═════════════════════════════════════════════════════════════════════════════╗
    ║                      BASE DE DATOS RELACIONAL (MySQL)                       ║
    ║     Tablas: `pagos` • `notificaciones` • `auditoria` • `reservaciones`      ║
    ╚═════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. SERVICIO 4: PAGOS Y CONTABILIDAD (ACCOUNTING)

### 2.1. Propósito y Modelo Contable
El Servicio de Pagos se encarga del registro financiero, aprobación de transacciones y conciliación en MySQL (cumpliendo con la tercera **A** del modelo de seguridad **AAA: Accounting / Contabilidad**).

1. Al generarse una reservación, su estado inicial es `PENDIENTE` (habitación apartada temporalmente).
2. El huésped realiza el pago en la pasarela seleccionando un método de pago (`TARJETA`, `TRANSFERENCIA`, `PAYPAL` o `EFECTIVO`).
3. La mutación `pagarReservacion` registra la transacción en la tabla `pagos` de MySQL, cambia el estado de la reservación a `CONFIRMADA`, registra la auditoría y dispara el evento `PagoConfirmado`.
4. El Bus de Eventos notifica al Servicio 5 (Notificaciones), el cual despacha el comprobante de pago al huésped.

---

### 2.2. Mutación GraphQL: `pagarReservacion`

#### Petición GraphQL (Request):
```graphql
mutation PagarReserva($reservacionId: ID!, $metodoPago: MetodoPago!, $monto: Float!) {
  pagarReservacion(
    reservacionId: $reservacionId
    metodoPago: $metodoPago
    monto: $monto
  ) {
    id
    reservacionId
    monto
    metodoPago
    estado
    referencia
    fechaPago
  }
}
```

#### Variables JSON enviadas por el Frontend:
```json
{
  "reservacionId": "res-101",
  "metodoPago": "TARJETA",
  "monto": 8400.00
}
```

#### Respuesta GraphQL del Backend (Response):
```json
{
  "data": {
    "pagarReservacion": {
      "id": "pago-9a8b7c6d",
      "reservacionId": "res-101",
      "monto": 8400.0,
      "metodoPago": "TARJETA",
      "estado": "APROBADO",
      "referencia": "TXN-2026-F4B1A8",
      "fechaPago": "2026-10-15T22:15:30.123456"
    }
  }
}
```

#### ¿Qué ocurre internamente en el Backend?:
1. **Autenticación (AAA):** Se valida el JWT del usuario en `info.context["user"]`.
2. **Autorización (RBAC):** Se valida que la reservación pertenezca al usuario autenticado (o que sea un Administrador).
3. **Persistencia MySQL:**
   - Se ejecuta: `INSERT INTO pagos (id, reservacion_id, monto, metodo_pago, estado, referencia, fecha_pago) VALUES (...)`.
   - Se ejecuta: `UPDATE reservaciones SET estado = 'CONFIRMADA' WHERE id = ...`.
   - Se ejecuta: `INSERT INTO auditoria (...)` registrando la acción contable.
4. **Despacho al Bus de Eventos:**
   ```python
   EventBus.publish("PagoConfirmado", {
       "pago_id": nuevo_pago.id,
       "reservacion_id": reservacion_id,
       "monto": monto,
       "usuario_id": user["id"],
       "referencia": nuevo_pago.referencia
   })
   ```

---

### 2.3. Query GraphQL: `misPagos` y `historialPagos`

Permite a los huéspedes descargar su historial de pagos y facturas, mientras que el administrador puede auditar todos los ingresos del sistema.

#### Petición GraphQL:
```graphql
query ObtenerPagos {
  misPagos {
    id
    reservacionId
    monto
    metodoPago
    estado
    referencia
    fechaPago
  }
}
```

#### Respuesta JSON:
```json
{
  "data": {
    "misPagos": [
      {
        "id": "pago-9a8b7c6d",
        "reservacionId": "res-101",
        "monto": 8400.0,
        "metodoPago": "TARJETA",
        "estado": "APROBADO",
        "referencia": "TXN-2026-F4B1A8",
        "fechaPago": "2026-10-15T22:15:30"
      }
    ]
  }
}
```

---

## 3. SERVICIO 5: NOTIFICACIONES MULTICANAL (EMAIL & SMS)

### 3.1. Propósito y Arquitectura Reactiva (Pub/Sub)
El Servicio de Notificaciones está 100% **desacoplado** del flujo transaccional. No es invocado manualmente por el usuario al pagar o reservar; reacciona de manera autónoma ante los eventos emitidos por el sistema:

| Evento Publicado | Disparador (Origen) | Canal Emitido | Contenido del Mensaje |
| :--- | :--- | :--- | :--- |
| **`ReservacionCreada`** | Servicio de Reservaciones | Email + SMS | Folio generado, fechas y recordatorio de pagar en los próximos 15 minutos. |
| **`PagoConfirmado`** | Servicio de Pagos | Email | Confirmación de pago aprobado, folio y comprobante digital con código TXN. |
| **`ReservacionCancelada`** | Servicio de Reservaciones | Email + SMS | Notificación de anulación de reserva, liberación de habitación y aviso de reembolso emitido. |

---

### 3.2. Query GraphQL: `misNotificaciones` (Huésped) y `historialNotificaciones` (Administrador)

#### Petición GraphQL para Huéspedes:
```graphql
query ConsultarBandeja {
  misNotificaciones {
    id
    canal
    destinatario
    asunto
    mensaje
    eventoOrigen
    fechaEnvio
  }
}
```

#### Petición GraphQL para el Administrador (Supervisión Global):
```graphql
query AuditoriaNotificacionesGlobal {
  historialNotificaciones {
    id
    usuarioId
    canal
    destinatario
    asunto
    mensaje
    eventoOrigen
    fechaEnvio
  }
}
```

#### Respuesta JSON recibida en el Frontend:
```json
{
  "data": {
    "historialNotificaciones": [
      {
        "id": "notif-001",
        "usuarioId": "usr-1",
        "canal": "EMAIL",
        "destinatario": "juan@cliente.com",
        "asunto": "Comprobante de Pago Aprobado - RES-2026-E3CB",
        "mensaje": "Tu pago por $8,400.00 MXN ha sido aprobado exitosamente. Folio: RES-2026-E3CB. Referencia bancaria: TXN-2026-A1B2C3.",
        "eventoOrigen": "PagoConfirmado",
        "fechaEnvio": "2026-10-15T22:16:00"
      }
    ]
  }
}
```

---

### 3.3. Mutación GraphQL: `limpiarNotificaciones` (Eliminación en Lote)

Diseñada para permitir que el Administrador vacíe el historial global en MySQL o que un cliente limpie su propia bandeja de entrada.

#### Petición GraphQL:
```graphql
mutation LimpiarBandeja {
  limpiarNotificaciones {
    exito
    mensaje
    totalEliminadas
  }
}
```

#### Respuesta JSON:
```json
{
  "data": {
    "limpiarNotificaciones": {
      "exito": true,
      "mensaje": "Historial de notificaciones eliminado correctamente de la base de datos.",
      "totalEliminadas": 14
    }
  }
}
```

#### Ejecución en MySQL:
- Si el usuario tiene rol `administrador`:
  ```sql
  DELETE FROM notificaciones;
  ```
- Si el usuario es un `cliente`:
  ```sql
  DELETE FROM notificaciones WHERE usuario_id = 'usr-1';
  ```

---

### 3.4. Mutación GraphQL: `eliminarNotificacion` (Eliminación Individual)

#### Petición GraphQL:
```graphql
mutation EliminarUna($id: ID!) {
  eliminarNotificacion(id: $id) {
    exito
    mensaje
  }
}
```

---

## 4. CÓMO EL FRONTEND GENERA LAS PETICIONES GRAPHQL (JAVASCRIPT FETCH)

En la aplicación (`static/app.js`), todas las llamadas a GraphQL se realizan mediante una función centralizada que inyecta automáticamente el token JWT en las cabeceras HTTP:

```javascript
// Función core para ejecutar cualquier Query o Mutation en GraphQL:
async graphql(query, variables = {}) {
  const headers = { "Content-Type": "application/json" };
  
  // Propagación de Identidad y Seguridad AAA mediante Token JWT:
  if (this.token) {
    headers["Authorization"] = `Bearer ${this.token}`;
  }

  const response = await fetch("/graphql", {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      query: query,
      variables: variables
    })
  });

  return await response.json();
}
```

### Ejemplo real de ejecución de Pago desde el Botón de la Pasarela:
```javascript
async ejecutarPagoPasarela(reservacionId, metodoPago, monto) {
  const mutation = `
    mutation Pagar($reservacionId: ID!, $metodoPago: MetodoPago!, $monto: Float!) {
      pagarReservacion(reservacionId: $reservacionId, metodoPago: $metodoPago, monto: $monto) {
        id
        referencia
        estado
      }
    }
  `;

  const res = await this.graphql(mutation, {
    reservacionId: reservacionId,
    metodoPago: metodoPago,
    monto: parseFloat(monto)
  });

  if (res.data?.pagarReservacion) {
    console.log("Pago exitoso. Folio de transacción:", res.data.pagarReservacion.referencia);
    // Refrescar notificaciones generadas por el EventBus
    await this.cargarNotificaciones();
  }
}
```

---

## 5. GUÍA PARA DEFENDER EL PROYECTO ANTE EL PROFESOR FLORENTINO OCTAVIO MEJÍA ROSALES

Si el profesor pregunta sobre los mecanismos internos del sistema, estas son las respuestas clave:

### 1. ¿Por qué usamos GraphQL en lugar de REST tradicional?
> **Respuesta:**  
> "En REST hubiéramos necesitado múltiples endpoints (`GET /api/reservas`, `POST /api/pagos`, `GET /api/notificaciones`) generando sobrecarga de peticiones y *over-fetching* (descargar campos innecesarios). Con **GraphQL** tenemos un único endpoint `/graphql` fuertemente tipado mediante esquemas de Strawberry. El frontend solicita exactamente los campos que necesita para renderizar la interfaz en una sola llamada de red."

---

### 2. ¿Cómo se comunican el Servicio de Pagos y el de Notificaciones?
> **Respuesta:**  
> "Están completamente desacoplados mediante el patrón **Pub/Sub (Publicador/Suscriptor) a través del Event Bus**. Cuando el Servicio de Pagos aprueba una transacción en MySQL, no llama directamente al código de Notificaciones. En su lugar, emite el evento `'PagoConfirmado'`. El Servicio de Notificaciones está suscrito a ese canal, escucha el evento y de forma asíncrona despacha el correo y SMS al cliente y persiste el mensaje en la tabla `notificaciones` de MySQL."

---

### 3. ¿Cómo se garantiza la seguridad en los pagos y la privacidad de las notificaciones?
> **Respuesta:**  
> "Implementamos el modelo **Triple A (AAA)**:
> 1. **Authentication (Autenticación):** Cada petición envía un token JWT en el encabezado `Authorization: Bearer <token>`.
> 2. **Authorization (Autorización / RBAC):** Los resolvers de Strawberry validan si el rol es `cliente` o `administrador`. Un cliente solo puede ver sus propios pagos y notificaciones (`WHERE usuario_id = user.id`); el administrador puede auditar todo.
> 3. **Accounting (Contabilidad / Auditoría):** Cada pago, cancelación o cambio de estado registra un asiento inmutable en la tabla `auditoria` y en la tabla `pagos` de MySQL con timestamps, IP y usuario responsable."

---

### 4. ¿Qué sucede en la Matriz PMS cuando el Administrador cancela una reservación?
> **Respuesta:**  
> "Al hacer clic en 'Cancelar Reservación' dentro de la Ficha Técnica de la habitación:
> 1. Se ejecuta la mutación `cancelarReservacion(id: $id)`.
> 2. Se actualiza el estado de la reservación a `CANCELADA` en MySQL.
> 3. Se publica el evento `'ReservacionCancelada'` en el Bus de Eventos.
> 4. El Servicio de Pagos detecta la cancelación y emite el reembolso correspondiente.
> 5. El Servicio de Notificaciones envía un SMS y correo al huésped informando la cancelación.
> 6. La habitación queda inmediatamente liberada (`🟢 Desocupada / Libre`), volviendo a estar disponible en tiempo real en la matriz del PMS y en el catálogo para nuevos huéspedes."
