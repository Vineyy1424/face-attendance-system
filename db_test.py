import mysql.connector
from db_schema import ensure_schema

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance"
)

cursor = db.cursor()
ensure_schema(db, cursor)
cursor.execute("SHOW TABLES")

for table in cursor:
    print(table)

print("Database connected successfully")