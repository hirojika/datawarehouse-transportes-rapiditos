"""Pruebas del DDL del DWH (sql/01_ddl.sql) contra el PostgreSQL de docker-compose.yml.

El script se ejecuta sobre una base de prueba aparte (por defecto
rapiditos_test), que las pruebas crean y eliminan, para no tocar nunca la base
rapiditos, que en fases posteriores tendrá datos.

Requisitos: contenedores activos (docker compose up -d) y el archivo .env configurado.
Ejecutar desde la raíz del repositorio con: pytest -v
"""

import os
import re
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import errors, sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

RAIZ = Path(__file__).resolve().parents[1]
RUTA_DDL = RAIZ / "sql" / "01_ddl.sql"
RUTA_MODELO = RAIZ / "docs" / "modelo_dimensional.md"

ESQUEMA = "dwh"
DIMENSIONES = {
    "dim_tiempo",
    "dim_cliente",
    "dim_servicio",
    "dim_zona",
    "dim_canal_venta",
    "dim_medio_pago",
}
HECHO = "fact_venta"
TABLAS_ESPERADAS = DIMENSIONES | {HECHO}

# columna de fact_venta -> (tabla referenciada, columna referenciada)
FK_ESPERADAS = {
    "id_tiempo": ("dim_tiempo", "id_tiempo"),
    "id_cliente": ("dim_cliente", "id_cliente"),
    "id_servicio": ("dim_servicio", "id_servicio"),
    "id_zona_origen": ("dim_zona", "id_zona"),
    "id_zona_destino": ("dim_zona", "id_zona"),
    "id_canal_venta": ("dim_canal_venta", "id_canal_venta"),
    "id_medio_pago": ("dim_medio_pago", "id_medio_pago"),
}

PATRON_TABLA = re.compile(r"^(dim|fact)_[a-z][a-z0-9]*(_[a-z0-9]+)*$")
PATRON_SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

NOMBRES_DIA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
NOMBRES_MES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]  # fmt: skip

load_dotenv(RAIZ / ".env")
BASE_PRODUCCION = os.getenv("DB_NAME", "rapiditos")
BASE_PRUEBA = os.getenv("DB_NAME_TEST", "rapiditos_test")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def parametros_conexion(base: str) -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "user": os.getenv("DB_USER", "rapiditos"),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname": base,
    }


def leer_ddl() -> str:
    return RUTA_DDL.read_text(encoding="utf-8")


def sentencias_ddl(script: str) -> list[str]:
    """Separa el script en sentencias.

    Corta en ';' y omite los comentarios '--', salvo dentro de textos entre
    comillas simples (los COMMENT ON pueden contener ';').
    """
    sentencias, actual, en_texto, i = [], [], False, 0
    while i < len(script):
        caracter = script[i]
        if en_texto:
            actual.append(caracter)
            if caracter == "'":
                en_texto = False  # una comilla doble ('') vuelve a abrir el texto
        elif caracter == "'":
            en_texto = True
            actual.append(caracter)
        elif script.startswith("--", i):
            fin_linea = script.find("\n", i)
            i = len(script) if fin_linea == -1 else fin_linea
            continue
        elif caracter == ";":
            sentencias.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
        i += 1
    sentencias.append("".join(actual).strip())
    return [s for s in sentencias if s]


def leer_modelo() -> dict[str, list[dict[str, str]]]:
    """Extrae las tablas de columnas de docs/modelo_dimensional.md.

    Devuelve {tabla: [{"columna", "tipo", "restriccion"}, ...]} en el orden
    del documento. Solo se leen las secciones cuyo título termina en el
    nombre de una tabla (dim_... o fact_...).
    """
    modelo: dict[str, list[dict[str, str]]] = {}
    tabla_actual = None
    for linea in RUTA_MODELO.read_text(encoding="utf-8").splitlines():
        titulo = re.match(r"^#{2,3}\s.*?\b((?:dim|fact)_[a-z0-9_]+)\s*$", linea)
        if titulo:
            tabla_actual = titulo.group(1)
            modelo[tabla_actual] = []
            continue
        if linea.startswith("#"):
            tabla_actual = None
            continue
        if tabla_actual is None or not linea.startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if celdas[0] in ("Columna", "") or set(celdas[0]) <= {"-", ":"}:
            continue
        modelo[tabla_actual].append(
            {"columna": celdas[0], "tipo": celdas[1], "restriccion": celdas[2]}
        )
    return modelo


