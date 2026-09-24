import os
import re
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
# NORMALIZACION
# ============================================================

def normalizar_texto(texto):

    texto = str(texto or "").lower().strip()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n"
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    texto = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def coincide_texto_autorizado(
    valor_guardado,
    valor_buscado
):

    guardado = normalizar_texto(
        valor_guardado
    )

    buscado = normalizar_texto(
        valor_buscado
    )

    if not guardado or not buscado:
        return False

    if guardado == buscado:
        return True

    if guardado in buscado:
        return True

    if buscado in guardado:
        return True

    palabras_guardado = set(
        guardado.split()
    )

    palabras_buscado = set(
        buscado.split()
    )

    if not palabras_guardado or not palabras_buscado:
        return False

    coincidencias = (
        palabras_guardado &
        palabras_buscado
    )

    return len(coincidencias) >= min(
        2,
        len(palabras_guardado),
        len(palabras_buscado)
    )


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

        # Primero buscamos coincidencia exacta.
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
            "SUPABASE BUSCAR ARCHIVO AUTORIZADO EXACTO:",
            respuesta.status_code,
            respuesta.text
        )

        if respuesta.status_code != 200:
            return None

        datos = respuesta.json()

        if datos:
            return datos[0]

        # Si no hay coincidencia exacta,
        # buscamos coincidencias flexibles.
        url_todos = (
            f"{SUPABASE_URL}/rest/v1/archivos_autorizados"
            f"?select=id,artista,titulo,archivo_url,file_id,duracion"
            f"&order=id.desc"
            f"&limit=1000"
        )

        respuesta_todos = requests.get(
            url_todos,
            headers=encabezados(),
            timeout=15
        )

        print(
            "SUPABASE BUSCAR ARCHIVO AUTORIZADO FLEXIBLE:",
            respuesta_todos.status_code,
            respuesta_todos.text
        )

        if respuesta_todos.status_code != 200:
            return None

        registros = respuesta_todos.json()

        mejor = None
        mejor_puntaje = -1

        artista_buscado = normalizar_texto(
            artista
        )

        titulo_buscado = normalizar_texto(
            titulo
        )

        for registro in registros:

            artista_guardado = registro.get(
                "artista",
                ""
            )

            titulo_guardado = registro.get(
                "titulo",
                ""
            )

            artista_guardado_norm = normalizar_texto(
                artista_guardado
            )

            titulo_guardado_norm = normalizar_texto(
                titulo_guardado
            )

            puntaje = 0

            if coincide_texto_autorizado(
                artista_guardado,
                artista
            ):
                puntaje += 100

            if coincide_texto_autorizado(
                titulo_guardado,
                titulo
            ):
                puntaje += 100

            if (
                artista_guardado_norm ==
                artista_buscado
            ):
                puntaje += 50

            if (
                titulo_guardado_norm ==
                titulo_buscado
            ):
                puntaje += 50

            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor = registro

        if mejor and mejor_puntaje >= 200:

            print(
                "ARCHIVO AUTORIZADO ENCONTRADO FLEXIBLE:",
                mejor
            )

            return mejor

        return None

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
