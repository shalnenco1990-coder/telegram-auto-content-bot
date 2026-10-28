import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

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
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())

        results = []
        for item in root.findall(".//item")[:6]:
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
    except Exception:
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
Для каждого найденного события укажи источник и ссылку.
Не выдавай отсутствие публикаций за доказательство отсутствия событий.
Если сведений нет, честно укажи это.
Отдельно перечисли, что необходимо проверить вручную.
Пиши конкретно, как для руководителя. До 3000 символов.

Дата: {date}
Результаты поиска:
{json.dumps(news, ensure_ascii=False)}
"""

    payload = {
        "model": "gpt-4.1-mini",
        "messages": [
            {
                "role": "system",
                "content": "Ты точный аналитик. Не выдумывай сведения и ссылки."
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1400,
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"].strip()

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
        f"☕ DEL CAPPUCCINO — ЕЖЕДНЕВНЫЙ ОТЧЁТ\n"
        f"📅 {today} | Алматы\n\n{report}"
    )

    send_message(message)
    print("Report sent successfully.")

if __name__ == "__main__":
    main()
