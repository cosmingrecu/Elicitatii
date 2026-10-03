import os
import time
import psycopg2
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DB_HOST = os.getenv("NEON_DB_HOST", "your_host")
DB_NAME = os.getenv("NEON_DB_NAME", "your_db")
DB_USER = os.getenv("NEON_DB_USER", "your_user")
DB_PASSWORD = os.getenv("NEON_DB_PASSWORD", "your_password")
DB_PORT = os.getenv("NEON_DB_PORT", "5432")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        sslmode="require"
    )

def run_extractor():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Selectăm un batch de maximum 100 de linkuri neprocesate pentru a proteja memoria RAM și timpul de execuție
    cur.execute("SELECT id, url FROM anunturi_detalii WHERE procesat = FALSE LIMIT 100;")
    randuri = cur.fetchall()
    
    if not randuri:
        print("Nu există linkuri noi de procesat în baza de date.")
        cur.close()
        conn.close()
        return

    print(f"S-au găsit {len_randuri := len(randuri)} linkuri de procesat în acest batch.")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page()

        for record_id, url in randuri:
            print(f"Procesare ID {record_id}: {url}")
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                
                # Extragere HTML brut și curățare cu BeautifulSoup
                html_content = page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Eliminare elemente inutile (meniuri, footer, scripturi)
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.extract()
                    
                # Extragere text util (ajustează selectorul specific conținutului principal dacă este nevoie, ex: div.continut-anunt)
                continut_principal = soup.get_text(separator="\n", strip=True)
                
                # Actualizare în baza de date
                cur_update = conn.cursor()
                cur_update.execute(
                    """
                    UPDATE anunturi_detalii 
                    SET continut = %s, procesat = TRUE 
                    WHERE id = %s;
                    """,
                    (continut_principal, record_id)
                )
                conn.commit()
                cur_update.close()
                
                # Pauză scurtă între cereri pentru a nu suprasolicita serverul ANAF
                time.sleep(1)
                
            except Exception as e:
                print(f"Erore la procesarea paginii {url} (ID: {record_id}): {e}")
                # Marcat ca procesat sau lăsat pentru reîncercare (aici marcăm cu eroare în conținut sau ignorăm pentru a nu bloca)
                try:
                    cur_err = conn.cursor()
                    cur_err.execute(
                        "UPDATE anunturi_detalii SET continut = %s, procesat = TRUE WHERE id = %s;",
                        (f"EROARE_EXTRAGERE: {str(e)}", record_id)
                    )
                    conn.commit()
                    cur_err.close()
                except Exception as db_err:
                    conn.rollback()
                    print(f"Erore la salvarea stării de eroare în DB: {db_err}")

        browser.close()

    cur.close()
    conn.close()
    print("Batch-ul de extracție s-a finalizat cu succes.")

if __name__ == "__main__":
    run_extractor()
