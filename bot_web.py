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


app = Flask(__name__)

crear_base()

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
)

SEARCH_RESULTS = {}


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

        # Máximo 5 resultados
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

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    try:

        update = request.get_json(
            silent=True
        ) or {}

        print(
            "UPDATE RECIBIDO:",
            update
        )

        # =================================================
        # CALLBACK
        # =================================================

        if "callback_query" in update:

            callback = update[
                "callback_query"
            ]

            callback_id = callback.get(
                "id"
            )

            data = callback.get(
                "data",
                ""
            )

            message = callback.get(
                "message",
                {}
            )

            chat = message.get(
                "chat",
                {}
            )

            chat_id = chat.get(
                "id"
            )

            answer_callback(
                callback_id
            )

            if data.startswith(
                "song_"
            ):

                try:

                    index = int(
                        data.split(
                            "_"
                        )[1]
                    )

                    resultados = SEARCH_RESULTS.get(
                        chat_id,
                        []
                    )

                    if (
                        0 <= index <
                        len(resultados)
                    ):

                        item = resultados[
                            index
                        ]

                        send_song(
                            chat_id,
                            item
                        )

                except Exception as e:

                    print(
                        "ERROR CALLBACK SONG:",
                        repr(e)
                    )

                return "OK", 200

            if data == "new_search":

                send_message(
                    chat_id,
                    "🔎 Escribí el artista y el título de la canción."
                )

                return "OK", 200

            return "OK", 200

        # =================================================
        # MENSAJE
        # =================================================

        message = update.get(
            "message"
        )

        if not message:

            return "OK", 200

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

        # =================================================
        # START
        # =================================================

        if text == "/start":

            main_menu(
                chat_id
            )

            return "OK", 200

        # =================================================
        # BUSCAR MUSICA
        # =================================================

        if text == "🔎 Buscar música":

            send_message(
                chat_id,
                "🔎 Escribí el artista y el título de la canción.\n\n"
                "Ejemplo:\n"
                "Rodrigo Tapari Una cerveza"
            )

            return "OK", 200

        # =================================================
        # MIS BUSQUEDAS
        # =================================================

        if text == "🎧 Mis búsquedas":

            ultima = buscar_ultima_busqueda(
                chat_id
            )

            if ultima:

                send_message(
                    chat_id,
                    f"🎧 Última búsqueda:\n\n{ultima}"
                )

                resultados = search_music(
                    ultima
                )

                show_results(
                    chat_id,
                    ultima,
                    resultados
                )

            else:

                send_message(
                    chat_id,
                    "🎧 Todavía no tenés búsquedas."
                )

            return "OK", 200

        # =================================================
        # INFOZONAL
        # =================================================

        if text == "ℹ️ InfoZonal":

            send_message(
                chat_id,
                "📰 InfoZonal\n\n"
                "Noticias de San Andrés de Giles y zona."
            )

            return "OK", 200

        # =================================================
        # AYUDA
        # =================================================

        if text == "❓ Ayuda":

            send_message(
                chat_id,
                "❓ Ayuda\n\n"
                "Escribí el nombre del artista "
                "y la canción que querés buscar.\n\n"
                "Ejemplo:\n"
                "Rodrigo Tapari Una cerveza"
            )

            return "OK", 200

        # =================================================
        # BUSQUEDA NORMAL
        # =================================================

        if text:

            # Guardar búsqueda en Supabase
            guardada = gua
