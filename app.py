import streamlit as st
import anthropic
import requests
import os
import json
import time
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def scrape_tiktok_account(username):
    start_url = "https://api.apify.com/v2/acts/clockworks~tiktok-profile-scraper/runs"
    payload = {
        "profiles": [username],
        "resultsPerPage": 50,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }
    params = {"token": APIFY_API_TOKEN}
    response = requests.post(start_url, json=payload, params=params, timeout=30)
    if response.status_code != 201:
        return None
    run_id = response.json()["data"]["id"]
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    for i in range(30):
        time.sleep(5)
        status_response = requests.get(status_url, params=params)
        status = status_response.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        elif status in ["FAILED", "ABORTED"]:
            return None
    dataset_id = status_response.json()["data"]["defaultDatasetId"]
    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    data_response = requests.get(data_url, params=params)
    return data_response.json()


def extract_video_data(data):
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
                "hashtags": [h if isinstance(h, str) else h.get("name", "") for h in item.get("hashtags", [])],
                "dauer": item.get("videoMeta", {}).get("duration", 0),
            })
    videos.sort(key=lambda x: x["datum"], reverse=True)
    last_12_months = []
    now = datetime.now(timezone.utc)
    for v in videos:
        try:
            dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
            if (now - dt).days <= 365:
                last_12_months.append(v)
        except:
            pass
    newest_30 = videos[:30]
    top_10 = sorted(last_12_months, key=lambda x: x["views"], reverse=True)[:10]
    bottom_10 = sorted(last_12_months, key=lambda x: x["views"])[:10]
    return {"newest_30": newest_30, "top_10": top_10, "bottom_10": bottom_10, "all": videos}


def suggest_comparison_accounts(main_data, username):
    profile_info = {"username": username, "videos": []}
    for item in main_data[:10]:
        profile_info["videos"].append({
            "beschreibung": item.get("text", ""),
            "hashtags": item.get("hashtags", []),
            "views": item.get("playCount", 0),
        })
    prompt = f"""Analysiere diesen TikTok Account und schlage passende Vergleichs-Accounts vor.

Account: @{username}
Letzte Videos und Hashtags:
{json.dumps(profile_info["videos"], ensure_ascii=False, indent=2)}

Schlage exakt 6 reale TikTok Accounts vor:
- 2 Top-Performer in dieser Nische (min. 100.000 Follower)
- 2 ähnlich große Accounts
- 2 kleinere Accounts

WICHTIG: Nur aktive Accounts die in den letzten 30 Tagen gepostet haben. Keine privaten Accounts. Bevorzuge bekannte deutschsprachige Accounts.

Antworte NUR in diesem JSON Format:
{{
  "nische": "beschreibung der nische",
  "accounts": [
    {{"username": "tiktok_username", "kategorie": "top_performer", "grund": "kurze begründung"}},
    {{"username": "tiktok_username", "kategorie": "top_performer", "grund": "kurze begründung"}},
    {{"username": "tiktok_username", "kategorie": "aehnlich", "grund": "kurze begründung"}},
    {{"username": "tiktok_username", "kategorie": "aehnlich", "grund": "kurze begründung"}},
    {{"username": "tiktok_username", "kategorie": "kleiner", "grund": "kurze begründung"}},
    {{"username": "tiktok_username", "kategorie": "kleiner", "grund": "kurze begründung"}}
  ]
}}"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text
    text = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def full_comparison_analysis(main_username, main_videos_dict, comparison_accounts_data, nische):
    newest = main_videos_dict.get("newest_30", [])
    top_10 = main_videos_dict.get("top_10", [])
    bottom_10 = main_videos_dict.get("bottom_10", [])
    comparison_summary = {}
    for username, videos_dict in comparison_accounts_data.items():
        if videos_dict:
            videos = videos_dict.get("newest_30", []) if isinstance(videos_dict, dict) else videos_dict
            if videos:
                total_views = sum(v["views"] for v in videos)
                total_likes = sum(v["likes"] for v in videos)
                avg_views = total_views // len(videos) if videos else 0
                avg_engagement = round((total_likes / total_views * 100) if total_views > 0 else 0, 2)
                comparison_summary[username] = {
                    "avg_views": avg_views,
                    "avg_engagement": avg_engagement,
                    "top_hashtags": list(set([h if isinstance(h, str) else h.get("name", "") for v in videos for h in (v["hashtags"] if isinstance(v["hashtags"], list) else [])]))[:10],
                    "avg_duration": round(sum(v["dauer"] for v in videos) / len(videos), 1) if videos else 0,
                }
    main_videos = newest
    main_total_views = sum(v["views"] for v in main_videos)
    main_total_likes = sum(v["likes"] for v in main_videos)
    main_avg_views = main_total_views // len(main_videos) if main_videos else 0
    main_avg_engagement = round((main_total_likes / main_total_views * 100) if main_total_views > 0 else 0, 2)
    prompt = f"""Du bist ein Expert für TikTok Analytics und Social Media Wachstum.

