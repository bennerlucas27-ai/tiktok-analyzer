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
import stripe

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")

st.set_page_config(page_title="TikTok AI Analyzer", page_icon="🎵", layout="wide")

# ─── AUTH FUNCTIONS ───────────────────────────────────────────────────────────

def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        return res.user, None
    except Exception as e:
        return None, str(e)

def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res.user, res.session, None
    except Exception as e:
        return None, None, str(e)

def sign_out():
    supabase.auth.sign_out()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def create_checkout_session(user_email, user_id):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url="https://tiktok-analyser.streamlit.app?success=true",
            cancel_url="https://tiktok-analyser.streamlit.app?canceled=true",
            customer_email=user_email,
            metadata={"user_id": user_id},
            automatic_tax={"enabled": True},
        )
        return session.url
    except Exception as e:
        return None

def has_used_free_analysis(user_id):
    try:
        result = supabase.table("analyses").select("id").eq("user_id", user_id).execute()
        return len(result.data) > 0
    except:
        return False

def is_premium(user_id):
    try:
        result = supabase.table("users").select("is_premium").eq("id", user_id).execute()
        if result.data:
            return result.data[0].get("is_premium", False)
        return False
    except:
        return False

# ─── TIKTOK FUNCTIONS ─────────────────────────────────────────────────────────

def scrape_tiktok_account(username):
    start_url = "https://api.apify.com/v2/acts/clockworks~tiktok-profile-scraper/runs"
    payload = {"profiles": [username], "resultsPerPage": 50, "shouldDownloadVideos": False, "shouldDownloadCovers": False}
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
    return requests.get(f"https://api.apify.com/v2/datasets/{dataset_id}/items", params=params).json()

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
    now = datetime.now(timezone.utc)
    last_12_months = []
    for v in videos:
        try:
            dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
            if (now - dt).days <= 365:
                last_12_months.append(v)
        except:
            pass
    return {
        "newest_30": videos[:30],
        "top_10": sorted(last_12_months, key=lambda x: x["views"], reverse=True)[:10],
        "bottom_10": sorted(last_12_months, key=lambda x: x["views"])[:10],
        "all": videos
    }

def suggest_comparison_accounts(main_data, username):
    profile_info = {"username": username, "videos": []}
    for item in main_data[:10]:
        profile_info["videos"].append({"beschreibung": item.get("text", ""), "hashtags": item.get("hashtags", []), "views": item.get("playCount", 0)})
    prompt = f"""Analysiere diesen TikTok Account und schlage passende Vergleichs-Accounts vor.
Account: @{username}
Videos: {json.dumps(profile_info["videos"], ensure_ascii=False, indent=2)}

Schlage exakt 6 reale aktive TikTok Accounts vor (in letzten 30 Tagen gepostet, nicht privat):
- 2 Top-Performer (min. 100k Follower)
- 2 ähnlich große Accounts
- 2 kleinere Accounts

Bevorzuge deutschsprachige Accounts.

Antworte NUR in diesem JSON Format:
{{"nische": "...", "accounts": [{{"username": "...", "kategorie": "top_performer", "grund": "..."}}, {{"username": "...", "kategorie": "top_performer", "grund": "..."}}, {{"username": "...", "kategorie": "aehnlich", "grund": "..."}}, {{"username": "...", "kategorie": "aehnlich", "grund": "..."}}, {{"username": "...", "kategorie": "kleiner", "grund": "..."}}, {{"username": "...", "kategorie": "kleiner", "grund": "..."}}]}}"""
    message = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000, messages=[{"role": "user", "content": prompt}])
    text = message.content[0].text.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)

