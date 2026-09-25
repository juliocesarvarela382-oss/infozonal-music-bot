import os
import re
import json
import requests

from flask import Flask, request

from music_database import crear_base
from music_database import guardar_busqueda
from music_database import buscar_ultima_busqueda
from music_database import buscar_archivo_autorizado
from music_database import guardar_archivo_autorizado


app = Flask(__name__)

crear_base()


BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

ADMIN_CHAT_ID = os.environ.get(
    "ADMIN_CHAT_ID",
    ""
).strip()

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    ""
).strip()

SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    ""
).strip()

JAMENDO_CLIENT_ID = os.environ.get(
    "JAMENDO_CLIENT_ID",
    ""
).strip()

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
)

SEARCH_RESULTS = {}

CARGAS = {}


# ============================================================
# TELEGRAM
# ============================================================

def telegram(method, data=None):

    try:

        url = f"{TELEGRAM_API}/{method}"

        respuesta = requests.post(
            url,
            data=data or {},
            timeout=30
        )

        try:
            resultado = respuesta.json()
        except Exception:
            resultado = {
                "ok": False,
                "text": respuesta.text
            }

        print(
            "TELEGRAM:",
            method,
            respuesta.status_code,
            resultado
        )

        return resultado

    except Exception as e:

        print(
            "ERROR TELEGRAM:",
            repr(e)
        )

        return {
            "ok": False,
            "error": str(e)
        }


def send_message(
    chat_id,
    text,
    reply_markup=None
):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:

        data["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )

    return telegram(
        "sendMessage",
        data
    )


def telegram_send_audio_file(
    chat_id,
    audio_bytes,
    filename,
    title,
    performer,
    caption=""
):

    try:

        url = f"{TELEGRAM_API}/sendAudio"

        files = {
            "audio": (
                filename,
                audio_bytes,
                "audio/mpeg"
            )
        }

        data = {
            "chat_id": chat_id,
            "title": title,
            "performer": performer
        }

        if caption:
            data["caption"] = caption

        respuesta = requests.post(
            url,
            data=data,
            files=files,
            timeout=90
        )

        try:
            resultado = respuesta.json()
        except Exception:
            resultado = {
                "ok": False,
                "text": respuesta.text
            }

        print(
            "TELEGRAM UPLOAD AUDIO:",
            respuesta.status_code,
            resultado
        )

        return resultado

    except Exception as e:

        print(
            "ERROR TELEGRAM UPLOAD AUDIO:",
            repr(e)
        )

        return {
            "ok": False,
            "error": str(e)
        }


def answer_callback(callback_id):

    return telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )


# ============================================================
# ADMINISTRADOR
# ============================================================

def es_administrador(chat_id):

    if not ADMIN_CHAT_ID:
        return False

    return str(chat_id) == str(
        ADMIN_CHAT_ID
    )


# ============================================================
# MENU PRINCIPAL
# ============================================================

def main_menu(chat_id):

    teclado = {
        "keyboard": [
            [
                {
                    "text": "🔎 Buscar música"
                }
            ],
            [
                {
                    "text": "🎧 Mis búsquedas"
                },
                {
                    "text": "ℹ️ InfoZonal"
                }
            ],
            [
                {
                    "text": "❓ Ayuda"
                }
            ]
        ],
        "resize_keyboard": True
    }

    if es_administrador(chat_id):

        teclado["keyboard"].append(
            [
                {
                    "text": "📚 Mis canciones autorizadas"
                }
            ]
        )

        teclado["keyboard"].append(
            [
                {
                    "text": "📥 Cargar canción autorizada"
                }
            ]
        )

    send_message(
        chat_id,
        "🎵 InfoZonal Music\n\n"
        "Buscá una canción escribiendo "
        "el artista y el título.\n\n"
        "Ejemplos:\n"
        "Rodrigo Tapari Una cerveza\n"
        "La Konga Universo paralelo\n"
        "Abel Pintos Sin principio ni final",
        teclado
    )


# ============================================================
# NORMALIZACION
# ============================================================

