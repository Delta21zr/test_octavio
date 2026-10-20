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

MÓDULO: SERVICIO DE USUARIOS (AUTENTICACIÓN Y AUTORIZACIÓN - MODELO AAA)
Archivo: services/usuarios.py
================================================================================
DESCRIPCIÓN GENERAL:
Este servicio web gestiona el ciclo de vida de las cuentas de usuario y aplica
los pilares de seguridad del Modelo Triple A (AAA):

1. AUTENTICACIÓN (Authentication):
   - Registro de nuevas cuentas (clientes).
   - Inicio de sesión con verificación de credenciales (correo y contraseña).
   - Generación y emisión de tokens de acceso JWT (JSON Web Tokens).

2. AUTORIZACIÓN (Authorization):
   - Control de Acceso Basado en Roles (RBAC: Role-Based Access Control).
   - Separación estricta entre privilegios de 'cliente' y 'administrador'.
   - Protección de la consulta de todos los usuarios (solo permitida para admins).

3. CONTABILIZACIÓN / AUDITORÍA (Accounting):
   - Cada intento de login (exitoso o fallido) y cada registro se audita
     automáticamente en la bitácora contable persistida en MySQL.
================================================================================
"""

import sys
import os
import uuid
import datetime
from typing import Optional, List

# Garantizar que la raíz del proyecto esté en el PYTHONPATH independientemente de dónde se invoque
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importación del framework GraphQL Strawberry
import strawberry  # type: ignore
from strawberry.types import Info  # type: ignore

# Acceso a la capa de datos (MySQL / Caché en memoria)
from data.db import USUARIOS_DB, guardar_usuario_db, obtener_usuario_mysql  # type: ignore

# Módulos de seguridad y auditoría AAA
from security import generar_token, requerir_autenticacion, requerir_autorizacion  # type: ignore
from accounting import registrar_evento  # type: ignore


# ==============================================================================
# SECCIÓN 1: MODELOS DE DATOS GRAPHQL (TYPES & INPUTS)
# ==============================================================================

@strawberry.input
class RegistroUsuarioInput:
    """Entrada para mutación registrarUsuario según estándar GraphQL."""
    nombre: str
    correo: str
    password: str
    rol: Optional[str] = "cliente"


@strawberry.type
class Usuario:
    """
    Representa la entidad pública de un usuario en el esquema GraphQL.
    Oculta la contraseña para proteger la confidencialidad de las credenciales.
    """
    id: strawberry.ID        # Identificador único de usuario (ej: 'u-101')
    nombre: str              # Nombre completo del usuario
    correo: str              # Correo electrónico único para inicio de sesión
    rol: str                 # Rol asignado: 'cliente' o 'administrador' (RBAC)
    creadoEn: str            # Fecha y hora en formato ISO de creación de cuenta


@strawberry.type
class AuthPayload:
    """
    Estructura de respuesta entregada tras operaciones de acceso (login o registro).
    Contiene el Token JWT necesario para firmar peticiones posteriores.
    """
    token: str                   # Cadena JWT codificada en Base64 con firma HS256
    usuario: Optional[Usuario]   # Objeto con los datos del usuario conectado (o None si hubo error)
    mensaje: str                 # Mensaje descriptivo legible (ej: 'Inicio de sesión exitoso')
    exito: bool                  # Bandera booleana (True si la operación tuvo éxito, False si falló)


# ==============================================================================
# SECCIÓN 2: QUERIES (CONSULTAS DE LECTURA)
# ==============================================================================

@strawberry.type
class UsuariosQueries:
    """
    Agrupa todas las consultas de solo lectura relacionadas con usuarios.
    """

    @strawberry.field
    def mi_perfil(self, info: Info) -> Optional[Usuario]:
        """
        CONSULTA: miPerfil
        Objetivo: Permite a un usuario autenticado consultar su propia información.
        
        FLUJO DE EJECUCIÓN (TRIPLE A):
        -------------------------------------------------------------
        1. [AUTENTICACIÓN]: 'requerir_autenticacion(info)' extrae el header HTTP
           'Authorization: Bearer <token>', valida la firma criptográfica y decodifica el token.
           Si el token es inválido o expiró, rechaza la petición con error 401.
        2. [BÚSQUEDA]: Obtiene el 'sub' (ID del usuario) dentro del payload del token
           y busca el registro correspondiente en la base de datos (USUARIOS_DB).
        3. [CONTABILIZACIÓN]: Registra en la bitácora contable que el usuario
           consultó su perfil propio satisfactoriamente.
        4. [RESPUESTA]: Retorna el objeto Usuario con sus campos públicos.
        """
        # Paso 1: Validar autenticación mediante el token JWT
        user_jwt = requerir_autenticacion(info)
        user_id = user_jwt.get("sub")
        
        # Paso 2: Buscar usuario en la base de datos
        user_data = USUARIOS_DB.get(user_id)
        if not user_data:
            return None

        # Paso 3: Registrar evento de auditoría (Accounting)
        registrar_evento(
            usuario_id=user_id,
            usuario_nombre=user_data["nombre"],
            rol=user_data["rol"],
            servicio="Usuarios",
            accion="CONSULTAR_PERFIL",
            estado="EXITO",
            detalle=f"Consulta de perfil propio ({user_data['correo']})"
        )

        # Paso 4: Retornar modelo GraphQL
        return Usuario(
            id=strawberry.ID(user_data["id"]),
            nombre=user_data["nombre"],
            correo=user_data["correo"],
            rol=user_data["rol"],
            creadoEn=user_data.get("creadoEn", "")
        )

    @strawberry.field
    def listar_usuarios(self, info: Info) -> List[Usuario]:
        """
        CONSULTA: listarUsuarios (PROTEGIDA POR RBAC)
        Objetivo: Devuelve la lista completa de todos los usuarios registrados.
        
        FLUJO DE EJECUCIÓN (TRIPLE A):
        -------------------------------------------------------------
        1. [AUTORIZACIÓN / RBAC]: 'requerir_autorizacion(info, ["administrador"])'
           verifica que el usuario no solo esté autenticado, sino que además
           su rol dentro del token sea estrictamente 'administrador'.
           Si un 'cliente' intenta llamar a este método, el servidor arroja error 403 Forbidden.
        2. [CONTABILIZACIÓN]: Registra el acceso del administrador a la lista general.
        3. [RESPUESTA]: Devuelve todos los usuarios registrados en el sistema.
        """
        # Paso 1: Exigir rol de administrador (Control de Acceso Basado en Roles)
        admin_jwt = requerir_autorizacion(info, ["administrador"])
        
        # Paso 2: Registrar evento en la bitácora de auditoría
        registrar_evento(
            usuario_id=admin_jwt.get("sub", ""),
            usuario_nombre=admin_jwt.get("nombre", ""),
            rol=admin_jwt.get("rol", ""),
            servicio="Usuarios",
            accion="LISTAR_USUARIOS",
            estado="EXITO",
            detalle="Administrador consultó la lista completa de usuarios registrados"
        )

        # Paso 3: Transformar diccionarios de BD en instancias de Usuario
        return [
            Usuario(
                id=strawberry.ID(u["id"]),
                nombre=u["nombre"],
                correo=u["correo"],
                rol=u["rol"],
                creadoEn=u.get("creadoEn", "")
            )
            for u in USUARIOS_DB.values()
        ]


# ==============================================================================
# SECCIÓN 3: MUTATIONS (OPERACIONES DE ESCRITURA Y ACCESO)
# ==============================================================================

@strawberry.type
class UsuariosMutations:
    """
    Agrupa las operaciones de cambio de estado: Login y Registro.
    """

    @strawberry.mutation
    def iniciar_sesion(self, correo: str, password: str) -> AuthPayload:
        """
        MUTATION: iniciarSesion
        Objetivo: Autenticar credenciales y otorgar un token JWT firmado.
        
        FLUJO DE EJECUCIÓN (TRIPLE A):
        -------------------------------------------------------------
        1. [LIMPIEZA]: Normaliza el correo electrónico (sin espacios y en minúsculas).
        2. [BÚSQUEDA]: Localiza el usuario en la base de datos por su correo.
        3. [VALIDACIÓN DE CREDENCIALES]:
           - Si el usuario no existe o la contraseña no coincide:
             a) Se audita en Accounting como 'LOGIN_FALLIDO' con estado 'FALLIDO'.
             b) Se retorna exito=False sin proporcionar ningún token.
        4. [EMISIÓN DE CREDENCIAL DIGITAL]:
           - Si las credenciales coinciden:
             a) Se emite un Token JWT firmado digitalmente con clave secreta HS256.
                El token encapsula: user_id, rol, nombre y correo.
             b) Se audita en Accounting como 'LOGIN_EXITOSO' con estado 'EXITO'.
             c) Se retorna el AuthPayload con el token emitido.
        """
        correo_limpio = correo.strip().lower()

        # Buscar usuario directamente en MySQL para garantizar acceso a usuarios de phpMyAdmin
        user = obtener_usuario_mysql(correo_limpio)
        
        # Validar contraseña (soporta texto plano y hash MD5 común en phpMyAdmin)
        import hashlib
        pwd_md5 = hashlib.md5(password.strip().encode("utf-8")).hexdigest().lower()
        
        valid_pwd = False
        if user and "password" in user:
            stored_pwd = str(user["password"]).strip()
            if stored_pwd == password.strip() or stored_pwd.lower() == pwd_md5:
                valid_pwd = True

        if not user or not valid_pwd:
            # Registrar intento fallido en la auditoría (Accounting)
            registrar_evento(
                usuario_id="DESCONOCIDO",
                usuario_nombre="Intento Fallido",
                rol="ninguno",
                servicio="Usuarios",
                accion="LOGIN_FALLIDO",
                estado="FALLIDO",
                detalle=f"Intento de inicio de sesión rechazado para el correo: {correo}"
            )
            return AuthPayload(
                token="",
                usuario=None,
                mensaje="Credenciales incorrectas (Correo o contraseña inválidos)",
                exito=False
            )

        # Generar Token JWT con claims de seguridad
        token_jwt = generar_token(
            user_id=user["id"],
            rol=user["rol"],
            nombre=user["nombre"],
            correo=user["correo"]
        )

        # Registrar acceso exitoso en la auditoría (Accounting)
        registrar_evento(
            usuario_id=user["id"],
            usuario_nombre=user["nombre"],
            rol=user["rol"],
            servicio="Usuarios",
            accion="LOGIN_EXITOSO",
            estado="EXITO",
            detalle=f"Usuario autenticado correctamente con rol: {user['rol']}"
        )

        return AuthPayload(
            token=token_jwt,
            usuario=Usuario(
                id=strawberry.ID(user["id"]),
                nombre=user["nombre"],
                correo=user["correo"],
                rol=user["rol"],
                creadoEn=user.get("creadoEn", "")
            ),
            mensaje="Inicio de sesión exitoso. Token JWT generado.",
            exito=True
        )

    @strawberry.mutation
    def registrar_usuario(
        self,
        nombre: Optional[str] = None,
        correo: Optional[str] = None,
        password: Optional[str] = None,
        rol: Optional[str] = "cliente",
        input: Optional[RegistroUsuarioInput] = None
    ) -> AuthPayload:
        """
        MUTATION: registrarUsuario
        Objetivo: Registrar un nuevo usuario en MySQL y memoria, otorgando sesión directa.
        Soporta tanto argumentos individuales como objeto 'input: RegistroUsuarioInput'.
        """
        if input:
            nombre = input.nombre
            correo = input.correo
            password = input.password
            rol = input.rol or "cliente"

        if not nombre or not correo or not password:
            return AuthPayload(
                token="",
                usuario=None,
                mensaje="Faltan campos obligatorios para registrar al usuario.",
                exito=False
            )

        correo_limpio = correo.strip().lower()

        # Verificar si el correo ya está registrado en MySQL o memoria
        existente = obtener_usuario_mysql(correo_limpio)
        if existente:
            return AuthPayload(
                token="",
                usuario=None,
                mensaje="El correo ingresado ya se encuentra registrado en el sistema.",
                exito=False
            )

        # Asignar rol permitido (por defecto 'cliente')
        rol_asignado = rol.lower() if rol in ["cliente", "administrador"] else "cliente"
        nuevo_id = f"u-{uuid.uuid4().hex[:6]}"
        fecha_registro = datetime.datetime.now().isoformat()

        nuevo_usuario = {
            "id": nuevo_id,
            "nombre": nombre.strip(),
            "correo": correo_limpio,
            "password": password.strip(),
            "rol": rol_asignado,
            "creadoEn": fecha_registro
        }

        # Guardar en memoria y persistir en MySQL (XAMPP phpMyAdmin)
        USUARIOS_DB[nuevo_id] = nuevo_usuario
        try:
            guardar_usuario_db(nuevo_usuario)
        except Exception as e:
            print(f"[MySQL Exception al registrar usuario]: {e}")

        # Generar Token JWT para inicio automático de sesión
        token_jwt = generar_token(nuevo_id, rol_asignado, nombre.strip(), correo_limpio)

        # Registrar en la bitácora contable (Accounting)
        registrar_evento(
            usuario_id=nuevo_id,
            usuario_nombre=nombre.strip(),
            rol=rol_asignado,
            servicio="Usuarios",
            accion="REGISTRO_USUARIO",
            estado="EXITO",
            detalle=f"Nuevo usuario registrado en la base de datos con rol '{rol_asignado}'"
        )

        return AuthPayload(
            token=token_jwt,
            usuario=Usuario(
                id=strawberry.ID(nuevo_id),
                nombre=nuevo_usuario["nombre"],
                correo=nuevo_usuario["correo"],
                rol=nuevo_usuario["rol"],
                creadoEn=fecha_registro
            ),
            mensaje="Usuario registrado con éxito.",
            exito=True
        )
