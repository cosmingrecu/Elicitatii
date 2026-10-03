import os
import time
import psycopg2
from playwright.sync_api import sync_playwright

DB_HOST = os.getenv("NEON_DB_HOST", "your_host")
DB_NAME = os.getenv("NEON_DB_NAME", "your_db")
DB_USER = os.getenv("NEON_DB_USER", "your_user")
DB_PASSWORD = os.getenv("NEON_DB_PASSWORD", "your_password")
DB_PORT = os.getenv("NEON_DB_PORT", "5432")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT, sslmode="require"
    )

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anunturi_detalii (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            tip_sectiune TEXT,
            titlu TEXT,
            continut TEXT,
            procesat BOOLEAN DEFAULT FALSE,
            data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def run_scraper():
    init_db()
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page()
        target_url = "https://www.anaf.ro/anunturi-valori-materiale/"
        
        try:
            print(f"Accesare {target_url}...")
            page.goto(target_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            pagina_curenta = 1
            max_pagini = 500
            
            while pagina_curenta <= max_pagini:
                print(f"Scraping pagină listă #{pagina_curenta}...")
                page.wait_for_timeout(2000)
                
                # Căutare linkuri de detaliu pe pagina curentă
                elemente_link = page.locator("a[href*='detalii'], a.detalii-anunt, table tr td a")
                count = elemente_link.count()
                
                inregistrate = 0
                for i in range(count):
                    el = elemente_link.nth(i)
                    href = el.get_attribute("href")
                    titlu = el.inner_text().strip()
                    
                    if href:
                        if href.startswith("/"):
                            href = "https://www.anaf.ro" + href
                        elif not href.startswith("http"):
                            href = target_url.rstrip("/") + "/" + href
                            
                        try:
                            cur.execute(
                                """
                                INSERT INTO anunturi_detalii (url, tip_sectiune, titlu)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (url) DO NOTHING;
                                """,
                                (href, "valori_materiale", titlu)
                            )
                            conn.commit()
                            inregistrate += 1
                        except Exception as e:
                            conn.rollback()
                            print(f"Erore inserare DB: {e}")

                print(f" -> Salvate {inregistrate} linkuri de pe pagina {pagina_curenta}.")
                
                # Navigare la pagina următoare folosind butonul specific paginării
                buton_urmatoare = page.locator("a:has-text('Următoare'), a.pagination-next, li.next a, a:has-text('>')")
                
                if buton_urmatoare.count() > 0 and not ("disabled" in (buton_urmatoare.first.get_attribute("class") or "")):
                    try:
                        buton_urmatoare.first.click()
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        pagina_curenta += 1
                    except Exception as ex:
                        print(f"Nu s-a putut avansa la pagina următoare: {ex}")
                        break
                else:
                    print("S-a ajuns la ultima pagină.")
                    break

            cur.close()
            conn.close()
        except Exception as e:
            print(f"Erore în scraper: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_scraper()
