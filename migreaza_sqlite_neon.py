import sqlite3
import psycopg2

print("Se deschide baza de date locală (SQLite)...")
conn_sqlite = sqlite3.connect("anaf_data.db")
conn_sqlite.row_factory = sqlite3.Row  # Ca să putem citi coloanele după nume
cur_sqlite = conn_sqlite.cursor()

# Verificăm ce tabel avem în SQLite (de obicei e "produse")
cur_sqlite.execute("SELECT * FROM produse;")
linii = cur_sqlite.fetchall()
print(s := f"S-au găsit {len(linii)} înregistrări în SQLite. Se pregătesc de transfer...")

print("Se conectează la baza de date din cloud (Neon)...")
conn_neon = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_qsnN2kp0BxPu",
    host="ep-twilight-cake-b5h76zxt-pooler.c-7.us-east-2.aws.neon.tech",
    port="5432",
    sslmode="require"
)
cur_neon = conn_neon.cursor()

# Inserăm rând cu rând pe Neon (folosind ON CONFLICT DO NOTHING ca să nu dăm eroare dacă există duplicate)
inserate = 0
for r in linii:
    # Extragem valorile din rândul SQLite (adaptat la structura ta de coloane)
    try:
        cur_neon.execute("""
            INSERT INTO produse (
                url, titlu, numar_licitatie, categorie, identificator, 
                cantitate, data_inceput, data_sfarsit, pret_pornire, 
                pret_evaluare, cota_tva, taxa_participare, institutie, 
                judet, loc_detinere, descriere, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING;
        """, (
            r["url"] if "url" in r.keys() else None,
            r["titlu"] if "titlu" in r.keys() else None,
            r["numar_licitatie"] if "numar_licitatie" in r.keys() else None,
            r["categorie" ] if "categorie" in r.keys() else None,
            r["identificator"] if "identificator" in r.keys() else None,
            r["cantitate"] if "cantitate" in r.keys() else None,
            r["data_inceput"] if "data_inceput" in r.keys() else None,
            r["data_sfarsit"] if "data_sfarsit" in r.keys() else None,
            r["pret_pornire"] if "pret_pornire" in r.keys() else None,
            r["pret_evaluare"] if "pret_evaluare" in r.keys() else None,
            r["cota_tva"] if "cota_tva" in r.keys() else None,
            r["taxa_participare"] if "taxa_participare" in r.keys() else None,
            r["institutie"] if "institutie" in r.keys() else None,
            r["judet"] if "judet" in r.keys() else None,
            r["loc_detinere"] if "loc_detinere" in r.keys() else None,
            r["descriere"] if "descriere" in r.keys() else None,
            r["status"] if "status" in r.keys() else 'PENDING'
        ))
        inserate += 1
        if inserate % 1000 == 0:
            print(f"S-au urcat {inserate} înregistrări...")
    except Exception as e:
        # Dacă o linie dă eroare, o sărim ca să nu oprească tot procesul
        continue

conn_neon.commit()

cur_sqlite.close()
conn_sqlite.close()
cur_neon.close()
conn_neon.close()

print(f"Gata! S-a finalizat migrarea. Au fost procesate {inserate} înregistrări pe Neon.")