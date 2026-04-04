def _ensure_column(cursor, table_name, column_name, definition_sql):
    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
    if cursor.fetchone() is None:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")


def ensure_schema(db, cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            student_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            roll_no VARCHAR(50) NOT NULL UNIQUE,
            birthdate DATE NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            date DATE NOT NULL,
            status VARCHAR(20) NOT NULL,
            UNIQUE KEY uniq_student_date (student_id, date),
            CONSTRAINT fk_attendance_student
                FOREIGN KEY (student_id)
                REFERENCES students(student_id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL
        )
        """
    )

    _ensure_column(cursor, "teachers", "full_name", "VARCHAR(120) NOT NULL DEFAULT 'Teacher'")
    _ensure_column(cursor, "teachers", "created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")
    _ensure_column(cursor, "teachers", "last_login_at", "DATETIME NULL")

    cursor.execute("SELECT teacher_id FROM teachers WHERE username=%s", ("admin",))
    if cursor.fetchone() is None:
        cursor.execute(
            """
            INSERT INTO teachers (username, password, full_name)
            VALUES (%s, %s, %s)
            """,
            ("admin", "admin", "Administrator"),
        )

    db.commit()