def normalize(text):

    text = str(text or "").lower().strip()

    text = re.sub(
        r"[^\w\sáéíóúüñ]",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def words(text):

    return set(
        normalize(text).split()
    )


# ============================================================
# DETECTAR ARTISTA
# ============================================================

def artist_matches(
    artista,
    artista_objetivo
):

    artista = normalize(artista)

    artista_objetivo = normalize(
        artista_objetivo
    )

    if not artista or not artista_objetivo:
        return False

    if artista == artista_objetivo:
        return True

    if artista_objetivo in artista:
        return True

    if artista in artista_objetivo:
        return True

    palabras_artista = words(
        artista
    )

    palabras_objetivo = words(
        artista_objetivo
    )

    if not palabras_artista or not palabras_objetivo:
        return False

    coincidencias = (
        palabras_artista &
        palabras_objetivo
    )

    return len(coincidencias) >= len(
        palabras_objetivo
    )


# ============================================================
# PUNTUACION
# ============================================================

def score_result(
    item,
    search_text,
    artista_objetivo=None
):

    titulo = item.get(
        "title",
        ""
    )

    artista = item.get(
        "artist",
        ""
    )

    query_words = words(
        search_text
    )

    result_words = words(
        f"{artista} {titulo}"
    )

    if not query_words:
        return 0

    coincidencias = (
        query_words &
        result_words
    )

    score = len(
        coincidencias
    )

    query_normalizada = normalize(
        search_text
    )

    texto_normalizado = normalize(
        f"{artista} {titulo}"
    )

    if query_normalizada == texto_normalizado:
        score += 20

    if query_normalizada in texto_normalizado:
        score += 5

    artista_normalizado = normalize(
        artista
    )

    titulo_normalizado = normalize(
        titulo
    )

    if artista_normalizado:

        if artista_normalizado in query_normalizada:
            score += 10

        if artista_objetivo:

            if artist_matches(
                artista,
                artista_objetivo
            ):
                score += 20
            else:
                score -= 20

    if titulo_normalizado:

        if titulo_normalizado in query_normalizada:
            score += 10

    return score


# ============================================================
# SUPABASE CACHE JAMENDO
# ============================================================

def jamendo_cache_key(
    artist,
    title
):

    return normalize(
        f"{artist} {title}"
    )


def jamendo_cache_get(
    artist,
    title
):

    try:

        if not SUPABASE_URL or not SUPABASE_KEY:
            return None

        clave = jamendo_cache_key(
            artist,
            title
        )

        url = (
            f"{SUPABASE_URL}/rest/v1/song_cache"
        )

        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization":
            f"Bearer {SUPABASE_KEY}"
        }

        respuesta = requests.get(
            url,
            params={
                "select": "query,telegram_file_id",
                "query": f"eq.{clave}",
                "limit": "1"
            },
            headers=headers,
            timeout=15
        )

        if respuesta.status_code == 200:

            filas = respuesta.json()

            if filas:

                file_id = filas[0].get(
                    "telegram_file_id"
                )

                if file_id:

                    print(
                        "CACHE ENCONTRADO EXACTO:",
                        clave
                    )

                    return file_id

        else:

            print(
                "SUPABASE CACHE GET EXACTO:",
                respuesta.status_code,
                respuesta.text
            )

        respuesta = requests.get(
            url,
            params={
                "select": "query,telegram_file_id",
                "limit": "1000"
            },
            headers=headers,
            timeout=15
        )

        if respuesta.status_code != 200:

            print(
                "SUPABASE CACHE GET FLEXIBLE:",
                respuesta.status_code,
                respuesta.text
            )

            return None

        filas = respuesta.json()

        objetivo_artista = normalize(
            artist
        )

        objetivo_titulo = normalize(
            title
        )

        palabras_artista = words(
            artist
        )

        palabras_titulo = words(
            title
        )

        mejor_file_id = None
        mejor_score = -1
        mejor_query = ""

        for fila in filas:

            query_guardada = normalize(
                fila.get(
                    "query",
                    ""
                )
            )

            file_id = fila.get(
                "telegram_file_id"
            )

            if not query_guardada or not file_id:
                continue

            palabras_guardadas = words(
                query_guardada
            )

            if not palabras_guardadas:
                continue

            puntaje = 0

            if query_guardada == clave:
                puntaje += 1000

            if objetivo_titulo:

                if objetivo_titulo in query_guardada:
                    puntaje += 300

                palabras_titulo_coinciden = (
                    palabras_titulo &
                    palabras_guardadas
                )

                if palabras_titulo:

                    porcentaje_titulo = (
                        len(
                            palabras_titulo_coinciden
                        )
                        /
                        len(
                            palabras_titulo
                        )
                    )

                    if porcentaje_titulo == 1:
                        puntaje += 250

                    elif porcentaje_titulo >= 0.5:
                        puntaje += 100

            if objetivo_artista:

                if objetivo_artista in query_guardada:
                    puntaje += 300

                palabras_artista_coinciden = (
                    palabras_artista &
                    palabras_guardadas
                )

                if palabras_artista:

                    porcentaje_artista = (
                        len(
                            palabras_artista_coinciden
                        )
                        /
                        len(
                            palabras_artista
                        )
                    )

                    if porcentaje_artista == 1:
                        puntaje += 250

                    elif porcentaje_artista >= 0.5:
                        puntaje += 100

            objetivo_total = (
                palabras_artista |
                palabras_titulo
            )

            coincidencias_total = (
                objetivo_total &
                palabras_guardadas
            )

            if objetivo_total:

                porcentaje_total = (
                    len(
                        coincidencias_total
                    )
                    /
                    len(
                        objetivo_total
                    )
                )

                if porcentaje_total == 1:
                    puntaje += 200

                elif porcentaje_total >= 0.5:
                    puntaje += 50

            if puntaje > mejor_score:

                mejor_score = puntaje

                mejor_file_id = file_id

                mejor_query = query_guardada

        if mejor_file_id and mejor_score >= 250:

            print(
                "CACHE ENCONTRADO FLEXIBLE:",
                mejor_query,
                "->",
                clave,
                "PUNTAJE:",
                mejor_score
            )

            return mejor_file_id

        print(
            "CACHE NO ENCONTRADO:",
            clave
        )

        return None

    except Exception as e:

        print(
            "ERROR CACHE GET:",
            repr(e)
        )

        return None


