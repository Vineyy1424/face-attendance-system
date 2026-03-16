import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance"
)

cursor = db.cursor()
cursor.execute("SHOW TABLES")

for table in cursor:
    print(table)

print("Database connected successfully")