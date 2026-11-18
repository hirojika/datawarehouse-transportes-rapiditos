"""Genera las tablas de la sección Estadísticas de Procesamiento del informe.

Lee:
- data/processed/estadisticas_preparacion.csv (filas leídas y tiempos de la preparación en Python)
- data/processed/etl_hop.log (registro de la última ejecución del workflow de Hop)
- la base rapiditos (staging, rechazos y modelo estrella), después de ejecutar el ETL

Escribe una tabla por archivo en informe/secciones/estadisticas/ (lineas, rechazos, hop,
tiempos y tablas), que incluye el capítulo estadisticas_de_procesamiento.tex.

Uso:  python herramientas/estadisticas_etl.py
"""

import csv
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from generar_diccionario import escapar

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "data" / "processed"
SALIDA = RAIZ / "informe" / "secciones" / "estadisticas"  # un archivo .tex por tabla

LINEAS = {
    "BUS": "Buses InterUrbanos",
    "TRN": "Trenes",
    "TAX": "Radio Taxis",
    "LOG": "Logística y Distribución",
    "AER": "Aerolíneas",
    "DEL": "URapid Delivery",
}
FUENTES = {
    "BUS": "Supertransporte",
    "TRN": "UK Train Rides",
    "TAX": "NYC TLC",
    "LOG": "Olist",
    "AER": "BTS DB1B",
    "DEL": "Delivery Center",
}


def n(valor) -> str:
    """Número con separador de miles chileno (punto)."""
    return f"{int(valor):,}".replace(",", ".")


def tabla(caption, label, columnas, encabezado, filas, nota=None) -> str:
    lineas = [
        "\\begin{table}[H]",
        "  \\centering",
        f"  \\caption{{{caption}}}",
        f"  \\label{{{label}}}",
        "  \\small",
        f"  \\begin{{tabularx}}{{\\linewidth}}{{@{{}}{columnas}@{{}}}}",
        "    \\toprule",
        "    " + " & ".join(f"\\textbf{{{e}}}" for e in encabezado) + " \\\\",
        "    \\midrule",
    ]
    for f in filas:
        if f == "---":
            lineas.append("    \\midrule")
        else:
            lineas.append("    " + " & ".join(f) + " \\\\")
    lineas += ["    \\bottomrule", "  \\end{tabularx}"]
    if nota:
        lineas.append(f"  \\par\\smallskip\\footnotesize {nota}")
    lineas += ["\\end{table}", ""]
    return "\n".join(lineas)


