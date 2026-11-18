"""Abre Apache Hop GUI con el proyecto del ETL listo para usar.

1. Registra el proyecto "rapiditos" (carpeta etl/hop) en la configuración de Hop del equipo,
   si todavía no existe.
2. Abre Hop GUI pasándole las credenciales de .env como propiedades de Java, para que la
   conexión "rapiditos" funcione sin escribir la contraseña en ningún archivo del proyecto.

En Hop GUI, elegir el proyecto "rapiditos" en la barra superior y abrir principal.hwf o
pipelines/*.hpl con File > Open.

Uso (igual en Windows y Linux, desde la raíz del repositorio):
    python etl/abrir_hop_gui.py
Requisitos: los mismos de etl/ejecutar_etl.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from ejecutar_etl import leer_env

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = RAIZ / "etl" / "hop"
VARIABLES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def script(hop: Path, nombre: str) -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", str(hop / f"{nombre}.bat")]
    return [str(hop / f"{nombre}.sh")]


def main() -> int:
    env = leer_env(RAIZ / ".env")
    hop = Path(os.environ.get("HOP_HOME", Path.home() / "hop"))
    if not Path(script(hop, "hop-gui")[-1]).exists():
        print(f"No se encontró Apache Hop en {hop}. Defina la variable HOP_HOME.")
        return 1

    config = hop / "config" / "hop-config.json"
    proyectos = json.loads(config.read_text(encoding="utf-8")).get("projectsConfig", {})
    registrados = {p.get("projectName") for p in proyectos.get("projectConfigurations", [])}
    if "rapiditos" not in registrados:
        subprocess.run(
            script(hop, "hop-conf")
            + [
                "--project-create",
                "--project",
                "rapiditos",
                "--project-home",
                str(PROYECTO),
                "--project-config-file",
                "project-config.json",
            ],
            check=True,
        )

    # shortcut: la contraseña viaja como propiedad de Java (visible en los procesos del equipo);
    # basta para un equipo de desarrollo local
    propiedades = " ".join(f"-D{v}={env[v]}" for v in VARIABLES)
    entorno = dict(os.environ, HOP_OPTIONS=f"-Xmx2048m {propiedades}")
    subprocess.Popen(script(hop, "hop-gui"), env=entorno, cwd=hop)
    print("Hop GUI se está abriendo. Elegir el proyecto 'rapiditos' en la barra superior.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