def tipo_canonico_modelo(tipo: str) -> str:
    """Normaliza un tipo del modelo: 'varchar(20)' -> 'VARCHAR(20)'."""
    return re.sub(r"\s+", " ", tipo.strip().upper())


def tipo_canonico_bd(tipo: str) -> str:
    """Lleva el tipo de format_type() al formato del modelo.

    'character varying(20)' -> 'VARCHAR(20)', 'numeric(12,2)' -> 'NUMERIC(12,2)'.
    """
    return re.sub(r"^character varying", "varchar", tipo).upper()


def fila_tiempo(fecha: date) -> dict:
    """Fila válida de dim_tiempo para una fecha, con la misma lógica que usará el ETL."""
    iso = fecha.isocalendar()
    return {
        "id_tiempo": int(fecha.strftime("%Y%m%d")),
        "fecha": fecha,
        "dia": fecha.day,
        "dia_semana": iso.weekday,
        "nombre_dia": NOMBRES_DIA[iso.weekday - 1],
        "es_fin_de_semana": iso.weekday >= 6,
        "semana_anio": iso.week,
        "mes": fecha.month,
        "nombre_mes": NOMBRES_MES[fecha.month - 1],
        "trimestre": (fecha.month + 2) // 3,
        "semestre": 1 if fecha.month <= 6 else 2,
        "anio": fecha.year,
    }


def consulta_insercion(tabla: str, columnas: list[str]) -> sql.Composed:
    """INSERT parametrizado que devuelve la PK de la fila (id_<entidad>)."""
    return sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}").format(
        sql.Identifier(ESQUEMA),
        sql.Identifier(tabla),
        sql.SQL(", ").join(map(sql.Identifier, columnas)),
        sql.SQL(", ").join(sql.Placeholder() * len(columnas)),
        sql.Identifier(f"id_{tabla.split('_', 1)[1]}"),
    )


def insertar(conexion: psycopg.Connection, tabla: str, fila: dict):
    cursor = conexion.execute(consulta_insercion(tabla, list(fila)), list(fila.values()))
    return cursor.fetchone()[0]


# Datos sintéticos de prueba: solo existen dentro de la transacción de cada
# prueba, en la base temporal, y se descartan al terminar.
FILA_CLIENTE = {
    "codigo_cliente": "PRUEBA-C1",
    "nombre_cliente": "Cliente sintético de prueba",
    "tipo_cliente": "persona",
    "pais_residencia": "Chile",
}
FILA_SERVICIO = {
    "codigo_servicio": "PRUEBA-S1",
    "linea_negocio": "Buses InterUrbanos Rapiditos",
    "medio_transporte": "bus",
    "tipo_servicio": "pasajeros",
    "clase_servicio": "ejecutiva",
}


def insertar_datos_base(conexion: psycopg.Connection) -> dict:
    """Inserta una fila válida en cada dimensión y devuelve las llaves para fact_venta."""
    zona = {"comuna": "Santiago", "ciudad": "Santiago", "region": "Metropolitana",
            "pais": "Chile", "continente": "América"}  # fmt: skip
    return {
        "id_tiempo": insertar(conexion, "dim_tiempo", fila_tiempo(date(2025, 3, 14))),
        "id_cliente": insertar(conexion, "dim_cliente", FILA_CLIENTE),
        "id_servicio": insertar(conexion, "dim_servicio", FILA_SERVICIO),
        "id_zona_origen": insertar(conexion, "dim_zona", {"codigo_zona": "PRUEBA-Z1", **zona}),
        "id_zona_destino": insertar(
            conexion, "dim_zona", {**zona, "codigo_zona": "PRUEBA-Z2", "comuna": "Valparaíso",
                                   "ciudad": "Valparaíso", "region": "Valparaíso"}
        ),  # fmt: skip
        "id_canal_venta": insertar(
            conexion, "dim_canal_venta", {"codigo_canal_venta": "PRUEBA-CV1",
                                          "nombre_canal_venta": "app"}
        ),  # fmt: skip
        "id_medio_pago": insertar(
            conexion, "dim_medio_pago", {"codigo_medio_pago": "PRUEBA-MP1",
                                         "nombre_medio_pago": "débito"}
        ),  # fmt: skip
    }


