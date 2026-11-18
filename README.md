# Proyecto Semestral BI — Transportes Rapiditos S.A. (Grupo 1)

Inteligencia de Negocios, INFB8101 Sección 412, UTEM. Todo el stack funciona en Linux y Windows.

Repositorio: https://github.com/hirojika/datawarehouse-transportes-rapiditos

Arquitectura de solución BI para la vista única del cliente de una empresa de transportes con seis líneas de negocio: Datawarehouse estrella en PostgreSQL 17, ETL con Apache Hop, cubo en Cube y dashboard en Streamlit.

Los PDF del curso (`referencias/`) no se versionan: se descargan de Canvas.

## Requisitos

- Docker y Docker Compose
  - Debian/Ubuntu: `sudo apt install docker.io docker-compose`, luego `sudo usermod -aG docker $USER` y volver a iniciar sesión.
  - Windows: Docker Desktop (con WSL 2).
- Python 3 y Git
- Java 17 o superior y Apache Hop 2.20.0 (para el ETL): descomprimir `apache-hop-client-2.20.0.zip` de https://downloads.apache.org/hop/2.20.0/ en la carpeta personal (queda `~/hop`) o definir la variable `HOP_HOME` con la carpeta de Hop.

## Puesta en marcha

```bash
git clone <url-del-repo>
cd proyecto-bi
python -m venv .venv
# Linux:   source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # Windows: copy .env.example .env
```

Editar `.env` y cambiar las dos claves (`DB_PASSWORD` y `PGADMIN_PASSWORD`).

Levantar PostgreSQL 17 y pgAdmin:

```bash
docker compose up -d
docker compose ps        # postgres debe aparecer como (healthy)
```

Los datos quedan en volúmenes de Docker: `docker compose down` detiene los servicios y conserva los datos, mientras que `docker compose down -v` los borra.

## Crear el DWH

Con `psql` dentro del contenedor (el comando es igual en Linux y Windows):

```bash
docker compose exec postgres psql -U rapiditos -d rapiditos -v ON_ERROR_STOP=1 -f /sql/01_ddl.sql
docker compose exec postgres psql -U rapiditos -d rapiditos -f /sql/99_validacion.sql
```

O desde pgAdmin:

1. Abrir `http://localhost:5050` y entrar con `PGADMIN_EMAIL` y `PGADMIN_PASSWORD` de `.env`.
2. En **Servers → Rapiditos (PostgreSQL 17)**, ingresar la clave `DB_PASSWORD`. La conexión ya viene configurada desde `docker/pgadmin/servers.json`.
3. Abrir el Query Tool sobre la base `rapiditos`, cargar `sql/01_ddl.sql` y ejecutarlo completo con F5.

`01_ddl.sql` se puede ejecutar las veces que se quiera: recrea el esquema `dwh` dentro de una transacción. La primera vez muestra el aviso `schema "dwh" does not exist, skipping`, que es normal.

La guía para exportar el diagrama del esquema estrella está en `docs/exportar_diagrama_pgadmin.md`.

## ETL (Avance N°2)

El ETL tiene dos partes: Python prepara los datos (`etl/python/`) y Apache Hop los carga (`etl/hop/`: workflow `principal.hwf` y pipelines `01_staging`, `02_dimensiones` y `03_hechos`). El detalle de cada fuente, su licencia y su uso está en `data/LEEME.md`.

1. **Datos.** Los archivos de las fuentes no se versionan. `python etl/python/descargar_fuentes.py` descarga las que no piden sesión a `data/raw/`. Las de Kaggle y Maven Analytics se descargan a mano, como indica `data/LEEME.md`.
2. **Carga completa.** Con los contenedores activos y `01_ddl.sql` ya ejecutado:

   ```bash
   python etl/ejecutar_etl.py --preparar   # prepara data/processed (unos 80 s) y ejecuta el workflow de Hop
   python etl/ejecutar_etl.py              # solo el workflow de Hop, con data/processed existente (unos 20 s)
   ```

   Cada ejecución recrea el esquema `stg`, vacía el `dwh` y lo vuelve a poblar. El workflow termina con `sql/04_validar_carga.sql`, que falla si alguna transacción se pierde o si los montos por línea no cuadran. El registro de Hop queda en `data/processed/etl_hop.log`.
3. **Hop GUI.** `python etl/abrir_hop_gui.py` registra el proyecto `rapiditos` y abre Hop GUI con las credenciales de `.env`.
4. **Estadísticas de Procesamiento.** `python herramientas/estadisticas_etl.py` genera las tablas del capítulo en `informe/secciones/estadisticas/`.
5. **DWH construido.** `python herramientas/exportar_dwh.py` genera `data/processed/05_datos_dwh.sql`, con los datos de las 7 tablas, para cargarlos sin Hop después de `01_ddl.sql`. No se versiona, porque contiene datos derivados de Delivery Center.