def jamendo_cache_save(
    artist,
    title,
    file_id
):

    try:

        if not SUPABASE_URL or not SUPABASE_KEY:
            return False

        clave = jamendo_cache_key(
            artist,
            title
        )

        url = (
            f"{SUPABASE_URL}/rest/v1/song_cache"
        )

        respuesta = requests.post(
            url,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization":
                f"Bearer {SUPABASE_KEY}",
                "Content-Type":
                "application/json",
                "Prefer":
                "resolution=merge-duplicates,return=minimal"
            },
            json={
                "query": clave,
                "telegram_file_id": file_id
            },
            timeout=15
        )

        print(
            "SUPABASE CACHE SAVE:",
            respuesta.status_code,
            respuesta.text
        )

        return respuesta.status_code in (
            200,
            201
        )

    except Exception as e:

        print(
            "ERROR CACHE SAVE:",
            repr(e)
        )

        return False


# ============================================================
# JAMENDO
# ============================================================

def jamendo_search(query):

    if not JAMENDO_CLIENT_ID:
        return []

    try:

        respuesta = requests.get(
            "https://api.jamendo.com/v3.0/tracks/",
            params={
                "client_id": JAMENDO_CLIENT_ID,
                "format": "json",
                "search": query,
                "limit": 20,
                "type": "single albumtrack",
                "order": "relevance",
                "audiodlformat": "mp32"
            },
            timeout=20
        )

        print(
            "JAMENDO:",
            respuesta.status_code
        )

        if respuesta.status_code != 200:

            print(
                "JAMENDO ERROR:",
                respuesta.text
            )

            return []

        datos = respuesta.json()

        resultados = []

        for item in datos.get(
            "results",
            []
        ):

            if not item.get(
                "audiodownload_allowed",
                False
            ):
                continue

            download_url = item.get(
                "audiodownload",
                ""
            )

            if not download_url:
                continue

            resultados.append(
                {
                    "id":
                    item.get(
                        "id"
                    ),

                    "artist":
                    item.get(
                        "artist_name",
                        ""
                    ),

                    "title":
                    item.get(
                        "name",
                        ""
                    ),

                    "duration":
                    item.get(
                        "duration",
                        0
                    ),

                    "download":
                    download_url,

                    "link":
                    item.get(
                        "shareurl",
                        ""
                    ),

                    "source":
                    "jamendo"
                }
            )

        resultados.sort(
            key=lambda item:
            score_result(
                item,
                query
            ),
            reverse=True
        )

        unicos = []

        vistos = set()

        for item in resultados:

            clave = (
                normalize(
                    item.get(
                        "artist",
                        ""
                    )
                ),
                normalize(
                    item.get(
                        "title",
                        ""
                    )
                )
            )

            if clave in vistos:
                continue

            vistos.add(
                clave
            )

            unicos.append(
                item
            )

            if len(unicos) >= 5:
                break

        print(
            "JAMENDO RESULTADOS:",
            len(unicos)
        )

        return unicos

    except Exception as e:

        print(
            "ERROR JAMENDO:",
            repr(e)
        )

        return []


