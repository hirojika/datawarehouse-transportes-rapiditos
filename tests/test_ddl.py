"""Pruebas del DDL del DWH (sql/01_ddl.sql) contra la MariaDB local de XAMPP.

El script se ejecuta sobre una base de prueba aparte (por defecto
dwh_rapiditos_test) para no borrar nunca dwh_rapiditos, que en fases
posteriores tendrá datos. Al terminar, la base de prueba se elimina.

Requisitos: XAMPP con MySQL/MariaDB activo y el archivo .env configurado.
Ejecutar desde la raíz del repositorio con: pytest -v
"""

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

RAIZ = Path(__file__).resolve().parents[1]
RUTA_DDL = RAIZ / "sql" / "01_ddl.sql"
RUTA_MODELO = RAIZ / "docs" / "modelo_dimensional.md"

BASE_PRODUCCION = "dwh_rapiditos"

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

load_dotenv(RAIZ / ".env")
BASE_PRUEBA = os.getenv("DB_NAME_TEST", "dwh_rapiditos_test")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def leer_ddl() -> str:
    return RUTA_DDL.read_text(encoding="utf-8")


def sentencias_ddl(script: str) -> list[str]:
    """Separa el script en sentencias.

    Corta en ';' y omite los comentarios '--', salvo dentro de textos entre
    comillas simples (los COMMENT pueden contener ';').
    """
    sentencias, actual, en_texto, i = [], [], False, 0
    while i < len(script):
        caracter = script[i]
        if en_texto:
            actual.append(caracter)
            if caracter == "\\":
                actual.append(script[i + 1])
                i += 1
            elif caracter == "'":
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
    """Normaliza un tipo del modelo: 'TINYINT(1)' -> 'TINYINT'."""
    tipo = re.sub(r"\s+", " ", tipo.strip().upper())
    return re.sub(r"^(TINYINT|SMALLINT|MEDIUMINT|INT|BIGINT)\(\d+\)", r"\1", tipo)


def tipo_canonico_bd(columna: dict) -> str:
    """Construye el tipo desde information_schema con el mismo formato del modelo."""
    tipo = columna["data_type"].upper()
    if tipo in ("VARCHAR", "CHAR"):
        tipo += f"({columna['largo']})"
    elif tipo == "DECIMAL":
        tipo += f"({columna['precision']},{columna['escala']})"
    if "unsigned" in columna["column_type"].lower():
        tipo += " UNSIGNED"
    return tipo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def motor():
    if BASE_PRUEBA == BASE_PRODUCCION:
        pytest.fail("DB_NAME_TEST no puede ser dwh_rapiditos: el test borraría el DWH real.")
    url = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except OperationalError as error:
        pytest.fail(
            "No se pudo conectar a MariaDB con los datos de .env. "
            f"¿Está XAMPP corriendo (sudo /opt/lampp/lampp start)? Detalle: {error}"
        )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def esquema(motor):
    """Ejecuta el DDL sobre la base de prueba y devuelve su metadata.

    Las sentencias se ejecutan una a una para registrar los avisos (SHOW
    WARNINGS) de cada una, igual que los muestra phpMyAdmin. El script corre
    dos veces: la segunda prueba el DROP DATABASE sobre una base que ya existe.
    """
    script = re.sub(rf"\b{BASE_PRODUCCION}\b", BASE_PRUEBA, leer_ddl())
    avisos = []

    # Si el script falla a mitad de camino, la base de prueba igual se elimina.
    try:
        conexion_cruda = motor.raw_connection()
        try:
            cursor = conexion_cruda.cursor()
            for ejecucion in (1, 2):
                for sentencia in sentencias_ddl(script):
                    cursor.execute(sentencia)
                    cursor.execute("SHOW WARNINGS")
                    for nivel, codigo, mensaje in cursor.fetchall():
                        avisos.append(
                            {
                                "ejecucion": ejecucion,
                                "sentencia": sentencia[:60],
                                "nivel": nivel,
                                "codigo": codigo,
                                "mensaje": mensaje,
                            }
                        )
            cursor.close()
        finally:
            conexion_cruda.close()

        parametros = {"esquema": BASE_PRUEBA}
        with motor.connect() as conexion:

            def consultar(sql: str) -> list[dict]:
                return [dict(f) for f in conexion.execute(text(sql), parametros).mappings()]

            datos = {
                "avisos": avisos,
                "base": consultar(
                    """SELECT DEFAULT_CHARACTER_SET_NAME AS charset,
                              DEFAULT_COLLATION_NAME AS collation_base
                       FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = :esquema"""
                ),
                "tablas": consultar(
                    """SELECT TABLE_NAME AS tabla, ENGINE AS motor,
                              TABLE_COLLATION AS collation_tabla, TABLE_COMMENT AS comentario
                       FROM information_schema.TABLES WHERE TABLE_SCHEMA = :esquema"""
                ),
                "columnas": consultar(
                    """SELECT TABLE_NAME AS tabla, COLUMN_NAME AS columna,
                              DATA_TYPE AS data_type, COLUMN_TYPE AS column_type,
                              CHARACTER_MAXIMUM_LENGTH AS largo, NUMERIC_PRECISION AS `precision`,
                              NUMERIC_SCALE AS escala, IS_NULLABLE AS acepta_nulo,
                              COLUMN_DEFAULT AS por_defecto, EXTRA AS extra,
                              CHARACTER_SET_NAME AS charset, COLUMN_COMMENT AS comentario
                       FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :esquema
                       ORDER BY TABLE_NAME, ORDINAL_POSITION"""
                ),
                "llaves": consultar(
                    """SELECT tc.TABLE_NAME AS tabla, tc.CONSTRAINT_TYPE AS tipo,
                              tc.CONSTRAINT_NAME AS restriccion, k.COLUMN_NAME AS columna
                       FROM information_schema.TABLE_CONSTRAINTS tc
                       JOIN information_schema.KEY_COLUMN_USAGE k
                         ON k.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
                        AND k.TABLE_NAME = tc.TABLE_NAME
                        AND k.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                       WHERE tc.TABLE_SCHEMA = :esquema
                         AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')"""
                ),
                "fks": consultar(
                    """SELECT TABLE_NAME AS tabla, CONSTRAINT_NAME AS restriccion,
                              COLUMN_NAME AS columna, REFERENCED_TABLE_NAME AS tabla_ref,
                              REFERENCED_COLUMN_NAME AS columna_ref
                       FROM information_schema.KEY_COLUMN_USAGE
                       WHERE TABLE_SCHEMA = :esquema AND REFERENCED_TABLE_NAME IS NOT NULL"""
                ),
            }

        yield datos
    finally:
        with motor.connect() as conexion:
            conexion.execute(text(f"DROP DATABASE IF EXISTS `{BASE_PRUEBA}`"))


