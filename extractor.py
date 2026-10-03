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
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT, sslmode="require"
    )

def run_extractor():
    conn = get_db_connection()
    cur = conn.cursor()
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page()

        while True:
            # Preluare câte un anunț neprocesat pe rând
            cur.execute("SELECT id, url FROM anunturi_detalii WHERE procesat = FALSE ORDER BY id ASC LIMIT 1;")
            rand = cur.fetchone()
            
            if not rand:
                print("Toate anunțurile au fost procesate.")
                break
                
            record_id, url = rand
            print(f"Extragere detaliu [ID: {record_id}]: {url}")
            
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                
                html_content = page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.extract()
                    
                continut_text = soup.get_text(separator="\n", strip=True)
                
                cur_update = conn.cursor()
                cur_update.execute(
                    """
                    UPDATE anunturi_detalii 
                    SET continut = %s, procesat = TRUE 
                    WHERE id = %s;
                    """,
                    (continut_text, record_id)
                )
                conn.commit()
                cur_update.close()
                
                time.sleep(1) # Pauză scurtă între cereri
                
            except Exception as e:
                print(f"Erore la procesarea URL-ului {url}: {e}")
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
                    print(f"Erore salvare eroare în DB: {db_err}")

        browser.close()

    cur.close()
    conn.close()
    print("Extracția pe rând s-a încheiat cu succes.")

if __name__ == "__main__":
    run_extractor()
