import mysql.connector

# Connect to database

db = mysql.connector.connect(
host="localhost",
user="root",
password="root",
database="smart_attendance"
)

cursor = db.cursor()

print("SMART ATTENDANCE PORTAL")

while True:

    print("\n1 Student Login")
    print("2 Teacher Login")
    print("3 Exit")

    choice = input("Choose option: ")

    if choice == "1":

        roll = input("Enter Roll Number: ")
        birthdate = input("Enter Birthdate (YYYY-MM-DD): ")

        query = "SELECT name FROM students WHERE roll_no=%s AND birthdate=%s"
        cursor.execute(query, (roll, birthdate))

        result = cursor.fetchone()

        if result:

            print("Welcome", result[0])

            while True:

                print("\nSTUDENT DASHBOARD")
                print("1 View My Attendance")
                print("2 View Attendance Percentage")
                print("3 Logout")

                student_choice = input("Choose option: ")

                if student_choice == "1":

                    query = """
                    SELECT date, status
                    FROM attendance
                    JOIN students ON attendance.student_id = students.student_id
                    WHERE students.roll_no = %s
                    """

                    cursor.execute(query, (roll,))
                    records = cursor.fetchall()

                    print("\nDate        Status")
                    print("-----------------------")

                    for r in records:
                        print(r[0], r[1])


                elif student_choice == "2":

                    query = """
                    SELECT
                    COUNT(*) AS total,
                    SUM(status='Present') AS present_days
                    FROM attendance
                    JOIN students ON attendance.student_id = students.student_id
                    WHERE students.roll_no = %s
                    """

                    cursor.execute(query, (roll,))
                    data = cursor.fetchone()

                    if data[0] == 0:
                        print("No attendance records yet")
                    else:
                        percentage = (data[1] / data[0]) * 100
                        print("Attendance Percentage:", round(percentage,2), "%")


                elif student_choice == "3":
                    break

                else:
                    print("Invalid option")

        else:
            print("Invalid Login")



    elif choice == "2":

        username = input("Enter Teacher Username: ")
        password = input("Enter Password: ")

        query = "SELECT username FROM teachers WHERE username=%s AND password=%s"
        cursor.execute(query, (username, password))

        result = cursor.fetchone()

        if result:
            print("Welcome", result[0])
        else:
            print("Invalid Login")


    elif choice == "3":
        print("Closing Portal...")
        break


    else:
        print("Invalid choice")

db.close()
print("Portal Closed")

