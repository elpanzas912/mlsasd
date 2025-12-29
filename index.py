import time
import sqlite3
import datetime
import re

from playwright.sync_api import sync_playwright, Page

# --- Funciones de la Base de Datos ---

def crear_conexion_y_tabla():
    """Se conecta a la BD SQLite y añade las columnas necesarias si faltan."""
    conn = sqlite3.connect('mercado_libre.db')
    cursor = conn.cursor()
    
    # Crea la tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_captura DATE NOT NULL,
            titulo TEXT,
            precio_actual REAL,
            precio_anterior REAL,
            descuento TEXT,
            vendidos_y_rating TEXT,
            vendidos_numerico INTEGER,
            vendedor TEXT,
            envio TEXT,
            info_adicional TEXT,
            link TEXT NOT NULL,
            imagen_url TEXT,
            categoria TEXT,
            origen_envio TEXT,
            tipo_envio_full TEXT,
            es_meli_plus INTEGER,
            UNIQUE(fecha_captura, link)
        )
    ''')

    # Añade columnas de forma segura si no existen
    columnas_existentes = [desc[1] for desc in cursor.execute("PRAGMA table_info(productos)").fetchall()]
    if 'categoria' not in columnas_existentes: cursor.execute("ALTER TABLE productos ADD COLUMN categoria TEXT")
    if 'origen_envio' not in columnas_existentes: cursor.execute("ALTER TABLE productos ADD COLUMN origen_envio TEXT DEFAULT 'Nacional'")
    if 'tipo_envio_full' not in columnas_existentes: cursor.execute("ALTER TABLE productos ADD COLUMN tipo_envio_full TEXT DEFAULT 'Normal'")
    if 'es_meli_plus' not in columnas_existentes: cursor.execute("ALTER TABLE productos ADD COLUMN es_meli_plus INTEGER DEFAULT 0")

    conn.commit()
    conn.close()
    print("Base de datos verificada y lista.")

def guardar_en_db(productos, fecha_actual):
    """Guarda una lista de productos en la base de datos para una fecha específica."""
    if not productos: return
    conn = sqlite3.connect('mercado_libre.db')
    cursor = conn.cursor()
    insertados = 0
    for prod in productos:
        cursor.execute('''
            INSERT OR IGNORE INTO productos (
                fecha_captura, titulo, precio_actual, precio_anterior, descuento, vendidos_y_rating,
                vendidos_numerico, vendedor, envio, info_adicional, link, imagen_url, categoria,
                origen_envio, tipo_envio_full, es_meli_plus
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fecha_actual, prod.get('titulo'), prod.get('precio_numerico'), prod.get('precio_anterior_numerico'),
            prod.get('descuento'), prod.get('vendidos_y_rating'), prod.get('vendidos_numerico'),
            prod.get('vendedor'), prod.get('envio'), prod.get('info_adicional'), prod.get('link'),
            prod.get('imagen_url'), prod.get('categoria'), prod.get('origen_envio'),
            prod.get('tipo_envio_full'), prod.get('es_meli_plus')
        ))
        if cursor.rowcount > 0: insertados += 1
    conn.commit()
    conn.close()
    print(f"   -> {insertados} nuevos registros guardados en la base de datos.")

# --- Funciones de Limpieza y Extracción ---

def limpiar_precio(precio_str):
    if not isinstance(precio_str, str) or precio_str == "N/A": return None
    try: return float(re.sub(r'[\$\s\.]', '', precio_str).replace(',', '.'))
    except (ValueError, TypeError): return None

def limpiar_vendidos(vendidos_str):
    if not isinstance(vendidos_str, str) or vendidos_str == "N/A": return 0
    vendidos_str = vendidos_str.lower()
    match_mil = re.search(r'(\d+[\.,]?\d*)\s*mil', vendidos_str)
    if match_mil: return int(float(match_mil.group(1).replace(',', '.')) * 1000)
    match_normal = re.search(r'(\d+)', vendidos_str)
    if match_normal: return int(match_normal.group(1))
    return 0
    
def get_safe_text(locator, default="N/A"):
    if locator.count() > 0:
        try:
            full_text = " ".join(locator.first.all_inner_texts())
            return full_text.strip().replace('\n', ' ').replace('\r', '')
        except Exception: return default
    return default

