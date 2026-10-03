import re
import sqlite3
import time
from bs4 import BeautifulSoup
import requests

DB_NAME = "anaf_data.db"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def init_db_complet():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS produse (
            url TEXT PRIMARY KEY,
            titlu TEXT,
            categorie TEXT,
            identificator TEXT,
            cantitate TEXT,
            data_inceput TEXT,
            data_sfarsit TEXT,
            pret_pornire REAL,
            pret_evaluare REAL,
            cota_tva TEXT,
            taxa_participare REAL,
            institutie TEXT,
            judet TEXT,
            loc_detinere TEXT,
            descriere TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS oferte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_produs TEXT,
            id_ofertant TEXT,
            data_ora TEXT,
            valoare_oferta REAL,
            FOREIGN KEY (url_produs) REFERENCES produse (url)
        )
    """)
  conn.commit()
  conn.close()


def curata_pret(text):
  if not text:
    return 0.0
  # Eliminăm orice în afară de cifre, punct și virgulă
  text_curat = (
      text.replace("Lei", "")
      .replace("LEI", "")
      .replace("lei", "")
      .strip()
  )
  # Dacă avem format românesc (ex: 12.345,67 sau 12.345)
  if "," in text_curat and "." in text_curat:
    if text_curat.find(",") > text_curat.find("."):
      text_curat = text_curat.replace(".", "").replace(",", ".")
    else:
      text_curat = text_curat.replace(",", "")
  elif "," in text_curat:
    # Verificăm dacă virgula e zecimală (are max 2-3 cifre după ea)
    parti = text_curat.split(",")
    if len(parti) == 2 and len(parti[1]) <= 2:
      text_curat = text_curat.replace(",", ".")
    else:
      text_curat = text_curat.replace(",", "")
  elif "." in text_curat:
    # Dacă sunt mai multe puncte, sunt separator de mii
    if text_curat.count(".") > 1:
      text_curat = text_curat.replace(".", "")
    else:
      # Un singur punct - poate fi mii sau zecimal (ex: 1500.00 sau 1.500)
      parti = text_curat.split(".")
      if len(parti[1]) == 3:  # Probabil mii
        text_curat = text_curat.replace(".", "")

  try:
    return float(text_curat)
  except:
    return 0.0


def extrage_valoare_flexibila(text_total, chei_posibile):
  for cheie in chei_posibile:
    # Căutăm eticheta urmată opțional de simboluri și de valoare urmată de Lei sau final de linie
    pattern = rf"{cheie}\s*[:\-]?\s*([\d\.,\s]+(?:\s*Lei)?)"
    match = re.search(pattern, text_total, re.IGNORECASE)
    if match:
      val_extrasa = match.group(1)
      pret = curata_pret(val_extrasa)
      if pret > 0:
        return pret
  return 0.0


def proceseaza_pagina(url):
  try:
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code != 200:
      return None, None

    soup = BeautifulSoup(response.text, "html.parser")
    text_total = soup.get_text(separator=" ", strip=True)

    # 1. Titlu
    h1 = soup.find("h1")
    titlu = h1.get_text(strip=True) if h1 else ""

    # 2. Categorie
    cat_match = re.search(
        r"(?:Acas[aă]\s*(?:Publicitate bunuri)?\s*Categorii)(.*?)(?="
        + re.escape(titlu[:20])
        + r"|$)",
        text_total,
        re.IGNORECASE,
    )
    categorie = cat_match.group(1).strip() if cat_match else ""

    # 3. Identificator
    id_match = re.search(
        r"Identificator\s*(?:publicitate)?:\s*(\d+)", text_total, re.IGNORECASE
    )
    identificator = id_match.group(1) if id_match else ""

    # 4. Județ
    judet_match = re.search(
        r"Județ\s*([A-ZĂÂÎȘȚ\s]+?)(?=\s*(?:Instituție|Structură|Loc|Preț|Data|$))",
        text_total,
    )
    judet = judet_match.group(1).strip() if judet_match else ""

    # 5. Date calendaristice (luăm toate datele de tip dată-oră din pagină)
    date_match = re.findall(
        r"(\d{2}\.\d{2}\.\d{4}\s*(?:•|-)?\s*\d{2}:\d{2}:\d{2})", text_total
    )
    data_inceput = date_match[0] if len(date_match) > 0 else ""
    data_sfarsit = date_match[1] if len(date_match) > 1 else ""

    # 6. Prețuri și Taxe (folosind variante multiple pentru a acoperi toate cazurile ANAF)
    pret_pornire = extrage_valoare_flexibila(text_total, [
        "Preț de pornire",
        "Preț pornire",
        "Pret de pornire",
        "Pret pornire",
    ])
    pret_evaluare = extrage_valoare_flexibila(text_total, [
        "Preț de evaluare",
        "Preț evaluare",
        "Pret de evaluare",
        "Pret evaluare",
    ])
    taxa_participare = extrage_valoare_flexibila(text_total, [
        "Taxă participare",
        "Taxa participare",
        "Taxă de participare",
    ])

    # 7. Cotă TVA
    tva_match = re.search(
        r"Cotă TVA\s*([0-9%,\.]+)", text_total, re.IGNORECASE
    )
    cota_tva = tva_match.group(1).strip() if tva_match else ""

    # 8. Instituție
    inst_match = re.search(
        r"Structură teritorială\s*(.*?)(?=Județ|Loc de deținere|Preț|$)",
        text_total,
    )
    institutie = inst_match.group(1).strip() if inst_match else ""

    # 9. Descriere (căutăm între 'Descriere' și un reper final comun)
    desc_match = re.search(r"Descriere\s*(.*?)(?=Sediu central ANAF|$)", text_total)
    descriere = desc_match.group(1).strip() if desc_match else ""

    # 10. Extragere oferte / licitatori din tabele
    oferte_lista = []
    tabele = soup.find_all("table")
    for tabel in tabele:
      rânduri = tabel.find_all("tr")
      for rând in rânduri[1:]:
        celule = rând.find_all("td")
        if len(celule) >= 3:
          id_ofertant = celule[0].get_text(strip=True)
          data_ora = celule[1].get_text(strip=True)
          val_oferta = curata_pret(celule[2].get_text(strip=True))
          if val_oferta > 0:
            oferte_lista.append({
                "id_ofertant": id_ofertant,
                "data_ora": data_ora,
                "valoare_oferta": val_oferta,
            })

    date_produs = {
        "titlu": titlu,
        "categorie": categorie,
        "identificator": identificator,
        "cantitate": "",
        "data_inceput": data_inceput,
        "data_sfarsit": data_sfarsit,
        "pret_pornire": pret_pornire,
        "pret_evaluare": pret_evaluare,
        "cota_tva": cota_tva,
        "taxa_participare": taxa_participare,
        "institutie": institutie,
        "judet": judet,
        "loc_detinere": "",
        "descriere": descriere,
    }

    return date_produs, oferte_lista

  except Exception as e:
    print(f"Eroare la procesarea paginii {url}: {e}")
    return None, None


def ruleaza_extragererea():
  init_db_complet()
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Resetăm sau luăm articolele PENDING
  cursor.execute(
      "SELECT url FROM produse WHERE status = 'PENDING' OR status IS NULL"
  )
  linkuri = cursor.fetchall()
  conn.close()

  print(f"Am găsit {len(linkuri)} produse de procesat.")

  for idx, (url,) in enumerate(linkuri, 1):
    print(f"[{idx}/{len(linkuri)}] Procesez: {url}")
    date_produs, oferte_lista = proceseaza_pagina(url)

    if date_produs:
      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()

      cursor.execute(
          """
                INSERT OR REPLACE INTO produse (
                    url, titlu, categorie, identificator, cantitate, data_inceput, 
                    data_sfarsit, pret_pornire, pret_evaluare, cota_tva, 
                    taxa_participare, institutie, judet, loc_detinere, descriere, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DONE')
            """,
          (
              url,
              date_produs["titlu"],
              date_produs["categorie"],
              date_produs["identificator"],
              date_produs["cantitate"],
              date_produs["data_inceput"],
              date_produs["data_sfarsit"],
              date_produs["pret_pornire"],
              date_produs["pret_evaluare"],
              date_produs["cota_tva"],
              date_produs["taxa_participare"],
              date_produs["institutie"],
              date_produs["judet"],
              date_produs["loc_detinere"],
              date_produs["descriere"],
          ),
      )

      cursor.execute("DELETE FROM oferte WHERE url_produs = ?", (url,))
      for o in oferte_lista:
        cursor.execute(
            """
                    INSERT INTO oferte (url_produs, id_ofertant, data_ora, valoare_oferta)
                    VALUES (?, ?, ?, ?)
                """,
            (url, o["id_ofertant"], o["data_ora"], o["valoare_oferta"]),
        )

      conn.commit()
      conn.close()

    time.sleep(0.3)

  print("Extracția completă s-a terminat cu succes!")


if __name__ == "__main__":
  ruleaza_extragererea()