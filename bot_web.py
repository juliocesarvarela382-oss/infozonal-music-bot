import os
import re
import requests
import json
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    print("ADVERTENCIA: BOT_TOKEN no configurado")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SEARCH_RESULTS = {}
USER_SEARCHES = {}


def telegram(method, data=None):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            data=data or {},
            timeout=30
        )

        print("TELEGRAM:", method, response.status_code)

        try:
            return response.json()
        except Exception:
            return {}

    except Exception as e:
        print("ERROR TELEGRAM:", e)
        return {}


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


def main_menu():
    return {
        "keyboard": [
            [
                {"text": "Buscar musica"},
                {"text": "Mis busquedas"}
            ],
            [
                {"text": "Ayuda"},
                {"text": "InfoZonal"}
            ]
        ],
        "resize_keyboard": True
    }


def normalize(text):
    if not text:
        return ""

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

    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def words(text):
    return set(normalize(text).split())


def score_result(query, artist, title):
    q = normalize(query)
    a = normalize(artist)
    t = normalize(title)

    if not a or not t:
        return 0

    score = 0

    q_words = words(q)
    a_words = words(a)
    t_words = words(t)

    score += len(q_words.intersection(a_words)) * 300
    score += len(q_words.intersection(t_words)) * 350

    if a in q:
        score += 1500

    if t in q:
        score += 1800

    if q == f"{a} {t}":
        score += 5000

    return score


def deezer_search(query):
    try:
        print("DEEZER BUSQUEDA:", query)

        response = requests.get(
            "https://api.deezer.com/search",
            params={
                "q": query,
                "limit": 50
            },
            timeout=25
        )

        print("DEEZER STATUS:", response.status_code)

        if response.status_code != 200:
            return []

        data = response.json()

        results = []

        for song in data.get("data", []):
            artist_data = song.get("artist") or {}

            artist = artist_data.get("name", "")
            title = song.get("title", "")
            preview = song.get("preview", "")

            if not artist or not title:
                continue

            results.append({
                "id": song.get("id"),
                "artist": artist,
                "title": title,
                "preview": preview,
                "link": song.get("link", ""),
                "duration": song.get("duration", 0),
                "score": score_result(query, artist, title)
            })

        return results

    except Exception as e:
        print("ERROR DEEZER:", e)
        return []


def search_music(query):
    query_clean = normalize(query)

    if not query_clean:
        return []

    all_results = []

    # Busqueda completa
    all_results.extend(deezer_search(query))

    query_words = query_clean.split()

    # Busquedas intentando detectar artista + titulo
    if len(query_words) >= 2:

        for artist_words_count in range(
            min(3, len(query_words) - 1),
            0,
            -1
        ):
            artist_part = " ".join(
                query_words[:artist_words_count]
            )

            title_part = " ".join(
                query_words[artist_words_count:]
            )

            if not title_part:
                continue

            artist_results = deezer_search(artist_part)

            for item in artist_results:
                artist_normalized = normalize(item["artist"])
                title_normalized = normalize(item["title"])

                title_words = words(title_part)

                matching_title_words = len(
                    title_words.intersection(
                        words(title_normalized)
                    )
                )

                artist_match = (
                    artist_part in artist_normalized
                    or artist_normalized in artist_part
                )

                if artist_match and matching_title_words > 0:
                    item["score"] += 4000
                    item["score"] += matching_title_words * 1000
                    all_results.append(item)

    # Eliminar duplicados
    unique = {}

    for item in all_results:
        key = (
            normalize(item["artist"]),
            normalize(item["title"])
        )

        if key not in unique:
            unique[key] = item
        else:
            if item["score"] > unique[key]["score"]:
                unique[key] = item

    results = list(unique.values())

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:8]


