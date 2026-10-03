import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import psycopg2
import re
import os

def obtine_conexiune():
    return psycopg2.connect(
        dbname=os.getenv("NEON_DB_NAME", "neondb"),
        user=os.getenv("NEON_DB_USER", "neondb_owner"),
        password=os.getenv("NEON_DB_PASSWORD", "npg_qsnN2kp0BxPu"),
        host=os.getenv("NEON_DB_HOST", "ep-twilight-cake-b5h76zxt-pooler.c-7.us-east-2.aws.neon.tech"),
        port=os.getenv("NEON_DB_PORT", "5432"),
        sslmode="require"
    )

def extrage_identificator(url):
    match = re.search(r'produs/([0-9-]+)', url)
    if match:
        return match.group(1).split('-')[0]
    return url

def initializeaza_baza():
    conn = obtine_conexiune()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anunturi_detalii (
            id SERIAL PRIMARY KEY,
            identificator TEXT UNIQUE,
            url TEXT,
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
        print(f"Eroare la deschiderea paginii de start: {e}")
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
            identificator = extrage_identificator(url)
            try:
                cur.execute("""
                    INSERT INTO anunturi_detalii (identificator, url, tip_sectiune)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (identificator) 
                    DO UPDATE SET 
                        url = EXCLUDED.url,
                        tip_sectiune = EXCLUDED.tip_sectiune;
                """, (identificator, url, tip_sectiune))
                conn.commit()
                salvate_pagina += 1
                total_salvate += 1
            except Exception as e:
                conn.rollback()
                print(f"Eroare la inserare pentru {identificator}: {e}")
        
        cur.close()
        conn.close()

        print(f"[{tip_sectiune}] Pagina {pagina_curenta}: am găsit {len(linkuri_detalii)} anunțuri ({salvate_pagina} procesate). Total: {total_salvate}")

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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        for tip, url in rute:
            try:
                colecteaza_sectiunea(page, tip, url)
            except Exception as e:
                print(f"Eroare pe secțiunea {tip}: {e}")
        browser.close()

if __name__ == "__main__":
    ruleaza_scraperul()