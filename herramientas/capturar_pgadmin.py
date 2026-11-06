"""Genera las capturas del Avance N°1 que lista docs/checklist_capturas.md.

Maneja el pgAdmin real de docker-compose.yml con un navegador sin interfaz
(Playwright + Chromium), conectado a la base rapiditos, y guarda en
docs/capturas/:

  02_pgadmin_ddl_ejecutado.png     sql/01_ddl.sql ejecutado en el Query Tool
  03_estructura_fact_venta.png     columnas de fact_venta en el Object Explorer
  05a ... 05e                      consultas de sql/99_validacion.sql

y además la figura del esquema, docs/diagramas/esquema_estrella.png: ERD Tool de
pgAdmin con fact_venta al centro y las dimensiones a los lados, recortado al
contenido. Esa figura se sobrescribe en cada ejecución.

Las capturas 01 (terminal con `docker compose ps`) y 04 (ERD Tool con la interfaz
completa) son capturas de pantalla reales del grupo: el script no las toca.

Usa un usuario de pgAdmin propio (capturas@rapiditos.cl), que se recrea en cada
ejecución, para no alterar el espacio de trabajo del usuario de PGADMIN_EMAIL.
La captura 02 vuelve a ejecutar el DDL, que recrea el esquema dwh: si alguna
tabla tiene datos, el script se detiene sin tocar nada.

Requisitos: contenedores activos (docker compose up -d), .env configurado y,
una sola vez, el navegador de Playwright: python -m playwright install chromium

Uso, desde la raíz del repositorio:
  python herramientas/capturar_pgadmin.py                # todas
  python herramientas/capturar_pgadmin.py --solo-figura  # solo la figura del esquema,
                                                         # sin volver a ejecutar el DDL
"""

import argparse
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from playwright.sync_api import Error as ErrorPlaywright
from playwright.sync_api import Frame, Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
CAPTURAS = RAIZ / "docs" / "capturas"
FIGURA_ESQUEMA = RAIZ / "docs" / "diagramas" / "esquema_estrella.png"

# Disposición en estrella del ERD: columna izquierda, centro y columna derecha
COLUMNAS_ESTRELLA = [
    ["dim_cliente", "dim_canal_venta", "dim_medio_pago"],
    ["fact_venta"],
    ["dim_tiempo", "dim_zona", "dim_servicio"],  # en este orden ninguna línea cruza una tabla
]
ANCHO_TABLA_ERD = 300  # pgAdmin usa 175 px y parte los tipos a mitad de palabra
SEPARACION_COLUMNAS = 130  # espacio para las líneas de las relaciones
SEPARACION_FILAS = 36
ZONA_DE_PASO_Y = 1500  # fila donde se dejan las tablas antes de ubicarlas

URL_PGADMIN = f"http://localhost:{os.getenv('PGADMIN_PORT', '5050')}"
USUARIO_CAPTURAS = "capturas@rapiditos.cl"
ANCHO = 1440
ESCALA = 2  # resolución doble para que el texto se lea bien en el PDF

# Captura -> número de la consulta en sql/99_validacion.sql
CONSULTAS_VALIDACION = {
    "05a_validacion_tablas": 2,
    "05b_validacion_fk": 5,
    "05c_validacion_resumen": 8,
    "05d_validacion_checks": 6,
    "05e_validacion_nomenclatura": 9,
}

# Medidas del Query Tool en píxeles CSS, para dimensionar la ventana y los paneles
# de modo que se vean la consulta completa y todas las filas del resultado
INICIO_EDITOR = 165  # borde superior del editor
ALTO_LINEA = 20  # alto de una línea del editor
ALTO_FILA = 25  # alto de una fila de la grilla de resultados
ALTO_RESULTADOS_BASE = 150  # pestañas, barra de la grilla, encabezado y barra de estado

# Preferencias del usuario de capturas: columnas de la grilla ajustadas al contenido
PREFERENCIAS = (
    "sqleditor:Results_grid:column_data_auto_resize=by_data",
    "sqleditor:Results_grid:column_data_max_width=900",
)

