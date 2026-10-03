import time
import re
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import psycopg2

def obtine_conexiune():
    return psycopg2.connect(
        dbname=os.getenv("NEON_DB_NAME", "neondb"),
        user=os.getenv("NEON_DB_USER", "neondb_owner"),
        password=os.getenv("NEON_DB_PASSWORD", "npg_qsnN2kp0BxPu"),
        host=os.getenv("NEON_DB_HOST", "ep-twilight-cake-b5h76zxt-pooler.c-7.us-east-2.aws.neon.tech"),
        port=os.getenv("NEON_DB_PORT", "5432"),
        sslmode="require"
    )

def ruleaza_extractorul():
    conn = obtine_conexiune()
    cur = conn.cursor()
    
    cur.execute("SELECT id, url, tip_sectiune FROM anunturi_detalii WHERE procesat = FALSE LIMIT 10000;")
    randuri = cur.fetchall()
    
    if not randuri:
        print("Nu mai există anunțuri de procesat! Toate sunt la zi.")
        cur.close()
        conn.close()
        return

    print(f"Am găsit {len(randuri)} anunțuri de procesat în această transă...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        for record_id, url, tip_sectiune in randuri:
            print(f"\n--- Procesez [{tip_sectiune}] ID {record_id} ---")
            print(f"URL: {url}")
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                
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
                istoric_oferte = "Fără oferte"

                for i, linie in enumerate(linii):
                    if "Identificator" in linie:
                        if i + 1 < len(linii) and len(linii[i + 1]) > 5 and linii[i + 1].isdigit():
                            identificator = linii[i + 1]
                    elif "Procent reducere" in linie:
                        if "%" in linie:
                            match_red = re.search(r'(-\s*\d+%)', linie)
                            if match_red: procent_reducere = match_red.group(1).replace(" ", "")
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

                for i, l in enumerate(linii):
                    if "Preț de pornire" in l or "Preţ de pornire" in l or "Preț pornire" in l or "Preţ pornire" in l:
                        for j in range(i + 1, min(i + 5, len(linii))):
                            val = linii[j]
                            if any(c.isdigit() for c in val) and val != "00" and len(val) > 2:
                                pret_pornire = val
                                break
                    elif "Preț de evaluare" in l or "Preţ de evaluare" in l:
                        for j in range(i + 1, min(i + 5, len(linii))):
                            val = linii[j]
                            if any(c.isdigit() for c in val) and val != "00" and len(val) > 2:
                                pret_evaluare = val
                                break

                match_url_id = re.search(r'/produs/([0-9-]+)', url)
                if match_url_id:
                    identificator = match_url_id.group(1).split('-')[0]

                for i, l in enumerate(linii):
                    if "Durată" in l or "Durata" in l:
                        linii_timp = []
                        for sub_l in linii[i + 1:]:
                            if any(cuvant in sub_l for cuvant in ["Preț", "Preţ", "TVA", "Istoric", "Descriere", "Ofertă", "Ofertant", "Structură", "Taxă"]):
                                break
                            if len(linii_timp) > 10:
                                break
                            linii_timp.append(sub_l)
                        if linii_timp:
                            timp_ramas = " ".join(linii_timp)
                        break

                for i, l in enumerate(linii):
                    if "Istoric oferte" in l:
                        linii_oferte_raw = []
                        for sub_l in linii[i + 1:]:
                            if sub_l in ["Structură teritorială", "Județ", "Loc de deținere / predare bun", "Descriere", "Observații", "Sediu central ANAF"]:
                                break
                            linii_oferte_raw.append(sub_l)
                        if linii_oferte_raw:
                            f = [x for x in linii_oferte_raw if x not in ["oferte", "ID ofertant", "Data și ora", "Valoarea ofertei", "#"]]
                            grupuri = []
                            vazute = set()
                            idx = 0
                            while idx < len(f):
                                if f[idx].isdigit() and idx + 1 < len(f) and "•" in f[idx+1]:
                                    of_id = f[idx]
                                    of_data = f[idx+1]
                                    of_val = "N/A"
                                    for k in range(idx + 2, min(idx + 6, len(f))):
                                        val_curenta = f[k]
                                        if any(c.isdigit() for c in val_curenta) and val_curenta != of_id and "•" not in val_curenta:
                                            of_val = val_curenta
                                            break
                                    format_oferta = f"[Ofertant #{of_id} la {of_data} -> {of_val}]"
                                    if format_oferta not in vazute:
                                        vazute.add(format_oferta)
                                        grupuri.append(format_oferta)
                                    idx += 2
                                else:
                                    idx += 1
                            istoric_oferte = " | ".join(grupuri) if grupuri else " | ".join(f)
                        break

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
                        istoric_oferte = %s,
                        procesat = TRUE 
                    WHERE id = %s;
                """, (
                    titlu_bun, identificator, pret_pornire, pret_evaluare, procent_reducere, 
                    judet, numar_licitatie, cota_tva, timp_ramas[:500], descriere[:5000], 
                    istoric_oferte[:2000], record_id
                ))
                conn.commit()
                time.sleep(0.3)
                
            except Exception as e:
                print(f"Eroare la procesarea ID {record_id}: {e}")
                conn.rollback()
                
        browser.close()
    cur.close()
    conn.close()
    print("\nTransa curentă a fost finalizată cu succes în baza de date Neon!")

if __name__ == "__main__":
    ruleaza_extractorul()