def fila_venta(llaves: dict, **cambios) -> dict:
    fila = {
        **llaves,
        "numero_transaccion": "PRUEBA-BUS-0000001",
        "edad_cliente": 34,
        "cantidad": 1,
        "monto_bruto": 12000,
        "monto_descuento": 2000,
        "monto_neto": 10000,
        "distancia_km": 120.5,
        "duracion_minutos": 95,
        "peso_kg": None,
    }
    return {**fila, **cambios}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_prueba():
    """Crea la base de prueba vacía y la elimina al terminar la sesión."""
    if BASE_PRUEBA == BASE_PRODUCCION:
        pytest.fail(f"DB_NAME_TEST no puede ser {BASE_PRODUCCION}: el test borraría el DWH real.")
    borrar = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(BASE_PRUEBA))
    try:
        admin = psycopg.connect(**parametros_conexion(BASE_PRODUCCION), autocommit=True)
    except psycopg.OperationalError as error:
        pytest.fail(
            "No se pudo conectar a PostgreSQL con los datos de .env. "
            f"¿Están corriendo los contenedores (docker compose up -d)? Detalle: {error}"
        )
    with admin:
        admin.execute(borrar)
        admin.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(BASE_PRUEBA))
        )
    yield BASE_PRUEBA
    with psycopg.connect(**parametros_conexion(BASE_PRODUCCION), autocommit=True) as admin:
        admin.execute(borrar)


