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

## Fases siguientes (referencia)
- [ ] Carga de datos con Python y Apache Hop (pipelines y workflow en Hop GUI)
- [ ] Conteos de filas poblados
- [ ] Consultas de KPI
- [ ] Cubo en Cube (Playground)
- [ ] Dashboard en Streamlit