# ---------------------------------------------------------------------------
# Pruebas estáticas del script (no requieren base de datos)
# ---------------------------------------------------------------------------


def test_script_es_idempotente():
    sentencias = sentencias_ddl(leer_ddl())
    assert sentencias[0] == f"DROP DATABASE IF EXISTS {BASE_PRODUCCION}"
    assert sentencias[1].startswith(f"CREATE DATABASE {BASE_PRODUCCION}")
    assert sentencias[2] == f"USE {BASE_PRODUCCION}"


def test_script_sin_load_data_ni_rutas_absolutas():
    ddl = leer_ddl()
    assert not re.search(r"LOAD\s+DATA|INFILE", ddl, re.IGNORECASE)
    assert not re.search(r"\b[A-Za-z]:\\", ddl), "Ruta absoluta de Windows en el script"
    assert not re.search(r"(?<![\w/])/(home|opt|usr|var|tmp|mnt)/", ddl), (
        "Ruta absoluta en el script"
    )


def test_dimensiones_se_crean_antes_que_hechos():
    orden = re.findall(r"CREATE TABLE (\w+)", leer_ddl())
    assert set(orden) == TABLAS_ESPERADAS
    assert orden[-1] == HECHO


def test_pk_declaradas_sin_nombre():
    # MariaDB ignora el nombre de la PK (la llama PRIMARY) y avisa con #1280.
    assert not re.search(r"CONSTRAINT\s+\w+\s+PRIMARY KEY", leer_ddl())


def test_modelo_documentado_tiene_las_7_tablas():
    assert set(leer_modelo()) == TABLAS_ESPERADAS


# ---------------------------------------------------------------------------
# Pruebas contra MariaDB
# ---------------------------------------------------------------------------


def test_ddl_se_ejecuta_sin_avisos(esquema):
    """El script debe correr limpio en phpMyAdmin. Solo se tolera la nota #1008
    del DROP DATABASE IF EXISTS cuando la base todavía no existe."""
    inesperados = [
        a for a in esquema["avisos"] if not (a["nivel"] == "Note" and a["codigo"] == 1008)
    ]
    if any(a["codigo"] in (1558, 1545) for a in inesperados):
        pytest.fail(
            "Las tablas de sistema de MariaDB (mysql.proc, mysql.event) están desactualizadas; "
            "no es un error del script. Ejecutar mysql_upgrade (ver README). "
            f"Avisos: {inesperados}"
        )
    assert inesperados == []