Erstelle eine detaillierte Vergleichsanalyse für @{main_username} in der Nische: {nische}

HAUPTACCOUNT @{main_username}:
- Durchschnittliche Views (letzte 30): {main_avg_views:,}
- Engagement Rate: {main_avg_engagement}%
- Analysierte Videos: {len(main_videos)}
- TOP 10 Videos (letztes Jahr): {json.dumps(top_10[:3], ensure_ascii=False)}
- SCHLECHTESTE 10 Videos (letztes Jahr): {json.dumps(bottom_10[:3], ensure_ascii=False)}

VERGLEICHS-ACCOUNTS:
{json.dumps(comparison_summary, ensure_ascii=False, indent=2)}

Erstelle eine strukturierte Analyse auf Deutsch mit:

## 1. 📊 Positions-Analyse
- Wo steht @{main_username} im Vergleich?
- Stärken und Schwächen
- Engagement Rate Vergleich

## 2. 🏆 Was die Top-Performer besser machen
- Konkrete Unterschiede in Content-Strategie
- Hashtag-Strategie
- Videolänge und Posting-Frequenz

## 3. 📈 Wachstumspotenzial
- Realistisches Potenzial basierend auf den Daten
- Welche Accounts als Vorbild nehmen

## 4. 🎯 5 konkrete Aktionen
Basierend auf dem was Top-Performer machen. Jede Aktion mit konkretem Beispiel.

## 5. ⚠️ Was sofort aufgehört werden sollte
Basierend auf den schlechtesten Videos und Vergleichsdaten.

