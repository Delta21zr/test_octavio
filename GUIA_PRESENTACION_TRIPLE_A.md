# 🛡️ Guía del Proyecto: Sistema de Reservaciones con Arquitectura SOA (5 Microservicios) y Modelo Triple A (AAA)
**Universidad Politécnica de Durango**  
**Materia:** Inteligencia Artificial / Arquitectura Orientada a Servicios (SOA / SaaS)  
**Docente:** Florentino Octavio Mejía Rosales  
**Alumno:** Salvador Rivera Delgado (Grupo B - Semestre 8)  
**Unidad 3:** Arquitectura SaaS, Microservicios y Bus de Mensajes con Modelo Triple A  

---

## 📌 1. Resumen de la Asignación y Solución Completa

Tomando el documento oficial del **"Sistema de reservaciones"** (10 páginas), se ha implementado la arquitectura completa de **los 5 microservicios** desacoplados, coordinados a través de un **Bus de Mensajes Empresarial (ESB / Broker Pub/Sub)** e integrados bajo el modelo de seguridad **Triple A (AAA)**:
1. **Autenticación (Authentication)**
2. **Autorización (Authorization)**
3. **Contabilización (Accounting / Auditoría / Trazabilidad)**

---

## 🏗️ 2. Los 5 Microservicios del Documento Oficial

| # | Microservicio | Archivo | Responsabilidad Principal (Documento de Octavio) | Modelo Triple A |
|---|---|---|---|---|
| **1** | **Usuarios** | `services/usuarios.py` | Registra usuarios, autentica (`iniciarSesion`), gestiona roles (`cliente`, `administrador`) y emite el token de acceso JWT. | **Autenticación:** Emisión y firma HS256 de JWT. **Autorización:** RBAC. **Contabilización:** Auditoría de accesos. |
| **2** | **Catálogo** | `services/catalogo.py` | Administra el inventario de recursos reservables: nombre, tipo, capacidad, tarifas y fotos. Permite búsqueda con filtros. | **Autorización:** Solo administradores pueden crear, modificar o eliminar recursos (bloqueo 403 a clientes). |
| **3** | **Reservaciones** | `services/reservaciones.py` | Valida disponibilidad/empalmes, emite folios (`RES-2026-XXXX`). Las reservas nacen en estado **`PENDIENTE`** y pasan a **`CONFIRMADA`** al recibir el evento del bus. | **Autorización:** Ownership check (el cliente solo agenda y cancela a su propio nombre). |
| **4** | **Pagos** | `services/pagos.py` | Cobra anticipos o total a través de pasarela externa simulada (Tarjeta, PayPal, SPEI). Emite comprobante `PAG-2026-XXXX`, publica evento `PagoConfirmado` y procesa reembolsos. | **Contabilización:** Registro financiero de cobros y reintegros en MySQL. |
| **5** | **Notificaciones** | `services/notificaciones.py` | Despacha correos electrónicos y SMS automáticos. No tiene endpoints mutables públicos: **se activa 100% por eventos del Bus de Mensajes**. | **Autorización:** Historial global exclusivo para administradores. |

---

## 🔄 3. Bus de Mensajes Empresarial (ESB / Broker Pub/Sub)

Específico de las páginas 5 y 6 del documento: los microservicios se comunican asíncronamente mediante un broker de eventos (equivalente a RabbitMQ / Apache Kafka):

1. **`ReservacionCreada`**:
   - Publicado por: **Reservaciones** al crear una nueva reserva (estado `PENDIENTE`).
   - Consumido por: **Notificaciones** (envía email/SMS con el folio y monto adeudado).
2. **`PagoConfirmado`** *(Regla clave página 8)*:
   - Publicado por: **Pagos** tras aprobar la transacción con pasarela.
   - Consumido por:
     * **Reservaciones:** Cambia automáticamente la reserva de `PENDIENTE` a **`CONFIRMADA`**.
     * **Notificaciones:** Envía el comprobante oficial y bienvenida al cliente.
