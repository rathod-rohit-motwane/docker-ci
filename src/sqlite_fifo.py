# sqlite_fifo.py

import sqlite3

def init_db(database_name, table_name):
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()

    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL
    );
    ''')
    conn.commit()

    return conn, cursor

def push_data(cursor, conn, table_name, data):
    cursor.execute(f"INSERT INTO {table_name} (data) VALUES (?)", (data,))
    conn.commit()

def pop_data(cursor,conn, table_name):
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        print("Reading data:", row)
        cursor.execute(f"DELETE FROM {table_name} WHERE id=?", (row[0],))
        conn.commit()
        return row[1]
    else:
       # print("No more data to read.")
        return None

def peek_data(cursor, table_name):
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        print("Peeking data:", row)
        return row[1]
    else:
       # print("No more data to peek.")
        return None


def flush_and_reset_db(cursor, conn, table_name):
    cursor.execute(f"DELETE FROM {table_name}")
    conn.commit()
    cursor.execute(f"UPDATE SQLITE_SEQUENCE SET seq = 0 WHERE name = '{table_name}'")
    conn.commit()
    print(f"Data flushed and {table_name} reset.")

def search_string(cursor, table_name, search_str):
    cursor.execute(f"SELECT * FROM {table_name} WHERE data LIKE ?", (f"%{search_str}%",))
    row = cursor.fetchone()
    if row:
        print(f"Found string '{search_str}' in data:", row)
        return True
    else:
        print(f"String '{search_str}' not found in the table.")
        return False

def count_elements(cursor, table_name):
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    return count  




def update_string(connection, table_name, search_str, new_str):
    # Step 1: Update the rows containing the search string
    update_query = f"UPDATE {table_name} SET data = ? WHERE data LIKE ?"
    with connection:
        connection.execute(update_query, (new_str, '%' + search_str + '%'))
        updated_count = connection.total_changes

    if updated_count > 0:
        print(f"String '{search_str}' found in the table. Updated {updated_count} row(s) with '{new_str}'.")
        return True
    else:
        print(f"String '{search_str}' not found in the table.")
        return False








def search_substring(cursor, table_name, substring):
    cursor.execute(f"SELECT * FROM {table_name} WHERE data LIKE ?", ('%' + substring + '%',))
    rows = cursor.fetchall()
    if rows:
        print(f"Substring '{substring}' found in the table:")
        result_strings = ""
        for row in rows:
            #result_strings.append(row[1])  # Assuming the string is in the first column of the table
            print(f"prev string is {row[1]}")
        return row[1]
    else:
        print(f"Substring '{substring}' not found in the table.")
        return ""