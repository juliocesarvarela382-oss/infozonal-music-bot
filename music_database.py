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
    # Las tablas ya fueron creadas directamente en Supabase.
    pass


# ============================================================
# CANCIONES / CACHE DE TELEGRAM
# ============================================================

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
            "ERROR GUARDANDO CANCION:",
            repr(e)
        )

        return False


# ============================================================
# BUSQUEDAS
# ============================================================

def guardar_busqueda(
    chat_id,
    busqueda
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/busquedas"
        )

        datos = {
            "chat_id": str(chat_id),
            "busqueda": busqueda
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
            "SUPABASE GUARDAR BUSQUEDA:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.status_code in (
            200,
            201
        )

    except Exception as e:

        print(
            "ERROR GUARDANDO BUSQUEDA:",
            repr(e)
        )

        return False


def buscar_ultima_busqueda(
    chat_id
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/busquedas"
            f"?chat_id=eq.{requests.utils.quote(str(chat_id))}"
            f"&select=busqueda,fecha"
            f"&order=id.desc"
            f"&limit=1"
        )

        respuesta = requests.get(
            url,
            headers=encabezados(),
            timeout=15
        )

        print(
            "SUPABASE ULTIMA BUSQUEDA:",
            respuesta.status_code,
            respuesta.text
        )

        if respuesta.status_code != 200:
            return None

        datos = respuesta.json()

        if not datos:
            return None

        return datos[0].get(
            "busqueda"
        )

    except Exception as e:

        print(
            "ERROR BUSCANDO ULTIMA BUSQUEDA:",
            repr(e)
        )

        return None


# ============================================================
# ARCHIVOS AUTORIZADOS
# ============================================================

def buscar_archivo_autorizado(
    artista,
    titulo
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/archivos_autorizados"
            f"?artista=eq.{requests.utils.quote(artista)}"
            f"&titulo=eq.{requests.utils.quote(titulo)}"
            f"&select=id,artista,titulo,archivo_url,file_id,duracion"
            f"&order=id.desc"
            f"&limit=1"
        )

        respuesta = requests.get(
            url,
            headers=encabezados(),
            timeout=15
        )

        print(
            "SUPABASE BUSCAR ARCHIVO AUTORIZADO:",
            respuesta.status_code,
            respuesta.text
        )

        if respuesta.status_code != 200:
            return None

        datos = respuesta.json()

        if not datos:
            return None

        return datos[0]

    except Exception as e:

        print(
            "ERROR BUSCANDO ARCHIVO AUTORIZADO:",
            repr(e)
        )

        return None


def guardar_archivo_autorizado(
    artista,
    titulo,
    archivo_url,
    file_id=None,
    duracion=0
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/archivos_autorizados"
        )

        datos = {
            "artista": artista,
            "titulo": titulo,
            "archivo_url": archivo_url,
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
            "SUPABASE GUARDAR ARCHIVO AUTORIZADO:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.status_code in (
            200,
            201
        )

    except Exception as e:

        print(
            "ERROR GUARDANDO ARCHIVO AUTORIZADO:",
            repr(e)
        )

        return False


def actualizar_file_id_autorizado(
    registro_id,
    file_id,
    duracion=0
):

    try:

        url = (
            f"{SUPABASE_URL}/rest/v1/archivos_autorizados"
            f"?id=eq.{registro_id}"
        )

        datos = {
            "file_id": file_id,
            "duracion": duracion or 0
        }

        respuesta = requests.patch(
            url,
            headers={
                **encabezados(),
                "Prefer": "return=minimal"
            },
            json=datos,
            timeout=15
        )

        print(
            "SUPABASE ACTUALIZAR FILE_ID AUTORIZADO:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.status_code in (
            200,
            204
        )

    except Exception as e:

        print(
            "ERROR ACTUALIZANDO FILE_ID AUTORIZADO:",
            repr(e)
        )

        return False