def send_jamendo_song(
    chat_id,
    item
):

    artist = item.get(
        "artist",
        ""
    )

    title = item.get(
        "title",
        ""
    )

    download_url = item.get(
        "download",
        ""
    )

    cached_file_id = jamendo_cache_get(
        artist,
        title
    )

    if cached_file_id:

        resultado = telegram(
            "sendAudio",
            {
                "chat_id": chat_id,
                "audio": cached_file_id,
                "title": title,
                "performer": artist
            }
        )

        if resultado.get(
            "ok"
        ):

            send_message(
                chat_id,
                "📥 Audio completo enviado desde Jamendo."
            )

            return True

    if not download_url:

        send_message(
            chat_id,
            "❌ Esta canción no tiene una descarga autorizada disponible."
        )

        return True

    send_message(
        chat_id,
        "📥 Descargando audio autorizado desde Jamendo..."
    )

    try:

        respuesta = requests.get(
            download_url,
            timeout=90
        )

        if (
            respuesta.status_code != 200
            or not respuesta.content
        ):

            send_message(
                chat_id,
                "❌ Jamendo no pudo entregar el archivo autorizado."
            )

            return True

        resultado = telegram_send_audio_file(
            chat_id,
            respuesta.content,
            "infozonal_music.mp3",
            title,
            artist,
            "Audio completo autorizado por Jamendo"
        )

        if resultado.get(
            "ok"
        ):

            file_id = (
                resultado
                .get(
                    "result",
                    {}
                )
                .get(
                    "audio",
                    {}
                )
                .get(
                    "file_id"
                )
            )

            if file_id:

                jamendo_cache_save(
                    artist,
                    title,
                    file_id
                )

            return True

        send_message(
            chat_id,
            "❌ No pude enviar el audio de Jamendo a Telegram."
        )

        return True

    except Exception as e:

        print(
            "ERROR DESCARGA JAMENDO:",
            repr(e)
        )

        send_message(
            chat_id,
            "❌ Ocurrió un error al descargar el audio autorizado."
        )

        return True


# ============================================================
# BUSQUEDA DE BIBLIOTECA AUTORIZADA
# ============================================================

def buscar_autorizadas_por_consulta(
    query
):

    canciones = listar_canciones_autorizadas()

    if not canciones:

        return []

    query_words = words(
        query
    )

    if not query_words:

        return []

    resultados = []

    for cancion in canciones:

        artista = cancion.get(
            "artista",
            ""
        )

        titulo = cancion.get(
            "titulo",
            ""
        )

        texto = (
            f"{artista} {titulo}"
        )

        palabras_resultado = words(
            texto
        )

        if not query_words.issubset(
            palabras_resultado
        ):

            continue

        item = {
            "id":
            cancion.get(
                "id"
            ),

            "artist":
            artista,

            "title":
            titulo,

            "duration":
            cancion.get(
                "duracion",
                0
            ),

            "source":
            "autorizado"
        }

        item["_score"] = score_result(
            item,
            query
        )

        resultados.append(
            item
        )

    resultados.sort(
        key=lambda item:
        item.get(
            "_score",
            0
        ),
        reverse=True
    )

    for item in resultados:

        item.pop(
            "_score",
            None
        )

    print(
        "BIBLIOTECA AUTORIZADA RESULTADOS:",
        len(resultados)
    )

    return resultados[:5]


# ============================================================
# BUSQUEDA
# ============================================================

def search_music(query):

    # --------------------------------------------------------
    # PRIMERO: BIBLIOTECA AUTORIZADA
    # --------------------------------------------------------

    resultados_autorizados = (
        buscar_autorizadas_por_consulta(
            query
        )
    )

    if resultados_autorizados:

        return resultados_autorizados

    # --------------------------------------------------------
    # SEGUNDO: JAMENDO
    # --------------------------------------------------------

    resultados_jamendo = jamendo_search(
        query
    )

    if resultados_jamendo:

        return resultados_jamendo

    return []


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

