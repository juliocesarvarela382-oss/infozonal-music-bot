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

def buscar_cancion(artista, titulo):
    db = conectar()
    cursor = db.cursor()

    cursor.execute("""
        SELECT file_id, duracion
        FROM canciones
        WHERE artista = ? AND titulo = ?
        ORDER BY id DESC
        LIMIT 1
    """, (artista, titulo))

    resultado = cursor.fetchone()

    db.close()

    return resultado
