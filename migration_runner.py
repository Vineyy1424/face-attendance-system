import os

import mysql.connector


MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def split_sql_statements(sql_text):
    statements = []
    current = []

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue

        current.append(raw_line)

        if line.endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement[:-1].strip())
            current = []

    trailing = "\n".join(current).strip()
    if trailing:
        statements.append(trailing)

    return statements


def run_migrations(
    base_dir,
    host="localhost",
    user="root",
    password="root",
    database="smart_attendance",
):
    migrations_dir = os.path.join(base_dir, "migrations")
    if not os.path.isdir(migrations_dir):
        return []

    migration_files = sorted(
        [f for f in os.listdir(migrations_dir) if f.lower().endswith(".sql")]
    )

    if not migration_files:
        return []

    db = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        use_pure=True,
    )
    cursor = db.cursor(buffered=True)

    try:
        cursor.execute(MIGRATIONS_TABLE_SQL)
        db.commit()

        cursor.execute("SELECT migration_name FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        applied_now = []

        for migration_name in migration_files:
            if migration_name in applied:
                continue

            migration_path = os.path.join(migrations_dir, migration_name)
            with open(migration_path, "r", encoding="utf-8") as file_handle:
                sql = file_handle.read()

            for statement in split_sql_statements(sql):
                cursor.execute(statement)
                if cursor.with_rows:
                    cursor.fetchall()

            cursor.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (%s)",
                (migration_name,),
            )
            db.commit()
            applied_now.append(migration_name)

        return applied_now

    finally:
        try:
            if cursor.with_rows:
                cursor.fetchall()
        except Exception:
            pass
        cursor.close()
        db.close()


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    applied_migrations = run_migrations(current_dir)
    if applied_migrations:
        print("Applied migrations:")
        for migration_name in applied_migrations:
            print(" -", migration_name)
    else:
        print("No pending migrations.")