def full_comparison_analysis(main_username, main_videos_dict, comparison_accounts_data, nische):
    newest = main_videos_dict.get("newest_30", [])
    top_10 = main_videos_dict.get("top_10", [])
    bottom_10 = main_videos_dict.get("bottom_10", [])
    comparison_summary = {}
    for uname, vdict in comparison_accounts_data.items():
        videos = vdict.get("newest_30", []) if isinstance(vdict, dict) else vdict
        if videos:
            total_views = sum(v["views"] for v in videos)
            total_likes = sum(v["likes"] for v in videos)
            avg_views = total_views // len(videos)
            comparison_summary[uname] = {
                "avg_views": avg_views,
                "avg_engagement": round((total_likes / total_views * 100) if total_views > 0 else 0, 2),
                "top_hashtags": list(set([h for v in videos for h in (v["hashtags"] if isinstance(v["hashtags"], list) else [])]))[:10],
                "avg_duration": round(sum(v["dauer"] for v in videos) / len(videos), 1),
            }
    main_total_views = sum(v["views"] for v in newest)
    main_total_likes = sum(v["likes"] for v in newest)
    main_avg_views = main_total_views // len(newest) if newest else 0
    main_avg_engagement = round((main_total_likes / main_total_views * 100) if main_total_views > 0 else 0, 2)
    prompt = f"""Du bist ein Expert für TikTok Analytics. Erstelle eine Vergleichsanalyse für @{main_username} in der Nische: {nische}

HAUPTACCOUNT @{main_username}:
- Ø Views (letzte 30): {main_avg_views:,}
- Engagement Rate: {main_avg_engagement}%
- TOP 10 Videos: {json.dumps(top_10[:3], ensure_ascii=False)}
- SCHLECHTESTE 10: {json.dumps(bottom_10[:3], ensure_ascii=False)}

VERGLEICHS-ACCOUNTS:
{json.dumps(comparison_summary, ensure_ascii=False, indent=2)}

Erstelle eine strukturierte Analyse auf Deutsch:
## 1. 📊 Positions-Analyse
## 2. 🏆 Was Top-Performer besser machen
## 3. 📈 Wachstumspotenzial
## 4. 🎯 5 konkrete Aktionen
## 5. ⚠️ Was sofort aufgehört werden sollte

Sei konkret und direkt."""
    message = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
    return message.content[0].text, main_avg_views, main_avg_engagement

def save_analysis(user_id, username, nische, avg_views, engagement_rate, comparison_accounts, analysis_text):
    try:
        supabase.table("analyses").insert({
            "user_id": user_id,
            "username": username,
            "nische": nische,
            "avg_views": avg_views,
            "engagement_rate": engagement_rate,
            "top_accounts": comparison_accounts,
            "analysis_text": analysis_text
        }).execute()
    except Exception as e:
        st.warning(f"Speichern fehlgeschlagen: {e}")

def load_analyses(user_id):
    try:
        result = supabase.table("analyses").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return result.data
    except:
        return []

# ─── AUTH SCREEN ──────────────────────────────────────────────────────────────