@pytest.fixture(scope="session")
def esquema(base_prueba):
    """Ejecuta el DDL dos veces sobre la base de prueba y devuelve su metadata.

    La segunda ejecución prueba que el script se puede repetir sobre un esquema
    que ya existe. Se registran los avisos (NOTICE, WARNING) que emite
    PostgreSQL, los mismos que muestra pgAdmin en la pestaña Mensajes.
    """
    avisos: list[dict] = []
    ejecucion_actual = {"numero": 0}

    def registrar_aviso(diagnostico: psycopg.errors.Diagnostic) -> None:
        avisos.append(
            {
                "ejecucion": ejecucion_actual["numero"],
                "severidad": diagnostico.severity_nonlocalized,
                "mensaje": diagnostico.message_primary,
            }
        )

    with psycopg.connect(**parametros_conexion(base_prueba), autocommit=True) as conexion:
        conexion.add_notice_handler(registrar_aviso)
        for numero in (1, 2):
            ejecucion_actual["numero"] = numero
            conexion.execute(leer_ddl())

    parametros = parametros_conexion(base_prueba)
    url = URL.create(
        "postgresql+psycopg",
        username=parametros["user"],
        password=parametros["password"],
        host=parametros["host"],
        port=parametros["port"],
        database=parametros["dbname"],
    )
    motor = create_engine(url)
    try:
        with motor.connect() as conexion:

            def consultar(consulta: str) -> list[dict]:
                return [dict(f) for f in conexion.execute(text(consulta)).mappings()]

            datos = {
                "avisos": avisos,
                "codificacion": conexion.execute(
                    text(
                        "SELECT pg_encoding_to_char(encoding) FROM pg_database "
                        "WHERE datname = current_database()"
                    )
                ).scalar_one(),
                "tablas": consultar(
                    """SELECT c.relname AS tabla, obj_description(c.oid, 'pg_class') AS comentario
                       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'dwh' AND c.relkind = 'r'"""
                ),
                "columnas": consultar(
                    """SELECT c.table_name AS tabla, c.column_name AS columna,
                              format_type(a.atttypid, a.atttypmod) AS tipo,
                              c.is_nullable AS acepta_nulo, c.column_default AS por_defecto,
                              c.identity_generation AS identity,
                              col_description(a.attrelid, a.attnum) AS comentario
                       FROM information_schema.columns c
                       JOIN pg_namespace n ON n.nspname = c.table_schema
                       JOIN pg_class cl ON cl.relnamespace = n.oid AND cl.relname = c.table_name
                       JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attname = c.column_name
                       WHERE c.table_schema = 'dwh'
                       ORDER BY c.table_name, c.ordinal_position"""
                ),
                "llaves": consultar(
                    """SELECT tc.table_name AS tabla, tc.constraint_type AS tipo,
                              tc.constraint_name AS restriccion, k.column_name AS columna
                       FROM information_schema.table_constraints tc
                       JOIN information_schema.key_column_usage k
                         ON k.constraint_schema = tc.constraint_schema
                        AND k.constraint_name = tc.constraint_name
                       WHERE tc.table_schema = 'dwh'
                         AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')"""
                ),
                "fks": consultar(
                    """SELECT con.conname AS restriccion, cl.relname AS tabla,
                              a.attname AS columna, ref.relname AS tabla_ref,
                              ra.attname AS columna_ref, cardinality(con.conkey) AS n_columnas,
                              con.confupdtype AS al_actualizar, con.confdeltype AS al_eliminar
                       FROM pg_constraint con
                       JOIN pg_class cl ON cl.oid = con.conrelid
                       JOIN pg_namespace n ON n.oid = cl.relnamespace
                       JOIN pg_class ref ON ref.oid = con.confrelid
                       JOIN pg_attribute a
                         ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
                       JOIN pg_attribute ra
                         ON ra.attrelid = con.confrelid AND ra.attnum = con.confkey[1]
                       WHERE n.nspname = 'dwh' AND con.contype = 'f'"""
                ),
                "checks": consultar(
                    """SELECT con.conname AS restriccion, cl.relname AS tabla,
                              ARRAY(SELECT a.attname::text
                                    FROM unnest(con.conkey) AS k(attnum)
                                    JOIN pg_attribute a
                                      ON a.attrelid = con.conrelid AND a.attnum = k.attnum
                              ) AS columnas
                       FROM pg_constraint con
                       JOIN pg_class cl ON cl.oid = con.conrelid
                       JOIN pg_namespace n ON n.oid = cl.relnamespace
                       WHERE n.nspname = 'dwh' AND con.contype = 'c'"""
                ),
                "indices": consultar(
                    """SELECT i.relname AS indice, t.relname AS tabla,
                              ARRAY(SELECT a.attname::text
                                    FROM unnest(x.indkey::int2[]) AS k(attnum)
                                    JOIN pg_attribute a
                                      ON a.attrelid = x.indrelid AND a.attnum = k.attnum
                              ) AS columnas,
                              EXISTS (SELECT 1 FROM pg_constraint con
                                      WHERE con.conindid = x.indexrelid
                                        AND con.contype IN ('p', 'u')) AS de_restriccion
                       FROM pg_index x
                       JOIN pg_class i ON i.oid = x.indexrelid
                       JOIN pg_class t ON t.oid = x.indrelid
                       JOIN pg_namespace n ON n.oid = t.relnamespace
                       WHERE n.nspname = 'dwh'"""
                ),
            }
    finally:
        motor.dispose()
    yield datos


@pytest.fixture
def transaccion(esquema, base_prueba):
    """Conexión con una fila válida en cada dimensión, dentro de una
    transacción que se descarta (rollback) al terminar la prueba."""
    conexion = psycopg.connect(**parametros_conexion(base_prueba))
    try:
        yield conexion, insertar_datos_base(conexion)
    finally:
        conexion.rollback()
        conexion.close()


# ---------------------------------------------------------------------------
# Pruebas estáticas del script (no requieren base de datos)
# ---------------------------------------------------------------------------


def test_script_es_idempotente_y_transaccional():
    sentencias = sentencias_ddl(leer_ddl())
    # La codificación va antes de la transacción, como en pg_dump: sin ella, psql
    # en Windows guarda mal las tildes (ver la cabecera de sql/01_ddl.sql)
    assert sentencias[0] == "SET client_encoding = 'UTF8'"
    assert sentencias[1] == "BEGIN"
    assert sentencias[2] == f"DROP SCHEMA IF EXISTS {ESQUEMA} CASCADE"
    assert sentencias[3] == f"CREATE SCHEMA {ESQUEMA}"
    assert sentencias[-1] == "COMMIT"


def test_script_sin_copy_ni_rutas_absolutas():
    ddl = leer_ddl()
    assert not re.search(r"\bCOPY\b", ddl, re.IGNORECASE)
    assert not re.search(r"\b[A-Za-z]:\\", ddl), "Ruta absoluta de Windows en el script"
    assert not re.search(r"(?<![\w/])/(home|opt|usr|var|tmp|mnt)/", ddl), (
        "Ruta absoluta en el script"
    )


