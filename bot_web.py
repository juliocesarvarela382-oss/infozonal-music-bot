import os
import re
import json
import requests
from flask import Flask, request

from music_database import conectar
from music_database import crear_base
from music_database import buscar_cancion


app = Flask(__name__)

crear_base()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


SEARCH_RESULTS = {}
USER_SEARCHES = {}


# =========================
# TELEGRAM
# =========================

def telegram(method, data=None):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            data=data or {},
            timeout=30
        )

        print(
            "TELEGRAM:",
            method,
            response.status_code,
            response.text[:500]
        )

        try:
            return response.json()
        except Exception:
            return {
                "ok": False,
                "description": response.text
            }

    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))

        return {
            "ok": False,
            "description": str(e)
        }


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    return telegram("sendMessage", data)


def answer_callback(callback_id):
    return telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )


# =========================
# MENÚ PRINCIPAL
# =========================

def main_menu():
    return {
        "keyboard": [
            [
                {
                    "text": "🔎 Buscar música"
                }
            ],
            [
                {
                    "text": "🎧 Mis búsquedas"
                }
            ],
            [
                {
                    "text": "ℹ️ InfoZonal"
                },
                {
                    "text": "❓ Ayuda"
                }
            ]
        ],
        "resize_keyboard": True
    }


# =========================
# NORMALIZACIÓN
# =========================

def normalize(text):
    text = text.lower().strip()

    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def words(text):
    return normalize(text).split()


# =========================
# PUNTUACIÓN DE RESULTADOS
# =========================

def score_result(query, artist, title):
    q = normalize(query)
    a = normalize(artist)
    t = normalize(title)

    score = 0

    if q == f"{a} {t}":
        score += 100

    q_words = set(words(q))
    a_words = set(words(a))
    t_words = set(words(t))

    if a_words and a_words.issubset(q_words):
        score += 40

    if t_words and t_words.issubset(q_words):
        score += 40

    for word in q_words:
        if word in a_words:
            score += 8

        if word in t_words:
            score += 8

    return score


# =========================
# DEEZER
# =========================

def deezer_search(query):
    try:
        response = requests.get(
            "https://api.deezer.com/search",
            params={
                "q": query,
                "limit": 50
            },
            timeout=20
        )

        if response.status_code != 200:
            print(
                "DEEZER ERROR:",
                response.status_code,
                response.text[:500]
            )

            return []

        data = response.json()

        results = []

        for song in data.get("data", []):
            artist_data = song.get("artist") or {}

            artist = artist_data.get("name", "")
            title = song.get("title", "")
            preview = song.get("preview", "")
            link = song.get("link", "")

            result = {
                "id": song.get("id"),
                "artist": artist,
                "title": title,
                "preview": preview,
                "link": link,
                "duration": song.get("duration", 0),
                "score": score_result(
                    query,
                    artist,
                    title
                )
            }

            results.append(result)

        return results

    except Exception as e:
        print("DEEZER EXCEPTION:", repr(e))

        return []


# =========================
# BÚSQUEDA INTELIGENTE
# =========================

def search_music(query):
    query = query.strip()

    if not query:
        return []

    results = []

    # Búsqueda completa
    results.extend(
        deezer_search(query)
    )

    query_words = words(query)

    # Intentar detectar artista + título
    if len(query_words) >= 2:

        for split in range(1, len(query_words)):

            artist_part = " ".join(
                query_words[:split]
            )

            title_part = " ".join(
                query_words[split:]
            )

            if not artist_part or not title_part:
                continue

            combined_queries = [
                f'artist:"{artist_part}" track:"{title_part}"',
                f'"{artist_part}" "{title_part}"',
                f"{artist_part} {title_part}"
            ]

            for search_query in combined_queries:

                extra_results = deezer_search(
                    search_query
                )

                results.extend(
                    extra_results
                )

    # Eliminar duplicados
    unique = {}

    for item in results:

        song_id = item.get("id")

        if not song_id:
            continue

        if song_id not in unique:
            unique[song_id] = item

        else:

            if item.get("score", 0) > unique[song_id].get("score", 0):
                unique[song_id] = item

    results = list(unique.values())

    # Ordenar por puntuación
    results.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    return results[:8]