def show_results(chat_id, query):
    print("BUSQUEDA FINAL:", query)

    results = search_music(query)

    print("CANTIDAD RESULTADOS:", len(results))

    if not results:
        send_message(
            chat_id,
            "No encontre resultados.\n\n"
            "Probá escribiendo:\n"
            "Artista + cancion\n\n"
            "Ejemplo:\n"
            "Rodrigo Tapari Una cerveza"
        )
        return

    SEARCH_RESULTS[chat_id] = results

    if chat_id not in USER_SEARCHES:
        USER_SEARCHES[chat_id] = []

    if query not in USER_SEARCHES[chat_id]:
        USER_SEARCHES[chat_id].insert(0, query)

    USER_SEARCHES[chat_id] = USER_SEARCHES[chat_id][:10]

    buttons = []

    for index, item in enumerate(results):
        label = f"{item['title']} - {item['artist']}"

        buttons.append([
            {
                "text": label[:60],
                "callback_data": f"song_{index}"
            }
        ])

    buttons.append([
        {
            "text": "Nueva busqueda",
            "callback_data": "new_search"
        }
    ])

    markup = {
        "inline_keyboard": buttons
    }

    send_message(
        chat_id,
        "RESULTADOS\n\nElegí una canción:",
        markup
    )

def send_authorized_audio(chat_id, audio_file, title, artist):
    try:
        with open(audio_file, "rb") as audio:

            result = telegram(
                "sendAudio",
                {
                    "chat_id": chat_id,
                    "audio": audio,
                    "title": title,
                    "performer": artist
                }
            )

        print("AUTHORIZED AUDIO RESULT:", result)

        return result

    except Exception as e:
        print("ERROR AUTHORIZED AUDIO:", e)
        return {}


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
        "Buscando preview de audio..."
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
            "No pude enviar el audio."
        )


@app.route("/", methods=["GET"])
def home():
    return "InfoZonal Music Bot OK"


@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        update = request.get_json(
            silent=True
        ) or {}

        print("UPDATE RECIBIDO")

        if "message" in update:

            message = update["message"]

            chat = message.get("chat", {})

            chat_id = chat.get("id")

            text = message.get("text", "")

            if not chat_id:
                return "OK"

            text = text.strip()

            if text == "/start":

                send_message(
                    chat_id,
                    "InfoZonal Music\n\n"
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

            if text in ("Buscar musica", "🔎 Buscar música"):

                send_message(
                    chat_id,
                    "Escribí el artista y la canción.\n\n"
                    "Ejemplo:\n"
                    "Rodrigo Tapari Una cerveza"
                )

                return "OK"

            if text in ("Mis busquedas", "🎧 Mis búsquedas"):

                searches = USER_SEARCHES.get(
                    chat_id,
                    []
                )

                if not searches:

                    send_message(
                        chat_id,
                        "Todavía no tenés búsquedas."
                    )

                else:

                    message_text = "Tus búsquedas:\n\n"

                    for index, search in enumerate(
                        searches,
                        1
                    ):
                        message_text += (
                            f"{index}. {search}\n"
                        )

                    send_message(
                        chat_id,
                        message_text
                    )

                return "OK"

            if text in ("Ayuda", "ℹ️ Ayuda"):

                send_message(
                    chat_id,
                    "Cómo buscar:\n\n"
                    "Artista\n"
                    "Artista + canción\n"
                    "Título de canción"
                )

                return "OK"

            if text in ("InfoZonal", "📢 InfoZonal"):

                send_message(
                    chat_id,
                    "InfoZonal\n\n"
                    "Noticias de San Andrés de Giles y zona."
                )

                return "OK"

            if text:

                show_results(
                    chat_id,
                    text
                )

                return "OK"

        if "callback_query" in update:

            callback = update["callback_query"]

            callback_id = callback.get("id")

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

            if callback_id:
                answer_callback(
                    callback_id
                )

            if data == "new_search":

                send_message(
                    chat_id,
                    "Escribí el artista o la canción."
                )

                return "OK"

            if data.startswith("song_"):

                try:
                    index = int(
                        data.replace(
                            "song_",
                            ""
                        )
                    )

                except Exception:
                    return "OK"

                results = SEARCH_RESULTS.get(
                    chat_id,
                    []
                )

                if index < 0 or index >= len(results):

                    send_message(
                        chat_id,
                        "La búsqueda venció. "
                        "Buscá nuevamente."
                    )

                    return "OK"

                send_song(
                    chat_id,
                    results[index]
                )

                return "OK"

        return "OK"

    except Exception as e:

        print(
            "ERROR WEBHOOK:",
            e
        )

        return "OK"


application = app