def test_existen_las_7_tablas(esquema):
    assert {t["tabla"] for t in esquema["tablas"]} == TABLAS_ESPERADAS


def test_columnas_coinciden_con_modelo(esquema):
    """Cada columna creada coincide con docs/modelo_dimensional.md: nombre, orden,
    tipo, nulos, PK, UNIQUE, AUTO_INCREMENT, DEFAULT y FK."""
    pk = {(k["tabla"], k["columna"]) for k in esquema["llaves"] if k["tipo"] == "PRIMARY KEY"}
    unicas = {(k["tabla"], k["columna"]) for k in esquema["llaves"] if k["tipo"] == "UNIQUE"}
    fks = {(f["tabla"], f["columna"]): f["tabla_ref"] for f in esquema["fks"]}

    for tabla, columnas_modelo in leer_modelo().items():
        columnas_bd = [c for c in esquema["columnas"] if c["tabla"] == tabla]
        assert [c["columna"] for c in columnas_bd] == [c["columna"] for c in columnas_modelo], (
            f"{tabla}: columnas distintas al modelo"
        )
        for bd, doc in zip(columnas_bd, columnas_modelo):
            nombre = f"{tabla}.{bd['columna']}"
            restriccion = doc["restriccion"]

            assert tipo_canonico_bd(bd) == tipo_canonico_modelo(doc["tipo"]), f"{nombre}: tipo"

            acepta_nulo = not re.search(r"NOT NULL|\bPK\b", restriccion)
            assert (bd["acepta_nulo"] == "YES") == acepta_nulo, f"{nombre}: nulos"

            es_pk = bool(re.search(r"\bPK\b", restriccion))
            assert ((tabla, bd["columna"]) in pk) == es_pk, f"{nombre}: PK"

            es_unica = "UNIQUE" in restriccion
            assert ((tabla, bd["columna"]) in unicas) == es_unica, f"{nombre}: UNIQUE"

            es_autoinc = "AUTO_INCREMENT" in restriccion
            assert ("auto_increment" in bd["extra"].lower()) == es_autoinc, (
                f"{nombre}: AUTO_INCREMENT"
            )

            defecto = re.search(r"DEFAULT\s+(\S+)", restriccion)
            if defecto:
                assert float(bd["por_defecto"]) == float(defecto.group(1)), f"{nombre}: DEFAULT"
            else:
                assert bd["por_defecto"] in (None, "NULL"), f"{nombre}: DEFAULT inesperado"

            fk_modelo = re.search(r"FK\s*→\s*(\w+)", restriccion)
            assert fks.get((tabla, bd["columna"])) == (fk_modelo.group(1) if fk_modelo else None), (
                f"{nombre}: FK"
            )


def test_fact_venta_tiene_las_7_fk_esperadas(esquema):
    fks = {
        f["columna"]: (f["tabla_ref"], f["columna_ref"])
        for f in esquema["fks"]
        if f["tabla"] == HECHO
    }
    assert fks == FK_ESPERADAS


def test_ninguna_dimension_tiene_fk(esquema):
    """Estrella pura: solo la tabla de hechos referencia a otras tablas."""
    con_fk = {f["tabla"] for f in esquema["fks"]}
    assert con_fk == {HECHO}
    assert {f["tabla_ref"] for f in esquema["fks"]} <= DIMENSIONES


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
        columnas_pk = [
            k["columna"]
            for k in esquema["llaves"]
            if k["tabla"] == tabla and k["tipo"] == "PRIMARY KEY"
        ]
        # En la tabla de hechos la entidad es la venta: fact_venta -> id_venta.
        assert columnas_pk == [f"id_{entidad}"], f"{tabla}: PK debe ser id_{entidad}"

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


def test_motor_innodb_y_utf8mb4(esquema):
    assert esquema["base"] == [{"charset": "utf8mb4", "collation_base": "utf8mb4_unicode_ci"}]
    for t in esquema["tablas"]:
        assert t["motor"] == "InnoDB", t["tabla"]
        assert t["collation_tabla"] == "utf8mb4_unicode_ci", t["tabla"]
    for c in esquema["columnas"]:
        if c["charset"] is not None:
            assert c["charset"] == "utf8mb4", f"{c['tabla']}.{c['columna']}"


def test_tablas_y_columnas_tienen_comentario(esquema):
    for t in esquema["tablas"]:
        assert t["comentario"].strip(), f"Tabla sin COMMENT: {t['tabla']}"
    for c in esquema["columnas"]:
        assert c["comentario"].strip(), f"Columna sin COMMENT: {c['tabla']}.{c['columna']}"
