# Checklist de capturas para el informe

La rúbrica otorga el puntaje máximo con **más de 7 capturas** que evidencien el proceso. Guardar en `docs/capturas/` con nombre `NN_descripcion.png`.

## Avance N°1

El informe LaTeX (`informe/secciones/modelamiento_dimensional.tex`) incluye estas capturas con estos nombres exactos. Mientras falte una, el PDF muestra un recuadro con el nombre del archivo pendiente.

Las capturas de XAMPP y phpMyAdmin de la versión MariaDB se eliminaron el 04-11-2026, con la migración a PostgreSQL. Quedan en el commit `edb900e`.

Las capturas 02, 03 y 05a–05e, y la figura del esquema, se generan con `python herramientas/capturar_pgadmin.py`, que maneja el pgAdmin real con un navegador sin interfaz. Hay que volver a ejecutarlo cada vez que cambie `sql/01_ddl.sql` o `sql/99_validacion.sql`. La 01 y la 04 son capturas de pantalla del grupo, y el script no las toca. El estado de lo pendiente está en `docs/capturas_pendientes.md`.

- [x] 01: `docker compose ps`, mostrando `postgres` (healthy) y `pgadmin` activos → `01_docker_servicios_activos.png`. Captura real de la terminal, hecha por el grupo el 05-11-2026
- [x] 02: Query Tool de pgAdmin con `sql/01_ddl.sql` ejecutado. En la pestaña **Messages** se ven `COMMIT` y "Query returned successfully" → `02_pgadmin_ddl_ejecutado.png`
- [x] 03: Columnas de `fact_venta` en pgAdmin (nodo **Columns** → pestaña **Properties**): las 17 columnas con su tipo, NOT NULL, PK y comentario → `03_estructura_fact_venta.png`
- [x] 04: ERD Tool de pgAdmin con el esquema estrella completo → `04_erd_esquema_estrella.png`. Hecha por el grupo en tema claro, el 05-11-2026. La figura del esquema (`docs/diagramas/esquema_estrella.png`) la genera el script (`--solo-figura`); la versión del 05-11-2026 está revisada
- [x] 05: Resultados de `sql/99_validacion.sql` en el Query Tool, una consulta por captura:
  - [x] Consulta 2 (tablas con su comentario) → `05a_validacion_tablas.png`
  - [x] Consulta 5 (llaves foráneas) → `05b_validacion_fk.png`
  - [x] Consulta 8 (resumen de la estrella) → `05c_validacion_resumen.png`
  - [x] Consulta 6 (restricciones CHECK) → `05d_validacion_checks.png`
  - [x] Consulta 9 (nomenclatura, 0 filas) → `05e_validacion_nomenclatura.png`

## Avance N°2

El informe incluye estas capturas con estos nombres exactos (capítulos Arquitectura Propuesta y Estadísticas de Procesamiento). Mientras falte una, el PDF muestra un recuadro con el nombre del archivo pendiente.

### Capturas de pgAdmin (las genera el script)

`python herramientas/capturar_pgadmin.py --avance2` ejecuta en pgAdmin cada consulta de `sql/98_consultas_carga.sql` con el DWH poblado y guarda su resultado. No modifica la base. Hay que repetirlo después de la ejecución final del ETL.

- [x] 06a: filas por tabla → `06a_carga_filas_por_tabla.png`
- [x] 06b: transacciones en staging, rechazadas y cargadas por línea → `06b_carga_por_linea.png`
- [x] 06c: rechazos por motivo → `06c_carga_rechazos.png`
- [x] 06d: conciliación staging contra `fact_venta` (diferencias en 0) → `06d_carga_conciliacion.png`
- [x] 06e: ventas por línea y año → `06e_carga_ventas_linea_anio.png`
- [x] 06f: indicadores por año → `06f_carga_indicadores_anio.png`

### Capturas de Apache Hop (las hace el grupo)

Hop GUI es una aplicación de escritorio y el script no la puede manejar. Preparación, una sola vez:

1. Tener los contenedores activos (`docker compose up -d`) y el ETL ejecutado al menos una vez (`python etl/ejecutar_etl.py`).
2. Abrir Hop GUI con `python etl/abrir_hop_gui.py`. El script registra el proyecto `rapiditos` y le pasa las credenciales de `.env`.
3. En la barra superior de Hop GUI, elegir el proyecto **rapiditos**.
4. Ventana maximizada, tema claro y sin paneles flotantes encima del diagrama.

Capturas, guardadas en `docs/capturas/` con estos nombres:

- [x] 07a: **workflow principal ejecutado.** File > Open > `principal.hwf`. Ejecutarlo (botón ▶ Run, configuración `local`) y esperar a que termine (unos 20 s). Capturar el diagrama con los ticks verdes de cada acción y, abajo, el panel de resultados con el registro → `07a_hop_workflow_principal.png`
- [x] 07b: **pipeline de staging.** File > Open > `pipelines/01_staging.hpl`. Capturar el diagrama completo (5 lecturas de CSV y 5 cargas a `stg`) → `07b_hop_pipeline_staging.png`
- [x] 07c: **pipeline de hechos.** File > Open > `pipelines/03_hechos.hpl`. Capturar el diagrama completo: lectura, filtro de reglas, rechazos, 6 búsquedas y carga de `fact_venta` → `07c_hop_pipeline_hechos.png`
- [x] 07d: **métricas del pipeline de hechos.** Con `03_hechos.hpl` abierto, ejecutarlo (▶ Run, `local`). Se puede ejecutar solo: vacía `fact_venta` y `stg.rechazo` al inicio y las vuelve a llenar. Al terminar, abrir la pestaña **Transform Metrics** del panel de resultados. Capturar el diagrama y la tabla de métricas, con las 118.263 filas de `Cargar fact_venta` y las 1.737 de `Registrar rechazo` → `07d_hop_metricas_ejecucion.png`
- [x] 07e: **ETL por línea de comandos.** En una terminal, desde la raíz del repositorio, ejecutar `python etl/ejecutar_etl.py`. Capturar el final de la salida: las acciones del workflow con `result=[true]`, la línea `Workflow duration` y `ETL terminado ... con código 0` → `07e_terminal_ejecucion_etl.png`. Se generó desde el registro real de la ejecución del 18-11-2026 (`data/processed/etl_hop.log`), con el usuario, el equipo y la ruta de la carpeta personal anonimizados

## Fases siguientes (referencia)
- [ ] Carga de datos con Python y Apache Hop (pipelines y workflow en Hop GUI)
- [ ] Conteos de filas poblados
- [ ] Consultas de KPI
- [ ] Cubo en Cube (Playground)
- [ ] Dashboard en Streamlit
