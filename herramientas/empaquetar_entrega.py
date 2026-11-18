"""Arma el paquete de entrega del Avance N°2 en entrega/.

Copia a una carpeta los archivos que se suben a la plataforma del curso, con un LEEME.txt
que indica a qué entregable corresponde cada uno, y la comprime en un zip. La carpeta
conserva la estructura del repositorio (sql/, etl/, data/processed/), porque el proyecto de
Apache Hop ubica los scripts y los archivos preparados con rutas relativas. Los scripts SQL
siguen siendo autónomos: cada uno funciona copiado solo a cualquier carpeta.

Antes de empaquetar hay que:
- compilar el informe y la guía (latexmk en informe/);
- ejecutar el ETL final (python etl/ejecutar_etl.py --preparar);
- generar el DWH construido (python herramientas/exportar_dwh.py).

El paquete del Avance N°1 se arma con la versión de este script del commit de ese avance.

Uso, desde la raíz del repositorio:
  python herramientas/empaquetar_entrega.py
"""

import hashlib
import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE = "Avance2_Grupo1_Rapiditos"
DESTINO = RAIZ / "entrega" / NOMBRE
ZIP = RAIZ / "entrega" / f"{NOMBRE}.zip"

# Archivo de origen en el repositorio → ruta dentro del paquete
ARCHIVOS = {
    "informe/informe.pdf": "Informe_Avance2_Grupo1.pdf",
    "informe/guia_ejecucion_windows.pdf": "guia_ejecucion_windows.pdf",
    "docs/diagramas/esquema_estrella.png": "esquema_estrella.png",
    ".env.example": ".env.example",
    "data/LEEME.md": "data/LEEME.md",
    "data/processed/05_datos_dwh.sql": "sql/05_datos_dwh.sql",
}
# Carpetas que se copian con su estructura (patrón glob relativo a la raíz)
PATRONES = [
    "sql/0[1-4]_*.sql",
    "sql/9[89]_*.sql",
    "etl/*.py",
    "etl/python/*.py",
    "etl/referencias/*.csv",
    "etl/hop/project-config.json",
    "etl/hop/*.hwf",
    "etl/hop/pipelines/*.hpl",
    "etl/hop/metadata/**/*.json",
    "data/processed/clientes.csv",
    "data/processed/zonas.csv",
    "data/processed/transacciones.csv",
    "data/processed/tipo_cambio.csv",
    "data/processed/estadisticas_preparacion.csv",
]