def extraer_datos_de_pagina_actual(page: Page, categoria_actual: str):
    try:
        page.wait_for_selector("ol.ui-search-layout", timeout=20000, state='visible')
        print("   ✅ Lista de productos visible.")
    except Exception: return []

    items = page.locator("li.ui-search-layout__item")
    cantidad_productos = items.count()
    if cantidad_productos == 0: return []
    print(f"   Encontrados {cantidad_productos} productos en esta página.")

    productos_en_pagina = []
    for i in range(cantidad_productos):
        item = items.nth(i)
        
        titulo_loc = item.locator(".ui-search-item__title, .poly-component__title")
        titulo = get_safe_text(titulo_loc)
        
        link = "N/A"
        link_loc = item.locator("a.ui-search-link, a.poly-component__title")
        if link_loc.count() > 0:
            link = link_loc.first.get_attribute("href")

        precio_simbolo = get_safe_text(item.locator(".andes-money-amount__currency-symbol").first)
        precio_fraccion = get_safe_text(item.locator(".price-tag-fraction, .andes-money-amount__fraction").first)
        precio_actual_str = f"{precio_simbolo} {precio_fraccion}" if precio_fraccion != "N/A" else "N/A"
        
        precio_anterior_str = get_safe_text(item.locator("s.andes-money-amount--previous .andes-money-amount__fraction"))
        descuento = get_safe_text(item.locator(".ui-search-price__discount, .poly-price__disc_label"))
        vendidos_y_rating = get_safe_text(item.locator(".ui-search-reviews__amount, .poly-component__review-compacted"))
        vendedor = get_safe_text(item.locator(".ui-search-item__seller-name, .poly-component__seller"))
        envio = get_safe_text(item.locator(".ui-search-item__shipping > p, .poly-component__shipping > span").first)
        
        # --- NUEVA LÓGICA CON BÚSQUEDA EN HTML ---
        item_html = item.inner_html()
        es_meli_plus = 1 if 'href="#poly_meli_plus"' in item_html else 0
        
        tipo_full = "Normal"
        if 'aria-label="Full Súper"' in item_html:
            tipo_full = "Full Súper"
        elif 'aria-label="FULL"' in item_html or 'aria-label="Enviado por FULL"' in item_html:
            tipo_full = "FULL"

        origen_envio = "Nacional"
        origen_loc = item.locator(".ui-search-item__shipping-info, .poly-component__shipped-from")
        if origen_loc.count() > 0:
            texto_origen = get_safe_text(origen_loc)
            if "desde" in texto_origen.lower():
                origen_envio = texto_origen.split('desde ')[-1].strip()

        info_adicional = get_safe_text(item.locator(".ui-search-official-store-label, .poly-component__cbt, .andes-tag"))
        
        imagen_url = "N/A"
        img_loc = item.locator("img.ui-search-result-image__element, img.poly-component__picture")
        if img_loc.count() > 0:
            imagen_url = img_loc.first.get_attribute("data-src") or img_loc.first.get_attribute("src")

        producto_data = {
            "titulo": titulo, "link": link, "categoria": categoria_actual, "origen_envio": origen_envio,
            "tipo_envio_full": tipo_full, "es_meli_plus": es_meli_plus,
            "vendidos_y_rating": vendidos_y_rating, "vendedor": vendedor, "envio": envio,
            "info_adicional": info_adicional, "imagen_url": imagen_url, "descuento": descuento,
            "precio_numerico": limpiar_precio(precio_actual_str),
            "precio_anterior_numerico": limpiar_precio(precio_anterior_str),
            "vendidos_numerico": limpiar_vendidos(vendidos_y_rating),
        }
        productos_en_pagina.append(producto_data)
    
    return productos_en_pagina

def run_scraper():
    crear_conexion_y_tabla()
    fecha_hoy = datetime.date.today()
    
    categorias_a_scrapear = [
        {"nombre": "Tienda Gadnic", "url_base": "https://listado.mercadolibre.com.ar/tienda/gadnic"}
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Headless True para servidores (GitHub Actions)
        page = browser.new_page()
        
        todos_los_productos = []
        
        for categoria in categorias_a_scrapear:
            print(f"\n{'='*20}\nIniciando scraping para: '{categoria['nombre']}'\n{'='*20}")
            
            pagina_actual = 1
            while True:
                url_base = categoria['url_base']
                if pagina_actual == 1:
                    url_a_visitar = url_base
                else:
                    offset = (pagina_actual - 1) * 48 + 1
                    url_a_visitar = f"{url_base}_Desde_{offset}"

                print(f"\n--- Procesando Página #{pagina_actual} ---")
                print(f"Navegando a: {url_a_visitar}")
                
                try: page.goto(url_a_visitar, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"   ❌ Error al cargar la página: {e}. Terminando categoría.")
                    break
                
                productos_de_pagina_actual = extraer_datos_de_pagina_actual(page, categoria['nombre'])
                
                if not productos_de_pagina_actual:
                    print("No se encontraron productos. Finalizando categoría.")
                    break
                
                todos_los_productos.extend(productos_de_pagina_actual)
                pagina_actual += 1
                time.sleep(1)

        browser.close()

    guardar_en_db(todos_los_productos, fecha_hoy)
    print(f"\nResumen total: {len(todos_los_productos)} productos extraídos.")

def main():
    print("Iniciando ejecución del scraper desde GitHub Actions...")
    run_scraper()
    print("Ejecución finalizada.")

if __name__ == "__main__":
    main()