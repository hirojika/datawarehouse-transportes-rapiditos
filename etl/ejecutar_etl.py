"""Ejecuta el ETL completo de Transportes Rapiditos.

1. (Opcional, --preparar) Etapas 1 y 2 en Python: lee data/raw/ y genera data/processed/.
2. Workflow principal de Apache Hop (etl/hop/principal.hwf): staging, dimensiones, hechos y
   validación de consistencia.

El registro de Hop se guarda en data/processed/etl_hop.log (lo usan las Estadísticas de
Procesamiento).

Uso (igual en Windows y Linux, desde la raíz del repositorio):
    python etl/ejecutar_etl.py              # solo Hop, con los archivos de data/processed
    python etl/ejecutar_etl.py --preparar   # primero regenera data/processed

Requisitos: Java 17 o superior; Apache Hop 2.20.0 en la carpeta indicada por la variable de
entorno HOP_HOME (por defecto, la carpeta hop dentro de la carpeta personal); archivo .env con
DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD; y el esquema dwh creado con sql/01_ddl.sql.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = RAIZ / "etl" / "hop"
LOG = RAIZ / "data" / "processed" / "etl_hop.log"
VARIABLES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def leer_env(ruta: Path) -> dict:
    """Lee un archivo .env (LLAVE=valor por línea) sin depender de paquetes externos."""
    valores = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                llave, valor = linea.split("=", 1)
                valores[llave.strip()] = valor.strip().strip("'\"")
    return valores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preparar", action="store_true", help="regenera data/processed antes")
    args = parser.parse_args()

    if args.preparar:
        script = RAIZ / "etl" / "python" / "preparar_datos.py"
        if subprocess.run([sys.executable, str(script)], cwd=script.parent).returncode:
            return 1

    env = leer_env(RAIZ / ".env")
    faltan = [v for v in VARIABLES if not env.get(v)]
    if faltan:
        print(f"Faltan en .env: {', '.join(faltan)}")
        return 1

    hop = Path(os.environ.get("HOP_HOME", Path.home() / "hop"))
    if os.name == "nt":
        comando = ["cmd", "/c", str(hop / "hop-run.bat")]
    else:
        comando = [str(hop / "hop-run.sh")]
    if not Path(comando[-1]).exists():
        print(f"No se encontró Apache Hop en {hop}. Defina la variable HOP_HOME.")
        return 1

    comando += [
        "--project-locations",
        f"rapiditos={PROYECTO}",
        "--project",
        "rapiditos",
        "--in-memory",
        "--runconfig",
        "local",
        "--level",
        "Basic",
        "--file",
        str(PROYECTO / "principal.hwf"),
    ]
    # shortcut: hop-run separa estos valores por comas, así que DB_PASSWORD no debe tener comas
    for v in VARIABLES:
        comando += ["--system-properties", f"{v}={env[v]}"]

    LOG.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.perf_counter()
    with open(LOG, "w", encoding="utf-8") as log:
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for linea in proceso.stdout:
            print(linea, end="")
            log.write(linea)
        codigo = proceso.wait()
    print(
        f"\nETL terminado en {time.perf_counter() - inicio:.0f} s con código {codigo}. "
        f"Registro: {LOG.relative_to(RAIZ)}"
    )
    return codigo


if __name__ == "__main__":
    sys.exit(main())
