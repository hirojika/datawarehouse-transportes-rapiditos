"""Arma el paquete de entrega del Avance N°1 en entrega/.

Copia a una carpeta los archivos que se suben a la plataforma del curso, con
un LEEME.txt que indica a qué entregable corresponde cada uno, y la comprime
en un zip. Cada archivo del paquete funciona por sí solo: los scripts SQL no
dependen de rutas y los PDF no necesitan nada más.

Antes de empaquetar hay que compilar el informe y la guía (latexmk en
informe/), para que los PDF estén al día.

Uso, desde la raíz del repositorio:
  python herramientas/empaquetar_entrega.py
"""

import hashlib
import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE = "Avance1_Grupo1_Rapiditos"
DESTINO = RAIZ / "entrega" / NOMBRE
ZIP = RAIZ / "entrega" / f"{NOMBRE}.zip"

# Archivo de origen en el repositorio → nombre dentro del paquete. Los SQL y la
# guía conservan su nombre, porque las cabeceras de los scripts y el informe
# los citan así.
ARCHIVOS = {
    "informe/informe.pdf": "Informe_Avance1_Grupo1.pdf",
    "sql/01_ddl.sql": "01_ddl.sql",
    "docs/diagramas/esquema_estrella.png": "esquema_estrella.png",
    "sql/99_validacion.sql": "99_validacion.sql",
    "informe/guia_ejecucion_windows.pdf": "guia_ejecucion_windows.pdf",
}

LEEME = """\
Proyecto Semestral de Inteligencia de Negocios (INFB8101), Sección 412, UTEM
Caso: Transportes Rapiditos S.A. - Avance N°1
Grupo 1: Ignacio Ahumada Poque, Leonardo Solís Ortiz, Vicente Fuentes
Rodríguez y Gabriel García Vega
Profesor: Luis Cofré B.

Contenido del paquete
---------------------

Entregable 1. Informe con el enunciado del caso
  Informe_Avance1_Grupo1.pdf
    Capítulo 1, Caso de Negocio, con el enunciado; además Fuentes de
    Información, Arquitectura Propuesta, Modelamiento Dimensional, Scripts
    del Datawarehouse, Bibliografía y Anexos.

Entregable 2. Código fuente del script SQL de creación del modelo
multidimensional (tipo estrella)
  01_ddl.sql
    Crea en PostgreSQL 17 el esquema dwh con la tabla de hechos fact_venta
    y sus seis dimensiones, sin datos.

Entregable 3. Modelo multidimensional definido (esquema de tablas)
  esquema_estrella.png
    Diagrama del modelo estrella (ERD Tool de pgAdmin). El informe lo
    presenta en la Figura 4.1 y detalla cada columna en el Anexo A.

Archivos de apoyo
  99_validacion.sql
    Consultas que verifican lo creado por 01_ddl.sql. Resultado esperado
    (filas por consulta): 1, 7, 58, 14, 7, 20, 21, 7 y 0.
  guia_ejecucion_windows.pdf
    Guía paso a paso para ejecutar los scripts en Windows, con PostgreSQL
    y pgAdmin o con Docker Desktop.

Repositorio del proyecto
------------------------
https://github.com/hirojika/datawarehouse-transportes-rapiditos
Contiene el código fuente completo (scripts SQL, pruebas, herramientas,
fuentes del informe) y la bitácora del proyecto. El informe lo describe en
el Anexo C. No es necesario para ejecutar los scripts de este paquete.

Cómo ejecutar
-------------
Los dos scripts SQL funcionan desde cualquier carpeta y no dependen de otros
archivos. En pgAdmin, abrir 01_ddl.sql en el Query Tool de una base nueva
(por ejemplo, rapiditos) y ejecutarlo completo con F5. El detalle está en
guia_ejecucion_windows.pdf.
"""


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main() -> None:
    faltan = [origen for origen in ARCHIVOS if not (RAIZ / origen).is_file()]
    if faltan:
        raise SystemExit(f"Faltan archivos: {', '.join(faltan)}")

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)

    for origen, nombre in ARCHIVOS.items():
        shutil.copy2(RAIZ / origen, DESTINO / nombre)
    # UTF-8 con BOM y saltos de línea de Windows, para que el Bloc de notas
    # muestre bien las tildes y las líneas
    (DESTINO / "LEEME.txt").write_text(LEEME, encoding="utf-8-sig", newline="\r\n")

    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zip_entrega:
        for archivo in sorted(DESTINO.iterdir()):
            zip_entrega.write(archivo, f"{NOMBRE}/{archivo.name}")

    # Comprobación: cada archivo del zip es idéntico a su origen
    with zipfile.ZipFile(ZIP) as zip_entrega:
        for origen, nombre in ARCHIVOS.items():
            contenido = zip_entrega.read(f"{NOMBRE}/{nombre}")
            if hashlib.sha256(contenido).hexdigest() != sha256(RAIZ / origen):
                raise SystemExit(f"El archivo {nombre} del zip no coincide con {origen}")
        nombres = zip_entrega.namelist()

    print(f"Paquete: {ZIP.relative_to(RAIZ)} ({ZIP.stat().st_size / 1_048_576:.1f} MB)")
    for nombre in nombres:
        print(f"  {nombre}")


if __name__ == "__main__":
    main()
