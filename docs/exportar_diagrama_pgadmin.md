# Exportar el esquema estrella desde el ERD Tool de pgAdmin

Sirve para el entregable 3 del Avance N°1 (Modelo Multidimensional Definido, Esquema de Tablas) y para la captura 04 de `docs/checklist_capturas.md`. Funciona igual en Linux y Windows, porque pgAdmin corre en Docker y se usa desde el navegador.

Reemplaza a la guía del Diseñador de phpMyAdmin, que se usó hasta la migración a PostgreSQL (04-11-2026).

## Requisitos

- Contenedores activos: `docker compose up -d`.
- `sql/01_ddl.sql` ejecutado sin errores, con el esquema `dwh` creado.

## Pasos

1. Abrir http://localhost:5050 y entrar con `PGADMIN_EMAIL` y `PGADMIN_PASSWORD` de `.env`.
2. En el panel izquierdo, abrir **Servers → Rapiditos (PostgreSQL 17)** e ingresar la clave `DB_PASSWORD`. Se puede marcar "Save password" para no volver a escribirla.
3. Abrir **Databases → rapiditos → Schemas** y hacer clic derecho sobre **dwh**.
4. Elegir **ERD For Schema**. Si la versión de pgAdmin no muestra esa opción, hacer clic derecho sobre la base `rapiditos` y elegir **ERD For Database**: aparecen las mismas 7 tablas, porque `dwh` es el único esquema con tablas.
5. Se abre el diagrama con las 7 tablas y las relaciones entre `fact_venta` y cada dimensión. `dim_zona` tiene **dos** relaciones (origen y destino).
6. Ordenar las tablas en forma de estrella: usar el botón de alineación automática (*Auto align*) y después arrastrar cada tabla desde su encabezado, con `fact_venta` al centro y las seis dimensiones alrededor. Una disposición posible:

   ```
                 dim_tiempo        dim_cliente
   dim_medio_pago        fact_venta        dim_servicio
             dim_canal_venta       dim_zona
   ```

7. Verificar que se vean las columnas con sus tipos (botón *Show details* activado) y ajustar el zoom con *Zoom to fit*.
8. **Captura 04:** con el diagrama completo a la vista, sacar una captura de pantalla y guardarla como `docs/capturas/04_erd_esquema_estrella.png`.
9. **Imagen del esquema:** usar el botón de descarga de imagen de la barra del ERD (*Download image*). El navegador guarda un PNG en la carpeta de descargas; moverlo a `docs/diagramas/esquema_estrella.png`. Es la imagen que usa el informe y la que se entrega por separado.
10. Opcional: el botón *Generate SQL* muestra el DDL que pgAdmin deduce del diagrama, útil para comparar con `sql/01_ddl.sql`.

## Verificación

- [x] La imagen muestra las 7 tablas con sus columnas y las 7 relaciones (dos hacia `dim_zona`).
- [x] `fact_venta` está al centro y ninguna dimensión se conecta con otra.
- [x] Archivos guardados: `docs/capturas/04_erd_esquema_estrella.png` y `docs/diagramas/esquema_estrella.png`.
