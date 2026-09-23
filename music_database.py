import os
import requests


SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    ""
).strip()

SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    ""
).strip()


def encabezados():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def crear_base():
    # La tabla ya fue creada directamente en Supabase.
    # No hace falta crearla desde el bot.
    pass


def buscar_cancion(artista, titulo):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/canciones"
            f"?artista=eq.{requests.utils.quote(artista)}"
            f"&titulo=eq.{requests.utils.quote(titulo)}"
            f"&select=file_id,duracion"
            f"&order=id.desc"
            f"&limit=1"
        )

        respuesta = requests.get(
            url,
            headers=encabezados(),
            timeout=15
        )

        print(
            "SUPABASE BUSCAR:",
            respuesta.status_code,
            respuesta.text
        )

        if respuesta.status_code != 200:
            return None

        datos = respuesta.json()

        if not datos:
            return None

        return (
            datos[0].get("file_id"),
            datos[0].get("duracion", 0)
        )

    except Exception as e:

        print(
            "ERROR BUSCANDO EN SUPABASE:",
            repr(e)
        )

        return None


def guardar_cancion(
    artista,
    titulo,
    file_id,
    duracion=0
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/canciones"
        )

        datos = {
            "artista": artista,
            "titulo": titulo,
            "file_id": file_id,
            "duracion": duracion or 0
        }

        respuesta = requests.post(
            url,
            headers={
                **encabezados(),
                "Prefer": "return=minimal"
            },
            json=datos,
            timeout=15
        )

        print(
            "SUPABASE GUARDAR:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.status_code in (
            200,
            201
        )

    except Exception as e:

        print(
            "ERROR GUARDANDO EN SUPABASE:",
            repr(e)
        )

        return False