def show_results(
    chat_id,
    query,
    resultados
):

    if not resultados:

        send_message(
            chat_id,
            "❌ No encontré canciones con descarga autorizada para esa búsqueda.\n\n"
            "Probá escribiendo artista y título."
        )

        return

    SEARCH_RESULTS[
        chat_id
    ] = resultados

    botones = []

    for index, item in enumerate(
        resultados
    ):

        artista = item.get(
            "artist",
            "Artista"
        )

        titulo = item.get(
            "title",
            "Canción"
        )

        texto = (
            f"🎵 {artista} – {titulo}"
        )

        botones.append(
            [
                {
                    "text":
                    texto[:60],

                    "callback_data":
                    f"song_{index}"
                }
            ]
        )

    send_message(
        chat_id,
        "🎵 Resultados encontrados:\n\n"
        "Elegí una canción:",
        {
            "inline_keyboard":
            botones
        }
    )


# ============================================================
# ENVIAR CANCION
# ============================================================

def send_song(
    chat_id,
    item
):

    if item.get(
        "source"
    ) == "jamendo":

        send_jamendo_song(
            chat_id,
            item
        )

        return

    title = item.get(
        "title",
        ""
    )

    artist = item.get(
        "artist",
        ""
    )

    autorizado = buscar_archivo_autorizado(
        artist,
        title
    )

    if autorizado:

        file_id_autorizado = autorizado.get(
            "file_id"
        )

        if file_id_autorizado:

            resultado = telegram(
                "sendAudio",
                {
                    "chat_id":
                    chat_id,

                    "audio":
                    file_id_autorizado,

                    "title":
                    title,

                    "performer":
                    artist
                }
            )

            if resultado.get(
                "ok"
            ):

                send_message(
                    chat_id,
                    "📥 Audio completo enviado."
                )

                return

    send_message(
        chat_id,
        "❌ Esta canción no está disponible para descarga en este momento."
    )


# ============================================================
# LISTAR CANCIONES AUTORIZADAS
# ============================================================

def listar_canciones_autorizadas():

    try:

        if not SUPABASE_URL or not SUPABASE_KEY:
            return None

        url = (
            f"{SUPABASE_URL}/rest/v1/archivos_autorizados"
            f"?select=id,artista,titulo,duracion"
            f"&order=id.asc"
            f"&limit=1000"
        )

        respuesta = requests.get(
            url,
            headers={
                "apikey":
                SUPABASE_KEY,

                "Authorization":
                f"Bearer {SUPABASE_KEY}",

                "Content-Type":
                "application/json"
            },
            timeout=15
        )

        print(
            "SUPABASE LISTAR AUTORIZADAS:",
            respuesta.status_code,
            respuesta.text
        )

        if respuesta.status_code != 200:
            return None

        return respuesta.json()

    except Exception as e:

        print(
            "ERROR LISTANDO AUTORIZADAS:",
            repr(e)
        )

        return None


def mostrar_canciones_autorizadas(
    chat_id
):

    if not es_administrador(
        chat_id
    ):

        send_message(
            chat_id,
            "❌ Esta función es solamente para el administrador."
        )

        return

    canciones = listar_canciones_autorizadas()

    if canciones is None:

        send_message(
            chat_id,
            "❌ No pude consultar la biblioteca autorizada."
        )

        return

    if not canciones:

        send_message(
            chat_id,
            "📚 Biblioteca autorizada\n\n"
            "Todavía no hay canciones cargadas."
        )

        return

    lineas = [
        "📚 BIBLIOTECA AUTORIZADA",
        "",
        f"🎵 Canciones cargadas: {len(canciones)}",
        ""
    ]

    for indice, cancion in enumerate(
        canciones,
        start=1
    ):

        artista = cancion.get(
            "artista",
            "Sin artista"
        )

        titulo = cancion.get(
            "titulo",
            "Sin título"
        )

        lineas.append(
            f"{indice}. 🎤 {artista} – {titulo}"
        )

    texto = "\n".join(
        lineas
    )

    if len(texto) > 4000:

        partes = []

        actual = ""

        for linea in lineas:

            if len(
                actual
            ) + len(
                linea
            ) + 1 > 3800:

                if actual:
                    partes.append(
                        actual
                    )

                actual = linea

            else:

                if actual:
                    actual += "\n"

                actual += linea

        if actual:
            partes.append(
                actual
            )

        for parte in partes:

            send_message(
                chat_id,
                parte
            )

    else:

        send_message(
            chat_id,
            texto
        )


