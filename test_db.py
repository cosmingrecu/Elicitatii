import sqlite3

conn = sqlite3.connect("anaf_data.db")
cursor = conn.cursor()
rezultate = cursor.execute(
    "SELECT titlu, pret_pornire, judet FROM produse WHERE status = 'DONE' LIMIT"
    " 5"
).fetchall()
for r in rezultate:
  print(r)
conn.close()