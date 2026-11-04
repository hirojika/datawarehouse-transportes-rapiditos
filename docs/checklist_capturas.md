# Checklist de capturas para el informe

La rúbrica otorga el puntaje máximo con **más de 7 capturas** que evidencien el proceso. Guardar en `docs/capturas/` con nombre `NN_descripcion.png`.

## Avance N°1

El informe LaTeX (`informe/secciones/modelamiento_dimensional.tex`) incluye estas capturas con estos nombres exactos.

- [x] 01: XAMPP con Apache y MySQL activos (Linux o Windows) → `01_xampp_activo.png`
- [x] 02: phpMyAdmin con el script `01_ddl.sql` ejecutado sin errores → `02_phpmyadmin_ddl_ejecutado.png`
- [x] 03: Estructura de `fact_venta` en phpMyAdmin (columnas, tipos, llaves) → `03_estructura_fact_venta.png`
- [x] 04: Diseñador de phpMyAdmin con el esquema estrella completo → `04_disenador_esquema_estrella.png` (ver `docs/exportar_diagrama_phpmyadmin.md`)
- [x] 05: Resultado de `sql/99_validacion.sql` (tablas, FK) → `05_validacion_information_schema.png` (completa) y recortes legibles `05a_validacion_tablas.png`, `05b_validacion_fk.png`, `05c_validacion_resumen.png`, que son los que usa el informe

## Fases siguientes (referencia)
- [ ] Carga de datos con Python / Talend
- [ ] Conteos de filas poblados
- [ ] Consultas de KPI
- [ ] Dashboard en Streamlit