3. **`ReservacionCancelada`**:
   - Publicado por: **Reservaciones** al anular una estancia.
   - Consumido por:
     * **Pagos:** Procesa el reembolso económico automático.
     * **Notificaciones:** Avisa la anulación al cliente.
4. **`PagoReembolsado`**:
   - Publicado por: **Pagos** tras reintegrar los fondos.
   - Consumido por: **Notificaciones** (envía comprobante de reembolso por SMS).

---

## 🔐 4. ¿Cómo se Implementa la Triple A (AAA) en el Proyecto?

### 1. Autenticación (Authentication) — *¿Quién eres?*
* Tokens **JWT (JSON Web Tokens)** firmados con algoritmo criptográfico `HS256` y expiración programada.
* El API Gateway intercepta cada petición en `/graphql`, valida la firma y provee el usuario en el contexto de Strawberry.

### 2. Autorización (Authorization) — *¿Qué puedes hacer?*
* **Control de Acceso Basado en Roles (RBAC):**
  - **Rol `cliente`:** Solo puede reservar a su propio nombre, ver sus propias reservas y pagar sus propias estancias. No puede crear recursos en el catálogo ni ver historiales ajenos (bloqueo con error 403 Forbidden).
  - **Rol `administrador`:** Permiso de administración del catálogo (`crearRecurso`), consulta de todas las reservaciones, historial global de notificaciones y tablero de auditoría.
* **Validación de Propiedad (Ownership Check):** Si el usuario Juan intenta cancelar o pagar la reserva de María, el sistema rechaza la operación de inmediato y registra el incidente en la auditoría contable.

### 3. Contabilización (Accounting / Auditoría) — *¿Qué hiciste, cuándo y cuánto consumiste?*
* Bitácora persistida en la tabla `auditoria` de MySQL (XAMPP).
* Campos registrados: `id`, `timestamp`, `usuarioId`, `usuarioNombre`, `rol`, `servicio`, `accion`, `estado` (`EXITO`, `DENEGADO`, `FALLIDO`), `monto` y `detalle`.
* Métricas SaaS calculadas en tiempo real:
  - Total de transacciones auditadas.
  - Monto económico comprometido en reservas y recaudado en pagos.
  - Conteo de notificaciones enviadas vía broker.
  - Conteo de intentos de intrusión y accesos denegados.

---

## 🚀 5. Instrucciones para Ejecutar y Demostrar el Proyecto

### Opción A: Ejecución Directa (Doble Clic)
Haz doble clic sobre el archivo:
```text
iniciar_servidor.bat
```

### Opción B: Ejecución por Consola
Abre una terminal en `c:\xampp\htdocs\Octavio` y ejecuta:
```bash
python main.py
```

URLs de acceso:
* 🌐 **Interfaz Web Interactiva:** `http://localhost:8000`
* ⚡ **GraphiQL Playground:** `http://localhost:8000/graphql`
* 🗄️ **phpMyAdmin (MySQL XAMPP):** `http://localhost/phpmyadmin` (Base de datos: `hotel_reservaciones`)

### Opción C: Ejecución de Pruebas Automatizadas
Para verificar el paso de pruebas de los 5 microservicios en consola:
```bash
python test_services.py
```

---

## 🎯 6. Guión de Presentación para la Revisión con el Profesor Octavio

### Paso 1: Introducción de la Arquitectura (40 segundos)
> *"Profesor Octavio, para esta entrega implementamos la arquitectura completa de los **5 microservicios** especificados en nuestro documento de arquitectura del Sistema de Reservaciones: **Usuarios**, **Catálogo**, **Reservaciones**, **Pagos** y **Notificaciones**. Además, implementamos el **Bus de Mensajes Empresarial (ESB / Broker Pub/Sub)** para la comunicación asíncrona y el modelo de seguridad **Triple A**."*

