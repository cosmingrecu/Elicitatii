import psycopg2
import re

def obtine_conexiune():
    return psycopg2.connect(
        dbname="anaf_warehouse",
        user="postgres",
        password="parola_ta_secreta",
        host="localhost",
        port="5432"
    )

linkuri_ceasuri = [
    "https://elicitatii.anaf.ro/publicitate/produs/12600011573000000001992-ceas-franck-muller",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011571000000001991-ceas-roger-dubuis",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011559000000001988-ceas-bulgari",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011568000000001989-ceas-ulysse-nardin",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011574000000001993-ceas-franck-muller",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011465000000001965-ceas-gerald-genta",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011464000000001964-ceas-franck-muller",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011462000000001963-ceas-cartier",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012036000000001955-ceas-roger-dubuis",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012051000000001957-ceas-hublot",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012049000000001956-ceas-buti",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011371000000001907-ceas-richard-mille",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011418000000001927-ceas-corum",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011417000000001926-ceas-rolex",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011395000000001920-ceas-audemars-piguet",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011394000000001919-ceas-audemars-piguet",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011386000000001913-ceas-jaeger-lecoultre",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011385000000001912-ceas-rolex",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011384000000001911-ceas-audemars-piguet",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012174000000001871-ceas-ebel",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011549000000001854-ceas-rolex",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012188000000001883-ceas-jaeger-lecoultre",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012187000000001882-ceas-chopard",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012186000000001881-ceas-franck-muller",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012185000000001880-ceas-omega",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012184000000001879-ceas-cartier",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012183000000001878-ceas-chanel",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012182000000001877-ceas-corum",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012180000000001876-ceas-chanel",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012179000000001875-ceas-jacob-co",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012178000000001874-ceas-eberhard",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012177000000001873-ceas-chopard",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012175000000001872-ceas-folli-follie",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011567000000001865-ceas-bulgari",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011560000000001858-ceas-rolex",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011558000000001857-ceas-franck-muller",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011557000000001856-ceas-vacheron-constantin",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011556000000001855-ceas-corum",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011566000000001864-ceas-iwc",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011565000000001863-ceas-hublot",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011564000000001862-ceas-cartier",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011563000000001861-ceas-audemars-piguet",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011562000000001860-ceas-jaeger-lecoultre",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011561000000001859-ceas-iwc",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011665000000001868-ceas-cartier",
    "https://elicitatii.anaf.ro/publicitate/produs/12600011662000000001867-ceas-patek-philippe",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012094000000001779-ceas-patek-philippe",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012107000000001781-ceas-audemars-piguet",
    "https://elicitatii.anaf.ro/publicitate/produs/12600012095000000001780-ceas-gerald-genta"
]

conn = obtine_conexiune()
cur = conn.cursor()

inserate = 0
for url in linkuri_ceasuri:
    match = re.search(r'produs/([0-9-]+)', url)
    identificator = match.group(1).split('-')[0] if match else None
    
    if not identificator:
        continue
        
    try:
        cur.execute("""
            INSERT INTO anunturi_detalii (identificator, url, tip_sectiune, procesat)
            VALUES (%s, %s, 'PUBLICITATE', FALSE)
            ON CONFLICT (identificator) 
            DO UPDATE SET 
                url = EXCLUDED.url,
                procesat = FALSE;
        """, (identificator, url))
        conn.commit()
        inserate += 1
    except Exception as e:
        conn.rollback()
        print(f"Eroare la inserare link {url}: {e}")

cur.close()
conn.close()
print(f"Gata! S-au adugat/resetat {inserate} linkuri de ceasuri în baza de date.")