"""Exporta los datos del DWH poblado a un script SQL autónomo (05_datos_dwh.sql).

El script resultante carga en el esquema dwh (creado con 01_ddl.sql) los mismos datos que dejó
el ETL, sin necesidad de Apache Hop ni de los archivos de las fuentes. Funciona en psql y en el
Query Tool de pgAdmin: se quitan los metacomandos de psql que agrega pg_dump 17.11
(\\restrict y \\unrestrict) y todo queda dentro de una sola transacción.

Salida: data/processed/05_datos_dwh.sql (no se versiona: contiene datos derivados de fuentes
cuya licencia no permite redistribuirlas; el empaquetador lo copia al paquete de entrega).

Requisitos: contenedor postgres de docker-compose.yml activo y el ETL ya ejecutado.
Uso:  python herramientas/exportar_dwh.py
"""

import subprocess
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "processed" / "05_datos_dwh.sql"

CABECERA = f"""\
-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°2: datos del Datawarehouse construido.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Profesor:          Luis Cofré B.
-- Generado:          {date.today():%d-%m-%Y}, con pg_dump desde la base poblada por el ETL.
--
-- Descripción:
--   Carga en el esquema dwh las 6 dimensiones y la tabla de hechos fact_venta
--   con los datos que produjo el ETL de Apache Hop. Permite revisar el DWH
--   construido sin ejecutar el ETL.
--   DATOS SINTÉTICOS CALIBRADOS: los clientes son sintéticos y las transacciones
--   provienen de datasets públicos, con fechas trasladadas a 2023-2025 y montos
--   convertidos a pesos chilenos (ver la sección Fuentes de Información del
--   informe).
--
-- Requisito: ejecutar antes 01_ddl.sql en la misma base.
-- Uso: igual que 01_ddl.sql (pgAdmin: abrir y ejecutar completo con F5;
--   psql -U <usuario> -d <base> -v ON_ERROR_STOP=1 -f 05_datos_dwh.sql).
--   Es idempotente: vacía las tablas del esquema dwh antes de cargarlas, dentro
--   de una sola transacción.
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

TRUNCATE dwh.fact_venta, dwh.dim_tiempo, dwh.dim_cliente, dwh.dim_servicio, dwh.dim_zona,
         dwh.dim_canal_venta, dwh.dim_medio_pago RESTART IDENTITY;
"""


def main() -> None:
    env = dotenv_values(RAIZ / ".env")
    volcado = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            env["DB_USER"],
            "-d",
            env["DB_NAME"],
            "--schema=dwh",
            "--data-only",
            "--inserts",
            "--rows-per-insert=1000",
            "--no-owner",
            "--no-privileges",
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    # Sin metacomandos de psql (líneas que empiezan con \): pgAdmin no los entiende.
    lineas = [x for x in volcado.splitlines() if not x.startswith("\\")]
    cuerpo = "\n".join(lineas).strip()
    SALIDA.write_text(f"{CABECERA}\n{cuerpo}\n\nCOMMIT;\n", encoding="utf-8")
    print(f"Generado {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
