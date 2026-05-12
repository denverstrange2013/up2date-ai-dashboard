from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI
import requests
import os
import json

load_dotenv()

app = Flask(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# ARTICLE CLUSTERING (UNCHANGED STABLE)
# =========================================================
def cluster_articles(topic, articles):

    topic_words = set(topic.lower().split())
    seen = set()
    clustered = []

    for a in articles:
        title = (a.get("title") or "").lower()

        if not title or title in seen:
            continue

        seen.add(title)

        if any(w in title for w in topic_words) or len(clustered) < 5:
            clustered.append(a)

    return clustered[:8]


# =========================================================
# SUMMARY (UNCHANGED)
# =========================================================
def generate_summary(topic, content):

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Summarize ONE real-world event in 4–6 sentences. No headlines list."
            },
            {
                "role": "user",
                "content": content
            }
        ]
    )

    return response.choices[0].message.content


# =========================================================
# TIMELINE (STRICT JSON — NO FALLBACKS)
# =========================================================
def generate_timeline(topic, content):

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Return ONLY valid JSON.\n\n"
                    "FORMAT:\n"
                    "[{\"date\":\"YYYY-MM-DDTHH:MM:SSZ\",\"event\":\"...\"}]\n\n"
                    "RULES:\n"
                    "- No text outside JSON\n"
                    "- No markdown\n"
                    "- Only use provided news\n"
                    "- Must be chronological"
                )
            },
            {
                "role": "user",
                "content": content
            }
        ]
    )

    try:
        return json.loads(response.choices[0].message.content)
    except:
        return []   # IMPORTANT: no broken fallback strings


# =========================================================
# STATS (RESTORED CLEAN FORMAT)
# =========================================================
def fetch_stats_articles(topic):

    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={topic}&"
        f"language=en&"
        f"sortBy=relevancy&"
        f"pageSize=10&"
        f"apiKey={NEWS_API_KEY}"
    )

    data = requests.get(url).json()
    return data.get("articles", [])[:10]


def generate_stats(topic, articles):

    content = "\n".join([
        f"{a.get('title','')}. {a.get('description','')}"
        for a in articles
    ])

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Return ONLY short bullet point statistics.\n"
                    "No explanations. No sentences.\n"
                    "Only numbers (deaths, cases, totals)."
                )
            },
            {
                "role": "user",
                "content": content
            }
        ]
    )

    return response.choices[0].message.content


# =========================================================
# ROUTE
# =========================================================
@app.route("/", methods=["GET", "POST"])
def home():

    topic = None
    articles = []
    summary = None
    timeline = []
    stats = None

    if request.method == "POST":

        topic = request.form.get("topic")

        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={topic}&"
            f"language=en&"
            f"sortBy=publishedAt&"
            f"pageSize=12&"
            f"apiKey={NEWS_API_KEY}"
        )

        data = requests.get(url).json()

        if "articles" in data:

            raw_articles = data["articles"]

            articles = cluster_articles(topic, raw_articles)

            cluster_text = "\n".join([
                f"{a.get('publishedAt','')} - {a.get('title','')}"
                for a in articles
            ])

            summary = generate_summary(topic, cluster_text)

            stats = generate_stats(topic, fetch_stats_articles(topic))

            timeline = generate_timeline(topic, cluster_text)

    return render_template(
        "index.html",
        topic=topic,
        articles=articles,
        summary=summary,
        timeline=timeline,
        stats=stats
    )


if __name__ == "__main__":
    app.run(debug=True)