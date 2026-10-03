import sqlite3
from bs4 import BeautifulSoup
import requests

# Luăm un URL random din baza ta de date locală
conn = sqlite3.connect("anaf_data.db")
sample_url = conn.execute(
    "SELECT url FROM produse WHERE status = 'DONE' LIMIT 1"
).fetchone()[0]
conn.close()

print(f"Analizez structura pentru: {sample_url}")
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
resp = requests.get(sample_url, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")

# Să vedem toate etichetele și valorile din pagină
print("\n--- TEXTE GĂSITE ÎN PAGINĂ ---")
for el in soup.find_all(["div", "span", "p", "strong", "td"]):
  txt = el.get_text(strip=True)
  if any(
      k in txt.lower()
      for k in [
          "preț",
          "data",
          "localitate",
          "judet",
          "garantie",
          "organ",
          "stare",
      ]
  ):
    print(f"Etichetă/Text: {txt}")