load_dotenv(RAIZ / ".env")


# ---------------------------------------------------------------------------
# Preparación
# ---------------------------------------------------------------------------


def docker_compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args], cwd=RAIZ, capture_output=True, text=True, check=False
    )


def setup_pgadmin(*args: str) -> subprocess.CompletedProcess:
    """Ejecuta el setup.py de pgAdmin dentro de su contenedor."""
    return docker_compose(
        "exec", "-T", "pgadmin", "/venv/bin/python3", "/pgadmin4/setup.py", *args
    )


def crear_usuario_capturas() -> str:
    """Recrea el usuario de capturas con la conexión de docker/pgadmin/servers.json."""
    clave = secrets.token_urlsafe(16)
    setup_pgadmin("delete-user", USUARIO_CAPTURAS, "--yes")
    creado = setup_pgadmin("add-user", USUARIO_CAPTURAS, clave, "--role", "User")
    if creado.returncode != 0 or "does not exist" in creado.stdout:
        sys.exit(f"No se pudo crear el usuario de capturas en pgAdmin:\n{creado.stdout}")
    servidores = setup_pgadmin("load-servers", "/pgadmin4/servers.json", "--user", USUARIO_CAPTURAS)
    if servidores.returncode != 0:
        sys.exit(f"No se pudo cargar servers.json:\n{servidores.stdout}{servidores.stderr}")
    preferencias = setup_pgadmin("set-prefs", USUARIO_CAPTURAS, *PREFERENCIAS)
    if preferencias.returncode != 0:
        sys.exit(f"No se pudieron fijar las preferencias:\n{preferencias.stdout}")
    return clave


def verificar_dwh_sin_datos() -> None:
    """Detiene el script si alguna tabla de dwh tiene filas (el DDL las borraría)."""
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "rapiditos"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "rapiditos"),
    ) as conexion:
        tablas = conexion.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'dwh'"
        ).fetchall()
        for (tabla,) in tablas:
            consulta = f'SELECT EXISTS (SELECT 1 FROM dwh."{tabla}")'
            if conexion.execute(consulta).fetchone()[0]:
                sys.exit(
                    f"dwh.{tabla} tiene datos: la captura 02 ejecuta sql/01_ddl.sql, que "
                    "recrea el esquema y los borraría. No se generó ninguna captura."
                )


def consultas_validacion() -> dict[int, str]:
    """Separa sql/99_validacion.sql en sus consultas numeradas ('-- N. ...')."""
    texto = (RAIZ / "sql" / "99_validacion.sql").read_text(encoding="utf-8")
    partes = re.split(r"(?m)^(?=-- \d+\. )", texto)
    return {
        int(re.match(r"-- (\d+)\.", parte).group(1)): parte.strip() + "\n"
        for parte in partes
        if re.match(r"-- \d+\. ", parte)
    }


# ---------------------------------------------------------------------------
# Manejo de pgAdmin
# ---------------------------------------------------------------------------


def guardar(pag: Page, nombre: str) -> None:
    pag.mouse.move(2, 400)  # sin tooltips en la captura
    time.sleep(0.6)
    ruta = CAPTURAS / f"{nombre}.png"
    pag.screenshot(path=ruta)
    print(f"  {ruta.relative_to(RAIZ)}")


def entrar(pag: Page, clave: str) -> None:
    pag.goto(f"{URL_PGADMIN}/login")
    pag.fill("input[name=email]", USUARIO_CAPTURAS)
    pag.fill("input[name=password]", clave)
    pag.click("button:has-text('Login')")
    pag.wait_for_load_state("networkidle")


def nodo(pag: Page, texto: str):
    """Nodo del Object Explorer por su texto (admite 'Tables (7)', 'Databases (2)', etc.)."""
    patron = re.compile(rf"^{re.escape(texto)}( \(\d+\))?$")
    return pag.locator("span.file-name", has_text=patron).first


