import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import psycopg2

def obtine_conexiune():
    return psycopg2.connect(
        dbname="anaf_warehouse",
        user="postgres",
        password="parola_ta_secreta",
        host="localhost",
        port="5432"
    )

def initializeaza_baza():
    conn = obtine_conexiune()
    cur = conn.cursor()
    # Resetăm tabelul ca să plecăm de la un set curat
    cur.execute("DROP TABLE IF EXISTS anunturi_detalii;")
    cur.execute("""
        CREATE TABLE anunturi_detalii (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE,
            titlu TEXT,
            identificator TEXT,
            pret_pornire TEXT,
            judet TEXT,
            descriere TEXT,
            tip_sectiune TEXT,
            procesat BOOLEAN DEFAULT FALSE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def colecteaza_sectiunea(page, cur, conn, tip_sectiune, url_start, max_pagini=700):
    print(f"\n--- Începem colectarea pentru: {tip_sectiune} ---")
    page.goto(url_start, timeout=60000)
    page.wait_for_load_state("networkidle")
    
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
        
        salvate_pagina = 0
        for url in linkuri_detalii:
            try:
                cur.execute("""
                    INSERT INTO anunturi_detalii (url, tip_sectiune)
                    VALUES (%s, %s)
                    ON CONFLICT (url) DO NOTHING;
                """, (url, tip_sectiune))
                conn.commit()
                salvate_pagina += 1
                total_salvate += 1
            except Exception:
                conn.rollback()

        print(f"[{tip_sectiune}] Pagina {pagina_curenta}: am găsit {len(linkuri_detalii)} anunțuri ({salvate_pagina} noi salvate). Total general: {total_salvate}")

        try:
            buton_urmatoare = page.locator("a:has-text('Următoare')")
            
            if buton_urmatoare.count() == 0:
                print(f"Am ajuns la ultima pagină pentru {tip_sectiune}.")
                break
                
            class_attr = buton_urmatoare.get_attribute("class") or ""
            if "disabled" in class_attr:
                print(f"Butonul 'Următoare' este dezactivat. Am terminat {tip_sectiune}.")
                break

            buton_urmatoare.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            pagina_curenta += 1
            
        except Exception as e:
            print(f"S-a terminat paginarea sau a apărut o eroare la pasul următor: {e}")
            break

def ruleaza_scraperul():
    initializeaza_baza()
    user_data_dir = "./browser_profile"
    
    rute = [
        ("PUBLICITATE", "https://elicitatii.anaf.ro/publicitate/categorii"),
        ("LICITATIE", "https://elicitatii.anaf.ro/licitatii/categorii")
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        conn = obtine_conexiune()
        cur = conn.cursor()
        
        for tip, url in rute:
            try:
                colecteaza_sectiunea(page, cur, conn, tip, url)
            except Exception as e:
                print(f"Eroare critică pe secțiunea {tip}: {e}")
                
        cur.close()
        conn.close()
        browser.close()
    print("\nToate listele au fost indexate cu succes în baza de date!")

if __name__ == "__main__":
    ruleaza_scraperul()