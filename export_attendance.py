import mysql.connector
import pandas as pd

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance"
)

query = """
SELECT students.student_id,
       students.name,
       attendance.date,
       attendance.status
FROM attendance
JOIN students
ON attendance.student_id = students.student_id
"""

# Read data
df = pd.read_sql(query, db)

# Save to Excel
df.to_excel("attendance_report.xlsx", index=False)

print("Attendance exported successfully!")

db.close()