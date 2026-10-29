import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

QUERIES = [
    '"Del Cappucino" Kazakhstan',
    '"Del Cappuccino" Kazakhstan',
    '"Del Cappucino" отзывы',
    '"Del Cappuccino" отзывы',
    '"Del Cappucino" меню',
    'Алматы кофейни рестораны новости',
]


def get_news(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "ru",
        "gl": "KZ",
        "ceid": "KZ:ru",
    })

    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            root = ET.fromstring(response.read())

        results = []

        for item in root.findall(".//item")[:4]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            date = item.findtext("pubDate", "").strip()
            source = item.findtext("source", "").strip()

            if title and link:
                results.append({
                    "title": title,
                    "link": link,
                    "date": date,
                    "source": source,
                })

        return results

    except Exception as error:
        print(f"Search error: {type(error).__name__}")
        return []


def make_report(news, date):
    prompt = f"""
Ты деловой ассистент руководителя сети Del Cappucino в Казахстане.
Подготовь краткий ежедневный отчёт на русском языке.

Разделы:
1. Новости сети и развитие бизнеса.
2. Отзывы и репутация.
3. Меню, цены, акции и конкуренты.
4. Владельцы и руководители — только подтверждённые публичные сведения.
5. Важные новости ресторанного рынка Алматы.

Используй только предоставленные результаты. Не выдумывай факты.
Для каждого события укажи источник и ссылку.
Не выдавай отсутствие публикаций за доказательство отсутствия событий.
Если сведений нет, честно укажи это.
Отдельно перечисли, что необходимо проверить вручную.
Пиши конкретно, как для руководителя. До 3000 символов.

Дата: {date}

Результаты поиска:
{json.dumps(news, ensure_ascii=False)}
"""

    payload = {
        "systemInstruction": {
            "parts": [{
                "text": "Ты точный аналитик. Не выдумывай сведения и ссылки."
            }]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 900,
        },
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.8-flash:generateContent"
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))

        except Exception as error:
        print(f"Gemini error: {type(error).__name__}: {error}")

        fallback_items = []
        for item in news[:8]:
            title = item.get("title", "").strip()
            link = item.get("link", "").strip()

            if title:
                entry = f"• {title}"
                if link:
                    entry += f"\n{link}"
                fallback_items.append(entry)

        if fallback_items:
            return (
                "⚠️ Не удалось получить AI-анализ Gemini.\n"
                "Ниже — найденные публикации без дополнительных выводов:\n\n"
                + "\n\n".join(fallback_items)
            )

        return (
            "⚠️ Не удалось получить ответ Gemini, "
            "а поиск не вернул публикаций для резервного отчёта.\n"
            "Это не означает, что новостей нет."
        )

    try:
        return "".join(
            part["text"]
            for part in data["candidates"][0]["content"]["parts"]
            if "text" in part
        ).strip()

    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini вернул ответ в неожиданном формате")


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Telegram message sending failed")


def main():
    today = datetime.now(
        ZoneInfo("Asia/Almaty")
    ).strftime("%d.%m.%Y")

    news = []
    seen = set()

    for query in QUERIES:
        for item in get_news(query):
            if item["link"] not in seen:
                seen.add(item["link"])
                news.append(item)

    report = make_report(news[:40], today)

    message = (
        "☕ DEL CAPPUCCINO — ЕЖЕДНЕВНЫЙ ОТЧЁТ\n"
        f"📅 {today} | Алматы\n\n{report}"
    )

    send_message(message)
    print("Report sent successfully.")


if __name__ == "__main__":
    main()