Sei sehr konkret und direkt."""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text, main_avg_views, main_avg_engagement


def save_analysis(username, nische, avg_views, engagement_rate, comparison_accounts, analysis_text):
    try:
        supabase.table("analyses").insert({
            "username": username,
            "nische": nische,
            "avg_views": avg_views,
            "engagement_rate": engagement_rate,
            "top_accounts": comparison_accounts,
            "analysis_text": analysis_text
        }).execute()
    except Exception as e:
        st.warning(f"Speichern fehlgeschlagen: {e}")


def load_analyses(username):
    try:
        result = supabase.table("analyses").select("*").eq("username", username).order("created_at", desc=True).execute()
        return result.data
    except:
        return []


# UI
st.set_page_config(page_title="TikTok AI Analyzer", page_icon="🎵", layout="wide")

# Navigation
page = st.sidebar.radio("Navigation", ["🔍 Neue Analyse", "📊 Dashboard"])
st.sidebar.divider()

if page == "🔍 Neue Analyse":
    st.title("🎵 TikTok AI Analyzer")
    st.subheader("KI-gestützte Analyse mit Konkurrenzvergleich")

    if "step" not in st.session_state:
        st.session_state.step = 1
    if "main_data" not in st.session_state:
        st.session_state.main_data = None
    if "suggestions" not in st.session_state:
        st.session_state.suggestions = None
    if "selected_accounts" not in st.session_state:
        st.session_state.selected_accounts = []

    if st.session_state.step == 1:
        st.markdown("### Schritt 1: Deinen Account analysieren")
        st.caption("ℹ️ Die Analyse basiert auf den letzten 50 Videos des Accounts.")
        username = st.text_input("TikTok Username", placeholder="z.B. lucasbenner")
        if st.button("🔍 Account scannen", type="primary"):
            if username:
                with st.spinner(f"@{username} wird gescannt..."):
                    data = scrape_tiktok_account(username)
                if data:
                    st.session_state.main_data = data
                    st.session_state.username = username
                    st.success(f"✅ {len(data)} Videos von @{username} geladen")
                    with st.spinner("KI sucht passende Vergleichs-Accounts..."):
                        try:
                            suggestions = suggest_comparison_accounts(data, username)
                            st.session_state.suggestions = suggestions
                            st.session_state.step = 2
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler bei Account-Suche: {e}")
                else:
                    st.error("Account nicht gefunden.")

    elif st.session_state.step == 2:
        suggestions = st.session_state.suggestions
        username = st.session_state.username
        st.markdown(f"### Schritt 2: Vergleichs-Accounts auswählen")
        st.info(f"**Erkannte Nische:** {suggestions['nische']}")
        st.markdown("Die KI hat folgende Accounts gefunden. Du kannst Usernamen direkt bearbeiten:")
        selected = []
        col1, col2, col3 = st.columns(3)
        top_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "top_performer"]
        similar_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "aehnlich"]
        smaller_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "kleiner"]
        with col1:
            st.markdown("#### 🏆 Top Performer")
            for i, acc in enumerate(top_accounts):
                edited = st.text_input(f"✏️ Username", value=acc["username"], key=f"edit_{acc['username']}_{i}")
                checked = st.checkbox(f"Einschließen", key=f"check_{acc['username']}_{i}", value=True)
                st.caption(acc["grund"])
                st.divider()
                if checked and edited:
                    selected.append(edited)
        with col2:
            st.markdown("#### 🔄 Ähnliche Accounts")
            for i, acc in enumerate(similar_accounts):
                edited = st.text_input(f"✏️ Username", value=acc["username"], key=f"edit_{acc['username']}_{i}_s")
                checked = st.checkbox(f"Einschließen", key=f"check_{acc['username']}_{i}_s", value=True)
                st.caption(acc["grund"])
                st.divider()
                if checked and edited:
                    selected.append(edited)
        with col3:
            st.markdown("#### 📉 Kleinere Accounts")
            for i, acc in enumerate(smaller_accounts):
                edited = st.text_input(f"✏️ Username", value=acc["username"], key=f"edit_{acc['username']}_{i}_k")
                checked = st.checkbox(f"Einschließen", key=f"check_{acc['username']}_{i}_k", value=False)
                st.caption(acc["grund"])
                st.divider()
                if checked and edited:
                    selected.append(edited)
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("← Zurück"):
                st.session_state.step = 1
                st.rerun()
        with col_next:
            if st.button("🚀 Vergleich starten", type="primary"):
                if selected:
                    st.session_state.selected_accounts = selected
                    st.session_state.step = 3
                    st.rerun()
                else:
                    st.warning("Wähle mindestens einen Account aus.")

    elif st.session_state.step == 3:
        username = st.session_state.username
        selected_accounts = st.session_state.selected_accounts
        suggestions = st.session_state.suggestions
        st.markdown("### Schritt 3: Vollständige Vergleichsanalyse")
        comparison_data = {}
        total = len(selected_accounts)
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, acc in enumerate(selected_accounts):
            status_text.text(f"Scanne @{acc}... ({i+1}/{total})")
            data = scrape_tiktok_account(acc)
            if data and len(data) > 0:
                extracted = extract_video_data(data)
                newest = extracted.get("newest_30", [])
                now = datetime.now(timezone.utc)
                recent = []
                for v in newest:
                    try:
                        dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
                        if (now - dt).days <= 30:
                            recent.append(v)
                    except:
                        pass
                if len(newest) == 0:
                    status_text.text(f"⚠️ @{acc} ist privat — wird übersprungen")
                    time.sleep(2)
                elif len(recent) == 0:
                    status_text.text(f"⚠️ @{acc} ist inaktiv — wird übersprungen")
                    time.sleep(2)
                else:
                    comparison_data[acc] = extracted
            else:
                status_text.text(f"⚠️ @{acc} nicht gefunden — wird übersprungen")
                time.sleep(2)
            progress_bar.progress((i + 1) / total)
        status_text.text("KI analysiert alle Daten...")
        main_videos = extract_video_data(st.session_state.main_data)
        newest = main_videos.get("newest_30", [])
        analysis, avg_views, engagement = full_comparison_analysis(
            username, main_videos, comparison_data, suggestions["nische"]
        )
        # Speichern in Supabase
        save_analysis(
            username=username,
            nische=suggestions["nische"],
            avg_views=avg_views,
            engagement_rate=engagement,
            comparison_accounts=list(comparison_data.keys()),
            analysis_text=analysis
        )
        progress_bar.empty()
        status_text.empty()
        col1, col2, col3, col4 = st.columns(4)
        total_views = sum(v["views"] for v in newest)
        total_likes = sum(v["likes"] for v in newest)
        avg_v = total_views // len(newest) if newest else 0
        eng = round((total_likes / total_views * 100) if total_views > 0 else 0, 2)
        with col1:
            st.metric("👁️ Gesamt Views", f"{total_views:,}")
        with col2:
            st.metric("❤️ Gesamt Likes", f"{total_likes:,}")
        with col3:
            st.metric("📊 Ø Views", f"{avg_v:,}")
        with col4:
            st.metric("💬 Engagement", f"{eng}%")
        st.divider()
        st.markdown("## 🤖 KI Vergleichsanalyse")
        st.markdown(analysis)
        st.divider()
        col_download, col_restart = st.columns([1, 1])
        with col_download:
            st.download_button(
                label="📥 Analyse downloaden",
                data=analysis,
                file_name=f"tiktok_vergleich_{username}.txt",
                mime="text/plain"
            )
        with col_restart:
            if st.button("🔄 Neue Analyse"):
                st.session_state.step = 1
                st.session_state.main_data = None
                st.session_state.suggestions = None
                st.session_state.selected_accounts = []
                st.rerun()

elif page == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.subheader("Deine gespeicherten Analysen")

    username_filter = st.text_input("TikTok Username", placeholder="z.B. lucasbenner")

    if st.button("📂 Analysen laden", type="primary"):
        if username_filter:
            analyses = load_analyses(username_filter)
            if analyses:
                st.success(f"✅ {len(analyses)} Analysen gefunden für @{username_filter}")

                # Verlauf Chart
                if len(analyses) > 1:
                    st.markdown("### 📈 Performance Verlauf")
                    import pandas as pd
                    df = pd.DataFrame([{
                        "Datum": a["created_at"][:10],
                        "Ø Views": a["avg_views"],
                        "Engagement %": a["engagement_rate"]
                    } for a in analyses])
                    df = df.sort_values("Datum")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.line_chart(df.set_index("Datum")["Ø Views"])
                    with col2:
                        st.line_chart(df.set_index("Datum")["Engagement %"])

                # Alle Analysen
                st.markdown("### 📋 Alle Analysen")
                for a in analyses:
                    with st.expander(f"📅 {a['created_at'][:10]} — Ø {a['avg_views']:,} Views — {a['engagement_rate']}% Engagement"):
                        st.markdown(f"**Nische:** {a['nische']}")
                        st.markdown(f"**Verglichene Accounts:** {', '.join(a['top_accounts']) if a['top_accounts'] else 'keine'}")
                        st.markdown("---")
                        st.markdown(a["analysis_text"])
                        st.download_button(
                            label="📥 Download",
                            data=a["analysis_text"],
                            file_name=f"analyse_{a['created_at'][:10]}.txt",
                            key=f"dl_{a['id']}"
                        )
            else:
                st.info(f"Noch keine Analysen für @{username_filter} gespeichert.")
        else:
            st.warning("Bitte Username eingeben.")
