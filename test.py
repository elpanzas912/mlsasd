import re
from playwright.sync_api import sync_playwright

def get_safe_text(locator, default="N/A"):
    """
    Función auxiliar robusta para obtener texto de un localizador de forma segura.
    Usa .first para evitar errores de modo estricto si hay múltiples coincidencias.
    """
    if locator.count() > 0:
        try:
            full_text = " ".join(locator.first.all_inner_texts())
            return full_text.strip().replace('\n', ' ').replace('\r', '')
        except Exception:
            # En caso de que el elemento desaparezca justo al intentar leerlo
            return default
    return default

def test_single_page_extraction():
    # --- CONFIGURACIÓN DE LA PRUEBA ---
    # Cambia la URL aquí para probar diferentes páginas o categorías
    url_test = "https://listado.mercadolibre.com.ar/tienda/gadnic/_NoIndex_True"
    # url_test = "https://listado.mercadolibre.com.ar/irrigador-bucal"

    with sync_playwright() as p:
        # headless=False para ver el navegador, slow_mo para ver qué hace
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()

        print(f"Navegando a la URL de prueba: {url_test}")
        try:
            page.goto(url_test, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"No se pudo cargar la página: {e}")
            browser.close()
            return

        # Esperamos a que la lista principal de productos esté visible
        try:
            page.wait_for_selector("ol.ui-search-layout", state='visible', timeout=20000)
            print("✅ Contenedor de productos encontrado.")
        except Exception as e:
            print(f"❌ No se pudo encontrar el contenedor de productos. Error: {e}")
            browser.close()
            return

        # Localizamos todos los items de la lista
        items = page.locator("li.ui-search-layout__item")
        count = items.count()
        print(f"Se encontraron {count} items en la página.\n")

        # Iteramos sobre cada item para extraer sus datos
        for i in range(count):
            print(f"--- Extrayendo Producto #{i + 1} ---")
            item = items.nth(i)

            # --- OBTENEMOS EL HTML INTERNO UNA SOLA VEZ PARA EFICIENCIA ---
            item_html = item.inner_html()

            # --- SELECTORES COMBINADOS Y ROBUSTOS ---
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
            
            # --- LÓGICA DE BÚSQUEDA EN TEXTO HTML ---
            
            # 1. Meli+
            es_meli_plus = 'href="#poly_meli_plus"' in item_html

            # 2. Tipo de Envío (FULL / FULL SÚPER)
            tipo_full = "Normal"
            if 'aria-label="Full Súper"' in item_html:
                tipo_full = "Full Súper"
            elif 'aria-label="FULL"' in item_html or 'aria-label="Enviado por FULL"' in item_html:
                tipo_full = "FULL"

            # 3. Origen del Envío
            origen_envio = "Nacional"
            origen_loc = item.locator(".ui-search-item__shipping-info, .poly-component__shipped-from")
            if origen_loc.count() > 0:
                texto_origen = get_safe_text(origen_loc)
                if "desde" in texto_origen.lower():
                    origen_envio = texto_origen.split('desde ')[-1].strip()

            # --- OTROS DATOS ---
            info_adicional = get_safe_text(item.locator(".ui-search-official-store-label, .poly-component__cbt, .andes-tag"))

            imagen_url = "N/A"
            img_loc = item.locator("img.ui-search-result-image__element, img.poly-component__picture")
            if img_loc.count() > 0:
                imagen_url = img_loc.first.get_attribute("data-src") or img_loc.first.get_attribute("src")

            # --- IMPRESIÓN COMPLETA EN CONSOLA ---
            print(f"  Título: {titulo}")
            print(f"  Precio: {precio_actual_str}")
            print(f"  Precio Ant.: {precio_anterior_str}")
            print(f"  Descuento: {descuento}")
            print(f"  Vendidos/Rating: {vendidos_y_rating}")
            print(f"  Vendedor: {vendedor}")
            print(f"  Info Envío: {envio}")
            print(f"  Tipo Envío: {tipo_full}")
            print(f"  Meli+: {'Sí' if es_meli_plus else 'No'}")
            print(f"  Origen: {origen_envio}")
            print(f"  Etiquetas Adicionales: {info_adicional}")
            print(f"  Link: {link}") # Link completo, sin cortar
            print(f"  Imagen: {imagen_url}")
            print("-" * 30)

        print("\nPrueba de extracción finalizada.")
        print("La ventana del navegador se cerrará en 15 segundos...")
        page.wait_for_timeout(15000)
        browser.close()

if __name__ == "__main__":
    test_single_page_extraction()