def leer_preparacion() -> dict:
    datos: dict = {}
    with open(PROCESADOS / "estadisticas_preparacion.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            datos.setdefault(fila["codigo_linea"], {})[fila["etapa"]] = float(fila["filas"])
    return datos


def leer_log() -> tuple[list, dict]:
    """Filas por transformación y duración de cada pipeline, según el registro de Hop."""
    texto = (PROCESADOS / "etl_hop.log").read_text(encoding="utf-8")
    pasos, duraciones, pipeline = [], {}, None
    for linea in texto.splitlines():
        m = re.search(r" - (\d\d_\w+) - Execution started", linea)
        if m:
            pipeline = m.group(1)
        m = re.search(
            r" - (.+)\.0 - Finished processing "
            r"\(I=(\d+), O=(\d+), R=(\d+), W=(\d+), U=\d+, E=(\d+)\)",
            linea,
        )
        if m and pipeline:
            nombre, i, o, r, w, e = m.groups()
            pasos.append((pipeline, nombre, max(int(i), int(r)), max(int(o), int(w)), int(e)))
        m = re.search(r" - (\w+) - (?:Pipeline|Workflow) duration : ([\d.]+) seconds", linea)
        if m:
            duraciones[m.group(1)] = float(m.group(2))
    return pasos, duraciones


def main() -> None:
    load_dotenv(RAIZ / ".env")
    prep = leer_preparacion()
    pasos, duraciones = leer_log()
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "rapiditos"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "rapiditos"),
    ) as cx:

        def por_linea(consulta):
            return dict(cx.execute(consulta).fetchall())

        stg = por_linea("SELECT codigo_linea, COUNT(*) FROM stg.transaccion GROUP BY 1")
        rech = por_linea("SELECT codigo_linea, COUNT(*) FROM stg.rechazo GROUP BY 1")
        hechos = por_linea(
            "SELECT LEFT(numero_transaccion, 3), COUNT(*) FROM dwh.fact_venta GROUP BY 1"
        )
        motivos = cx.execute(
            "SELECT motivo, codigo_linea, COUNT(*) FROM stg.rechazo GROUP BY 1, 2 ORDER BY 3 DESC"
        ).fetchall()
        conteos = []
        for esquema, nombre in cx.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('stg', 'dwh') AND table_type = 'BASE TABLE' "
            "ORDER BY 1 DESC, (table_name LIKE 'fact%'), table_name"
        ).fetchall():
            filas = cx.execute(f'SELECT COUNT(*) FROM "{esquema}"."{nombre}"').fetchone()[0]
            conteos.append((esquema, nombre, filas))

    # Tabla 1: embudo por línea
    filas, tot = [], [0, 0, 0, 0]
    for c, nombre in LINEAS.items():
        leidas = prep[c]["filas leídas"]
        fila_vals = [leidas, stg.get(c, 0), rech.get(c, 0), hechos.get(c, 0)]
        tot = [a + b for a, b in zip(tot, fila_vals)]
        filas.append(
            [escapar(nombre), escapar(FUENTES[c])]
            + [n(v) for v in fila_vals]
            + [f"{100 * hechos.get(c, 0) / stg[c]:.1f} \\%".replace(".", ",")]
        )
    filas += [
        "---",
        ["\\textbf{Total}", ""]
        + [f"\\textbf{{{n(v)}}}" for v in tot]
        + [f"\\textbf{{{100 * tot[3] / tot[1]:.1f} \\%}}".replace(".", ",")],
    ]
    partes = [
        tabla(
            "Registros procesados por línea de negocio",
            "tab:est_lineas",
            ">{\\raggedright\\arraybackslash}p{2.6cm}>{\\raggedright\\arraybackslash}Xrrrrr",
            ["Línea", "Fuente", "Leídos", "Staging", "Rechazados", "Cargados", "\\% carga"],
            filas,
            "Leídos: filas de la fuente leídas por la preparación en Python. Staging: muestra "
            "cargada en stg.transaccion. Cargados: filas de fact\\_venta. El porcentaje de carga "
            "se calcula sobre staging.",
        ),
    ]

    # Tabla 2: motivos de rechazo
    filas = [[escapar(m), escapar(LINEAS[c]), n(k)] for m, c, k in motivos]
    filas += ["---", ["\\textbf{Total}", "", f"\\textbf{{{n(sum(k for *_, k in motivos))}}}"]]
    partes.append(
        tabla(
            "Transacciones rechazadas por motivo",
            "tab:est_rechazos",
            ">{\\raggedright\\arraybackslash}Xlr",
            ["Motivo (regla de calidad)", "Línea", "Filas"],
            filas,
        )
    )

    # Tabla 3: filas por transformación de Hop
    filas, previo = [], None
    for pipeline, nombre, entrada, salida, errores in pasos:
        if previo and pipeline != previo:
            filas.append("---")
        filas.append(
            [
                escapar(pipeline) if pipeline != previo else "",
                escapar(nombre),
                n(entrada),
                n(salida),
                n(errores),
            ]
        )
        previo = pipeline
    partes.append(
        tabla(
            "Filas por transformación en la ejecución del ETL (registro de Apache Hop)",
            "tab:est_hop",
            "l>{\\raggedright\\arraybackslash}Xrrr",
            ["Pipeline", "Transformación", "Entrada", "Salida", "Errores"],
            filas,
            "Entrada: filas leídas del archivo, de la base o de la transformación anterior. "
            "Salida: filas escritas en la base o enviadas a la transformación siguiente. "
            "En los archivos CSV, la entrada incluye la fila de encabezado.",
        )
    )

    # Tabla 4: tiempos
    def seg(s: float) -> str:
        return f"{s:.1f}".replace(".", ",")

    filas = [
        [escapar(f"Preparación en Python: {LINEAS[c]}"), seg(prep[c]["segundos"])] for c in LINEAS
    ]
    filas += [
        [escapar(f"Hop: pipeline {p}"), seg(s)] for p, s in duraciones.items() if p != "principal"
    ]
    if "principal" in duraciones:
        filas += [
            "---",
            [
                "\\textbf{Workflow principal de Hop (total)}",
                f"\\textbf{{{seg(duraciones['principal'])}}}",
            ],
        ]
    partes.append(
        tabla(
            "Tiempo de ejecución por etapa",
            "tab:est_tiempos",
            ">{\\raggedright\\arraybackslash}Xr",
            ["Etapa", "Segundos"],
            filas,
        )
    )

    # Tabla 5: filas por tabla
    filas = [[f"\\bd{{{e}.{escapar(t)}}}", n(k)] for e, t, k in conteos]
    partes.append(
        tabla(
            "Filas por tabla después de la carga",
            "tab:est_tablas",
            ">{\\raggedright\\arraybackslash}Xr",
            ["Tabla", "Filas"],
            filas,
        )
    )

    SALIDA.mkdir(parents=True, exist_ok=True)
    nombres = ["lineas", "rechazos", "hop", "tiempos", "tablas"]
    for nombre, contenido in zip(nombres, partes, strict=True):
        (SALIDA / f"{nombre}.tex").write_text(
            "% Generado por herramientas/estadisticas_etl.py. No editar a mano.\n" + contenido,
            encoding="utf-8",
        )
    print(f"Generadas {len(nombres)} tablas en {SALIDA.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