# ============================================================
# CARGA DE ARCHIVOS AUTORIZADOS
# ============================================================

def iniciar_carga(
    chat_id
):

    if not es_administrador(
        chat_id
    ):

        send_message(
            chat_id,
            "❌ Esta función es solamente para el administrador."
        )

        return

    CARGAS[
        chat_id
    ] = {
        "paso":
        "artista"
    }

    send_message(
        chat_id,
        "📥 Cargar archivo autorizado\n\n"
        "Escribí el nombre del artista."
    )


def procesar_carga_texto(
    chat_id,
    text
):

    estado = CARGAS.get(
        chat_id
    )

    if not estado:
        return False

    if not es_administrador(
        chat_id
    ):

        CARGAS.pop(
            chat_id,
            None
        )

        return False

    paso = estado.get(
        "paso"
    )

    if paso == "artista":

        estado[
            "artista"
        ] = text.strip()

        estado[
            "paso"
        ] = "titulo"

        send_message(
            chat_id,
            "🎵 Ahora escribí el título de la canción."
        )

        return True

    if paso == "titulo":

        estado[
            "titulo"
        ] = text.strip()

        estado[
            "paso"
        ] = "archivo"

        send_message(
            chat_id,
            "📁 Ahora enviame el archivo de audio completo.\n\n"
            "Debe ser un archivo que tengas autorización para distribuir."
        )

        return True

    return False


def procesar_archivo_audio(
    chat_id,
    message
):

    estado = CARGAS.get(
        chat_id
    )

    if not estado:
        return False

    if not es_administrador(
        chat_id
    ):

        CARGAS.pop(
            chat_id,
            None
        )

        return False

    audio = message.get(
        "audio"
    )

    document = message.get(
        "document"
    )

    if audio:

        file_id = audio.get(
            "file_id"
        )

        duration = audio.get(
            "duration",
            0
        )

    elif document:

        mime_type = document.get(
            "mime_type",
            ""
        )

        if not mime_type.startswith(
            "audio/"
        ):

            send_message(
                chat_id,
                "❌ Ese archivo no parece ser un audio.\n\n"
                "Enviame un archivo de audio."
            )

            return True

        file_id = document.get(
            "file_id"
        )

        duration = 0

    else:

        return False

    if not file_id:

        send_message(
            chat_id,
            "❌ Telegram no entregó el identificador del archivo."
        )

        return True

    artista = estado.get(
        "artista",
        ""
    )

    titulo = estado.get(
        "titulo",
        ""
    )

    if not artista or not titulo:

        send_message(
            chat_id,
            "❌ Faltan datos del archivo."
        )

        CARGAS.pop(
            chat_id,
            None
        )

        return True

    archivo_url = (
        f"telegram://{file_id}"
    )

    guardado = guardar_archivo_autorizado(
        artista,
        titulo,
        archivo_url,
        file_id,
        duration
    )

    print(
        "ARCHIVO AUTORIZADO GUARDADO:",
        guardado,
        artista,
        "-",
        titulo
    )

    CARGAS.pop(
        chat_id,
        None
    )

    if guardado:

        send_message(
            chat_id,
            "✅ Archivo autorizado guardado correctamente.\n\n"
            f"🎤 Artista: {artista}\n"
            f"🎵 Título: {titulo}\n\n"
            "Ahora el bot podrá entregar este audio completo "
            "cuando alguien busque esa canción."
        )

    else:

        send_message(
            chat_id,
            "❌ No pude guardar el archivo en Supabase."
        )

    return True


# ============================================================
# PAGINA PRINCIPAL
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "InfoZonal Music Bot OK"