def expandir(pag: Page, ruta: list[str]) -> None:
    """Expande cada nodo de la ruta solo si su hijo todavía no se ve."""
    for padre, hijo in zip(ruta, ruta[1:]):
        if not nodo(pag, hijo).is_visible():
            nodo(pag, padre).dblclick()
        nodo(pag, hijo).wait_for()
        time.sleep(0.4)


def conectar(pag: Page) -> None:
    """Expande Servers y responde el diálogo de clave del servidor."""
    nodo(pag, "Servers").dblclick()
    dialogo = pag.locator(".MuiDialog-root", has_text="Connect to Server")
    dialogo.wait_for()
    dialogo.locator("input[type=password]").fill(os.environ["DB_PASSWORD"])
    dialogo.locator("button", has_text=re.compile(r"^\s*OK\s*$")).click()
    nodo(pag, "Databases").wait_for()


def abrir_query_tool(pag: Page) -> Frame:
    """Abre el Query Tool sobre la base rapiditos y devuelve su frame (vive en un iframe)."""
    antes = set(pag.frames)
    nodo(pag, "rapiditos").click()
    pag.get_by_text("Tools", exact=True).click()
    pag.locator("[role=menuitem]", has_text="Query Tool").first.click()
    for _ in range(60):
        nuevos = [f for f in pag.frames if f not in antes and f is not pag.main_frame]
        con_editor = [f for f in nuevos if f.locator(".cm-content").count()]
        if con_editor:
            break
        time.sleep(0.5)
    else:
        sys.exit("No se abrió el Query Tool de pgAdmin.")
    qt = con_editor[-1]
    qt.locator(".cm-content").wait_for()
    # El panel Scratch Pad no aporta a las capturas y le quita ancho al editor
    qt.locator("[role=tab]", has_text="Scratch Pad").locator("button[aria-label=Close]").click()
    return qt


def cerrar_avisos(pag: Page) -> None:
    """Cierra los avisos flotantes ("Successfully run...") de la página principal."""
    for boton in pag.locator("[data-test=notifier-message] button").all():
        try:
            boton.click(timeout=1500)
        except ErrorPlaywright:
            pass  # el aviso se cerró solo o todavía se estaba moviendo
    pag.wait_for_timeout(400)


def ejecutar(pag: Page, qt: Frame, consulta: str) -> None:
    """Reemplaza el contenido del editor, vuelve al inicio, ejecuta con F5 y espera el fin.

    El fin se detecta en las respuestas de /sqleditor/poll/, que pgAdmin consulta
    mientras la consulta corre: el texto de éxito en pantalla puede ser de la anterior.
    """
    cerrar_avisos(pag)
    qt.locator(".cm-content").click()
    pag.keyboard.press("ControlOrMeta+A")
    pag.keyboard.press("Delete")
    pag.keyboard.insert_text(consulta)
    pag.keyboard.press("Escape")  # cierra el autocompletado, si se abrió
    pag.keyboard.press("ControlOrMeta+Home")
    respuestas = []

    def registrar(respuesta):
        if "/sqleditor/poll/" in respuesta.url:
            respuestas.append(respuesta)

    pag.on("response", registrar)
    pag.keyboard.press("F5")
    try:
        for _ in range(240):
            estados = [r.json().get("data", {}).get("status") for r in respuestas]
            terminado = [e for e in estados if e != "Busy"]
            if terminado:
                if terminado[0] != "Success":
                    sys.exit(f"La consulta terminó con estado {terminado[0]}:\n{consulta[:200]}")
                break
            pag.wait_for_timeout(250)  # time.sleep no deja procesar los eventos de red
        else:
            sys.exit("La consulta no terminó en 60 segundos.")
    finally:
        pag.remove_listener("response", registrar)
    time.sleep(1)


# ---------------------------------------------------------------------------
# Capturas
# ---------------------------------------------------------------------------