# =========================
# MOSTRAR RESULTADOS
# =========================

def show_results(chat_id, query):

    send_message(
        chat_id,
        "🔎 Buscando música...\n\n"
        f"Consulta: {query}"
    )

    results = search_music(query)

    if not results:

        send_message(
            chat_id,
            "❌ No encontré resultados.\n\n"
            "Probá escribiendo nuevamente "
            "el artista y el título."
        )

        return

    SEARCH_RESULTS[chat_id] = results

    # Guardar búsqueda
    if chat_id not in USER_SEARCHES:
        USER_SEARCHES[chat_id] = []

    if query not in USER_SEARCHES[chat_id]:
        USER_SEARCHES[chat_id].append(query)

    # Limitar historial
    USER_SEARCHES[chat_id] = USER_SEARCHES[chat_id][-10:]

    buttons = []

    for index, item in enumerate(results):

        artist = item.get("artist", "")
        title = item.get("title", "")

        button_text = f"{artist} – {title}"

        if len(button_text) > 60:
            button_text = button_text[:57] + "..."

        buttons.append(
            [
                {
                    "text": button_text,
                    "callback_data": f"song_{index}"
                }
            ]
        )

    buttons.append(
        [
            {
                "text": "🔎 Nueva búsqueda",
                "callback_data": "new_search"
            }
        ]
    )

    send_message(
        chat_id,
        "🎵 Encontré estos resultados:\n\n"
        "Elegí una canción:",
        {
            "inline_keyboard": buttons
        }
    )


# =========================
# ENVIAR CANCIÓN / PREVIEW
# =========================

