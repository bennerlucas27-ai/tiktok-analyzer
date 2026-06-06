import streamlit as st
import anthropic
import requests
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def get_tiktok_data(username):
    # Job starten
    start_url = "https://api.apify.com/v2/acts/clockworks~tiktok-profile-scraper/runs"

    payload = {
        "profiles": [username],
        "resultsPerPage": 30,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }

    params = {"token": APIFY_API_TOKEN}

    with st.spinner("TikTok Scraper wird gestartet..."):
        response = requests.post(start_url, json=payload, params=params, timeout=30)

    if response.status_code != 201:
        st.error(f"Fehler beim Starten: {response.status_code}")
        return None

    run_id = response.json()["data"]["id"]

    # Warten bis fertig
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"

    with st.spinner("Daten werden geladen... (kann 30-60 Sekunden dauern)"):
        for i in range(30):
            time.sleep(5)
            status_response = requests.get(status_url, params=params)
            status = status_response.json()["data"]["status"]

            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "ABORTED"]:
                st.error("Scraper fehlgeschlagen.")
                return None

    # Daten holen
    dataset_id = status_response.json()["data"]["defaultDatasetId"]
    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    data_response = requests.get(data_url, params=params)

    return data_response.json()


def analyze_with_claude(data, username):
    videos = []
    for item in data:
        if "videoMeta" in item or "text" in item:
            videos.append({
                "beschreibung": item.get("text", ""),
                "views": item.get("playCount", 0),
                "likes": item.get("diggCount", 0),
                "comments": item.get("commentCount", 0),
                "shares": item.get("shareCount", 0),
                "datum": item.get("createTimeISO", ""),
                "hashtags": item.get("hashtags", []),
                "dauer": item.get("videoMeta", {}).get("duration", 0),
            })

    if not videos:
        return "Keine Videos gefunden."

    prompt = f"""Du bist ein Expert für TikTok Analytics und Social Media Wachstum.

Analysiere die TikTok Daten von @{username} und gib eine detaillierte Analyse auf Deutsch.

Hier sind die letzten {len(videos)} Videos:

{json.dumps(videos, ensure_ascii=False, indent=2)}

Erstelle eine strukturierte Analyse mit:

1. **Performance Übersicht**
   - Durchschnittliche Views, Likes, Comments
   - Engagement Rate
   - Bestes und schlechtestes Video

2. **Content Analyse**
   - Welche Themen/Typen performen am besten
   - Welche Hashtags funktionieren
   - Optimale Videolänge

3. **Posting Muster**
   - Beste Posting-Zeiten
   - Posting-Frequenz

4. **Konkrete Empfehlungen**
   - 5 spezifische Aktionen die @{username} sofort umsetzen kann
   - Was unbedingt vermieden werden sollte

5. **Wachstumsprognose**
   - Realistisches 30-Tage Ziel wenn Empfehlungen umgesetzt werden

Sei direkt, konkret und actionable. Keine generischen Tipps."""

    with st.spinner("AI analysiert deine Daten..."):
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

    return message.content[0].text


# UI
st.set_page_config(page_title="TikTok Analyzer", page_icon="🎵", layout="wide")

st.title("🎵 TikTok AI Analyzer")
st.subheader("Analysiere deinen TikTok Account mit KI")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    username = st.text_input("TikTok Username", placeholder="z.B. lucasbenner")
    analyze_btn = st.button("🔍 Analysieren", type="primary")

if analyze_btn and username:
    data = get_tiktok_data(username)

    if data:
        st.success(f"✅ {len(data)} Videos geladen")

        col1, col2, col3 = st.columns(3)

        total_views = sum(item.get("playCount", 0) for item in data)
        total_likes = sum(item.get("diggCount", 0) for item in data)
        avg_views = total_views // len(data) if data else 0

        with col1:
            st.metric("👁️ Gesamt Views", f"{total_views:,}")
        with col2:
            st.metric("❤️ Gesamt Likes", f"{total_likes:,}")
        with col3:
            st.metric("📊 Ø Views pro Video", f"{avg_views:,}")

        st.divider()

        analysis = analyze_with_claude(data, username)

        st.markdown("## 🤖 AI Analyse")
        st.markdown(analysis)

        st.divider()
        st.download_button(
            label="📥 Analyse downloaden",
            data=analysis,
            file_name=f"tiktok_analyse_{username}.txt",
            mime="text/plain"
        )

elif analyze_btn and not username:
    st.warning("Bitte gib einen TikTok Username ein.")

else:
    st.info("👈 Gib links einen TikTok Username ein und klicke auf Analysieren.")