def test_script_sin_metacomandos_de_psql():
    """Un metacomando (\\i, \\c, \\copy...) no funciona en el Query Tool de pgAdmin."""
    assert not re.search(r"^\s*\\", leer_ddl(), re.MULTILINE)


def test_dimensiones_se_crean_antes_que_hechos():
    orden = re.findall(rf"CREATE TABLE {ESQUEMA}\.(\w+)", leer_ddl())
    assert set(orden) == TABLAS_ESPERADAS
    assert orden[-1] == HECHO


def test_modelo_documentado_tiene_las_7_tablas():
    assert set(leer_modelo()) == TABLAS_ESPERADAS


# ---------------------------------------------------------------------------
# Pruebas de la estructura creada en PostgreSQL
# ---------------------------------------------------------------------------


def test_ddl_se_ejecuta_sin_avisos_inesperados(esquema):
    """Cada ejecución debe emitir un solo aviso, el NOTICE de DROP SCHEMA IF EXISTS:
    en la primera el esquema todavía no existe y en la segunda se borra con sus
    7 tablas. Cualquier otro aviso o WARNING es un problema del script."""
    for numero in (1, 2):
        avisos = [a for a in esquema["avisos"] if a["ejecucion"] == numero]
        assert [a["severidad"] for a in avisos] == ["NOTICE"], f"Ejecución {numero}: {avisos}"


def test_codificacion_utf8(esquema):
    assert esquema["codificacion"] == "UTF8"


def test_existen_las_7_tablas(esquema):
    assert {t["tabla"] for t in esquema["tablas"]} == TABLAS_ESPERADAS


def test_columnas_coinciden_con_modelo(esquema):
    """Cada columna creada coincide con docs/modelo_dimensional.md: nombre, orden,
    tipo, nulos, PK, UNIQUE, IDENTITY, DEFAULT, FK y CHECK."""
    pk = {(k["tabla"], k["columna"]) for k in esquema["llaves"] if k["tipo"] == "PRIMARY KEY"}
    unicas = {(k["tabla"], k["columna"]) for k in esquema["llaves"] if k["tipo"] == "UNIQUE"}
    fks = {(f["tabla"], f["columna"]): f["tabla_ref"] for f in esquema["fks"]}
    checks = {c["restriccion"] for c in esquema["checks"]}

    for tabla, columnas_modelo in leer_modelo().items():
        columnas_bd = [c for c in esquema["columnas"] if c["tabla"] == tabla]
        assert [c["columna"] for c in columnas_bd] == [c["columna"] for c in columnas_modelo], (
            f"{tabla}: columnas distintas al modelo"
        )
        for bd, doc in zip(columnas_bd, columnas_modelo):
            columna = bd["columna"]
            nombre = f"{tabla}.{columna}"
            restriccion = doc["restriccion"]

            assert tipo_canonico_bd(bd["tipo"]) == tipo_canonico_modelo(doc["tipo"]), (
                f"{nombre}: tipo"
            )

            acepta_nulo = not re.search(r"NOT NULL|\bPK\b", restriccion)
            assert (bd["acepta_nulo"] == "YES") == acepta_nulo, f"{nombre}: nulos"

            es_pk = bool(re.search(r"\bPK\b", restriccion))
            assert ((tabla, columna) in pk) == es_pk, f"{nombre}: PK"

            es_unica = "UNIQUE" in restriccion
            assert ((tabla, columna) in unicas) == es_unica, f"{nombre}: UNIQUE"

            es_identity = "IDENTITY" in restriccion
            assert bd["identity"] == ("BY DEFAULT" if es_identity else None), (
                f"{nombre}: IDENTITY"
            )

            defecto = re.search(r"DEFAULT\s+(-?\d+(?:\.\d+)?)", restriccion)
            if defecto:
                assert float(bd["por_defecto"]) == float(defecto.group(1)), f"{nombre}: DEFAULT"
            else:
                assert bd["por_defecto"] is None, f"{nombre}: DEFAULT inesperado"

            fk_modelo = re.search(r"FK\s*→\s*(\w+)", restriccion)
            assert fks.get((tabla, columna)) == (fk_modelo.group(1) if fk_modelo else None), (
                f"{nombre}: FK"
            )

            tiene_check = "CHECK" in restriccion
            assert (f"ck_{tabla}_{columna}" in checks) == tiene_check, f"{nombre}: CHECK"


