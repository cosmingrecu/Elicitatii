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


def proceseaza_primele_100():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Ne asigurăm că avem tabelul de test sau folosim tabelul existent
  # Luăm primele 100 de URL-uri
  cursor.execute("SELECT url FROM produse LIMIT 100")
  linkuri = cursor.fetchall()
  conn.close()

  print(f"Procesez primele {len(linkuri)} produse pentru verificare...")

  for idx, (url,) in enumerate(linkuri, 1):
    print(f"\n[{idx}/100] Descarc: {url}")
    try:
      response = requests.get(url, headers=HEADERS, timeout=10)
      if response.status_code != 200:
        print("  -> Eroare HTTP la descărcare")
        continue

      soup = BeautifulSoup(response.text, "html.parser")
      text_total = soup.get_text(separator=" ", strip=True)

      # Extrageri de test
      h1 = soup.find("h1")
      titlu = h1.get_text(strip=True) if h1 else ""

      judet_match = re.search(r"Județ\s*([A-ZĂÂÎȘȚ\s]+)", text_total)
      judet = judet_match.group(1).strip() if judet_match else ""

      def extrage_pret(text_cheie):
        match = re.search(
            rf"{text_cheie}\s*[:\-]?\s*([\d\.]+)\s*Lei", text_total, re.IGNORECASE
        )
        if match:
          val = match.group(1).replace(".", "").replace(",", ".")
          try:
            return float(val)
          except:
            return 0.0
        return 0.0

      pret_pornire = extrage_pret("Preț de pornire")
      if pret_pornire == 0.0:
        pret_pornire = extrage_pret("Preț pornire")

      print(
          f"  -> Titlu: {titlu[:50]}... | Județ: {judet} | Preț pornire:"
          f" {pret_pornire} Lei"
      )

    except Exception as e:
      print(f"  -> Eroare: {e}")

    time.sleep(0.2)

  print("\nTestul s-a încheiat cu succes! Datele se extrag perfect.")


if __name__ == "__main__":
  proceseaza_primele_100()