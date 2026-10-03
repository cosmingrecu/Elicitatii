from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import time
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests

# Configurare baze de date locală SQLite
DB_NAME = "anaf_data.db"

urls_categorii_baza = [
    "https://elicitatii.anaf.ro/publicitate/categorii/bunuri-mobile",
    "https://elicitatii.anaf.ro/publicitate/categorii/bunuri-imobile",
    "https://elicitatii.anaf.ro/licitatii/categorii/bunuri-imobile",
    "https://elicitatii.anaf.ro/licitatii/categorii/bunuri-mobile",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS produse (
            url TEXT PRIMARY KEY,
            titlu TEXT,
            identificator TEXT,
            pret_pornire TEXT,
            pret_evaluare TEXT,
            numar_licitatie TEXT,
            istoric_oferte TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    """)
  conn.commit()
  conn.close()


def salveaza_link_in_db(url):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO produse (url, status) VALUES (?, 'PENDING')", (url,)
  )
  conn.commit()
  conn.close()


def ia_linkuri_nedescărcate():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT url FROM produse WHERE status = 'PENDING'")
  links = [row[0] for row in cursor.fetchall()]
  conn.close()
  return links


def marcheaza_sters_sau_gata(url, data):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  if data:
    cursor.execute(
        """
            UPDATE produse SET titlu=?, identificator=?, pret_pornire=?, pret_evaluare=?, numar_licitatie=?, istoric_oferte=?, status='DONE'
            WHERE url=?
        """,
        (
            data.get("Titlu"),
            data.get("Identificator"),
            data.get("Pret_Pornire"),
            data.get("Pret_Evaluare"),
            data.get("Numar_Licitatie"),
            str(data.get("Istoric_Oferte")),
            url,
        ),
    )
  else:
    cursor.execute(
        "UPDATE produse SET status='ERROR' WHERE url=?", (url,)
    )
  conn.commit()
  conn.close()


def colectaza_toate_linkurile():
  print("Colectez lista completă de linkuri...")
  for cat_url in urls_categorii_baza:
    page_num = 1
    while True:
      url_curent = (
          cat_url if page_num == 1 else f"{cat_url}?pagina={page_num}"
      )
      try:
        response = requests.get(url_curent, headers=headers, timeout=10)
        if response.status_code != 200:
          break
        soup = BeautifulSoup(response.text, "html.parser")
        linkuri_pe_pagina = 0
        for a in soup.find_all("a", href=True):
          href = a["href"]
          if "/produs/" in href or "/licitatie/" in href:
            link_complet = (
                f"https://elicitatii.anaf.ro{href}"
                if not href.startswith("http")
                else href
            )
            salveaza_link_in_db(link_complet)
            linkuri_pe_pagina += 1
        if linkuri_pe_pagina == 0:
          break
        page_num += 1
      except Exception:
        break


def extrage_detalii_produs(url):
  data = {"URL": url}
  try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
      return None
    soup = BeautifulSoup(response.text, "html.parser")

    h1 = soup.find("h1")
    data["Titlu"] = h1.text.strip() if h1 else ""

    for element in soup.find_all(["div", "span", "p", "li", "td"]):
      txt = element.get_text(strip=True)
      if "Identificator publicitate" in txt or "Identificator licitație" in txt:
        next_el = element.find_next_sibling()
        if next_el:
          data["Identificator"] = next_el.get_text(strip=True)
      elif "Preț de pornire" in txt and "TVA" in txt:
        next_el = element.find_next_sibling()
        if next_el:
          data["Pret_Pornire"] = next_el.get_text(strip=True)
      elif "Preț de evaluare" in txt and "TVA" in txt:
        next_el = element.find_next_sibling()
        if next_el:
          data["Pret_Evaluare"] = next_el.get_text(strip=True)
      elif "Licitația Număr" in txt:
        next_el = element.find_next_sibling()
        if next_el:
          data["Numar_Licitatie"] = next_el.get_text(strip=True)

    tabel_oferte = soup.find("table")
    oferenti_lista = []
    if tabel_oferte:
      for tr in tabel_oferte.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) >= 3:
          oferenti_lista.append({
              "ID_Ofertant": tds[0].get_text(strip=True),
              "Data_Ora": tds[1].get_text(strip=True),
              "Valoare_Oferta": tds[2].get_text(strip=True),
          })
    data["Istoric_Oferte"] = oferenti_lista
    return data
  except Exception:
    return None


def exporta_in_google_sheets():
  print("Export datele în Google Sheets...")
  scope = [
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/drive",
  ]
  # Ai nevoie de un fișier service_account.json descărcat din Google Cloud Console
  try:
    creds = Credentials.from_service_account_file(
        "service_account.json", scopes=scope
    )
    client = gspread.authorize(creds)

    # Creează sau deschide un sheet numit "ANAF_Licitatii"
    try:
      sheet = client.open("ANAF_Licitatii").sheet1
    except Exception:
      sheet = client.create("ANAF_Licitatii").sheet1

    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT url, titlu, identificator, pret_pornire, pret_evaluare,"
        " numar_licitatie, istoric_oferte FROM produse WHERE status='DONE'",
        conn,
    )
    conn.close()

    # Curățăm și urcăm în Google Sheets
    sheet.clear()
    sheet.update(
        [df.columns.values.tolist()] + df.fillna("").values.tolist()
    )
    print("Succes! Datele au fost sincronizate în Google Sheets.")
  except Exception as e:
    print(
        f"Eroare la Google Sheets (asigură-te că ai fișierul"
        f" service_account.json): {e}"
    )


if __name__ == "__main__":
  init_db()

  # Pasul 1: Colectăm linkurile (dacă rulezi din nou, le știe pe cele vechi)
  colectaza_toate_linkurile()

  # Pasul 2: Luăm doar ce a rămas de descărcat (Pending)
  linkuri_de_procesat = ia_linkuri_nedescărcate()
  print(f"Total linkuri de procesat în baza de date: {len(linkuri_de_procesat)}")

  # Pasul 3: Rulăm în paralel cu 15 thread-uri (zboară prin ele în ~5-10 minute)
  with ThreadPoolExecutor(max_workers=15) as executor:
    future_to_url = {
        executor.submit(extrage_detalii_produs, link): link
        for link in linkuri_de_procesat
    }
    for future in as_completed(future_to_url):
      url = future_to_url[future]
      rezultat = future.result()
      marcheaza_sters_sau_gata(url, rezultat)
      print(f"Procesat și salvat local: {url}")

  # Pasul 4: Trimitem totul curat în Google Sheet
  exporta_in_google_sheets()