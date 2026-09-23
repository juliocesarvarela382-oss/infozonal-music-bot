import os
import re
import json
import requests

from flask import Flask, request

from music_database import crear_base
from music_database import buscar_cancion
from music_database import guardar_cancion
from music_database import guardar_busqueda
from music_database import buscar_ultima_busqueda
from music_database import buscar_archivo_autorizado
from music_database import guardar_archivo_autorizado
from music_database import actualizar_file_id_autorizado


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

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
)

SEARCH_RESULTS = {}

CARGAS = {}


# =========================================================
# TELEGRAM
# =========================================================

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


def answer_callback(callback_id):

    return telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )


# =========================================================
# MENU PRINCIPAL
# =========================================================

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


# =========================================================
# NORMALIZACION
# =========================================================

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


# =========================================================
# DETECTAR ARTISTA
# =========================================================

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


# =========================================================
# PUNTUACION
# =========================================================

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


# =========================================================
# DEEZER
# =========================================================

def deezer_search(query):

    try:

        respuesta = requests.get(
            "https://api.deezer.com/search",
            params={
                "q": query,
                "limit": 25
            },
            timeout=20
        )

        print(
            "DEEZER:",
            respuesta.status_code
        )

        if respuesta.status_code != 200:
            return []

        datos = respuesta.json()

        resultados = []

        for item in datos.get(
            "data",
            []
        ):

            artista = item.get(
                "artist",
                {}
            ).get(
                "name",
                ""
            )

            titulo = item.get(
                "title",
                ""
            )

            preview = item.get(
                "preview",
                ""
            )

            link = item.get(
                "link",
                ""
            )

            duration = item.get(
                "duration",
                0
            )

            track_id = item.get(
                "id"
            )

            resultados.append(
                {
                    "id": track_id,
                    "artist": artista,
                    "title": titulo,
                    "preview": preview,
                    "link": link,
                    "duration": duration
                }
            )

        return resultados

    except Exception as e:

        print(
            "ERROR DEEZER:",
            repr(e)
        )

        return []


# =========================================================
# BUSQUEDA
# =========================================================

def search_music(query):

    resultados = deezer_search(
        query
    )

    if not resultados:
        return []

    resultados_iniciales = sorted(
        resultados,
        key=lambda item:
        score_result(
            item,
            query
        ),
        reverse=True
    )

    artista_objetivo = ""

    if resultados_iniciales:

        artista_objetivo = resultados_iniciales[0].get(
            "artist",
            ""
        )

    print(
        "ARTISTA DETECTADO:",
        artista_objetivo
    )

    resultados.sort(
        key=lambda item:
        score_result(
            item,
            query,
            artista_objetivo
        ),
        reverse=True
    )

    filtrados = []

    for item in resultados:

        artista = item.get(
            "artist",
            ""
        )

        if artist_matches(
            artista,
            artista_objetivo
        ):

            filtrados.append(
                item
            )

    if len(filtrados) < 1:

        filtrados = resultados

    unicas = []

    vistas = set()

    for item in filtrados:

        artista = normalize(
            item.get(
                "artist",
                ""
            )
        )

        titulo = normalize(
            item.get(
                "title",
                ""
            )
        )

        clave = (
            artista,
            titulo
        )

        if clave in vistas:
            continue

        vistas.add(
            clave
        )

        unicas.append(
            item
        )

        if len(unicas) >= 5:
            break

    print(
        "RESULTADOS FINALES:",
        len(unicas)
    )

    for numero, item in enumerate(
        unicas,
        start=1
    ):

        print(
            numero,
            "-",
            item.get("artist"),
            "-",
            item.get("title")
        )

    return unicas


# =========================================================
# MOSTRAR RESULTADOS
# =========================================================

def show_results(
    chat_id,
    query,
    resultados
):

    if not resultados:

        send_message(
            chat_id,
            "❌ No encontré canciones con esa búsqueda.\n\n"
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
                    "text": texto[:60],
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
            "inline_keyboard": botones
        }
    )


# =========================================================
# ENVIAR CANCION
# =========================================================

