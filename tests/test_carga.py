"""Pruebas de la carga del DWH: consistencia de lo que dejó el ETL en la base rapiditos.

Se ejecutan después del ETL (python etl/ejecutar_etl.py) y solo leen datos.
Si fact_venta está vacía, se omiten.
"""

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

LINEAS = {
    "Buses InterUrbanos Rapiditos",
    "Trenes Rapiditos",
    "Radio Taxis Rapiditos",
    "Logística y Distribución Rapiditos",
    "Aerolíneas Rapiditos",
    "URapid Delivery",
}


@pytest.fixture(scope="module")
def cur():
    try:
        conexion = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", "rapiditos"),
            password=os.getenv("DB_PASSWORD", ""),
            dbname=os.getenv("DB_NAME", "rapiditos"),
        )
    except psycopg.OperationalError as e:
        pytest.skip(f"Sin conexión a la base: {e}")
    with conexion, conexion.cursor() as c:
        c.execute("SELECT to_regclass('dwh.fact_venta') IS NOT NULL")
        if not c.fetchone()[0]:
            pytest.skip("No existe dwh.fact_venta")
        c.execute("SELECT COUNT(*) FROM dwh.fact_venta")
        if c.fetchone()[0] == 0:
            pytest.skip("fact_venta vacía: ejecutar antes el ETL")
        yield c


def uno(cur, consulta):
    cur.execute(consulta)
    return cur.fetchone()[0]


def test_las_seis_lineas_tienen_ventas(cur):
    cur.execute(
        "SELECT DISTINCT s.linea_negocio FROM dwh.fact_venta f "
        "JOIN dwh.dim_servicio s USING (id_servicio)"
    )
    assert {f[0] for f in cur.fetchall()} == LINEAS


def test_ninguna_transaccion_se_pierde(cur):
    stg = uno(cur, "SELECT COUNT(*) FROM stg.transaccion")
    hechos = uno(cur, "SELECT COUNT(*) FROM dwh.fact_venta")
    rechazos = uno(cur, "SELECT COUNT(*) FROM stg.rechazo")
    assert stg == hechos + rechazos


def test_cantidad_y_monto_cuadran_por_linea(cur):
    cur.execute("""
        SELECT v.codigo_linea
          FROM (SELECT codigo_linea, COUNT(*) n, SUM(monto_neto) neto
                  FROM stg.v_transaccion_conformada WHERE motivo_rechazo IS NULL GROUP BY 1) v
          FULL JOIN (SELECT LEFT(numero_transaccion, 3) codigo_linea, COUNT(*) n,
                            SUM(monto_neto) neto
                       FROM dwh.fact_venta GROUP BY 1) f USING (codigo_linea)
         WHERE v.n IS DISTINCT FROM f.n OR v.neto IS DISTINCT FROM f.neto""")
    assert cur.fetchall() == []


def test_rechazos_tienen_motivo_y_no_estan_en_hechos(cur):
    assert uno(cur, "SELECT COUNT(*) FROM stg.rechazo WHERE motivo IS NULL OR motivo = ''") == 0
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*) FROM stg.rechazo r
          JOIN dwh.fact_venta f USING (numero_transaccion)""",
        )
        == 0
    )


def test_dim_tiempo_cubre_2023_a_2025_sin_huecos(cur):
    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT fecha), MIN(fecha), MAX(fecha) FROM dwh.dim_tiempo"
    )
    n, distintas, minimo, maximo = cur.fetchone()
    assert (n, distintas, str(minimo), str(maximo)) == (1096, 1096, "2023-01-01", "2025-12-31")


def test_edad_coincide_con_fecha_de_nacimiento(cur):
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*)
          FROM dwh.fact_venta f
          JOIN dwh.dim_cliente c USING (id_cliente)
          JOIN dwh.dim_tiempo t USING (id_tiempo)
         WHERE f.edad_cliente IS DISTINCT FROM
               EXTRACT(YEAR FROM AGE(t.fecha, c.fecha_nacimiento))::SMALLINT""",
        )
        == 0
    )


def test_empresas_sin_edad_ni_genero(cur):
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*) FROM dwh.dim_cliente
         WHERE tipo_cliente = 'empresa' AND (genero IS NOT NULL OR fecha_nacimiento IS NOT NULL)""",
        )
        == 0
    )


def test_clientes_marcados_como_sinteticos(cur):
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*) FROM dwh.dim_cliente
         WHERE nombre_cliente NOT LIKE 'Cliente Sintético %'
           AND nombre_cliente NOT LIKE 'Empresa Sintética %'""",
        )
        == 0
    )


def test_registro_anterior_a_la_primera_compra(cur):
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*)
          FROM dwh.fact_venta f
          JOIN dwh.dim_cliente c USING (id_cliente)
          JOIN dwh.dim_tiempo t USING (id_tiempo)
         WHERE c.fecha_registro > t.fecha""",
        )
        == 0
    )


def test_hay_clientes_multilinea(cur):
    assert (
        uno(
            cur,
            """
        SELECT COUNT(*) FROM (
            SELECT id_cliente FROM dwh.fact_venta JOIN dwh.dim_servicio USING (id_servicio)
             GROUP BY id_cliente HAVING COUNT(DISTINCT linea_negocio) > 1) m""",
        )
        > 0
    )
