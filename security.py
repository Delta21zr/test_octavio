# type: ignore
# pyright: reportMissingImports=false
# pyright: reportMissingTypeStubs=false
# pylint: skip-file
# flake8: noqa
"""
================================================================================
UNIVERSIDAD POLITÉCNICA DE DURANGO
Materia: Arquitectura de Software / Servicios Web
Profesor: Florentino Octavio Mejía Rosales
Alumno: Salvador Rivera Delgado

MÓDULO: SEGURIDAD Y CONTROL DE ACCESO (AUTENTICACIÓN Y AUTORIZACIÓN - TRIPLE A)
Archivo: security.py
================================================================================
DESCRIPCIÓN GENERAL:
Este módulo implementa los dos primeros pilares del Modelo de Seguridad AAA:

1. AUTENTICACIÓN (Authentication):
   - Generación de JSON Web Tokens (JWT) firmados con el algoritmo HS256.
   - Validación de firmas criptográficas y vigencia temporal (expiración).
   - Extracción de identidad del usuario ('sub', 'rol', 'correo', 'nombre').

2. AUTORIZACIÓN (Authorization):
   - Control de Acceso Basado en Roles (RBAC: Role-Based Access Control).
   - Verificación de permisos ('cliente', 'administrador').
   - Rechazo inmediato de peticiones no autorizadas mediante errores 403 Forbidden.
================================================================================
"""

import sys
import os
import jwt  # type: ignore
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strawberry.types import Info  # type: ignore
from data.db import USUARIOS_DB  # type: ignore

# Clave secreta y algoritmo criptográfico para firmar los tokens JWT
SECRET_KEY = "clave_secreta_unipoli_sistemas_reservaciones_2026"
ALGORITHM = "HS256"
TOKEN_EXPIRATION_HOURS = 4  # Vigencia de la sesión: 4 horas


def generar_token(user_id: str, rol: str, nombre: str, correo: str) -> str:
    """
    1. AUTENTICACIÓN (Triple A - Emisión de Identidad Digital):
    Crea y firma un JSON Web Token (JWT) que encapsula la identidad del usuario.
    
    Claims incluidos en el token:
    - 'sub': Identificador único del usuario (ej: 'u-101')
    - 'rol': Rol asignado ('cliente' o 'administrador')
    - 'nombre': Nombre del titular
    - 'correo': Correo electrónico
    - 'exp': Fecha y hora de expiración (UTC)
    - 'iat': Fecha y hora de emisión (Issued At)
    """
    payload = {
        "sub": user_id,
        "rol": rol,
        "nombre": nombre,
        "correo": correo,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> Optional[Dict[str, Any]]:
    """
    1. AUTENTICACIÓN (Triple A - Verificación de Identidad):
    Descifra y valida la firma criptográfica y expiración del Token JWT.
    Retorna el diccionario con los claims si es válido, o None si expiró o fue alterado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def obtener_usuario_actual(info: Info) -> Optional[Dict[str, Any]]:
    """
    Extrae la información del usuario autenticado desde el contexto de GraphQL.
    El contexto es inyectado previamente por el middleware de FastAPI/Strawberry.
    """
    if hasattr(info, "context") and isinstance(info.context, dict):
        return info.context.get("user")
    return None


def requerir_autenticacion(info: Info) -> Dict[str, Any]:
    """
    1. AUTENTICACIÓN (Triple A - Filtro Obligatorio):
    Exige que la petición HTTP cuente con un Token JWT válido en el header:
    'Authorization: Bearer <token>'.
    Si el usuario no está autenticado, lanza 'PermissionError' bloqueando la acción.
    """
    user = obtener_usuario_actual(info)
    if not user:
        raise PermissionError(
            "Autenticación requerida: Debes enviar un Token JWT válido en el header 'Authorization: Bearer <token>'"
        )
    return user


def requerir_autorizacion(info: Info, roles_permitidos: list[str]) -> Dict[str, Any]:
    """
    2. AUTORIZACIÓN (Triple A - Control de Acceso por Roles / RBAC):
    Verifica que el usuario no solo esté autenticado, sino que además su rol
    forme parte de la lista de roles permitidos para ejecutar la función.
    Si no tiene el rol adecuado, lanza 'PermissionError' (403 Forbidden).
    """
    user = requerir_autenticacion(info)
    user_rol = user.get("rol", "")
    if user_rol not in roles_permitidos:
        raise PermissionError(
            f"Autorización denegada: Tu rol '{user_rol}' no tiene permisos para esta acción. Roles requeridos: {roles_permitidos}"
        )
    return user