def send_song(
    chat_id,
    item
):

    title = item.get(
        "title",
        ""
    )

    artist = item.get(
        "artist",
        ""
    )

    preview = item.get(
        "preview",
        ""
    )

    duration = item.get(
        "duration",
        0
    )

    # Primero buscamos un archivo autorizado completo
    autorizado = buscar_archivo_autorizado(
        artist,
        title
    )

    if autorizado:

        file_id_autorizado = autorizado.get(
            "file_id"
        )

        if file_id_autorizado:

            print(
                "ARCHIVO AUTORIZADO ENCONTRADO:",
                artist,
                "-",
                title
            )

            resultado = telegram(
                "sendAudio",
                {
                    "chat_id": chat_id,
                    "audio": file_id_autorizado,
                    "title": title,
                    "performer": artist
                }
            )

            print(
                "AUDIO AUTORIZADO RESULT:",
                resultado
            )

            if resultado.get("ok"):

                send_message(
                    chat_id,
                    "📥 Audio completo enviado."
                )

                return

    # Después buscamos el cache normal del preview
    guardada = buscar_cancion(
        artist,
        title
    )

    if guardada:

        file_id, duracion_guardada = guardada

        if file_id:

            print(
                "FILE_ID ENCONTRADO:",
                artist,
                "-",
                title
            )

            resultado = telegram(
                "sendAudio",
                {
                    "chat_id": chat_id,
                    "audio": file_id,
                    "title": title,
                    "performer": artist
                }
            )

            print(
                "AUDIO CACHE RESULT:",
                resultado
            )

            if resultado.get("ok"):

                link = item.get(
                    "link",
                    ""
                )

                if link:

                    send_message(
                        chat_id,
                        "🎵 Escuchá la canción completa:",
                        {
                            "inline_keyboard": [
                                [
                                    {
                                        "text":
                                        "🔗 Escuchar canción completa",
                                        "url": link
                                    }
                                ]
                            ]
                        }
                    )

                return

    if not preview:

        send_message(
            chat_id,
            "Encontré la canción, pero no hay preview disponible."
        )

        return

    send_message(
        chat_id,
        "🎵 Buscando preview de audio..."
    )

    resultado = telegram(
        "sendAudio",
        {
            "chat_id": chat_id,
            "audio": preview,
            "title": title,
            "performer": artist,
            "caption": "Preview de 30 segundos"
        }
    )

    print(
        "AUDIO RESULT:",
        resultado
    )

    if resultado.get("ok"):

        try:

            file_id = (
                resultado
                .get("result", {})
                .get("audio", {})
                .get("file_id")
            )

            if file_id:

                guardado = guardar_cancion(
                    artist,
                    title,
                    file_id,
                    duration
                )

                print(
                    "FILE_ID GUARDADO EN SUPABASE:",
                    artist,
                    "-",
                    title,
                    guardado
                )

        except Exception as e:

            print(
                "ERROR GUARDANDO FILE_ID:",
                repr(e)
            )

    link = item.get(
        "link",
        ""
    )

    if link:

        send_message(
            chat_id,
            "🎵 Escuchá la canción completa:",
            {
                "inline_keyboard": [
                    [
                        {
                            "text":
                            "🔗 Escuchar canción completa",
                            "url": link
                        }
                    ]
                ]
            }
        )

    if not resultado.get("ok"):

        send_message(
            chat_id,
            "❌ No pude enviar el preview de audio."
        )


# =========================================================
# CARGA DE ARCHIVOS AUTORIZADOS
# =========================================================

def es_administrador(chat_id):

    if not ADMIN_CHAT_ID:
        return False

    return str(chat_id) == str(
        ADMIN_CHAT_ID
    )


def iniciar_carga(chat_id):

    if not es_administrador(chat_id):

        send_message(
            chat_id,
            "❌ Esta función es solamente para el administrador."
        )

        return

    CARGAS[
        chat_id
    ] = {
        "paso": "artista"
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

    if not es_administrador(chat_id):

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

    if not es_administrador(chat_id):

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


# =========================================================
# PAGINA PRINCIPAL
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "InfoZonal Music Bot OK"


# =========================================================
# WEBHOOK
# =========================================================