`sql/98_consultas_carga.sql` tiene consultas de verificación del DWH poblado: filas por tabla, rechazos, conciliación e indicadores.

## Pruebas y estilo

Con los contenedores activos y el venv activado:

```bash
pytest -v        # DDL en rapiditos_test (la crea y la borra); la carga se revisa en rapiditos, solo lectura
ruff check .
```

## Capturas para el informe

`herramientas/capturar_pgadmin.py` genera las capturas 02, 03 y 05a–05e del Avance N°1 en `docs/capturas/`, y la figura del esquema en `docs/diagramas/esquema_estrella.png`, que sobrescribe. La 01 (terminal) y la 04 (ERD con la interfaz) son capturas del grupo, y el script no las toca. Maneja el pgAdmin real con un navegador sin interfaz (Playwright y Chromium), usando un usuario de pgAdmin propio que se crea y se borra en cada ejecución. Por eso no altera tu espacio de trabajo en pgAdmin.

```bash
python -m playwright install chromium   # una sola vez: descarga el navegador
python herramientas/capturar_pgadmin.py
```

El script vuelve a ejecutar `01_ddl.sql`. Si alguna tabla de `dwh` ya tiene datos, se detiene sin tocar nada.

Avance N°2: `python herramientas/capturar_pgadmin.py --avance2` genera las capturas 06a–06f con las consultas de `sql/98_consultas_carga.sql` sobre el DWH poblado, sin modificarlo. Las capturas de Hop GUI (07a–07e) las hace el grupo, con las instrucciones de `docs/checklist_capturas.md`.

## Diccionario de datos del informe

`herramientas/generar_diccionario.py` lee el catálogo de PostgreSQL (tipos, nulos, llaves, `CHECK` y comentarios `COMMENT ON`) y escribe el Anexo A del informe en `informe/secciones/anexo_diccionario.tex`. Hay que volver a ejecutarlo cada vez que cambie `sql/01_ddl.sql`; el archivo generado no se edita a mano.

```bash
python herramientas/generar_diccionario.py
```

## Paquete de entrega

`herramientas/empaquetar_entrega.py` arma `entrega/Avance1_Grupo1_Rapiditos.zip` con lo que se sube a la plataforma del curso: el informe en PDF, `01_ddl.sql`, el esquema estrella, `99_validacion.sql`, la guía para Windows y un `LEEME.txt` que indica a qué entregable corresponde cada archivo. Antes hay que compilar el informe y la guía. El script comprueba que cada archivo del zip sea idéntico a su origen. La carpeta `entrega/` no se versiona, porque se regenera.

```bash
python herramientas/empaquetar_entrega.py
```

## Informe y dashboard

Informe (LaTeX), desde la carpeta `informe/`: `latexmk informe.tex`. `informe/.latexmkrc` elige LuaLaTeX; `latexmk -pdf informe.tex` usa pdfLaTeX. latexmk ejecuta BibTeX y repite las pasadas hasta resolver las referencias (Tabla 1.1, Figura 3.1) y las citas. Sin latexmk, la secuencia es `lualatex`, `bibtex`, `lualatex`, `lualatex`: con una sola pasada aparecen "??" y "[?]". Las referencias están en `informe/referencias.bib`.

`informe/guia_ejecucion_windows.pdf` (fuente `.tex` en la misma carpeta, se compila igual) es la guía para que el profesor ejecute el script en Windows: PostgreSQL y pgAdmin instalados directamente, `psql` o Docker Desktop.

En VS Code o VSCodium con LaTeX Workshop, `.vscode/settings.json` deja lista la receta "Informe (latexmk, LuaLaTeX y BibTeX)", que compila al guardar.

Dashboard: `streamlit run dashboard/app.py` → `http://localhost:8501`.

## Documentación

- `docs/modelo_dimensional.md`: fuente de verdad del diseño.
- `docs/bitacora.md`: registro de decisiones, cambios y verificaciones.
- `docs/checklist_capturas.md`: capturas para el informe.

## Reglas del grupo

- Nombres de tablas y columnas en `snake_case` y minúsculas.
- Todo en UTF-8.
- Nada de rutas absolutas.
- Antes de subir un script SQL, probarlo en una base limpia (`pytest` lo hace).
- Commits con mensajes descriptivos en español.
- Registrar decisiones y cambios en `docs/bitacora.md`.
