import psycopg2

# Pune aici connection string-ul copiat de la Neon
DATABASE_URL = "postgresql://neondb_owner:npg_qsnN2kp0BxPu@ep-twilight-cake-b5h76zxt-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Test simplu
cursor.execute("SELECT version();")
print("Conectat cu succes la:", cursor.fetchone())

cursor.close()
conn.close()