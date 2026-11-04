# Exportar el esquema estrella desde el Diseñador de phpMyAdmin

Sirve para el entregable 3 del Avance N°1 (Modelo Multidimensional Definido, Esquema de Tablas) y para la captura 04 de `docs/checklist_capturas.md`. Funciona igual en Linux y Windows porque todo se hace desde el navegador.

Los nombres de menú van en español y, entre paréntesis, en inglés, porque phpMyAdmin puede estar en cualquiera de los dos idiomas.

## Requisitos

- XAMPP con Apache y MySQL activos.
- `sql/01_ddl.sql` ejecutado sin errores, con la base `dwh_rapiditos` creada.

## Pasos

1. Abrir http://localhost/phpmyadmin.
2. En el panel izquierdo, hacer clic en **dwh_rapiditos**.
3. En la barra superior, abrir **Más (More) → Diseñador (Designer)**. En pantallas anchas el Diseñador aparece directamente como pestaña.
4. Se ven las 7 tablas con líneas entre `fact_venta` y cada dimensión. `dim_zona` tiene **dos** líneas (origen y destino).
5. Ordenar las tablas en forma de estrella: arrastrar cada una desde su barra de título, con `fact_venta` al centro y las seis dimensiones alrededor. Una disposición posible:

   ```
                 dim_tiempo        dim_cliente
   dim_medio_pago        fact_venta        dim_servicio
             dim_canal_venta       dim_zona
   ```

6. Guardar la disposición. En el menú lateral del Diseñador, usar **Guardar página (Save page)** con un nombre como `estrella_rapiditos`. Así no se pierde al recargar.
7. **Captura 04:** con todas las tablas a la vista (si hace falta, alejar con `Ctrl` + `-` en el navegador), sacar una captura de pantalla y guardarla como `docs/capturas/04_disenador_esquema_estrella.png`.
8. **Imagen del esquema (`docs/diagramas/esquema_estrella.png`):** recortar la captura 04 dejando solo el diagrama, sin el menú izquierdo ni la barra superior. Sirve cualquier editor de imágenes (en Linux, ImageMagick: `convert 04_disenador_esquema_estrella.png -crop ANCHOxALTO+X+Y +repage esquema_estrella.png`). Es la imagen que usa el informe y la que se entrega por separado: muestra tipos, llaves y relaciones en colores.
9. Opcional: usar **Exportar esquema (Export schema)** en el menú lateral del Diseñador.
   - Formato **PDF**: phpMyAdmin genera un diccionario de datos (una página por tabla, con tipos y comentarios) y deja el esquema en la última página, con tablas muy pequeñas. Se guardó como `docs/diagramas/diccionario_datos_phpmyadmin.pdf`, útil como anexo de evidencia.
   - Formato **SVG**: se guardó como `docs/diagramas/esquema_estrella.svg`. Al convertirlo a PNG con ImageMagick se pierden los colores, por eso la imagen oficial es el recorte del paso 8.

## Si el Diseñador muestra un aviso sobre el almacenamiento de configuración

phpMyAdmin necesita su base interna `phpmyadmin` para guardar páginas del Diseñador. En XAMPP normalmente ya viene creada. Si aparece el aviso *"El almacenamiento de configuración de phpMyAdmin no está completamente configurado"* (*"The phpMyAdmin configuration storage is not completely configured"*):

1. Hacer clic en el enlace **Averiguar por qué (Find out why)**.
2. Hacer clic en **Crear (Create)**, que crea la base `phpmyadmin` y sus tablas.
3. Volver al paso 3.

Sin ese almacenamiento, el Diseñador igual muestra el esquema y se puede sacar la captura; solo no se puede guardar la página.

## Verificación

- [ ] La imagen muestra las 7 tablas con sus columnas y las 7 relaciones (dos hacia `dim_zona`).
- [ ] `fact_venta` está al centro y ninguna dimensión se conecta con otra.
- [ ] Archivos guardados: `docs/capturas/04_disenador_esquema_estrella.png` y `docs/diagramas/esquema_estrella.png` (opcionales: `diccionario_datos_phpmyadmin.pdf`, `esquema_estrella.svg`).