### Paso 2: Demostración en la Interfaz Web (`http://localhost:8000`)
1. **Catálogo y Búsqueda (Servicio 2):**
   - Muestra las sedes hoteleras y el catálogo de habitaciones con filtros dinámicos (tipo, capacidad, tarifas).
2. **Crear Reservación (Servicio 3) & Estado PENDIENTE:**
   - Inicia sesión como **Juan Pérez (Cliente)**.
   - Elige una habitación y reserva.
   - Muestra cómo la reservación nace en estado **`PENDIENTE DE PAGO`** (como estipula la página 8 del documento).
3. **Pasarela de Pagos (Servicio 4) & Evento PagoConfirmado:**
   - Haz clic en el botón **"💳 Pagar Ahora"**.
   - Selecciona Tarjeta de Crédito, PayPal o Transferencia y confirma el pago.
   - Muestra el comprobante oficial generado (`PAG-2026-XXXX`).
   - Muestra cómo la reservación cambió automáticamente a **`CONFIRMADA`** gracias al evento asíncrono `PagoConfirmado` recibido por el bus de mensajes.
4. **Centro de Notificaciones (Servicio 5):**
   - Haz clic en el icono de la campana 🔔 en el navbar.
   - Muestra los correos electrónicos y SMS despachados automáticamente por el bus ante cada evento (`ReservacionCreada`, `PagoConfirmado`).

### Paso 3: Demostración del Panel SOA y Triple A
1. Haz clic en el botón **"🛡️ Panel SOA & AAA (Profesor)"**:
   - **Pestaña 1 (Arquitectura SOA):** Muestra el diagrama oficial de la página 6 que conecta el Cliente con el API Gateway GraphQL, los microservicios y el Bus de Mensajes.
   - **Pestaña 2 (Autenticación JWT):** Muestra el token activo y el payload decodificado.
   - **Pestaña 3 (Autorización RBAC):** Presiona los botones de prueba:
     * *Cliente intentando dar de alta habitación en Catálogo* ➔ **Bloqueo 403 Forbidden**.
     * *Cliente intentando cancelar reserva ajena* ➔ **Bloqueo de propiedad**.
   - **Pestaña 4 (Contabilización):** Muestra las métricas SaaS en tiempo real y la bitácora inmutable de eventos guardada en MySQL.

---

## 📂 7. Estructura de Archivos del Proyecto

```text
c:\xampp\htdocs\Octavio\
├── main.py                     # Servidor FastAPI + API Gateway GraphQL (Strawberry)
├── schema.py                   # Esquema GraphQL unificado (5 Microservicios + AAA)
├── event_bus.py                # Bus de Mensajes Empresarial (ESB / Broker Pub/Sub)
├── security.py                 # Módulo de Autenticación JWT y Autorización RBAC
├── accounting.py               # Módulo de Contabilización (Auditoría MySQL y Métricas SaaS)
├── database.sql                # Script DDL/DML con tablas para los 5 microservicios
├── test_services.py            # Suite de pruebas automatizadas de los 5 microservicios
├── iniciar_servidor.bat        # Lanzador para Windows
├── GUIA_PRESENTACION_TRIPLE_A.md # Guía escolar para la revisión
├── data/
│   └── db.py                   # Persistencia híbrida (MySQL XAMPP + Caché en RAM)
├── services/
│   ├── usuarios.py             # Servicio 1: Usuarios (Login, Registro, JWT)
│   ├── catalogo.py             # Servicio 2: Catálogo (Recursos, Tarifas, Búsqueda)
│   ├── reservaciones.py        # Servicio 3: Reservaciones (Disponibilidad, Folios)
│   ├── pagos.py                # Servicio 4: Pagos (Pasarela, Comprobantes, Reembolsos)
│   └── notificaciones.py        # Servicio 5: Notificaciones (Correos y SMS asíncronos)
└── static/
    ├── index.html              # Interfaz web interactiva del sistema
    ├── style.css               # Estilos y diseño del sistema hotelero
    └── app.js                  # Lógica cliente para interactuar con GraphQL y el Bus
```