def test_fact_venta_tiene_las_7_fk_esperadas(esquema):
    fks = {
        f["columna"]: (f["tabla_ref"], f["columna_ref"])
        for f in esquema["fks"]
        if f["tabla"] == HECHO
    }
    assert fks == FK_ESPERADAS


def test_fk_son_restrict_y_de_una_columna(esquema):
    for f in esquema["fks"]:
        assert f["n_columnas"] == 1, f
        # 'r' = RESTRICT en pg_constraint
        assert (f["al_actualizar"], f["al_eliminar"]) == ("r", "r"), f


def test_ninguna_dimension_tiene_fk(esquema):
    """Estrella pura: solo la tabla de hechos referencia a otras tablas."""
    con_fk = {f["tabla"] for f in esquema["fks"]}
    assert con_fk == {HECHO}
    assert {f["tabla_ref"] for f in esquema["fks"]} <= DIMENSIONES


def test_fk_de_la_tabla_de_hechos_tienen_indice(esquema):
    """PostgreSQL no indexa las FK por su cuenta: el script crea uno por cada FK."""
    indices = {
        (i["tabla"], tuple(i["columnas"])): i["indice"]
        for i in esquema["indices"]
        if not i["de_restriccion"]
    }
    for columna in FK_ESPERADAS:
        assert indices.get((HECHO, (columna,))) == f"ix_{HECHO}_{columna}", columna


def test_nomenclatura_de_tablas_y_columnas(esquema):
    for t in esquema["tablas"]:
        assert PATRON_TABLA.match(t["tabla"]), f"Tabla fuera de norma: {t['tabla']}"
        # Heurística de singular válida para este modelo: ninguna entidad termina en "s".
        assert not t["tabla"].endswith("s"), f"Tabla en plural: {t['tabla']}"
    for c in esquema["columnas"]:
        assert PATRON_SNAKE.match(c["columna"]), (
            f"Columna fuera de norma: {c['tabla']}.{c['columna']}"
        )


def test_nomenclatura_de_llaves(esquema):
    for tabla in TABLAS_ESPERADAS:
        entidad = tabla.split("_", 1)[1]
        llaves_pk = [
            k for k in esquema["llaves"] if k["tabla"] == tabla and k["tipo"] == "PRIMARY KEY"
        ]
        # En la tabla de hechos la entidad es la venta: fact_venta -> id_venta.
        assert [k["columna"] for k in llaves_pk] == [f"id_{entidad}"], f"{tabla}: PK"
        assert {k["restriccion"] for k in llaves_pk} == {f"pk_{tabla}"}, f"{tabla}: nombre PK"

    for k in esquema["llaves"]:
        if k["tipo"] == "UNIQUE":
            assert k["restriccion"] == f"uq_{k['tabla']}_{k['columna']}", k

    for tabla in DIMENSIONES - {"dim_tiempo"}:
        entidad = tabla.removeprefix("dim_")
        assert {
            "tabla": tabla,
            "tipo": "UNIQUE",
            "restriccion": f"uq_{tabla}_codigo_{entidad}",
            "columna": f"codigo_{entidad}",
        } in esquema["llaves"], f"{tabla}: falta codigo_{entidad} UNIQUE"

    for f in esquema["fks"]:
        assert f["restriccion"] == f"fk_{f['tabla']}_{f['columna']}", f
        # La FK se llama igual que la PK referenciada, con sufijo de rol opcional.
        assert f["columna"] == f["columna_ref"] or f["columna"].startswith(
            f"{f['columna_ref']}_"
        ), f


def test_nomenclatura_de_checks_e_indices(esquema):
    """ck_<tabla>_<columna> e ix_<tabla>_<columna>, donde la columna es una de las
    que usa la restricción o el índice (un CHECK puede usar varias)."""
    for c in esquema["checks"]:
        nombres_validos = {f"ck_{c['tabla']}_{columna}" for columna in c["columnas"]}
        assert c["restriccion"] in nombres_validos, c
    for i in esquema["indices"]:
        if not i["de_restriccion"]:
            nombres_validos = {f"ix_{i['tabla']}_{columna}" for columna in i["columnas"]}
            assert i["indice"] in nombres_validos, i


