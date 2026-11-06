"""Genera el diccionario de datos del informe (Anexo A) desde el catálogo de PostgreSQL.

Lee las tablas del esquema dwh (tipos, nulos, llaves, CHECK y comentarios de
COMMENT ON) y escribe informe/secciones/anexo_diccionario.tex. Hay que volver a
ejecutarlo cada vez que cambie sql/01_ddl.sql, para que el anexo coincida con la
base.

Uso, desde la raíz del repositorio y con los contenedores activos:
  python herramientas/generar_diccionario.py
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "informe" / "secciones" / "anexo_diccionario.tex"

# Orden del anexo: la tabla de hechos primero y luego las dimensiones
TABLAS = [
    "fact_venta",
    "dim_tiempo",
    "dim_cliente",
    "dim_servicio",
    "dim_zona",
    "dim_canal_venta",
    "dim_medio_pago",
]

# Origen previsto de los datos de cada tabla (Sección Fuentes de Información)
ORIGEN = {
    "fact_venta": "Transacciones de las seis fuentes públicas de la Sección~\\ref{sec:fuentes} "
    "(una fila por pasaje, viaje, envío o pedido), asignadas a clientes sintéticos.",
    "dim_tiempo": "Se genera con un script SQL (\\bd{generate_series}) para 2023 a 2025; "
    "no requiere fuente externa.",
    "dim_cliente": "Sintética: clientes residentes en Chile, con la distribución por comuna, "
    "sexo y edad del Censo de Población y Vivienda 2024.",
    "dim_servicio": "Catálogo de los servicios de cada línea de negocio, con los atributos que "
    "informa cada fuente (tipo y clase de servicio, medio de transporte).",
    "dim_zona": "Tablas de zonas de cada fuente (zonas de taxi de Nueva York, puntos de ANTT, "
    "estaciones del Reino Unido, aeropuertos de EE.UU.) y comunas de Chile del Censo 2024.",
    "dim_canal_venta": "Canales de compra informados por las fuentes, normalizados a un "
    "catálogo común.",
    "dim_medio_pago": "Tipos de pago informados por las fuentes, normalizados a un catálogo "
    "común.",
}

CONSULTA_COLUMNAS = """
SELECT a.attname AS columna,
       format_type(a.atttypid, a.atttypmod) AS tipo,
       a.attnotnull AS no_nulo,
       col_description(a.attrelid, a.attnum) AS comentario,
       ARRAY(SELECT CASE con.contype WHEN 'p' THEN 'PK' WHEN 'f' THEN 'FK'
                                     WHEN 'u' THEN 'UQ' ELSE 'CK' END
             FROM pg_constraint con
             WHERE con.conrelid = a.attrelid
               AND a.attnum = ANY (con.conkey)
               AND (con.contype IN ('p', 'f', 'u')
                    OR con.conname = 'ck_' || %(tabla)s || '_' || a.attname)
             ORDER BY array_position(ARRAY['p', 'f', 'u', 'c']::"char"[], con.contype)
       ) AS llaves
FROM pg_attribute a
WHERE a.attrelid = ('dwh.' || %(tabla)s)::regclass
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""


def escapar(texto: str) -> str:
    """Escapa los caracteres especiales de LaTeX en un texto libre."""
    reemplazos = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(reemplazos.get(c, c) for c in texto)


def tipo_legible(tipo: str) -> str:
    """'character varying(20)' -> 'VARCHAR(20)'; 'numeric(12,2)' -> 'NUMERIC(12,2)'."""
    return tipo.replace("character varying", "varchar").upper()


def tabla_latex(conexion: psycopg.Connection, tabla: str) -> str:
    comentario = conexion.execute(
        "SELECT obj_description(('dwh.' || %s)::regclass, 'pg_class')", (tabla,)
    ).fetchone()[0]
    filas = conexion.execute(CONSULTA_COLUMNAS, {"tabla": tabla}).fetchall()
    lineas = [
        f"\\subsubsection{{Tabla \\bd{{{tabla}}}}}",
        "",
        f"{escapar(comentario or '')}. \\textbf{{Origen:}} {ORIGEN[tabla]}",
        "",
        "\\begin{table}[H]",
        "  \\centering",
        f"  \\caption{{Diccionario de datos de \\bd{{{tabla}}}}}",
        "  \\small",
        "  \\begin{tabularx}{\\linewidth}{@{}>{\\raggedright\\arraybackslash}p{4.0cm}"
        "lcl>{\\raggedright\\arraybackslash}X@{}}",
        "    \\toprule",
        "    \\textbf{Columna} & \\textbf{Tipo} & \\textbf{Nulo} & \\textbf{Clave}"
        " & \\textbf{Descripción} \\\\",
        "    \\midrule",
    ]
    for columna, tipo, no_nulo, descripcion, llaves in filas:
        lineas.append(
            f"    \\bd{{{columna}}} & {tipo_legible(tipo)} & {'No' if no_nulo else 'Sí'} & "
            f"{', '.join(llaves)} & {escapar(descripcion or '')} \\\\"
        )
    lineas += ["    \\bottomrule", "  \\end{tabularx}", "\\end{table}", ""]
    return "\n".join(lineas)


def main() -> None:
    load_dotenv(RAIZ / ".env")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "rapiditos"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "rapiditos"),
    ) as conexion:
        partes = [
            "% =============================================================================",
            "% Anexo A: Diccionario de Datos.",
            "% Generado por herramientas/generar_diccionario.py desde el catálogo de",
            "% PostgreSQL. No editar a mano: volver a ejecutar el script.",
            "% =============================================================================",
            "",
        ]
        partes += [tabla_latex(conexion, tabla) for tabla in TABLAS]
    SALIDA.write_text("\n".join(partes), encoding="utf-8")
    print(f"Diccionario generado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