# ============================================================
# WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    try:

        update = request.get_json(
            silent=True
        )

        print(
            "UPDATE RECIBIDO:",
            update
        )

        if not update:
            return "OK", 200

        # ----------------------------------------------------
        # MENSAJES
        # ----------------------------------------------------

        message = update.get(
            "message"
        )

        if message:

            chat = message.get(
                "chat",
                {}
            )

            chat_id = chat.get(
                "id"
            )

            text = message.get(
                "text",
                ""
            ).strip()

            if not chat_id:
                return "OK", 200

            if procesar_archivo_audio(
                chat_id,
                message
            ):

                return "OK", 200

            if text == "/start":

                main_menu(
                    chat_id
                )

                return "OK", 200

            if text == "/miid":

                send_message(
                    chat_id,
                    f"🆔 Tu Chat ID es:\n\n{chat_id}"
                )

                return "OK", 200

            if text == "/cargar":

                iniciar_carga(
                    chat_id
                )

                return "OK", 200

            if text == "/cancelar":

                CARGAS.pop(
                    chat_id,
                    None
                )

                send_message(
                    chat_id,
                    "❌ Operación cancelada."
                )

                main_menu(
                    chat_id
                )

                return "OK", 200

            if text == "📚 Mis canciones autorizadas":

                mostrar_canciones_autorizadas(
                    chat_id
                )

                return "OK", 200

            if text == "📥 Cargar canción autorizada":

                iniciar_carga(
                    chat_id
                )

                return "OK", 200

            if procesar_carga_texto(
                chat_id,
                text
            ):

                return "OK", 200

            if text == "🔎 Buscar música":

                send_message(
                    chat_id,
                    "🔎 Escribí el artista y el título de la canción.\n\n"
                    "Ejemplo:\n"
                    "Rodrigo Tapari Una cerveza"
                )

                return "OK", 200

            if text == "🎧 Mis búsquedas":

                ultima = buscar_ultima_busqueda(
                    chat_id
                )

                if not ultima:

                    send_message(
                        chat_id,
                        "🎧 Todavía no tenés búsquedas guardadas."
                    )

                    return "OK", 200

                send_message(
                    chat_id,
                    "🎧 Última búsqueda:\n\n"
                    f"{ultima}\n\n"
                    "🔎 Buscando nuevamente..."
                )

                resultados = search_music(
                    ultima
                )

                show_results(
                    chat_id,
                    ultima,
                    resultados
                )

                return "OK", 200

            if text == "ℹ️ InfoZonal":

                send_message(
                    chat_id,
                    "🎵 InfoZonal Music\n\n"
                    "Bot de búsqueda musical de InfoZonal.\n\n"
                    "Las búsquedas priorizan primero la biblioteca "
                    "autorizada de InfoZonal y luego música descargable "
                    "desde Jamendo cuando el artista permite la descarga.\n\n"
                    "Si ninguna de las dos fuentes tiene una descarga "
                    "autorizada disponible, la canción no estará disponible."
                )

                return "OK", 200

            if text == "❓ Ayuda":

                send_message(
                    chat_id,
                    "❓ AYUDA\n\n"
                    "Escribí artista y título para buscar una canción.\n\n"
                    "Ejemplo:\n"
                    "Abel Pintos Sin principio ni final\n\n"
                    "El bot muestra hasta 5 resultados.\n\n"
                    "Primero busca en la biblioteca autorizada de InfoZonal.\n"
                    "Si no encuentra coincidencias, busca en Jamendo.\n\n"
                    "Las descargas automáticas se realizan únicamente "
                    "cuando existe autorización para entregar el audio."
                )

                return "OK", 200

            if text:

                guardar_busqueda(
                    chat_id,
                    text
                )

                resultados = search_music(
                    text
                )

                show_results(
                    chat_id,
                    text,
                    resultados
                )

                return "OK", 200

        # ----------------------------------------------------
        # CALLBACKS
        # ----------------------------------------------------

        callback = update.get(
            "callback_query"
        )

        if callback:

            callback_id = callback.get(
                "id"
            )

            from_chat = callback.get(
                "message",
                {}
            ).get(
                "chat",
                {}
            )

            chat_id = from_chat.get(
                "id"
            )

            data = callback.get(
                "data",
                ""
            )

            if callback_id:

                answer_callback(
                    callback_id
                )

            if data.startswith(
                "song_"
            ):

                try:

                    index = int(
                        data.split(
                            "_",
                            1
                        )[1]
                    )

                except Exception:

                    return "OK", 200

                resultados = SEARCH_RESULTS.get(
                    chat_id,
                    []
                )

                if (
                    index < 0
                    or index >= len(
                        resultados
                    )
                ):

                    send_message(
                        chat_id,
                        "❌ Ese resultado ya no está disponible."
                    )

                    return "OK", 200

                item = resultados[
                    index
                ]

                send_song(
                    chat_id,
                    item
                )

                return "OK", 200

        return "OK", 200

    except Exception as e:

        print(
            "ERROR WEBHOOK:",
            repr(e)
        )

        return "OK", 200
