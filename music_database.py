import sqlite3

def conectar():
    return sqlite3.connect("music.db")

def crear_base():
    db = conectar()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artista TEXT NOT NULL,
            titulo TEXT NOT NULL,
            file_id TEXT,
            duracion INTEGER,
            fecha_agregado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()
    db.close()
