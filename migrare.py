import sqlite3

conn = sqlite3.connect("anaf_data.db")
cursor = conn.cursor()

# Lista de coloane pe care vrem să fim siguri că le avem în tabelul produse
coloane_necesare = [
    ("categorie", "TEXT"),
    ("identificator", "TEXT"),
    ("cantitate", "TEXT"),
    ("data_inceput", "TEXT"),
    ("data_sfarsit", "TEXT"),
    ("pret_pornire", "REAL"),
    ("pret_evaluare", "REAL"),
    ("cota_tva", "TEXT"),
    ("taxa_participare", "REAL"),
    ("institutie", "TEXT"),
    ("judet", "TEXT"),
    ("loc_detinere", "TEXT"),
    ("descriere", "TEXT"),
    ("status", "TEXT DEFAULT 'PENDING'"),
]

# Verificăm ce coloane există deja
cursor.execute("PRAGMA table_info(produse)")
coloane_existente = [info[1] for info in cursor.fetchall()]

# Adăugăm coloanele lipsă
for col_nume, col_tip in coloane_necesare:
  if col_nume not in coloane_existente:
    print(f"Adaug coloana lipsă: {col_nume}")
    cursor.execute(f"ALTER TABLE produse ADD COLUMN {col_nume} {col_tip}")

conn.commit()
conn.close()
print("Migrarea s-a terminat cu succes!")