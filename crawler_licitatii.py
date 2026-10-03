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

def ruleaza_ciclu_licitatii():
    conn = obtine_conexiune()
    cur = conn.cursor()
    
    # Extragem doar licitațiile active, sortate inteligent
    cur.execute("""
        SELECT id, url, istoric_oferte 
        FROM anunturi_detalii 
        WHERE url LIKE '%/licitatii/produs/%'
          AND status_licitatie = 'ACTIVA'
        ORDER BY are_oferte DESC, data_ultima_actualizare ASC NULLS FIRST
        LIMIT 30;
    """)
    randuri = cur.fetchall()
    
    if not randuri:
        print("[Info] Nu există licitații active de verificat momentan. Pauză de 5 minute...")
        cur.close()
        conn.close()
        time.sleep(300)
        return

    print(f"\n[Procesare] Am găsit {len(randuri)} licitații prioritare pentru verificare...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./browser_profile",
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        for record_id, url, istoric_vechi in randuri:
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                text_pag = soup.get_text(separator="\n", strip=True)
                linii = [l.strip() for l in text_pag.split('\n') if l.strip()]

                # Parsare istoric oferte (logica ta validată)
                istoric_oferte = "Fără oferte"
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

                # Determinăm flag-urile logice
                are_oferte_nou = True if istoric_oferte != "Fără oferte" else False
                
                # Verificăm dacă licitația a expirat după textul din pagină (opțional, dacă există un indicator de timp)
                # Dacă timpul a expirat, putem seta status_licitatie = 'EXPIRATA'

                # Salvăm în DB actualizând timestamp-ul
                cur.execute("""
                    UPDATE anunturi_detalii 
                    SET istoric_oferte = %s,
                        are_oferte = %s,
                        data_ultima_actualizare = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (istoric_oferte[:2000], are_oferte_nou, record_id))
                conn.commit()
                
                if are_oferte_nou and istoric_oferte != istoric_vechi:
                    print(f" [ALERTĂ] Ofertă nouă detectată la ID {record_id}!")
                else:
                    print(f" -> ID {record_id} verificat (Fără modificări noi).")

                time.sleep(0.5)
                
            except Exception as e:
                print(f"[Eroare] ID {record_id}: {e}")
                conn.rollback()
        
        browser.close()
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("Pornire daemon de monitorizare licitații...")
    while True:
        try:
            ruleaza_ciclu_licitatii()
        except Exception as e:
            print(f"Eroare critică în bucla principală: {e}")
            time.sleep(10)