def send_song(chat_id, item):

    title = item.get("title", "")
    artist = item.get("artist", "")
    preview = item.get("preview", "")

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

    result = telegram(
        "sendAudio",
        {
            "chat_id": chat_id,
            "audio": preview,
            "title": title,
            "performer": artist,
            "caption": "Preview de 30 segundos"
        }
    )

    print("AUDIO RESULT:", result)

    # Guardar file_id en SQLite
    if result.get("ok"):

        try:

            file_id = result["result"]["audio"]["file_id"]

            db = conectar()
            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO canciones
                (artista, titulo, file_id, duracion)
                VALUES (?, ?, ?, ?)
                """,
                (
                    artist,
                    title,
                    file_id,
                    item.get("duration", 0)
                )
            )

            db.commit()
            db.close()

            print(
                "FILE_ID GUARDADO:",
                artist,
                "-",
                title
            )

        except Exception as e:

            print(
                "ERROR GUARDANDO FILE_ID:",
                repr(e)
            )

    # Botón para escuchar la canción completa
    # directamente en Deezer
    link = item.get("link", "")

    if link:

        send_message(
            chat_id,
            "🎵 Escuchá la canción completa:",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔗 Escuchar canción completa",
                            "url": link
                        }
                    ]
                ]
            }
        )

    if not result.get("ok"):

        send_message(
            chat_id,
            "❌ No pude enviar el preview de audio."
        )


# =========================
# PÁGINA PRINCIPAL
# =========================

@app.route("/", methods=["GET"])
def home():

    return "InfoZonal Music Bot OK"


# =========================
# WEBHOOK TELEGRAM
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    try:

        update = request.get_json(
            silent=True
        ) or {}

        print(
            "UPDATE RECIBIDO:",
            update
        )

        # =====================
        # MENSAJES NORMALES
        # =====================

        message = update.get("message")

        if message:

            chat = message.get("chat") or {}
            chat_id = chat.get("id")

            text = message.get("text", "")

            if not chat_id:
                return "OK"

            text = text.strip()

            # /start
            if text == "/start":

                send_message(
                    chat_id,
                    "🎵 InfoZonal Music\n\n"
                    "Buscá una canción escribiendo "
                    "el artista y el título.\n\n"
                    "Ejemplos:\n"
                    "Rodrigo Tapari Una cerveza\n"
                    "Ráfaga Una cerveza\n"
                    "Soda Stereo De Música Ligera\n"
                    "La Renga La Balada del Diablo y la Muerte",
                    main_menu()
                )

                return "OK"

            # Buscar música
            if text in (
                "Buscar musica",
                "Buscar música",
                "🔎 Buscar música"
            ):

                send_message(
                    chat_id,
                    "🔎 Escribí el artista y la canción.\n\n"
                    "Ejemplo:\n"
                    "Rodrigo Tapari Una cerveza"
                )

                return "OK"

            # Mis búsquedas
            if text in (
                "Mis busquedas",
                "Mis búsquedas",
                "🎧 Mis búsquedas"
            ):

                searches = USER_SEARCHES.get(
                    chat_id,
                    []
                )

                if not searches:

                    send_message(
                        chat_id,
                        "🎧 Todavía no tenés búsquedas guardadas."
                    )

                    return "OK"

                buttons = []

                for search in reversed(searches):

                    buttons.append(
                        [
                            {
                                "text": f"🔎 {search}",
                                "callback_data": f"history_{search}"
                            }
                        ]
                    )

                send_message(
                    chat_id,
                    "🎧 Tus últimas búsquedas:",
                    {
                        "inline_keyboard": buttons
                    }
                )

                return "OK"

            # Ayuda
            if text in (
                "Ayuda",
                "❓ Ayuda"
            ):

                send_message(
                    chat_id,
                    "❓ AYUDA\n\n"
                    "Para buscar música escribí:\n\n"
                    "Artista + canción\n\n"
                    "Ejemplo:\n"
                    "Rodrigo Tapari Una cerveza\n\n"
                    "El bot mostrará los resultados "
                    "disponibles y un preview de 30 segundos."
                )

                return "OK"

            # InfoZonal
            if text in (
                "InfoZonal",
                "ℹ️ InfoZonal"
            ):

                send_message(
                    chat_id,
                    "📡 InfoZonal\n\n"
                    "Noticias, información y actualidad "
                    "de San Andrés de Giles y zona.\n\n"
                    "San Andrés de Giles y zona."
                )

                return "OK"

            # Si escribió cualquier otra cosa,
            # se interpreta como búsqueda
            show_results(
                chat_id,
                text
            )

            return "OK"

        # =====================
        # BOTONES INLINE
        # =====================

        callback = update.get(
            "callback_query"
        )

        if callback:

            callback_id = callback.get(
                "id"
            )

            callback_data = callback.get(
                "data",
                ""
            )

            callback_message = callback.get(
                "message"
            ) or {}

            callback_chat = callback_message.get(
                "chat"
            ) or {}

            chat_id = callback_chat.get(
                "id"
            )

            answer_callback(
                callback_id
            )

            # Nueva búsqueda
            if callback_data == "new_search":

                send_message(
                    chat_id,
                    "🔎 Escribí el artista y la canción.\n\n"
                    "Ejemplo:\n"
                    "Rodrigo Tapari Una cerveza"
                )

                return "OK"

            # Búsqueda del historial
            if callback_data.startswith(
                "history_"
            ):

                query = callback_data[
                    len("history_"):
                ]

                show_results(
                    chat_id,
                    query
                )

                return "OK"

            # Selección de canción
            if callback_data.startswith(
                "song_"
            ):

                try:

                    index = int(
                        callback_data[
                            len("song_"):
                        ]
                    )

                except ValueError:

                    return "OK"

                results = SEARCH_RESULTS.get(
                    chat_id,
                    []
                )

                if index < 0 or index >= len(results):

                    send_message(
                        chat_id,
                        "❌ Ese resultado ya no está disponible."
                    )

                    return "OK"

                item = results[index]

                send_song(
                    chat_id,
                    item
                )

                return "OK"

        return "OK"

    except Exception as e:

        print(
            "WEBHOOK ERROR:",
            repr(e)
        )

        return "OK"


# =========================
# WSGI
# =========================

application = app