def captura_ddl(pag: Page) -> Frame:
    """02: sql/01_ddl.sql ejecutado en el Query Tool, con el resultado en Messages."""
    qt = abrir_query_tool(pag)
    ejecutar(pag, qt, (RAIZ / "sql" / "01_ddl.sql").read_text(encoding="utf-8"))
    qt.locator("[role=tab]", has_text="Messages").first.click()
    qt.get_by_text(re.compile("Query returned successfully")).first.wait_for()
    guardar(pag, "02_pgadmin_ddl_ejecutado")
    return qt


def captura_estructura(pag: Page) -> None:
    """03: columnas de fact_venta (pestaña Properties del nodo Columns)."""
    pag.set_viewport_size({"width": ANCHO, "height": 960})
    expandir(pag, ["rapiditos", "Schemas", "dwh", "Tables", "fact_venta", "Columns"])
    nodo(pag, "Columns").click()
    pag.locator("[role=tab]", has_text=re.compile(r"^Properties$")).first.click()
    pag.get_by_text("peso_kg", exact=True).first.wait_for()
    guardar(pag, "03_estructura_fact_venta")


def ajustar_paneles(pag: Page, qt: Frame, lineas: int, filas: int) -> None:
    """Fija el alto de la ventana y mueve el divisor entre el editor y los resultados
    para que se vean todas las líneas de la consulta y todas las filas."""
    divisor_y = INICIO_EDITOR + lineas * ALTO_LINEA + 15
    alto = max(700, divisor_y + ALTO_RESULTADOS_BASE + max(filas, 2) * ALTO_FILA)
    pag.set_viewport_size({"width": ANCHO, "height": alto})
    pag.wait_for_timeout(500)
    # El divisor horizontal es el .dock-divider ancho (los verticales son angostos)
    for divisor in qt.locator(".dock-divider").all():
        caja = divisor.bounding_box()
        if caja and caja["width"] > 500:
            x, y = caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2
            pag.mouse.move(x, y)
            pag.mouse.down()
            pag.mouse.move(x, divisor_y, steps=8)
            pag.mouse.up()
            break
    pag.wait_for_timeout(500)


def ajustar_columnas(pag: Page, qt: Frame) -> None:
    """Ensancha las columnas de la grilla cuyo texto queda cortado con "…".

    pgAdmin calcula el ancho con una estimación que se queda corta. Las celdas usan
    overflow: clip, que no informa el ancho real del texto, así que se mide cada
    texto con un canvas en la fuente de la celda y se arrastra el borde del título.
    """
    for encabezado in qt.locator("[role=columnheader]").all():
        necesario = qt.evaluate(
            """(col) => {
                const lienzo = document.createElement("canvas").getContext("2d");
                const celdas = document.querySelectorAll(
                    `[role=gridcell][aria-colindex="${col}"]`);
                return Math.max(0, ...[...celdas].map(celda => {
                    const s = getComputedStyle(celda);
                    lienzo.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
                    return lienzo.measureText(celda.textContent).width
                        + parseFloat(s.paddingLeft) + parseFloat(s.paddingRight);
                }));
            }""",
            encabezado.get_attribute("aria-colindex"),
        )
        caja = encabezado.bounding_box()
        falta = necesario + 24 - caja["width"]  # margen: la medida del canvas se queda corta
        if necesario and falta > 0:
            borde, y = caja["x"] + caja["width"] - 2, caja["y"] + caja["height"] / 2
            pag.mouse.move(borde, y)
            pag.mouse.down()
            pag.mouse.move(borde + falta, y, steps=5)
            pag.mouse.up()
            pag.wait_for_timeout(150)


