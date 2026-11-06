# Capturas pendientes del Avance N°1

Actualizado el 05-11-2026. **No queda nada pendiente:** las 10 imágenes del informe están revisadas y aprobadas. Las instrucciones del punto 1 quedan como referencia, por si hay que rehacer la Figura 1 a mano.

## Estado de cada imagen

| Figura en el informe | Archivo | Estado | Quién la hizo |
|---|---|---|---|
| Figura 1: esquema estrella | `docs/diagramas/esquema_estrella.png` | Lista. Generada y revisada el 05-11 (2510 × 2070 px) | Script (`--solo-figura`), en el pgAdmin real |
| Figura 2: servicios activos | `docs/capturas/01_docker_servicios_activos.png` | Lista. Captura real de la terminal, revisada el 05-11 | Grupo |
| Figura 3: DDL ejecutado | `docs/capturas/02_pgadmin_ddl_ejecutado.png` | Lista | Script, en el pgAdmin real |
| Figura 4: columnas de `fact_venta` | `docs/capturas/03_estructura_fact_venta.png` | Lista | Script, en el pgAdmin real |
| Figura 5: ERD en pgAdmin | `docs/capturas/04_erd_esquema_estrella.png` | Lista, con una observación (ver punto 2) | Grupo, tema claro, revisada el 05-11 |
| Figuras 6 a 10: validación | `docs/capturas/05a` a `05e_*.png` | Listas | Script, en el pgAdmin real |

`docs/diagramas/esquema_estrella_original.png` es el respaldo de la primera exportación del grupo. El informe no lo usa y se puede borrar cuando la Figura 1 esté lista.

## 1. Figura 1: esquema estrella (lista)

### Revisión de la versión recibida el 05-11

El orden de las tablas y el tema claro están bien, pero no se aprobó por dos problemas:

1. **Tres relaciones salen por el lado equivocado de `fact_venta`.** Las de `dim_cliente`, `dim_canal_venta` y `dim_medio_pago` dibujan la "pata de gallo" (el lado "muchos") en el costado **derecho** de `fact_venta`, con un trazo suelto. Luego la línea pasa por detrás de la tabla hasta salir por la izquierda. Se lee como si las 7 relaciones fueran hacia la derecha.
2. **Poca resolución.** La imagen mide 533 × 808 px, y la letra queda de unos 8 px: en el PDF impreso no se lee.

La pata de gallo de esas tres relaciones debe quedar en el costado **izquierdo** de `fact_venta`, que es el que mira hacia esas dimensiones. Además, la imagen debe medir al menos unos 1500 px de alto.

### Opción A: con el script (recomendada; la usada el 05-11)

La versión corregida ya está probada:
- recuadros anchos, sin texto cortado;
- todas las patas de gallo del lado correcto;
- ninguna línea pasa sobre una tabla;
- doble resolución.

Se genera con `python herramientas/capturar_pgadmin.py --solo-figura`, que no ejecuta el DDL ni rehace las otras capturas.

### Opción B: a mano en pgAdmin

1. `docker compose up -d`, abrir http://localhost:5050 y entrar con `PGADMIN_EMAIL` y `PGADMIN_PASSWORD` de `.env`. El tema claro ya quedó configurado.
2. En el árbol: **Servers → Rapiditos (PostgreSQL 17) → Databases → rapiditos → Schemas → dwh**. Clic derecho → **ERD For Schema**. Verificar que se vean los tipos (botón *Show Details*, el del ojo).
3. Ordenar las tablas arrastrándolas desde la franja gris superior de cada una:

   | Columna izquierda | Centro | Columna derecha |
   |---|---|---|
   | `dim_cliente` | | `dim_tiempo` |
   | `dim_canal_venta` | `fact_venta` | `dim_servicio` o `dim_zona` |
   | `dim_medio_pago` | | `dim_zona` o `dim_servicio` |

4. **Corregir el lado de las líneas:** arrastra `fact_venta` un cuadro de la grilla hacia la derecha, suéltala, y vuelve a dejarla donde estaba. pgAdmin recalcula de qué lado sale cada línea. Repite el mismo vaivén con `dim_cliente`, `dim_canal_venta` y `dim_medio_pago`.
5. **Revisar antes de capturar:**
   - las patas de gallo de las tres dimensiones de la izquierda están en el costado izquierdo de `fact_venta`, y las de las tres de la derecha en el costado derecho;
   - no hay trazos sueltos;
   - ninguna línea pasa por encima o por detrás de una tabla.
6. **Agrandar antes de capturar:**
   - ocultar el árbol (botón de la barra lateral izquierda);
   - poner el navegador en pantalla completa (F11);
   - aumentar el zoom del navegador con **Ctrl +** hasta 150 % o 200 %;
   - usar *Zoom to Fit*.

   Así la imagen sale con más píxeles.
7. Capturar solo el área de las tablas, sin la barra del ERD ni el árbol. No usar el botón *Download image*, porque pierde las líneas.
8. Guardarla como `docs/diagramas/esquema_estrella.png` y avisar. **Después de eso no hay que ejecutar `herramientas/capturar_pgadmin.py`**, porque sobrescribe esta figura.

Limitación de la opción B: pgAdmin parte algunos tipos largos en dos líneas dentro de los recuadros (por ejemplo, "character var / ying(20)"). Se acepta.

## 2. Figura 5: ERD en pgAdmin (lista, con observación)

La captura recibida cumple: se ve la interfaz del ERD Tool, en tema claro, con las 7 tablas completas y sus líneas. Ya está en el informe y es mejor que la anterior.

Tiene el mismo detalle que la Figura 1: las tres relaciones de la izquierda salen por el costado derecho de `fact_venta`, y la letra es chica. Si haces la Figura 1 con la opción B, conviene volver a sacar esta en la misma sesión, después del paso 6: ventana completa de pgAdmin, con la barra del ERD visible. Se guarda como `docs/capturas/04_erd_esquema_estrella.png`. Es opcional.

## Cómo pasármelas

1. Guarda la imagen con su nombre exacto en su carpeta, o pégala en el chat.
2. Avísame cuál es.
3. La reviso con estos criterios:
   - **Generales:** PNG, la letra se lee y no hay claves, avisos ni ventanas ajenas.
   - **Figura 1:** las 7 tablas completas, `fact_venta` al centro y las 7 relaciones visibles (2 hacia `dim_zona`). Cada pata de gallo en el costado de `fact_venta` que mira a su dimensión, ninguna línea sobre o detrás de una tabla, ninguna dimensión conectada con otra, y al menos unos 1500 px de alto.
   - **04:** la interfaz del ERD Tool visible y las 7 tablas completas, con sus líneas.
4. Te digo si quedó bien o no, y por qué. Si quedó bien, la dejo en el informe, recompilo y te confirmo el resultado.
