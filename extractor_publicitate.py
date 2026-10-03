import time
import re
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

def asigura_structura_bazei(cur, conn):
    cur.execute("""
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS pret_pornire TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS pret_evaluare TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS procent_reducere TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS judet TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS identificator TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS numar_licitatie TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS cota_tva TEXT;
        ALTER TABLE anunturi_detalii ADD COLUMN IF NOT EXISTS timp_ramas TEXT;
    """)
    conn.commit()

def ruleaza_extractorul():
    conn = obtine_conexiune()
    cur = conn.cursor()
    asigura_structura_bazei(cur, conn)
    
    # Selectăm doar anunțurile neprocesate care conțin '/publicitate/produs/' în URL
    cur.execute("SELECT id, url FROM anunturi_detalii WHERE procesat = FALSE AND url LIKE '%/publicitate/produs/%' LIMIT 50;")
    randuri = cur.fetchall()
    
    if not randuri:
        print("Nu mai există anunțuri de publicitate de procesat! Toate sunt la zi.")
        cur.close()
        conn.close()
        return

    print(f"Am găsit {len(randuri)} anunțuri de publicitate de procesat în această transă...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        for record_id, url in randuri:
            print(f"\n--- Procesez Publicitate ID {record_id} ---")
            print(f"URL: {url}")
            try:
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                
                # 1. Extragere Titlu (H1)
                titlu_bun = "N/A"
                h1_tag = soup.find('h1')
                if h1_tag:
                    titlu_bun = h1_tag.get_text(strip=True)
                
                text_pag = soup.get_text(separator="\n", strip=True)
                linii = [l.strip() for l in text_pag.split('\n') if l.strip()]

                identificator = "N/A"
                pret_pornire = "N/A"
                pret_evaluare = "N/A"
                procent_reducere = "N/A"
                judet = "N/A"
                numar_licitatie = "N/A"
                cota_tva = "N/A"
                descriere = "N/A"
                timp_ramas = "N/A"

                # 2. Parsare inteligentă linie cu linie bazată pe etichete
                for i, linie in enumerate(linii):
                    if "Identificator publicitate" in linie or "Identificator" in linie:
                        if i + 1 < len(linii) and len(linii[i + 1]) > 10 and linii[i + 1].isdigit():
                            identificator = linii[i + 1]
                    elif "Preț pornire" in linie or "Preţ pornire" in linie:
                        if i + 1 < len(linii):
                            pret_pornire = linii[i + 1]
                    elif "Preț de evaluare" in linie or "Preţ de evaluare" in linie:
                        if i + 1 < len(linii):
                            pret_evaluare = linii[i + 1]
                    elif "Procent reducere" in linie:
                        if "%" in linie:
                            match_red = re.search(r'(-\d+%)', linie)
                            if match_red: procent_reducere = match_red.group(1)
                        elif i + 1 < len(linii):
                            procent_reducere = linii[i + 1]
                    elif "Licitația Număr" in linie or "Licitatia Numar" in linie:
                        if i + 1 < len(linii):
                            numar_licitatie = linii[i + 1]
                    elif "Cotă TVA" in linie or "Cota TVA" in linie:
                        if i + 1 < len(linii):
                            cota_tva = linii[i + 1]
                    elif linie.startswith("Județ") or linie.startswith("Judet"):
                        if len(linie) > 5 and not linie.endswith(":"):
                            judet = linie.replace("Județ", "").replace("Judet", "").strip()
                        elif i + 1 < len(linii):
                            judet = linii[i + 1]

                # 3. Extragere Durată / Perioadă Publicitate
                for i, l in enumerate(linii):
                    if "Durată publicitate" in l or "Durata publicitate" in l:
                        linii_timp = []
                        for sub_l in linii[i + 1:]:
                            if sub_l in ["Preț pornire", "Preţ pornire", "Preț de evaluare", "Preţ de evaluare", "Pentru a vă înscrie", "Descriere", "Modalitățile de înscriere"]:
                                break
                            linii_timp.append(sub_l)
                        if linii_timp:
                            timp_ramas = " ".join(linii_timp)
                        break

                # Fallback prin Regex pentru Identificator extras direct din URL
                match_url_id = re.search(r'/produs/(\d+)-', url)
                if match_url_id:
                    identificator = match_url_id.group(1)
                elif identificator == "N/A":
                    match_id = re.search(r'\b126000\d+\b', text_pag)
                    if match_id:
                        identificator = match_id.group(0)

                # Fallback prin Regex pentru Procent Reducere dacă a scăpat
                if procent_reducere == "N/A":
                    match_red_gen = re.search(r'(-\d+%)', text_pag)
                    if match_red_gen:
                        procent_reducere = match_red_gen.group(1)

                # 4. Extragere secțiune Descriere dedicată
                try:
                    idx_desc = linii.index("Descriere")
                    linii_desc = []
                    for l in linii[idx_desc + 1:]:
                        if l in ["Specificații", "Observații", "Sediu central ANAF", "Achiziții"]:
                            break
                        linii_desc.append(l)
                    descriere = " ".join(linii_desc)
                except ValueError:
                    descriere = titlu_bun

                # Afișăm în consolă rezultatele extrase pentru control vizual
                print(f" -> Titlu: {titlu_bun}")
                print(f" -> ID: {identificator}")
                print(f" -> Preț Pornire: {pret_pornire}")
                print(f" -> Preț Evaluare: {pret_evaluare}")
                print(f" -> Procent Reducere: {procent_reducere}")
                print(f" -> Licitația Număr: {numar_licitatie}")
                print(f" -> Cotă TVA: {cota_tva}")
                print(f" -> Județ: {judet}")
                print(f" -> Durată Publicitate: {timp_ramas}")

                # Salvăm în baza de date
                cur.execute("""
                    UPDATE anunturi_detalii 
                    SET titlu = %s, 
                        identificator = %s,
                        pret_pornire = %s,
                        pret_evaluare = %s,
                        procent_reducere = %s,
                        judet = %s,
                        numar_licitatie = %s,
                        cota_tva = %s,
                        timp_ramas = %s,
                        descriere = %s, 
                        procesat = TRUE 
                    WHERE id = %s;
                """, (titlu_bun, identificator, pret_pornire, pret_evaluare, procent_reducere, judet, numar_licitatie, cota_tva, timp_ramas[:500], descriere[:5000], record_id))
                conn.commit()
                
                time.sleep(0.3)
                
            except Exception as e:
                print(f"Eroare la procesarea ID {record_id}: {e}")
                conn.rollback()
                
        browser.close()
    cur.close()
    conn.close()
    print("\nTransa curentă a fost finalizată cu succes!")

if __name__ == "__main__":
    ruleaza_extractorul()