import psycopg2

# Configurare conexiune
conn = psycopg2.connect(
    dbname="anaf_warehouse",
    user="postgres",
    password="parola_ta_secreta",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Crearea tabelului Produse
cur.execute("""
CREATE TABLE IF NOT EXISTS produse (
    id SERIAL PRIMARY KEY,
    url VARCHAR(500) UNIQUE,
    titlu TEXT,
    numar_licitatie INT,
    pret_evaluare DECIMAL,
    pret_pornire DECIMAL,
    status VARCHAR(50),
    data_adaugare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Crearea tabelului Oferte (pentru istoric)
cur.execute("""
CREATE TABLE IF NOT EXISTS oferte (
    id SERIAL PRIMARY KEY,
    produs_id INT REFERENCES produse(id),
    valoare_oferta DECIMAL,
    data_oferta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
cur.close()
conn.close()
print("Tabelele au fost create cu succes!")