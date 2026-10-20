-- ==============================================================================
-- BASE DE DATOS: hotel_reservaciones
-- PROYECTO: Sistema de Reservaciones (SOA / SaaS con Modelo Triple A - 5 Servicios)
-- DOCENTE: Florentino Octavio Mejia Rosales
-- ALUMNO: Salvador Rivera Delgado (Semestre 8 - Grupo B)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `hotel_reservaciones` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `hotel_reservaciones`;

-- ==============================================================================
-- 1. TABLA: hoteles (Sedes y Destinos Hoteleros)
-- ==============================================================================
DROP TABLE IF EXISTS `hoteles`;
CREATE TABLE `hoteles` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `nombre` VARCHAR(100) NOT NULL,
    `ubicacion` VARCHAR(100) NOT NULL,
    `descripcion` TEXT,
    `foto` VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `hoteles` (`id`, `nombre`, `ubicacion`, `descripcion`, `foto`) VALUES
('h-1', 'Hotel Paraíso Playa', 'Cancún, Quintana Roo', 'Resort frente al mar con acceso directo a playa privada, albercas y restaurante de mariscos.', 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80'),
('h-2', 'Hotel Paraíso Bosque Real', 'Mazamitla, Jalisco', 'Cabañas de descanso rodeadas de bosque y naturaleza, con chimenea y fogateros.', 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80'),
('h-3', 'Hotel Paraíso Centro', 'Guadalajara, Jalisco', 'Hotel moderno en el corazón de la ciudad, ideal para viajes ejecutivos y eventos.', 'https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80');

-- ==============================================================================
-- 2. TABLA: usuarios (Servicio 1: Usuarios - Triple A)
-- ==============================================================================
DROP TABLE IF EXISTS `usuarios`;
CREATE TABLE `usuarios` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `nombre` VARCHAR(100) NOT NULL,
    `correo` VARCHAR(100) NOT NULL UNIQUE,
    `password` VARCHAR(100) NOT NULL,
    `rol` VARCHAR(20) NOT NULL DEFAULT 'cliente',
    `creadoEn` VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `usuarios` (`id`, `nombre`, `correo`, `password`, `rol`, `creadoEn`) VALUES
('u-101', 'Salvador Rivera (Admin)', 'admin@hotel.com', '123', 'administrador', '2026-01-15T09:00:00'),
('u-102', 'Juan Pérez (Cliente)', 'juan@cliente.com', '123', 'cliente', '2026-02-10T14:30:00'),
('u-103', 'María López (Cliente)', 'maria@cliente.com', '123', 'cliente', '2026-03-01T11:20:00');

-- ==============================================================================
-- 3. TABLA: recursos (Servicio 2: Catálogo de Recursos Reservables)
-- ==============================================================================
DROP TABLE IF EXISTS `recursos`;
CREATE TABLE `recursos` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `hotelId` VARCHAR(50) NOT NULL,
    `nombre` VARCHAR(100) NOT NULL,
    `tipo` VARCHAR(50) NOT NULL,
    `capacidad` INT NOT NULL DEFAULT 2,
    `tarifa` DECIMAL(10,2) NOT NULL,
    `descripcion` TEXT,
    `foto` VARCHAR(255),
    CONSTRAINT `fk_recursos_hotel` FOREIGN KEY (`hotelId`) REFERENCES `hoteles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `recursos` (`id`, `hotelId`, `nombre`, `tipo`, `capacidad`, `tarifa`, `descripcion`, `foto`) VALUES
('r-12', 'h-1', 'Suite Frente al Mar', 'HABITACION_LUJO', 4, 2500.00, 'Cama King Size, jacuzzi privado, vista panorámica al mar y desayuno incluido.', 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80'),
('r-14', 'h-1', 'Habitación Doble Playa', 'HABITACION_DOBLE', 2, 1400.00, 'Dos camas matrimoniales, aire acondicionado, balcón con vista parcial a la alberca.', 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=800&q=80'),
('r-20', 'h-1', 'Mesa Terraza Marítima', 'RESTAURANTE_MESA', 6, 500.00, 'Mesa en terraza al aire libre con vista al atardecer frente a la playa.', 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80'),
('r-16', 'h-2', 'Cabaña Familiar Bosque', 'HABITACION_LUJO', 6, 3200.00, 'Cabaña rústica de dos pisos con chimenea de leña, sala y vista a los pinos.', 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80'),
('r-18', 'h-2', 'Habitación Rústica Deluxe', 'HABITACION_DOBLE', 2, 1600.00, 'Acabados en madera, cama Queen, calefacción y terraza privada.', 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80'),
('r-25', 'h-3', 'Salón de Eventos Ejecutivo', 'SALON_EVENTOS', 50, 6500.00, 'Espacio climatizado con proyector, audio y mobiliario para conferencias.', 'https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=800&q=80');

-- ==============================================================================
-- 4. TABLA: reservaciones (Servicio 3: Reservaciones)
-- ==============================================================================
DROP TABLE IF EXISTS `reservaciones`;
CREATE TABLE `reservaciones` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `folio` VARCHAR(50) NOT NULL UNIQUE,
    `usuarioId` VARCHAR(50) NOT NULL,
    `recursoId` VARCHAR(50) NOT NULL,
    `fechaInicio` VARCHAR(50) NOT NULL,
    `fechaFin` VARCHAR(50) NOT NULL,
    `personas` INT NOT NULL DEFAULT 1,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    `total` DECIMAL(10,2) NOT NULL,
    `creadoEn` VARCHAR(50),
    CONSTRAINT `fk_reservas_usuario` FOREIGN KEY (`usuarioId`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_reservas_recurso` FOREIGN KEY (`recursoId`) REFERENCES `recursos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `reservaciones` (`id`, `folio`, `usuarioId`, `recursoId`, `fechaInicio`, `fechaFin`, `personas`, `estado`, `total`, `creadoEn`) VALUES
('res-1', 'RES-2026-001', 'u-102', 'r-12', '2026-10-18T15:00:00', '2026-10-21T12:00:00', 2, 'CONFIRMADA', 7500.00, '2026-10-01T10:00:00'),
('res-2', 'RES-2026-002', 'u-103', 'r-14', '2026-10-22T15:00:00', '2026-10-24T12:00:00', 2, 'PENDIENTE', 2800.00, '2026-10-02T16:20:00');

-- ==============================================================================
-- 5. TABLA: pagos (Servicio 4: Pagos y Reembolsos)
-- ==============================================================================
DROP TABLE IF EXISTS `pagos`;
CREATE TABLE `pagos` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `reservacionId` VARCHAR(50) NOT NULL,
    `usuarioId` VARCHAR(50) NOT NULL,
    `monto` DECIMAL(10,2) NOT NULL,
    `metodoPago` VARCHAR(50) NOT NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'APROBADO',
    `comprobante` VARCHAR(50) NOT NULL UNIQUE,
    `fecha` VARCHAR(50) NOT NULL,
    CONSTRAINT `fk_pagos_reservacion` FOREIGN KEY (`reservacionId`) REFERENCES `reservaciones` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pagos_usuario` FOREIGN KEY (`usuarioId`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `pagos` (`id`, `reservacionId`, `usuarioId`, `monto`, `metodoPago`, `estado`, `comprobante`, `fecha`) VALUES
('pag-1', 'res-1', 'u-102', 7500.00, 'TARJETA_CREDITO', 'APROBADO', 'PAG-2026-A101', '2026-10-01T10:05:00');

-- ==============================================================================
-- 6. TABLA: notificaciones (Servicio 5: Notificaciones vía Bus de Eventos)
-- ==============================================================================
DROP TABLE IF EXISTS `notificaciones`;
CREATE TABLE `notificaciones` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `usuarioId` VARCHAR(50) NOT NULL,
    `canal` VARCHAR(20) NOT NULL DEFAULT 'EMAIL',
    `destinatario` VARCHAR(100) NOT NULL,
    `asunto` VARCHAR(150) NOT NULL,
    `mensaje` TEXT NOT NULL,
    `eventoOrigen` VARCHAR(50) NOT NULL,
    `fechaEnvio` VARCHAR(50) NOT NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'ENVIADO',
    CONSTRAINT `fk_notif_usuario` FOREIGN KEY (`usuarioId`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `notificaciones` (`id`, `usuarioId`, `canal`, `destinatario`, `asunto`, `mensaje`, `eventoOrigen`, `fechaEnvio`, `estado`) VALUES
('notif-1', 'u-102', 'EMAIL', 'juan@cliente.com', 'Confirmación de Reservación RES-2026-001', 'Estimado Juan Pérez, tu reservación en Suite Frente al Mar ha sido confirmada con éxito. Pago procesado: $7,500.00 MXN.', 'PagoConfirmado', '2026-10-01T10:06:00', 'ENVIADO'),
('notif-2', 'u-103', 'SMS', 'maria@cliente.com', 'Reservación Pendiente de Pago RES-2026-002', 'Hola María López, tu reservación RES-2026-002 está registrada. Por favor realiza tu pago para confirmarla.', 'ReservacionCreada', '2026-10-02T16:21:00', 'ENVIADO');

-- ==============================================================================
-- 7. TABLA: auditoria (Contabilización / Accounting - Modelo Triple A)
-- ==============================================================================
DROP TABLE IF EXISTS `auditoria`;
CREATE TABLE `auditoria` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `timestamp` VARCHAR(50) NOT NULL,
    `usuarioId` VARCHAR(50),
    `usuarioNombre` VARCHAR(100),
    `rol` VARCHAR(50),
    `servicio` VARCHAR(50),
    `accion` VARCHAR(100),
    `estado` VARCHAR(20),
    `monto` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `detalle` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `auditoria` (`id`, `timestamp`, `usuarioId`, `usuarioNombre`, `rol`, `servicio`, `accion`, `estado`, `monto`, `detalle`) VALUES
('log-001', '2026-10-05T07:00:00', 'u-101', 'Salvador Rivera (Admin)', 'administrador', 'Usuarios', 'LOGIN_EXITOSO', 'EXITO', 0.00, 'Inicio de sesión con emisión de token JWT'),
('log-002', '2026-10-05T07:15:00', 'u-102', 'Juan Pérez (Cliente)', 'cliente', 'Reservaciones', 'CREAR_RESERVACION', 'EXITO', 7500.00, 'Generación de Folio RES-2026-001 para Suite Frente al Mar (3 noches)'),
('log-003', '2026-10-05T07:16:00', 'u-102', 'Juan Pérez (Cliente)', 'cliente', 'Pagos', 'PAGO_APROBADO', 'EXITO', 7500.00, 'Cobro procesado mediante TARJETA_CREDITO. Comprobante PAG-2026-A101'),
('log-004', '2026-10-05T07:16:05', 'u-102', 'Juan Pérez (Cliente)', 'cliente', 'Notificaciones', 'NOTIFICACION_ENVIADA', 'EXITO', 0.00, 'Email enviado a juan@cliente.com por evento PagoConfirmado');

-- ==============================================================================
-- 8. TABLA: resenas (Servicio de Reseñas / Interacciones Tienda Online Alan)
-- ==============================================================================
DROP TABLE IF EXISTS `resenas`;
CREATE TABLE `resenas` (
    `id` VARCHAR(50) NOT NULL PRIMARY KEY,
    `recursoId` VARCHAR(50) NOT NULL,
    `usuarioId` VARCHAR(50) NOT NULL,
    `usuarioNombre` VARCHAR(100),
    `reservacionId` VARCHAR(50),
    `calificacion` INT NOT NULL DEFAULT 5,
    `titulo` VARCHAR(150),
    `comentario` TEXT,
    `fecha` VARCHAR(50),
    `servicioExterno` VARCHAR(100),
    `reviewIdExterno` VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `resenas` (`id`, `recursoId`, `usuarioId`, `usuarioNombre`, `reservacionId`, `calificacion`, `titulo`, `comentario`, `fecha`, `servicioExterno`, `reviewIdExterno`) VALUES
('rev-1', 'r-12', 'u-102', 'Juan Pérez', 'res-1', 5, '¡Experiencia inolvidable frente al mar!', 'La suite tiene una vista impresionante, el jacuzzi privado es excelente y la atención de primera.', '2026-10-18T16:00:00', 'Tienda Online Alan (Interactions)', 'rev-ext-101'),
('rev-2', 'r-16', 'u-103', 'María López', 'res-2', 5, 'Cabaña perfecta para descansar', 'El bosque y la chimenea hacen que la estancia sea mágica. Muy recomendado para familias.', '2026-10-19T11:30:00', 'Tienda Online Alan (Interactions)', 'rev-ext-102');