def mover_tabla(pag: Page, tabla, x: float, y: float) -> None:
    """Arrastra una tabla del ERD hasta que su esquina superior izquierda quede en (x, y).

    El arrastre se toma de la franja superior de la tabla, lejos del botón del ojo.
    pgAdmin ajusta la posición a una grilla de 10 px, así que se acepta esa diferencia;
    al empezar a arrastrar se pierden unos píxeles, por eso se corrige una vez más.
    """
    for _ in range(2):
        caja = tabla.bounding_box()
        dx, dy = x - caja["x"], y - caja["y"]
        if abs(dx) <= 10 and abs(dy) <= 10:
            return
        agarre_x, agarre_y = caja["x"] + caja["width"] * 0.75, caja["y"] + 12
        pag.mouse.move(agarre_x, agarre_y)
        pag.mouse.down()
        pag.mouse.move(agarre_x + dx, agarre_y + dy, steps=12)
        pag.mouse.up()
        pag.wait_for_timeout(200)
    caja = tabla.bounding_box()
    if abs(x - caja["x"]) > 10 or abs(y - caja["y"]) > 10:
        sys.exit(
            f"No se pudo ubicar una tabla del ERD: se pidió ({x:.0f}, {y:.0f}) y quedó en "
            f"({caja['x']:.0f}, {caja['y']:.0f})."
        )


