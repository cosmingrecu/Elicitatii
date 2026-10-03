import os
import time
import psycopg2
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Preluare credențiale Neon DB din mediul GitHub Actions sau fallback local
DB_HOST = os.getenv("NEON_DB_HOST", "localhost")
DB_NAME = os.getenv("NEON_DB_NAME", "anaf_warehouse")
DB_USER = os.getenv("NEON_DB_USER", "postgres")
DB_PASSWORD = os.getenv("NEON_DB_PASSWORD", "parola_ta_secreta")
DB_PORT = os.getenv("NEON_DB_PORT", "5432")

def obtine_conexiune():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        sslmode="require" if DB_HOST != "localhost" else "prefer"
    )

def initializeaza_baza():
    conn = obtine_conexiune()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anunturi_detalii (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            titlu TEXT,
            pret_pornire TEXT,
            pret_evaluare TEXT,
            procent_reducere TEXT,
            judet TEXT,
            numar_licitatie TEXT,
            cota_tva TEXT,
            timp_ramas TEXT,
            descriere TEXT,
            istoric_oferte TEXT,
            tip_sectiune TEXT,
            procesat BOOLEAN DEFAULT FALSE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def colecteaza_sectiunea(page, tip_sectiune, url_start, max_pagini=700):
    print(f"\n--- Începem colectarea pentru: {tip_sectiune} ---")
    try:
        page.goto(url_start, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"Erore la deschiderea paginii de start: {e}")
        return
    
    pagina_curenta = 1
    total_salvate = 0

    while pagina_curenta <= max_pagini:
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        linkuri_detalii = []
        for a in soup.find_all('a', href=True):
            if "Vedeți detalii" in a.get_text():
                href = a['href']
                full_url = href if href.startswith('http') else "https://elicitatii.anaf.ro" + href
                linkuri_detalii.append(full_url)
        
        if not linkuri_detalii:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/detalii/' in href or '/anunt/' in href or '/licitatie/' in href:
                    full_url = href if href.startswith('http') else "https://elicitatii.anaf.ro" + href
                    linkuri_detalii.append(full_url)

        linkuri_detalii = list(set(linkuri_detalii))
        
        conn = obtine_conexiune()
        cur = conn.cursor()
        salvate_pagina = 0
        
        for url in linkuri_detalii:
            try:
                # Inserare bazată pe unicitatea URL-ului. Dacă URL-ul există deja, este ignorat complet (DO NOTHING).
                cur.execute("""
                    INSERT INTO anunturi_detalii (url, tip_sectiune)
                    VALUES (%s, %s)
                    ON CONFLICT (url) DO NOTHING;
                """, (url, tip_sectiune))
                
                # Verificăm dacă rândul a fost efectiv inserat
                if cur.rowcount > 0:
                    salvate_pagina += 1
                    total_salvate += 1
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Erore la inserare pentru URL-ul {url}: {e}")
        
        cur.close()
        conn.close()

        print(f"[{tip_sectiune}] Pagina {pagina_curenta}: am găsit {len(linkuri_detalii)} anunțuri ({salvate_pagina} noi salvate). Total noi: {total_salvate}")

        try:
            buton_urmatoare = page.locator("a:has-text('Următoare')")
            if buton_urmatoare.count() == 0 or "disabled" in (buton_urmatoare.get_attribute("class") or ""):
                break
            buton_urmatoare.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            pagina_curenta += 1
        except Exception:
            break

def ruleaza_scraperul():
    initializeaza_baza()
    rute = [
        ("PUBLICITATE", "https://elicitatii.anaf.ro/publicitate/categorii"),
        ("LICITATIE", "https://elicitatii.anaf.ro/licitatii/categorii")
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        for tip, url in rute:
            try:
                colecteaza_sectiunea(page, tip, url)
            except Exception as e:
                print(f"Erore pe secțiunea {tip}: {e}")
        browser.close()

if __name__ == "__main__":
    ruleaza_scraperul()