LEEME = """\
Proyecto Semestral de Inteligencia de Negocios (INFB8101), Sección 412, UTEM
Caso: Transportes Rapiditos S.A. - Avance N°2
Grupo 1: Ignacio Ahumada Poque, Leonardo Solís Ortiz, Vicente Fuentes
Rodríguez y Gabriel García Vega
Profesor: Luis Cofré B.

Contenido del paquete
---------------------

Entregable 1. Informe de seguimiento del proyecto BI
  Informe_Avance2_Grupo1.pdf
    Informe actualizado: Caso de Negocio, Fuentes de Información,
    Arquitectura Propuesta, Estadísticas de Procesamiento (nuevo),
    Modelamiento Dimensional, Scripts del Datawarehouse y Seguimiento del
    Proyecto (nuevo).

Entregable 2. Scripts del Datawarehouse construido (carpeta sql)
  01_ddl.sql            Crea el modelo estrella (esquema dwh), sin datos.
  05_datos_dwh.sql      Datawarehouse construido: carga los datos de las 7
                        tablas (118.263 ventas). Ejecutar después de
                        01_ddl.sql. No requiere Apache Hop.
  02_stg.sql            Esquema de staging del ETL y vista de conformación.
  03_preparar_carga.sql Prepara el dwh para la carga y genera dim_tiempo.
  04_validar_carga.sql  Validación de consistencia con que termina el ETL.
  98_consultas_carga.sql  Consultas de verificación del DWH poblado.
  99_validacion.sql     Consultas que verifican la estructura (Avance N°1).
  Los scripts 02 a 04 los ejecuta el ETL; también funcionan solos.

Entregable 3. ETL correspondientes (proyecto de integración)
  etl/hop/              Proyecto de Apache Hop 2.20.0: workflow
                        principal.hwf y pipelines 01_staging, 02_dimensiones
                        y 03_hechos.
  etl/referencias/      Catálogos y equivalencias que aplica el ETL.
  etl/python/           Extracción y preparación de los datos (Python).
  etl/ejecutar_etl.py   Ejecuta el ETL completo con hop-run.
  etl/abrir_hop_gui.py  Abre el proyecto en Hop GUI.
  data/processed/       Archivos ya preparados, para ejecutar el ETL de Hop
                        sin descargar las fuentes.

Archivos de apoyo
  guia_ejecucion_windows.pdf  Cómo ejecutar los scripts y el ETL en Windows
                              (secciones A y B: modelo; sección C: Avance N°2).
  esquema_estrella.png        Diagrama del modelo estrella.
  data/LEEME.md               Fuentes de datos, licencias y uso en el ETL.
  .env.example                Plantilla de la conexión que usa el ETL.

Cómo ejecutar
-------------
Revisión rápida: en pgAdmin, ejecutar sql/01_ddl.sql y luego
sql/05_datos_dwh.sql en una base nueva (por ejemplo, rapiditos).
ETL completo: seguir la sección C.2 de guia_ejecucion_windows.pdf
(Java 17+, Apache Hop 2.20.0 y Python 3; luego python etl\\ejecutar_etl.py).

Datos
-----
Los clientes son sintéticos y las transacciones provienen de datasets
públicos, con fechas trasladadas a 2023-2025 y montos convertidos a pesos
chilenos (ver Fuentes de Información en el informe). 05_datos_dwh.sql y
data/processed contienen datos derivados del dataset Delivery Center, cuya
licencia no es abierta: se entregan solo para la evaluación del curso y no
deben redistribuirse.

Repositorio del proyecto
------------------------
https://github.com/hirojika/datawarehouse-transportes-rapiditos
Contiene el código fuente completo y la bitácora del proyecto (Anexo C del
informe). No es necesario para ejecutar los archivos de este paquete.
"""


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main() -> None:
    copias = dict(ARCHIVOS)
    for patron in PATRONES:
        encontrados = sorted(RAIZ.glob(patron))
        if not encontrados:
            raise SystemExit(f"Ningún archivo coincide con {patron}")
        copias |= {str(f.relative_to(RAIZ)): str(f.relative_to(RAIZ)) for f in encontrados}
    faltan = [origen for origen in copias if not (RAIZ / origen).is_file()]
    if faltan:
        raise SystemExit(f"Faltan archivos: {', '.join(faltan)}")

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    for origen, nombre in copias.items():
        (DESTINO / nombre).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / origen, DESTINO / nombre)
    # UTF-8 con BOM y saltos de línea de Windows, para que el Bloc de notas
    # muestre bien las tildes y las líneas
    (DESTINO / "LEEME.txt").write_text(LEEME, encoding="utf-8-sig", newline="\r\n")

    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_entrega:
        for archivo in sorted(p for p in DESTINO.rglob("*") if p.is_file()):
            zip_entrega.write(archivo, f"{NOMBRE}/{archivo.relative_to(DESTINO).as_posix()}")

    # Comprobación: cada archivo del zip es idéntico a su origen
    with zipfile.ZipFile(ZIP) as zip_entrega:
        for origen, nombre in copias.items():
            contenido = zip_entrega.read(f"{NOMBRE}/{Path(nombre).as_posix()}")
            if hashlib.sha256(contenido).hexdigest() != sha256(RAIZ / origen):
                raise SystemExit(f"El archivo {nombre} del zip no coincide con {origen}")
        total = len(zip_entrega.namelist())

    print(
        f"Paquete: {ZIP.relative_to(RAIZ)} ({ZIP.stat().st_size / 1_048_576:.1f} MB, "
        f"{total} archivos)"
    )


if __name__ == "__main__":
    main()