def figura_esquema(pag: Page) -> None:
    """Figura del esquema estrella: ERD Tool del esquema dwh, con fact_venta al centro.

    La exportación "Download image" de pgAdmin pierde las líneas de las relaciones,
    por eso se fotografía el lienzo del ERD, recortado a las tablas. Las tablas se
    llevan primero a una fila de paso, para que al ubicarlas ninguna tape a otra.
    """
    pag.set_viewport_size({"width": 3200, "height": 2600})  # lienzo amplio: todo a la vista
    expandir(pag, ["rapiditos", "Schemas", "dwh"])
    antes = set(pag.frames)
    nodo(pag, "dwh").click(button="right")
    pag.locator("[role=menuitem]", has_text="ERD For Schema").first.click()
    for _ in range(60):
        nuevos = [f for f in pag.frames if f not in antes and f is not pag.main_frame]
        con_tablas = [f for f in nuevos if f.locator(".TableNode-tableNode").count() >= 7]
        if con_tablas:
            erd = con_tablas[-1]
            break
        pag.wait_for_timeout(500)
    else:
        sys.exit("No se abrió el ERD Tool con las 7 tablas.")
    # Solo se ensancha el recuadro de cada tabla, para que cada columna quede en una línea.
    # Las tablas se arrastran después, así pgAdmin vuelve a calcular las líneas.
    erd.add_style_tag(
        content=f".TableNode-tableNode {{ width: {ANCHO_TABLA_ERD}px !important; }}"
    )
    pag.wait_for_timeout(1500)

    tablas = {}
    for tabla in erd.locator(".TableNode-tableNode").all():
        # La fila del esquema ("dwh") y la del nombre usan la misma clase
        textos = tabla.locator(".TableNode-tableNameText").all_inner_texts()
        nombres = [t.strip() for t in textos if re.match(r"^(dim|fact)_", t.strip())]
        if nombres:
            tablas[nombres[0]] = tabla
    esperadas = {t for columna in COLUMNAS_ESTRELLA for t in columna}
    if set(tablas) != esperadas:
        sys.exit(f"El ERD no muestra las 7 tablas del modelo: {sorted(tablas)}")

    marco = erd.frame_element().bounding_box()
    barra = erd.locator("button[aria-label='Auto Align']").bounding_box()
    inicio_lienzo = barra["y"] + barra["height"] + 4
    origen_x, origen_y = marco["x"] + 70, inicio_lienzo + 70

    # 1. Fila de paso: todas las tablas abajo, separadas
    for i, nombre in enumerate(sorted(tablas)):
        x_paso = marco["x"] + 20 + i * (ANCHO_TABLA_ERD + 40)
        mover_tabla(pag, tablas[nombre], x_paso, ZONA_DE_PASO_Y)

    # 2. Ubicación final: cada columna centrada en la vertical
    ancho = max(t.bounding_box()["width"] for t in tablas.values())
    altos = {n: t.bounding_box()["height"] for n, t in tablas.items()}
    alto_columna = [sum(altos[n] for n in col) + SEPARACION_FILAS * (len(col) - 1)
                    for col in COLUMNAS_ESTRELLA]  # fmt: skip
    for i, columna in enumerate(COLUMNAS_ESTRELLA):
        x = origen_x + i * (ancho + SEPARACION_COLUMNAS)
        y = origen_y + (max(alto_columna) - alto_columna[i]) / 2
        for nombre in columna:
            mover_tabla(pag, tablas[nombre], x, y)
            y += altos[nombre] + SEPARACION_FILAS

    # pgAdmin elige el costado por el que entra cada línea según la posición de las
    # tablas en el último arrastre; un leve vaivén de cada tabla lo recalcula
    for tabla in tablas.values():
        caja = tabla.bounding_box()
        agarre_x, agarre_y = caja["x"] + caja["width"] * 0.75, caja["y"] + 12
        for desplazamiento in (20, 0):
            pag.mouse.move(agarre_x, agarre_y + (0 if desplazamiento == 20 else 20))
            pag.mouse.down()
            pag.mouse.move(agarre_x, agarre_y + desplazamiento, steps=6)
            pag.mouse.up()
            pag.wait_for_timeout(150)

    # Clic en una zona vacía del lienzo para quitar la selección de la última tabla
    pag.mouse.click(origen_x + 3 * (ancho + SEPARACION_COLUMNAS) + 80, origen_y)
    pag.mouse.move(2, 400)
    pag.wait_for_timeout(800)
    cajas = [t.bounding_box() for t in tablas.values()]
    margen = 50  # incluye las líneas que rodean las tablas de los costados
    x0 = max(marco["x"], min(c["x"] for c in cajas) - margen)  # sin el árbol de la izquierda
    y0 = max(inicio_lienzo, min(c["y"] for c in cajas) - margen)  # sin la barra del ERD
    x1 = max(c["x"] + c["width"] for c in cajas) + margen
    y1 = max(c["y"] + c["height"] for c in cajas) + margen
    recorte = {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
    pag.screenshot(path=FIGURA_ESQUEMA, clip=recorte)
    print(f"  {FIGURA_ESQUEMA.relative_to(RAIZ, walk_up=True)}")


def capturas_validacion(pag: Page, qt: Frame) -> None:
    """05a-05e: cada consulta de sql/99_validacion.sql con su resultado, en el mismo Query Tool."""
    consultas = consultas_validacion()
    pag.locator("[role=tab]", has_text="rapiditos/rapiditos@").first.click()
    pag.locator("button[aria-label='Hide Object Explorer']").click()  # más ancho para la grilla
    for nombre, numero in CONSULTAS_VALIDACION.items():
        consulta = consultas[numero]
        ejecutar(pag, qt, consulta)
        qt.locator("[role=tab]", has_text="Data Output").first.click()
        total = qt.get_by_text(re.compile(r"Total rows: \d+")).first.inner_text()
        filas = int(re.search(r"\d+", total).group())
        ajustar_paneles(pag, qt, consulta.rstrip("\n").count("\n") + 1, filas)
        ajustar_columnas(pag, qt)
        cerrar_avisos(pag)
        guardar(pag, nombre)


def main() -> None:
    argumentos = argparse.ArgumentParser(description="Capturas de pgAdmin del Avance N°1")
    argumentos.add_argument(
        "--solo-figura",
        action="store_true",
        help="genera solo docs/diagramas/esquema_estrella.png, sin ejecutar el DDL",
    )
    solo_figura = argumentos.parse_args().solo_figura
    if not solo_figura:
        verificar_dwh_sin_datos()
    clave = crear_usuario_capturas()
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    print("Capturas generadas:")
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pag = navegador.new_page(
            viewport={"width": ANCHO, "height": 860}, device_scale_factor=ESCALA
        )
        entrar(pag, clave)
        conectar(pag)
        expandir(pag, ["Databases", "rapiditos"])
        if solo_figura:
            figura_esquema(pag)
        else:
            qt = captura_ddl(pag)
            captura_estructura(pag)
            figura_esquema(pag)
            capturas_validacion(pag, qt)
        navegador.close()
    setup_pgadmin("delete-user", USUARIO_CAPTURAS, "--yes")


if __name__ == "__main__":
    main()