def test_tablas_y_columnas_tienen_comentario(esquema):
    for t in esquema["tablas"]:
        assert (t["comentario"] or "").strip(), f"Tabla sin COMMENT: {t['tabla']}"
    for c in esquema["columnas"]:
        assert (c["comentario"] or "").strip(), (
            f"Columna sin COMMENT: {c['tabla']}.{c['columna']}"
        )


# ---------------------------------------------------------------------------
# Pruebas de las restricciones con datos (en la base temporal, con rollback)
# ---------------------------------------------------------------------------


def test_acepta_una_venta_valida(transaccion):
    conexion, llaves = transaccion
    assert insertar(conexion, HECHO, fila_venta(llaves)) >= 1


def test_dim_tiempo_acepta_tres_anios_de_fechas(transaccion):
    """Las fechas de 2022 a 2024 cumplen todos los CHECK de dim_tiempo. Incluye un
    año bisiesto y semanas ISO que cruzan el año (2022-01-02 es la semana 52 de
    2021 y 2024-12-30 es la semana 1 de 2025)."""
    conexion, _ = transaccion
    inicio, fin = date(2022, 1, 1), date(2024, 12, 31)
    filas = [fila_tiempo(inicio + timedelta(days=d)) for d in range((fin - inicio).days + 1)]
    with conexion.cursor() as cursor:
        cursor.executemany(
            consulta_insercion("dim_tiempo", list(filas[0])), [list(f.values()) for f in filas]
        )
    total = conexion.execute(
        "SELECT COUNT(*) FROM dwh.dim_tiempo WHERE anio BETWEEN 2022 AND 2024"
    ).fetchone()[0]
    assert total == 1096


@pytest.mark.parametrize(
    ("tabla", "construir_fila"),
    [
        pytest.param(
            "dim_tiempo", lambda _: {**fila_tiempo(date(2025, 3, 15)), "mes": 4},
            id="mes_distinto_de_la_fecha",
        ),
        pytest.param(
            "dim_tiempo", lambda _: {**fila_tiempo(date(2025, 3, 15)), "id_tiempo": 20250316},
            id="id_tiempo_distinto_de_la_fecha",
        ),
        pytest.param(
            "dim_tiempo", lambda _: {**fila_tiempo(date(2025, 3, 15)), "es_fin_de_semana": False},
            id="sabado_sin_marcar_como_fin_de_semana",
        ),
        pytest.param(
            "dim_cliente",
            lambda _: {**FILA_CLIENTE, "codigo_cliente": "PRUEBA-C2", "tipo_cliente": "pyme"},
            id="tipo_cliente_fuera_de_dominio",
        ),
        pytest.param(
            "dim_servicio",
            lambda _: {**FILA_SERVICIO, "codigo_servicio": "PRUEBA-S2",
                       "linea_negocio": "Buses Rapiditos"},
            id="linea_de_negocio_inexistente",
        ),
        pytest.param(
            HECHO, lambda llaves: fila_venta(llaves, monto_neto=11000),
            id="neto_distinto_de_bruto_menos_descuento",
        ),
        pytest.param(
            HECHO, lambda llaves: fila_venta(llaves, monto_descuento=13000, monto_neto=-1000),
            id="descuento_mayor_que_bruto",
        ),
        pytest.param(HECHO, lambda llaves: fila_venta(llaves, cantidad=0), id="cantidad_cero"),
        pytest.param(
            HECHO, lambda llaves: fila_venta(llaves, edad_cliente=150), id="edad_fuera_de_rango"
        ),
    ],
)  # fmt: skip
def test_check_rechaza_datos_inconsistentes(transaccion, tabla, construir_fila):
    conexion, llaves = transaccion
    with pytest.raises(errors.CheckViolation):
        insertar(conexion, tabla, construir_fila(llaves))


def test_fk_rechaza_venta_con_cliente_inexistente(transaccion):
    conexion, llaves = transaccion
    with pytest.raises(errors.ForeignKeyViolation):
        insertar(conexion, HECHO, fila_venta({**llaves, "id_cliente": llaves["id_cliente"] + 999}))