def show_auth():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎵 TikTok AI Analyzer")
        st.subheader("KI-gestützte Analyse mit Konkurrenzvergleich")
        st.divider()

        tab1, tab2 = st.tabs(["🔑 Einloggen", "✨ Registrieren"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Passwort", type="password", key="login_password")
            if st.button("Einloggen", type="primary", use_container_width=True):
                if email and password:
                    user, session, error = sign_in(email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.session = session
                        st.rerun()
                    else:
                        st.error("Login fehlgeschlagen. Email oder Passwort falsch.")

        with tab2:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Passwort (min. 6 Zeichen)", type="password", key="signup_password")
            if st.button("Kostenlos registrieren", type="primary", use_container_width=True):
                if email and password:
                    user, error = sign_up(email, password)
                    if user:
                        st.success("✅ Account erstellt! Bitte einloggen.")
                    else:
                        st.error(f"Fehler: {error}")

        st.divider()
        st.caption("✅ Kostenlos: Eine vollständige Analyse | 🚀 Premium: Dashboard + alle Features")

# ─── MAIN APP ─────────────────────────────────────────────────────────────────

def show_app():
    user = st.session_state.user
    user_id = user.id
    user_email = user.email
    premium = is_premium(user_id)
    used_free = has_used_free_analysis(user_id)

    # Sidebar
    with st.sidebar:
        st.markdown(f"👤 **{user_email}**")
        if premium:
            st.success("🚀 Premium")
        else:
            st.info("✨ Free")
        st.divider()
        if premium:
            page = st.radio("Navigation", ["🔍 Neue Analyse", "📊 Dashboard"])
        else:
            page = "🔍 Neue Analyse"
        st.divider()
        if st.button("Ausloggen"):
            sign_out()

    if page == "🔍 Neue Analyse":
        st.title("🎵 TikTok AI Analyzer")
        st.subheader("KI-gestützte Analyse mit Konkurrenzvergleich")

        # Paywall Check
        if used_free and not premium:
            st.warning("⚠️ Du hast deine kostenlose Analyse bereits genutzt.")
            st.markdown("### 🚀 Upgrade auf Premium")
            st.markdown("""
            **Was du bekommst:**
            - ✅ Unbegrenzte Analysen
            - ✅ Dashboard mit Performance Verlauf
            - ✅ Posting Streak Tracker
            - ✅ KI Coaching jeden Montag
            - ✅ Wachstums-Statistiken
            """)
            try:
                checkout_url = create_checkout_session(user_email, user_id)
                if checkout_url:
                    st.markdown(f'<a href="{checkout_url}" target="_blank"><button style="background-color:#FF4B4B;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:16px;cursor:pointer;">🚀 Jetzt upgraden — 19€/Monat</button></a>', unsafe_allow_html=True)
                else:
                    st.error("Checkout URL leer — prüfe Stripe Keys")
            except Exception as e:
                st.error(f"Stripe Fehler: {e}")
            return

        if "step" not in st.session_state:
            st.session_state.step = 1

        if st.session_state.step == 1:
            st.markdown("### Schritt 1: Deinen Account analysieren")
            st.caption("ℹ️ Analyse basiert auf den letzten 50 Videos.")
            username = st.text_input("TikTok Username", placeholder="z.B. lucasbenner")
            if st.button("🔍 Account scannen", type="primary"):
                if username:
                    with st.spinner(f"@{username} wird gescannt..."):
                        data = scrape_tiktok_account(username)
                    if data:
                        st.session_state.main_data = data
                        st.session_state.username = username
                        st.success(f"✅ {len(data)} Videos geladen")
                        with st.spinner("KI sucht Vergleichs-Accounts..."):
                            try:
                                suggestions = suggest_comparison_accounts(data, username)
                                st.session_state.suggestions = suggestions
                                st.session_state.step = 2
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler: {e}")
                    else:
                        st.error("Account nicht gefunden.")

        elif st.session_state.step == 2:
            suggestions = st.session_state.suggestions
            username = st.session_state.username
            st.markdown("### Schritt 2: Vergleichs-Accounts auswählen")
            st.info(f"**Erkannte Nische:** {suggestions['nische']}")
            st.caption("💡 Du kannst Usernamen direkt bearbeiten.")
            selected = []
            col1, col2, col3 = st.columns(3)
            top_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "top_performer"]
            similar_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "aehnlich"]
            smaller_accounts = [a for a in suggestions["accounts"] if a["kategorie"] == "kleiner"]
            with col1:
                st.markdown("#### 🏆 Top Performer")
                for i, acc in enumerate(top_accounts):
                    edited = st.text_input("✏️ Username", value=acc["username"], key=f"e_{acc['username']}_{i}")
                    checked = st.checkbox("Einschließen", key=f"c_{acc['username']}_{i}", value=True)
                    st.caption(acc["grund"])
                    st.divider()
                    if checked and edited:
                        selected.append(edited)
            with col2:
                st.markdown("#### 🔄 Ähnliche Accounts")
                for i, acc in enumerate(similar_accounts):
                    edited = st.text_input("✏️ Username", value=acc["username"], key=f"e_{acc['username']}_{i}_s")
                    checked = st.checkbox("Einschließen", key=f"c_{acc['username']}_{i}_s", value=True)
                    st.caption(acc["grund"])
                    st.divider()
                    if checked and edited:
                        selected.append(edited)
            with col3:
                st.markdown("#### 📉 Kleinere Accounts")
                for i, acc in enumerate(smaller_accounts):
                    edited = st.text_input("✏️ Username", value=acc["username"], key=f"e_{acc['username']}_{i}_k")
                    checked = st.checkbox("Einschließen", key=f"c_{acc['username']}_{i}_k", value=False)
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

        elif st.session_state.step == 3:
            username = st.session_state.username
            selected_accounts = st.session_state.selected_accounts
            suggestions = st.session_state.suggestions
            st.markdown("### Schritt 3: Vollständige Vergleichsanalyse")
            comparison_data = {}
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i, acc in enumerate(selected_accounts):
                status_text.text(f"Scanne @{acc}... ({i+1}/{len(selected_accounts)})")
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
                        status_text.text(f"⚠️ @{acc} ist privat — übersprungen")
                        time.sleep(2)
                    elif len(recent) == 0:
                        status_text.text(f"⚠️ @{acc} ist inaktiv — übersprungen")
                        time.sleep(2)
                    else:
                        comparison_data[acc] = extracted
                progress_bar.progress((i + 1) / len(selected_accounts))
            status_text.text("KI analysiert alle Daten...")
            main_videos = extract_video_data(st.session_state.main_data)
            newest = main_videos.get("newest_30", [])
            analysis, avg_views, engagement = full_comparison_analysis(username, main_videos, comparison_data, suggestions["nische"])
            save_analysis(user_id, username, suggestions["nische"], avg_views, engagement, list(comparison_data.keys()), analysis)
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

            if not premium:
                st.success("🎉 Das war deine kostenlose Analyse!")
                st.markdown("### 🚀 Mehr Features mit Premium")
                st.markdown("Dashboard, Verlauf, KI Coaching und mehr für nur **19€/Monat**")
                try:
                    checkout_url = create_checkout_session(user_email, user_id)
                    if checkout_url:
                        st.markdown(f'<a href="{checkout_url}" target="_blank"><button style="background-color:#FF4B4B;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:16px;cursor:pointer;">🚀 Jetzt upgraden — 19€/Monat</button></a>', unsafe_allow_html=True)
                    else:
                        st.error("Checkout URL leer — prüfe Stripe Keys")
                except Exception as e:
                    st.error(f"Stripe Fehler: {e}")

            col_dl, col_new = st.columns(2)
            with col_dl:
                st.download_button("📥 Analyse downloaden", data=analysis, file_name=f"analyse_{username}.txt", mime="text/plain")
            with col_new:
                if st.button("🔄 Neue Analyse"):
                    st.session_state.step = 1
                    st.session_state.main_data = None
                    st.session_state.suggestions = None
                    st.session_state.selected_accounts = []
                    st.rerun()

    elif page == "📊 Dashboard" and premium:
        st.title("📊 Dashboard")
        analyses = load_analyses(user_id)
        if analyses:
            st.success(f"✅ {len(analyses)} Analysen gespeichert")
            if len(analyses) > 1:
                st.markdown("### 📈 Performance Verlauf")
                import pandas as pd
                df = pd.DataFrame([{"Datum": a["created_at"][:10], "Ø Views": a["avg_views"], "Engagement %": a["engagement_rate"]} for a in analyses])
                df = df.sort_values("Datum")
                col1, col2 = st.columns(2)
                with col1:
                    st.line_chart(df.set_index("Datum")["Ø Views"])
                with col2:
                    st.line_chart(df.set_index("Datum")["Engagement %"])
            st.markdown("### 📋 Alle Analysen")
            for a in analyses:
                with st.expander(f"📅 {a['created_at'][:10]} — @{a['username']} — Ø {a['avg_views']:,} Views — {a['engagement_rate']}% Engagement"):
                    st.markdown(f"**Nische:** {a['nische']}")
                    st.markdown(f"**Verglichene Accounts:** {', '.join(a['top_accounts']) if a['top_accounts'] else 'keine'}")
                    st.divider()
                    st.markdown(a["analysis_text"])
                    st.download_button("📥 Download", data=a["analysis_text"], file_name=f"analyse_{a['created_at'][:10]}.txt", key=f"dl_{a['id']}")
        else:
            st.info("Noch keine Analysen gespeichert. Starte deine erste Analyse!")

# ─── ROUTER ───────────────────────────────────────────────────────────────────

if "user" not in st.session_state:
    show_auth()
else:
    show_app()
