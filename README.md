# Proyecto Semestral BI — Transportes Rapiditos S.A. (Grupo 1)

Inteligencia de Negocios, INFB8101 Sección 412, UTEM. Todo el stack funciona en Linux y Windows.

Repositorio: https://github.com/hirojika/datawarehouse-transportes-rapiditos

Arquitectura de solución BI para la vista única del cliente de una empresa de transportes con seis líneas de negocio: Datawarehouse estrella en PostgreSQL 17, ETL con Apache Hop, cubo en Cube y dashboard en Streamlit.

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
4. **DWH construido.** El paquete de entrega incluye `05_datos_dwh.sql`, con los datos de las 7 tablas, para cargarlos sin Hop después de `01_ddl.sql`. No se versiona, porque contiene datos derivados de Delivery Center.

`sql/98_consultas_carga.sql` tiene consultas de verificación del DWH poblado: filas por tabla, rechazos, conciliación e indicadores.

## Pruebas

Con los contenedores activos y el venv activado:

```bash
pytest -v        # DDL en rapiditos_test (la crea y la borra); la carga se revisa en rapiditos, solo lectura
```

## Informe y dashboard

Informe (LaTeX), desde la carpeta `informe/`: `latexmk informe.tex`. `informe/.latexmkrc` elige LuaLaTeX; `latexmk -pdf informe.tex` usa pdfLaTeX. latexmk ejecuta BibTeX y repite las pasadas hasta resolver las referencias (Tabla 1.1, Figura 3.1) y las citas. Sin latexmk, la secuencia es `lualatex`, `bibtex`, `lualatex`, `lualatex`: con una sola pasada aparecen "??" y "[?]". Las referencias están en `informe/referencias.bib`.

`informe/guia_ejecucion_windows.pdf` (fuente `.tex` en la misma carpeta, se compila igual) es la guía para que el profesor ejecute el script en Windows: PostgreSQL y pgAdmin instalados directamente, `psql` o Docker Desktop.

Dashboard: `streamlit run dashboard/app.py` → `http://localhost:8501`.

## Documentación

- `docs/modelo_dimensional.md`: fuente de verdad del diseño.
- `docs/fuentes_de_informacion.md`: fuentes de datos de cada línea de negocio.

## Reglas del grupo

- Nombres de tablas y columnas en `snake_case` y minúsculas.
- Todo en UTF-8.
- Nada de rutas absolutas.
- Antes de subir un script SQL, probarlo en una base limpia (`pytest` lo hace).
- Commits con mensajes descriptivos en español.
