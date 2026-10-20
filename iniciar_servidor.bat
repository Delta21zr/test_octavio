@echo off
title Sistema de Reservaciones SOA / SaaS - Triple A
echo ======================================================================
echo    INICIANDO SERVICIO DE USUARIOS Y RESERVACIONES (TRIPLE A - AAA)
echo    Docente: Florentino Octavio Mejia Rosales
echo    Alumno:  Salvador Rivera Delgado
echo ======================================================================
echo.
echo Abriendo servidor FastAPI + Strawberry GraphQL...
echo.
echo   Interfaz Web:     http://localhost:8000
echo   GraphiQL:         http://localhost:8000/graphql
echo.
echo Presiona Ctrl+C para detener el servidor cuando termines.
echo.
python main.py
pause
