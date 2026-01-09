import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get the schema (CREATE TABLE statements)
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
schema = cursor.fetchall()

# Get the data (INSERT INTO statements)
data = []
for table_name in [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")]:
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    data.append((table_name, columns, rows))

# Write to dump.sql
with open('dump.sql', 'w') as f:
    # Write the schema
    for statement in schema:
        if statement[0]:
            f.write(statement[0] + ';\n')

    # Write the data
    for table_name, columns, rows in data:
        for row in rows:
            values = ', '.join([f"'{value}'" if isinstance(value, str) else str(value) for value in row])
            f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values});\n")

conn.close()