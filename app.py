import streamlit as st
import anthropic
import requests
import os
import json
import time
import re
import random
import pandas as pd
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

# Token Pakete
STRIPE_TOKEN_1 = "price_1TgtD76ng13JhR6oyCCBYNLD"   # 1 Analyse = 1€
STRIPE_TOKEN_3 = "price_1TgtDW6ng13JhR6okqTZgMiw"   # 3 Analysen = 2€
STRIPE_TOKEN_10 = "price_1TgtDp6ng13JhR6o2eMTXe5J"  # 10 Analysen = 5€

TOKEN_PACKAGES = [
    {"price_id": STRIPE_TOKEN_1, "tokens": 1, "preis": "1€", "label": "Starter — 1 Analyse"},
    {"price_id": STRIPE_TOKEN_3, "tokens": 3, "preis": "2€", "label": "Value — 3 Analysen"},
    {"price_id": STRIPE_TOKEN_10, "tokens": 10, "preis": "5€", "label": "Pro — 10 Analysen"},
]

st.set_page_config(page_title="TikTok AI Analyzer", page_icon="🎵", layout="wide")

# ─── GLOBAL CSS ───────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0 !important; padding-bottom: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div { background: #0d0d0f !important; border-right: 0.5px solid rgba(255,255,255,0.06) !important; }

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif !important;
    background-color: #0a0a0b !important;
    color: #e8e6e0 !important;
}

div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03) !important;
    border: 0.5px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
}
div[data-testid="metric-container"] label {
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: rgba(232,230,224,0.3) !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 24px !important;
    color: #e8e6e0 !important;
}

.section-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: rgba(232,230,224,0.25);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 0.5px;
    background: rgba(255,255,255,0.05);
}

.db-panel {
    background: rgba(255,255,255,0.02);
    border: 0.5px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 0;
}

.metric-accent-red { height: 2px; background: #ff4d4d; border-radius: 2px; margin-bottom: 10px; }
.metric-accent-amber { height: 2px; background: #f5a623; border-radius: 2px; margin-bottom: 10px; }
.metric-accent-teal { height: 2px; background: #1d9e75; border-radius: 2px; margin-bottom: 10px; }
.metric-accent-blue { height: 2px; background: #378add; border-radius: 2px; margin-bottom: 10px; }

.live-indicator {
    display: inline-block;
    width: 7px;
    height: 7px;
    background: #1d9e75;
    border-radius: 50%;
    margin-right: 6px;
    animation: livepulse 1.8s ease-in-out infinite;
}
@keyframes livepulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.2; }
}

.video-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 0.5px solid rgba(255,255,255,0.05);
}
.video-rank { font-family: 'DM Mono', monospace; font-size: 11px; color: rgba(232,230,224,0.2); width: 24px; }
.video-title { flex: 1; font-size: 13px; color: rgba(232,230,224,0.75); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.video-views { font-family: 'DM Mono', monospace; font-size: 13px; color: rgba(232,230,224,0.5); }
.video-eng { font-size: 11px; color: #1d9e75; font-family: 'DM Mono', monospace; }

.compare-row { margin-bottom: 10px; }
.compare-label {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: rgba(232,230,224,0.4);
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
}
.compare-track { height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; }

.wt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.wt-card { background: rgba(255,255,255,0.03); border: 0.5px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 14px 16px; }
.wt-label { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(232,230,224,0.25); margin-bottom: 6px; }
.wt-value { font-family: 'DM Mono', monospace; font-size: 22px; font-weight: 500; color: #e8e6e0; }
.wt-sub { font-size: 10px; color: rgba(232,230,224,0.25); margin-top: 3px; }

.acc-tag { display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; padding: 3px 8px; border-radius: 4px; margin-right: 6px; }
.acc-tag-you { background: rgba(255,77,77,0.08); border: 0.5px solid rgba(255,77,77,0.25); color: #ff4d4d; }
.acc-tag-top { background: rgba(245,166,35,0.08); border: 0.5px solid rgba(245,166,35,0.25); color: #f5a623; }
.acc-tag-similar { background: rgba(55,138,221,0.08); border: 0.5px solid rgba(55,138,221,0.25); color: #378add; }

.upgrade-card { background: rgba(255,77,77,0.04); border: 0.5px solid rgba(255,77,77,0.2); border-radius: 10px; padding: 24px; text-align: center; }

.sidebar-user { background: rgba(255,255,255,0.04); border: 0.5px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px 16px; margin-bottom: 16px; }
.sidebar-email { font-size: 12px; color: rgba(232,230,224,0.45); font-family: 'DM Mono', monospace; margin-bottom: 6px; }
.sidebar-badge-premium { display: inline-block; background: rgba(255,77,77,0.1); border: 0.5px solid rgba(255,77,77,0.3); color: #ff4d4d; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 3px 8px; border-radius: 4px; }
.sidebar-badge-free { display: inline-block; background: rgba(255,255,255,0.04); border: 0.5px solid rgba(255,255,255,0.1); color: rgba(232,230,224,0.35); font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 3px 8px; border-radius: 4px; }

div[data-testid="stExpander"] { background: rgba(255,255,255,0.02) !important; border: 0.5px solid rgba(255,255,255,0.07) !important; border-radius: 8px !important; }
hr { border-color: rgba(255,255,255,0.06) !important; }
</style>
""", unsafe_allow_html=True)


# ─── AUTH FUNCTIONS ───────────────────────────────────────────────────────────

def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            # Give 1 free token on signup
            try:
                supabase.table("users").upsert({"id": res.user.id, "tokens": 1}).execute()
            except:
                pass
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


def get_tokens(user_id):
    try:
        result = supabase.table("users").select("tokens").eq("id", user_id).execute()
        if result.data:
            return result.data[0].get("tokens", 0) or 0
        return 0
    except:
        return 0

def deduct_token(user_id):
    try:
        current = get_tokens(user_id)
        if current <= 0:
            return False
        supabase.table("users").update({"tokens": current - 1}).eq("id", user_id).execute()
        return True
    except:
        return False

def add_tokens(user_id, amount):
    try:
        current = get_tokens(user_id)
        supabase.table("users").upsert({"id": user_id, "tokens": current + amount}).execute()
        return True
    except:
        return False

def create_token_checkout(user_email, user_id, price_id, tokens):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            success_url="https://tiktok-analyser.streamlit.app?tokens_success=true",
            cancel_url="https://tiktok-analyser.streamlit.app?canceled=true",
            customer_email=user_email,
            metadata={"user_id": user_id, "tokens": str(tokens)},
        )
        return session.url
    except:
        return None


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
                "watchtime": item.get("videoMeta", {}).get("avgWatchTime", 0),
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

def save_analysis(user_id, username, nische, avg_views, engagement_rate, comparison_accounts, analysis_text, video_dates=None):
    try:
        supabase.table("analyses").insert({
            "user_id": user_id,
            "username": username,
            "nische": nische,
            "avg_views": avg_views,
            "engagement_rate": engagement_rate,
            "top_accounts": comparison_accounts,
            "analysis_text": analysis_text,
            "video_dates": video_dates or []
        }).execute()
    except Exception as e:
        st.warning(f"Speichern fehlgeschlagen: {e}")

def load_analyses(user_id):
    try:
        result = supabase.table("analyses").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return result.data
    except:
        return []


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fmt(n):
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def days_ago(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        d = (datetime.now(timezone.utc) - dt).days
        if d == 0: return "Heute"
        if d == 1: return "Gestern"
        return f"vor {d}d"
    except:
        return ""

def delta_pct(arr):
    if len(arr) >= 2 and arr[1]:
        return round(((arr[0] - arr[1]) / arr[1]) * 100, 1)
    return None


# ─── AUTH SCREEN ──────────────────────────────────────────────────────────────

def show_auth():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;padding:48px 0 28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;
                        color:rgba(232,230,224,0.2);margin-bottom:14px;">TikTok AI Analyzer</div>
            <div style="font-family:'Syne',sans-serif;font-size:30px;font-weight:800;
                        color:#e8e6e0;line-height:1.15;margin-bottom:10px;">
                Versteh deinen Content.<br>Wirklich.
            </div>
            <div style="font-size:13px;color:rgba(232,230,224,0.35);margin-bottom:36px;">
                KI-gestützte Analyse mit Konkurrenzvergleich
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Einloggen", "Registrieren"])
        with tab1:
            email = st.text_input("Email", key="login_email", placeholder="deine@email.com")
            password = st.text_input("Passwort", type="password", key="login_password", placeholder="••••••••")
            if st.button("Einloggen →", type="primary", use_container_width=True):
                if email and password:
                    user, session, error = sign_in(email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.session = session
                        st.rerun()
                    else:
                        st.error("Login fehlgeschlagen — Email oder Passwort falsch.")
        with tab2:
            email = st.text_input("Email", key="signup_email", placeholder="deine@email.com")
            password = st.text_input("Passwort (min. 6 Zeichen)", type="password", key="signup_password", placeholder="••••••••")
            if st.button("Kostenlos starten →", type="primary", use_container_width=True):
                if email and password:
                    user, error = sign_up(email, password)
                    if user:
                        st.success("✅ Account erstellt!")
                        st.info("📧 Wir haben dir eine Bestätigungs-Email geschickt. Bitte bestätige deine Email bevor du dich einloggst.")
                    else:
                        st.error(f"Fehler: {error}")

        st.markdown("""
        <div style="text-align:center;margin-top:18px;">
            <span style="font-size:11px;color:rgba(232,230,224,0.18);">
                ✓ 1 kostenlose Analyse &nbsp;·&nbsp; ✓ Kein Abo nötig &nbsp;·&nbsp; ✓ Premium ab 19€/Mo
            </span>
        </div>
        """, unsafe_allow_html=True)


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def show_dashboard(user_id, user_email, premium, analyses):
    import plotly.graph_objects as go

    latest = analyses[0] if analyses else None
    all_avg_views = [a["avg_views"] for a in analyses if a.get("avg_views")]
    all_eng = [float(a["engagement_rate"]) for a in analyses if a.get("engagement_rate")]

    views_delta = delta_pct(all_avg_views)
    eng_delta = delta_pct(all_eng)

    # ── HEADER ──
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:20px 2px 14px;border-bottom:0.5px solid rgba(255,255,255,0.05);margin-bottom:22px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span class="live-indicator"></span>
            <span style="font-size:11px;font-weight:700;letter-spacing:0.14em;
                          text-transform:uppercase;color:rgba(232,230,224,0.25);">Live Dashboard</span>
        </div>
        <div style="font-size:11px;color:rgba(232,230,224,0.18);font-family:'DM Mono',monospace;">
            {len(analyses)} Analysen gespeichert
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not latest:
        st.info("Noch keine Analyse vorhanden. Starte deine erste Analyse!")
        return

    # ── TÄGLICHE KI ANWEISUNG ──
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    briefing_key = f"daily_briefing_v2_{latest.get('id','')}_{today_str}"
    cached_briefing = st.session_state.get(briefing_key)
    # Invalidate old format (HTML or multi-line cards)
    if cached_briefing and "::" not in cached_briefing:
        del st.session_state[briefing_key]
        cached_briefing = None

    # Gather data for briefing
    video_dates_raw = latest.get("video_dates") or []
    top_videos = sorted(video_dates_raw, key=lambda x: x.get("views", 0), reverse=True)[:5]
    flop_videos = sorted(video_dates_raw, key=lambda x: x.get("views", 0))[:5]

    # Best posting hours from top videos
    hour_views = {}
    for v in video_dates_raw:
        try:
            dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
            h = dt.hour
            hour_views.setdefault(h, []).append(v.get("views", 0))
        except:
            pass
    best_hours = sorted(hour_views.keys(), key=lambda h: sum(hour_views[h])/len(hour_views[h]), reverse=True)[:3] if hour_views else []
    best_hours_str = " · ".join([f"{h}:00 Uhr" for h in sorted(best_hours)]) if best_hours else "Daten fehlen noch"

    # Auto-generate if not cached
    if not cached_briefing:
        try:
            briefing_prompt = f"""Du bist ein viraler TikTok-Stratege spezialisiert auf emotionale Hooks und Pattern Interrupts.

ACCOUNT DATEN:
- Account: @{latest.get('username','—')}
- Nische: {latest.get('nische','—')}
- Ø Views: {fmt(latest.get('avg_views'))}
- Beste Posting-Zeit: {best_hours_str}
- Top Videos (was funktioniert hat): {json.dumps(top_videos[:3], ensure_ascii=False)}
- Flop Videos (was nicht funktioniert hat): {json.dumps(flop_videos[:3], ensure_ascii=False)}

HOOK-REGELN — PFLICHT:
- Die Account-Nische ist "{latest.get('nische','—')}" — der Hook MUSS thematisch zu DIESER Nische passen, egal ob Sport, Business, Beauty, Comedy, Food, Gaming, Reisen oder irgendetwas anderes
- NIEMALS informative Hooks ("Hier sind 3 Tipps...")
- IMMER emotional, unerwartet oder mitten in einer Szene
- Nutze das große Projekt/Ziel des Accounts falls aus den Daten erkennbar
- Verbinde mit aktuellen Trends oder Ereignissen wenn passend
- Der Hook soll eine Frage im Kopf erzeugen die man beantworten will
- KRITISCH: Erfinde NIEMALS konkrete Fakten, Zahlen, Distanzen oder Ereignisse die nicht aus den Account-Daten oben hervorgehen. Beschreibe stattdessen ein Gefühl, einen Gedanken oder eine Handlung — keine erfundene Kilometerzahl oder erfundenes Detail.
- WICHTIG FÜR VARIATION: Wähle bei jeder Generierung eine andere Perspektive/Emotion (z.B. abwechselnd: Zweifel, Stolz, Wut, Erschöpfung, Entschlossenheit, Selbstironie, Vorfreude, Einsamkeit). Wiederhole nicht denselben Satzbau wie "Mein Körper sagte X — ich Y". Variiere Tonfall, Satzlänge und Blickwinkel deutlich von Versuch zu Versuch.

HOOK-TYPEN als Stilvorbild — wähle den Typ der zur Nische "{latest.get('nische','—')}" passt, die Beispiel-Themen sind nur Inspiration für den TON, nicht zum Kopieren:
- Mitten in einer dramatischen Szene ohne erfundene Zahl (Sport: "Mein Körper sagte Stopp — ich nicht" / Business: "Der Kunde sagte nein — ich hab nicht aufgelegt" / Beauty: "Ich hab geweint vorm Spiegel — heute zeig ich warum")
- Emotionale Offenbarung — passend zur Nische formuliert
- Unerwarteter Kontrast (Alter, Erfahrung, Erwartung vs. Realität) — passend zur Nische
- Direkte Provokation ("Die meisten geben hier auf — ich nicht")
- Selbstironisch — eigene Schwäche zugeben, passend zur Nische
- Stille Beobachtung ("Niemand sieht diesen Teil von [Tätigkeit aus der Nische]")

Antworte NUR in exakt diesem Format, keine Abweichungen, kein Intro:

HOOK::[fertiger Hook-Satz, max 12 Wörter, emotional und unerwartet]
ZEIT::[Uhrzeit, z.B. 17:00 Uhr]
FORMAT::[z.B. 18–25 Sek · schnelle Cuts · authentisch]
HASHTAGS::[8 Hashtags mit #, durch Leerzeichen getrennt]
AKTION::[Eine konkrete Sache heute anders machen, max 1 Satz]

Nur diese 5 Zeilen. Kein weiterer Text.

(Variations-Anker, nicht erwähnen: {random.choice(['Zweifel','Stolz','Wut','Erschöpfung','Entschlossenheit','Selbstironie','Vorfreude','Einsamkeit','Trotz','Erleichterung'])})"""

            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                temperature=1.0,
                messages=[{"role": "user", "content": briefing_prompt}]
            )
            cached_briefing = msg.content[0].text.strip()
            st.session_state[briefing_key] = cached_briefing
        except:
            cached_briefing = None

    # Parse compact format
    def parse_briefing(text):
        result = {}
        for line in (text or "").split("\n"):
            if "::" in line:
                key, val = line.split("::", 1)
                result[key.strip()] = val.strip()
        return result

    parsed = parse_briefing(cached_briefing)

    today_display = datetime.now(timezone.utc).strftime("%a, %d. %b")

    st.markdown('<div class="section-label">Heutige Anweisung</div>', unsafe_allow_html=True)

    if parsed.get("HOOK"):
        hashtags = parsed.get("HASHTAGS", "")
        hashtags_html = " ".join([
            f'<span style="color:rgba(232,230,224,0.35);font-size:11px;">{h}</span>'
            for h in hashtags.split() if h.startswith("#")
        ])
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.02);border:0.5px solid rgba(255,255,255,0.07);
                    border-radius:12px;padding:22px 26px;margin-bottom:6px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                            color:rgba(232,230,224,0.25);">{today_display}</div>
                <div style="font-size:11px;color:rgba(232,230,224,0.2);font-family:'DM Mono',monospace;">
                    @{latest.get('username','—')} · {latest.get('nische','—')[:30]}
                </div>
            </div>
            <div style="font-size:20px;font-weight:700;color:#e8e6e0;line-height:1.3;margin-bottom:20px;">
                🎣 &nbsp;{parsed.get('HOOK','—')}
            </div>
            <div style="display:flex;align-items:center;gap:24px;padding:14px 0;
                        border-top:0.5px solid rgba(255,255,255,0.05);
                        border-bottom:0.5px solid rgba(255,255,255,0.05);margin-bottom:16px;">
                <div>
                    <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                                color:rgba(232,230,224,0.25);margin-bottom:4px;">Jetzt posten</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;color:#e8e6e0;">
                        ⏰ &nbsp;{parsed.get('ZEIT','—')}
                    </div>
                </div>
                <div style="width:0.5px;height:32px;background:rgba(255,255,255,0.07);"></div>
                <div>
                    <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                                color:rgba(232,230,224,0.25);margin-bottom:4px;">Format</div>
                    <div style="font-size:13px;color:rgba(232,230,224,0.6);">
                        🎬 &nbsp;{parsed.get('FORMAT','—')}
                    </div>
                </div>
            </div>
            <div style="margin-bottom:14px;">{hashtags_html}</div>
            <div style="background:rgba(255,77,77,0.04);border:0.5px solid rgba(255,77,77,0.15);
                        border-radius:8px;padding:10px 14px;">
                <span style="font-size:11px;font-weight:700;color:rgba(255,77,77,0.7);
                             letter-spacing:0.06em;text-transform:uppercase;margin-right:8px;">⚡ Heute</span>
                <span style="font-size:12px;color:rgba(232,230,224,0.6);">{parsed.get('AKTION','—')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Fallback: delete bad cache and show button to retry
        if briefing_key in st.session_state:
            del st.session_state[briefing_key]
        st.markdown("""
        <div style="background:rgba(255,255,255,0.02);border:0.5px solid rgba(255,255,255,0.07);
                    border-radius:10px;padding:20px;text-align:center;">
            <div style="font-size:13px;color:rgba(232,230,224,0.3);margin-bottom:12px;">
                Anweisung konnte nicht geladen werden.
            </div>
        </div>
        """, unsafe_allow_html=True)

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Neue Anweisung", key="refresh_briefing"):
            if briefing_key in st.session_state:
                del st.session_state[briefing_key]
            st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── CONTENT PLANNER ──
    st.markdown('<div class="section-label">Content Planer — Was machst du heute?</div>', unsafe_allow_html=True)

    planner_input = st.text_input(
        "Beschreib kurz deinen Tag",
        placeholder="z.B. 25km Longrun morgens, danach Meal Prep, abends am Laptop",
        label_visibility="collapsed",
        key="planner_input"
    )

    planner_key = f"planner_{today_str}_{hash(planner_input)}"

    if planner_input and len(planner_input) > 5:
        col_btn1, col_btn2 = st.columns([2, 2])
        with col_btn1:
            find_moments = st.button("🎬 Beste Video-Momente finden", type="primary", key="planner_btn", use_container_width=True)
        with col_btn2:
            update_hook = st.button("🎣 Hook auf meinen Tag anpassen", key="update_hook_btn", use_container_width=True)

        if update_hook:
            with st.spinner("Hook wird angepasst..."):
                try:
                    hook_update_prompt = f"""Du bist ein viraler TikTok-Stratege.

ACCOUNT: @{latest.get('username','—')} | Nische: {latest.get('nische','—')}
Heute: {planner_input}

Erstelle eine angepasste Tagesanweisung basierend auf dem heutigen Tag.
Nutze konkrete Momente aus dem Tag für den Hook.

Antworte NUR in exakt diesem Format:
HOOK::[fertiger Hook-Satz, max 12 Wörter, emotional, basierend auf dem heutigen Tag]
ZEIT::[beste Uhrzeit heute]
FORMAT::[Videolänge · Stil · Ton]
HASHTAGS::[8 Hashtags mit #]
AKTION::[Eine konkrete Sache heute, basierend auf dem Tag]

Nur diese 5 Zeilen. Kein weiterer Text."""

                    msg = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=300,
                        messages=[{"role": "user", "content": hook_update_prompt}]
                    )
                    new_briefing = msg.content[0].text.strip()
                    st.session_state[briefing_key] = new_briefing
                    st.success("✅ Hook angepasst!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")
    else:
        find_moments = False

    if planner_input and len(planner_input) > 5:
        if find_moments:
            with st.spinner("KI analysiert deinen Tag..."):
                try:
                    planner_prompt = f"""Du bist ein viraler TikTok Content Stratege.

ACCOUNT: @{latest.get('username','—')} | Nische: {latest.get('nische','—')} | Ø Views: {fmt(latest.get('avg_views'))}

Der Creator hat heute folgendes vor:
{planner_input}

Identifiziere genau 3 VIDEO-MOMENTE aus diesem Tag die viral gehen können.
Nur die 3 besten — nicht mehr.

Für jeden Moment:
- Welcher genaue Moment im Tag (konkret)
- Warum dieser Moment viral gehen kann (1 Satz)
- Fertiger Hook-Satz (emotional, max 10 Wörter)

REGELN:
- Nur Momente die wirklich im Text vorkommen
- Emotional und unerwartet — kein "ich zeige euch wie ich..."
- Nutze Pattern Interrupts und Dramatik

Antworte in diesem Format:
MOMENT1::
WARUM1::
HOOK1::
MOMENT2::
WARUM2::
HOOK2::
MOMENT3::
WARUM3::
HOOK3::

Kein weiterer Text."""

                    msg = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=600,
                        messages=[{"role": "user", "content": planner_prompt}]
                    )
                    planner_result = msg.content[0].text.strip()
                    st.session_state[planner_key] = planner_result
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")

        # Render result
        if st.session_state.get(planner_key):
            result = st.session_state[planner_key]

            # Parse multiline format: KEY:: auf einer Zeile, Wert auf nächster
            lines = {}
            raw_lines = [l.strip() for l in result.split("\n") if l.strip()]
            current_key = None
            for line in raw_lines:
                if line.endswith("::"):
                    current_key = line[:-2].strip()
                    lines[current_key] = ""
                elif "::" in line:
                    k, v = line.split("::", 1)
                    lines[k.strip()] = v.strip()
                    current_key = k.strip()
                elif current_key:
                    lines[current_key] = (lines[current_key] + " " + line).strip()

            moments = []
            for i in range(1, 4):
                m = lines.get(f"MOMENT{i}") or lines.get(f"MOMENT {i}")
                w = lines.get(f"WARUM{i}") or lines.get(f"WARUM {i}")
                h = lines.get(f"HOOK{i}") or lines.get(f"HOOK {i}")
                if h:
                    moments.append({"moment": m or "—", "warum": w or "—", "hook": h})

            if moments:
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                cols = st.columns(len(moments))
                for i, (col, m) in enumerate(zip(cols, moments)):
                    with col:
                        done = st.checkbox(f"Erledigt", key=f"planner_done_{i}_{today_str}")
                        opacity = "0.3" if done else "1"
                        text_deco = "line-through" if done else "none"
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02);border:0.5px solid {'rgba(29,158,117,0.3)' if done else 'rgba(255,255,255,0.07)'};
                                    border-radius:10px;padding:18px;opacity:{opacity};transition:all 0.2s;">
                            <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                                        color:rgba(232,230,224,0.2);margin-bottom:8px;">Video {i+1}</div>
                            <div style="font-size:15px;font-weight:700;color:#e8e6e0;line-height:1.3;margin-bottom:10px;text-decoration:{text_deco};">
                                🎣 {m['hook']}
                            </div>
                            <div style="font-size:11px;color:rgba(232,230,224,0.4);margin-bottom:6px;">
                                📍 {m['moment']}
                            </div>
                            <div style="font-size:11px;color:rgba(29,158,117,0.8);font-style:italic;">
                                {m['warum']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── HERO METRICS ──
    st.markdown('<div class="section-label">Performance — Letzte Analyse</div>', unsafe_allow_html=True)

    total_views_est = int(latest.get("avg_views", 0) or 0) * 30
    total_likes_est = int(round(total_views_est * float(latest.get("engagement_rate", 0) or 0) / 100))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="metric-accent-red"></div>', unsafe_allow_html=True)
        st.metric("GESAMT VIEWS", fmt(total_views_est),
                  delta=f"{views_delta:+.1f}%" if views_delta is not None else None)
    with c2:
        st.markdown('<div class="metric-accent-amber"></div>', unsafe_allow_html=True)
        st.metric("GESAMT LIKES", fmt(total_likes_est))
    with c3:
        st.markdown('<div class="metric-accent-teal"></div>', unsafe_allow_html=True)
        st.metric("ENGAGEMENT",
                  f"{latest.get('engagement_rate', '—')}%",
                  delta=f"{eng_delta:+.1f}%" if eng_delta is not None else None)
    with c4:
        st.markdown('<div class="metric-accent-blue"></div>', unsafe_allow_html=True)
        st.metric("Ø VIEWS / VIDEO", fmt(latest.get("avg_views")))

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    # ── ROW 4: STREAK TRACKER + KALENDER + KI COACHING ──
    st.markdown('<div class="section-label">Posting Streak & KI Coaching</div>', unsafe_allow_html=True)

    # Collect all video dates from latest analysis
    video_dates_raw = latest.get("video_dates") or []

    # Parse dates
    posting_days = set()
    views_by_day = {}
    for v in video_dates_raw:
        try:
            dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
            day_str = dt.strftime("%Y-%m-%d")
            posting_days.add(day_str)
            views_by_day[day_str] = views_by_day.get(day_str, 0) + int(v.get("views", 0))
        except:
            pass

    # Streak calculation
    today = datetime.now(timezone.utc).date()
    streak = 0
    check_day = today
    while str(check_day) in posting_days:
        streak += 1
        check_day = check_day.replace(day=check_day.day - 1) if check_day.day > 1 else (
            check_day.replace(month=check_day.month - 1, day=28) if check_day.month > 1
            else check_day.replace(year=check_day.year - 1, month=12, day=28)
        )

    total_posts = len(video_dates_raw)
    active_days = len(posting_days)
    avg_views_per_day = int(sum(views_by_day.values()) / max(active_days, 1))

    col_streak, col_cal, col_coach = st.columns([1, 1.6, 1.4])

    with col_streak:
        st.markdown('<div class="db-panel" style="height:100%">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:16px;">Posting Streak</div>', unsafe_allow_html=True)

        streak_color = "#ff4d4d" if streak >= 7 else "#f5a623" if streak >= 3 else "#1d9e75" if streak >= 1 else "rgba(232,230,224,0.2)"
        st.markdown(f"""
        <div style="text-align:center;padding:10px 0 16px;">
            <div style="font-family:'DM Mono',monospace;font-size:52px;font-weight:500;color:{streak_color};line-height:1;">
                {streak}
            </div>
            <div style="font-size:11px;color:rgba(232,230,224,0.3);margin-top:4px;letter-spacing:0.06em;">
                {'🔥 Tage in Folge' if streak > 0 else 'Heute noch posten!'}
            </div>
        </div>
        <div style="border-top:0.5px solid rgba(255,255,255,0.05);padding-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div style="text-align:center;">
                <div style="font-family:'DM Mono',monospace;font-size:18px;color:#e8e6e0;">{total_posts}</div>
                <div style="font-size:10px;color:rgba(232,230,224,0.25);margin-top:2px;">Videos gesamt</div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'DM Mono',monospace;font-size:18px;color:#e8e6e0;">{active_days}</div>
                <div style="font-size:10px;color:rgba(232,230,224,0.25);margin-top:2px;">Posting-Tage</div>
            </div>
        </div>
        <div style="margin-top:12px;text-align:center;">
            <div style="font-family:'DM Mono',monospace;font-size:16px;color:#e8e6e0;">{fmt(avg_views_per_day)}</div>
            <div style="font-size:10px;color:rgba(232,230,224,0.25);margin-top:2px;">Ø Views pro Post-Tag</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_cal:
        st.markdown('<div class="db-panel" style="height:100%">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:14px;">Kalender — Letzte 42 Tage</div>', unsafe_allow_html=True)

        # Build 6-week calendar
        from datetime import timedelta
        cal_start = today - timedelta(days=41)
        weeks = []
        week = []
        cur = cal_start
        # Align to Monday
        weekday_offset = cal_start.weekday()
        for _ in range(weekday_offset):
            week.append(None)
        while cur <= today:
            week.append(cur)
            if len(week) == 7:
                weeks.append(week)
                week = []
            cur += timedelta(days=1)
        if week:
            while len(week) < 7:
                week.append(None)
            weeks.append(week)

        day_labels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        cal_html = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin-bottom:8px;">'
        for dl in day_labels:
            cal_html += f'<div style="text-align:center;font-size:9px;color:rgba(232,230,224,0.2);font-weight:700;letter-spacing:0.06em;padding-bottom:2px;">{dl}</div>'
        cal_html += '</div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;">'

        for week in weeks:
            for day in week:
                if day is None:
                    cal_html += '<div></div>'
                    continue
                day_str = str(day)
                is_today = day == today
                has_post = day_str in posting_days
                views = views_by_day.get(day_str, 0)

                if is_today:
                    bg = "rgba(55,138,221,0.3)"
                    border = "rgba(55,138,221,0.6)"
                elif has_post:
                    # Color intensity by views
                    max_v = max(views_by_day.values()) if views_by_day else 1
                    intensity = min(views / max_v, 1.0)
                    r = int(29 + (255-29) * (1-intensity))
                    g = int(158 * intensity)
                    b = int(117 * intensity)
                    bg = f"rgba({255-int(226*intensity)},{int(158*intensity)},{int(117*intensity)},0.7)"
                    bg = f"rgba(29,158,117,{0.25 + intensity * 0.65:.2f})"
                    border = "rgba(29,158,117,0.4)"
                else:
                    bg = "rgba(255,255,255,0.03)"
                    border = "rgba(255,255,255,0.06)"

                tooltip = f"{views:,} Views" if has_post else "Kein Post"
                cal_html += f'<div title="{day.day}. — {tooltip}" style="aspect-ratio:1;background:{bg};border:0.5px solid {border};border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:9px;font-family:DM Mono,monospace;color:rgba(232,230,224,{0.7 if has_post or is_today else 0.2});">{day.day}</div>'

        cal_html += '</div>'
        cal_html += """
        <div style="display:flex;align-items:center;gap:16px;margin-top:12px;">
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:10px;height:10px;border-radius:2px;background:rgba(29,158,117,0.8);"></div>
                <span style="font-size:10px;color:rgba(232,230,224,0.3);">Gepostet</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:10px;height:10px;border-radius:2px;background:rgba(255,255,255,0.03);border:0.5px solid rgba(255,255,255,0.1);"></div>
                <span style="font-size:10px;color:rgba(232,230,224,0.3);">Kein Post</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
                <div style="width:10px;height:10px;border-radius:2px;background:rgba(55,138,221,0.3);border:0.5px solid rgba(55,138,221,0.6);"></div>
                <span style="font-size:10px;color:rgba(232,230,224,0.3);">Heute</span>
            </div>
        </div>"""
        st.markdown(cal_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_coach:
        st.markdown('<div class="db-panel" style="height:100%">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:14px;">KI Coaching</div>', unsafe_allow_html=True)

        coaching_key = f"coaching_{latest.get('id','')}"
        cached_coaching = st.session_state.get(coaching_key)

        if cached_coaching:
            st.markdown(f'<div style="font-size:13px;color:rgba(232,230,224,0.75);line-height:1.7;">{cached_coaching}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="font-size:12px;color:rgba(232,230,224,0.35);line-height:1.7;margin-bottom:14px;">
                Basierend auf deinen letzten Daten:<br>
                <span style="color:rgba(232,230,224,0.55);">Ø {fmt(latest.get('avg_views'))} Views · {latest.get('engagement_rate','—')}% Eng · {active_days} Posting-Tage · Streak: {streak}</span>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🤖 KI Coaching generieren", type="primary", use_container_width=True):
                with st.spinner("KI analysiert deine Daten..."):
                    try:
                        top_videos_info = sorted(video_dates_raw, key=lambda x: x.get("views", 0), reverse=True)[:3]
                        coaching_prompt = f"""Du bist ein TikTok Growth Coach. Gib kurze, direkte Wachstumsempfehlungen für diese Woche.

DATEN:
- Account: @{latest.get('username','—')}
- Nische: {latest.get('nische','—')}
- Ø Views: {fmt(latest.get('avg_views'))}
- Engagement: {latest.get('engagement_rate','—')}%
- Posting-Streak: {streak} Tage
- Aktive Posting-Tage (letzte 30d): {active_days}
- Top 3 Videos: {json.dumps(top_videos_info, ensure_ascii=False)}

Gib genau 4 konkrete Empfehlungen für diese Woche. Jede Empfehlung max. 2 Sätze.
Format: Nummerierte Liste, direkt und actionable. Kein Intro, keine Zusammenfassung. Auf Deutsch."""
                        msg = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=500,
                            messages=[{"role": "user", "content": coaching_prompt}]
                        )
                        coaching_text = msg.content[0].text
                        st.session_state[coaching_key] = coaching_text
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    # ── ROW 5: TOP / FLOP VIDEOS ──
    st.markdown('<div class="section-label">Top & Flop Videos — Letzte Analyse</div>', unsafe_allow_html=True)

    col_top, col_flop = st.columns(2)
    last_top = st.session_state.get("last_top_videos", [])
    last_flop = st.session_state.get("last_flop_videos", [])

    def video_list_html(videos, empty_msg):
        if not videos:
            return f'<div style="color:rgba(232,230,224,0.18);font-size:12px;text-align:center;padding:20px 0;">{empty_msg}</div>'
        out = ""
        for i, v in enumerate(videos[:5]):
            title = (v.get("beschreibung") or "")[:52] or "(kein Titel)"
            views = fmt(v.get("views", 0))
            eng = round((v.get("likes", 0) / max(v.get("views", 1), 1) * 100), 1)
            datum = days_ago(v.get("datum", ""))
            out += f"""
            <div class="video-item">
                <span class="video-rank">0{i+1}</span>
                <div style="flex:1;min-width:0;">
                    <div class="video-title">{title}</div>
                    <div style="font-size:10px;color:rgba(232,230,224,0.2);font-family:'DM Mono',monospace;margin-top:2px;">{datum}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div class="video-views">{views}</div>
                    <div class="video-eng">{eng}%</div>
                </div>
            </div>"""
        return out

    with col_top:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">🏆 Top Videos</div>', unsafe_allow_html=True)
        st.markdown(video_list_html(last_top, "Daten nach nächster Analyse verfügbar"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_flop:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">📉 Flop Videos</div>', unsafe_allow_html=True)
        st.markdown(video_list_html(last_flop, "Daten nach nächster Analyse verfügbar"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    # ── ROW 5: ALLE ANALYSEN ──
    st.markdown('<div class="section-label">Alle gespeicherten Analysen</div>', unsafe_allow_html=True)

    for a in analyses:
        with st.expander(f"📅 {a['created_at'][:10]}  ·  @{a['username']}  ·  {fmt(a['avg_views'])} Ø Views  ·  {a.get('engagement_rate','—')}% Eng"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<div style="font-size:10px;color:rgba(232,230,224,0.3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Nische</div><div style="font-size:14px;color:#e8e6e0;">{a.get("nische","—")}</div>', unsafe_allow_html=True)
            with c2:
                accs = ", ".join(a["top_accounts"]) if a.get("top_accounts") else "—"
                st.markdown(f'<div style="font-size:10px;color:rgba(232,230,224,0.3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Verglichene Accounts</div><div style="font-size:12px;font-family:DM Mono,monospace;color:rgba(232,230,224,0.6);">{accs}</div>', unsafe_allow_html=True)
            st.markdown(a.get("analysis_text", ""))
            st.download_button(
                "📥 Analyse downloaden",
                data=a.get("analysis_text", ""),
                file_name=f"analyse_{a['username']}_{a['created_at'][:10]}.txt",
                key=f"dl_{a['id']}"
            )


# ─── QUICK REFRESH ────────────────────────────────────────────────────────────

def quick_refresh(user_id, username):
    """Scrapt nur den eigenen Account, aktualisiert video_dates + metrics in Supabase. Kein Vergleich, keine KI."""
    with st.spinner(f"Quick Refresh für @{username}..."):
        data = scrape_tiktok_account(username)
    if not data:
        st.error("Account nicht erreichbar.")
        return False

    videos = extract_video_data(data)
    newest = videos.get("newest_30", [])
    all_videos = videos.get("all", [])

    if not newest:
        st.error("Keine Videos gefunden.")
        return False

    total_views = sum(v["views"] for v in newest)
    total_likes = sum(v["likes"] for v in newest)
    avg_views = total_views // len(newest)
    engagement = round((total_likes / total_views * 100) if total_views > 0 else 0, 2)
    video_dates_list = [{"datum": v["datum"], "views": v["views"], "beschreibung": (v.get("beschreibung") or "")[:80]} for v in all_videos if v.get("datum")]

    # Get latest analysis to update
    try:
        result = supabase.table("analyses").select("id, nische, top_accounts, analysis_text").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        if result.data:
            latest_id = result.data[0]["id"]
            supabase.table("analyses").update({
                "avg_views": avg_views,
                "engagement_rate": engagement,
                "video_dates": video_dates_list,
            }).eq("id", latest_id).execute()
        else:
            st.error("Keine bestehende Analyse gefunden. Mach zuerst eine vollständige Analyse.")
            return False
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

    # Update session state
    st.session_state["last_top_videos"] = videos.get("top_10", [])
    st.session_state["last_flop_videos"] = videos.get("bottom_10", [])

    # Watchtime
    watchtime_vals = [v.get("watchtime", 0) for v in newest if v.get("watchtime")]
    dur_vals = [v.get("dauer", 0) for v in newest if v.get("dauer")]
    if watchtime_vals:
        avg_wt = sum(watchtime_vals) / len(watchtime_vals)
        avg_dur_v = sum(dur_vals) / len(dur_vals) if dur_vals else 0
        by_dur = {}
        for v in newest:
            d = v.get("dauer", 0)
            wt = v.get("watchtime", 0)
            if d > 0 and wt > 0:
                bucket = "<10s" if d < 10 else "10-20s" if d < 20 else "20-30s" if d < 30 else "30-60s" if d < 60 else ">60s"
                by_dur.setdefault(bucket, []).append(wt / d * 100)
        st.session_state["last_watchtime"] = {
            "avg_watchtime": round(avg_wt, 1),
            "avg_duration": round(avg_dur_v, 1),
            "best_watchtime": round(max(watchtime_vals), 1),
            "dropoff_sec": round(avg_wt, 0),
            "by_duration": {k: round(sum(vals)/len(vals), 1) for k, vals in by_dur.items()},
        }

    return True, avg_views, engagement


# ─── ANALYTICS PAGE ───────────────────────────────────────────────────────────

def show_analytics(user_id, analyses):
    import plotly.graph_objects as go

    latest = analyses[0] if analyses else None

    PLOTLY_LAYOUT = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono", color="rgba(232,230,224,0.35)", size=10),
        margin=dict(l=0, r=4, t=6, b=0),
        showlegend=False, hovermode="x unified",
    )
    AXIS_X = dict(showgrid=False, zeroline=False, tickformat="%d.%m", tickfont=dict(size=10))
    AXIS_Y = dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", zeroline=False, tickfont=dict(size=10))

    st.markdown("""
    <div style="padding:20px 2px 14px;border-bottom:0.5px solid rgba(255,255,255,0.05);margin-bottom:22px;">
        <div style="font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;
                    color:rgba(232,230,224,0.25);">Analytics</div>
    </div>
    """, unsafe_allow_html=True)

    if not latest:
        st.info("Erst eine Analyse starten.")
        return

    # ── PERFORMANCE CHARTS ──
    st.markdown('<div class="section-label">Performance-Verlauf</div>', unsafe_allow_html=True)

    if len(analyses) > 1:
        df = pd.DataFrame([{
            "Datum": a["created_at"][:10],
            "Ø Views": a.get("avg_views", 0) or 0,
            "Engagement %": float(a.get("engagement_rate", 0) or 0)
        } for a in reversed(analyses)])
        df["Datum"] = pd.to_datetime(df["Datum"])

        col_v, col_e = st.columns(2)
        with col_v:
            st.markdown('<div class="db-panel">', unsafe_allow_html=True)
            fig_v = go.Figure()
            fig_v.add_trace(go.Scatter(
                x=df["Datum"], y=df["Ø Views"],
                mode="lines+markers",
                line=dict(color="#ff4d4d", width=2),
                marker=dict(size=5, color="#ff4d4d", line=dict(color="#0a0a0b", width=2)),
                fill="tozeroy", fillcolor="rgba(255,77,77,0.06)",
                hovertemplate="%{y:,.0f} Views<extra></extra>",
            ))
            fig_v.update_layout(**PLOTLY_LAYOUT, height=180, xaxis={**AXIS_X}, yaxis={**AXIS_Y, "tickformat": ",d"})
            st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:8px;">Ø Views über Zeit</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_v, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

        with col_e:
            st.markdown('<div class="db-panel">', unsafe_allow_html=True)
            fig_e = go.Figure()
            fig_e.add_trace(go.Scatter(
                x=df["Datum"], y=df["Engagement %"],
                mode="lines+markers",
                line=dict(color="#1d9e75", width=2),
                marker=dict(size=5, color="#1d9e75", line=dict(color="#0a0a0b", width=2)),
                fill="tozeroy", fillcolor="rgba(29,158,117,0.06)",
                hovertemplate="%{y:.2f}%<extra></extra>",
            ))
            fig_e.update_layout(**PLOTLY_LAYOUT, height=180, xaxis={**AXIS_X}, yaxis={**AXIS_Y, "ticksuffix": "%"})
            st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:8px;">Engagement Rate</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_e, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Mindestens 2 Analysen für Verlauf nötig.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── ACCOUNT VERGLEICH ──
    st.markdown('<div class="section-label">Account-Vergleich</div>', unsafe_allow_html=True)

    col_cmp, col_hist = st.columns([1, 1.3])

    with col_cmp:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">Verglichene Accounts</div>', unsafe_allow_html=True)
        if latest and latest.get("top_accounts"):
            my_views = int(latest.get("avg_views", 0) or 0)
            raw_accounts = latest.get("top_accounts", []) or []
            comp_accounts = [str(a) if not isinstance(a, str) else a for a in raw_accounts]
            username = latest.get("username", "du")
            all_bars = [{"label": f"@{username}", "views": my_views, "color": "#ff4d4d"}]
            for acc in comp_accounts[:4]:
                all_bars.append({"label": f"@{acc}", "views": None, "color": "rgba(255,255,255,0.12)"})
            max_views = max([b["views"] for b in all_bars if b["views"]], default=1)
            bars_html = ""
            for b in all_bars:
                pct = round((b["views"] / max_views) * 100) if b["views"] else 12
                val_str = fmt(b["views"]) if b["views"] else "n/a"
                bars_html += f"""<div class="compare-row">
                    <div class="compare-label"><span>{b['label']}</span>
                    <span style="color:{'#e8e6e0' if b['views'] else 'rgba(232,230,224,0.2)'};">{val_str}</span></div>
                    <div class="compare-track"><div style="width:{pct}%;height:100%;background:{b['color']};border-radius:3px;"></div></div>
                </div>"""
            st.markdown(bars_html, unsafe_allow_html=True)
            st.markdown(f'<div style="margin-top:14px;font-size:11px;color:rgba(232,230,224,0.3);">Nische: {latest.get("nische","—")}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:rgba(232,230,224,0.2);font-size:13px;text-align:center;padding:20px 0;">Keine Daten</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_hist:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">Zwei Analysen vergleichen</div>', unsafe_allow_html=True)
        if len(analyses) >= 2:
            opts_labels = [f"📅 {a['created_at'][:10]}  ·  @{a['username']}  ·  {fmt(a['avg_views'])} Ø Views" for a in analyses]
            col_sa, col_sb = st.columns(2)
            with col_sa:
                idx_a = st.selectbox("A", range(len(opts_labels)), format_func=lambda i: opts_labels[i], index=0, key="an_cmp_a", label_visibility="collapsed")
            with col_sb:
                idx_b = st.selectbox("B", range(len(opts_labels)), format_func=lambda i: opts_labels[i], index=min(1, len(analyses)-1), key="an_cmp_b", label_visibility="collapsed")
            a_data = analyses[idx_a]
            b_data = analyses[idx_b]
            def diff_badge(va, vb):
                if va is None or vb is None or float(vb or 0) == 0: return ""
                pct = round(((float(va) - float(vb)) / float(vb)) * 100, 1)
                color = "#1d9e75" if pct >= 0 else "#ff4d4d"
                return f'<span style="color:{color};font-family:DM Mono,monospace;font-size:11px;">{"+" if pct>=0 else ""}{pct}%</span>'
            rows = [
                ("Ø Views", fmt(a_data.get("avg_views")), fmt(b_data.get("avg_views")), diff_badge(a_data.get("avg_views"), b_data.get("avg_views"))),
                ("Engagement", f"{a_data.get('engagement_rate','—')}%", f"{b_data.get('engagement_rate','—')}%", diff_badge(a_data.get("engagement_rate"), b_data.get("engagement_rate"))),
                ("Account", f"@{a_data.get('username','—')}", f"@{b_data.get('username','—')}", ""),
                ("Datum", a_data["created_at"][:10], b_data["created_at"][:10], ""),
            ]
            tbl = '<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:8px;"><thead><tr>'
            for h, c in [("Metrik","rgba(232,230,224,0.2)"),("A","rgba(255,77,77,0.55)"),("B","rgba(55,138,221,0.55)"),("Δ","rgba(232,230,224,0.2)")]:
                align = "left" if h == "Metrik" else "right"
                tbl += f'<th style="text-align:{align};padding:7px 4px;font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:{c};border-bottom:0.5px solid rgba(255,255,255,0.06);">{h}</th>'
            tbl += "</tr></thead><tbody>"
            for label, va, vb, dlt in rows:
                tbl += f'<tr><td style="padding:8px 4px;color:rgba(232,230,224,0.35);border-bottom:0.5px solid rgba(255,255,255,0.04);">{label}</td><td style="text-align:right;padding:8px 4px;font-family:DM Mono,monospace;color:#e8e6e0;border-bottom:0.5px solid rgba(255,255,255,0.04);">{va}</td><td style="text-align:right;padding:8px 4px;font-family:DM Mono,monospace;color:rgba(232,230,224,0.45);border-bottom:0.5px solid rgba(255,255,255,0.04);">{vb}</td><td style="text-align:right;padding:8px 4px;border-bottom:0.5px solid rgba(255,255,255,0.04);">{dlt}</td></tr>'
            tbl += "</tbody></table>"
            st.markdown(tbl, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:rgba(232,230,224,0.2);font-size:13px;text-align:center;padding:20px 0;">Mindestens 2 Analysen nötig</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── WATCHTIME ──
    st.markdown('<div class="section-label">Watchtime-Analyse</div>', unsafe_allow_html=True)
    wt = st.session_state.get("last_watchtime", {})
    avg_wt = wt.get("avg_watchtime")
    avg_dur = wt.get("avg_duration")
    completion = round((avg_wt / avg_dur * 100), 1) if avg_wt and avg_dur and avg_dur > 0 else None
    best_wt = wt.get("best_watchtime")
    dropoff = wt.get("dropoff_sec")

    def wt_card(label, value, sub):
        return f'<div class="wt-card"><div class="wt-label">{label}</div><div class="wt-value">{value}</div><div class="wt-sub">{sub}</div></div>'

    st.markdown(f"""<div class="wt-grid">
        {wt_card("Ø Watchtime", f"{avg_wt:.1f}s" if avg_wt else "—", f"von Ø {avg_dur:.0f}s Länge" if avg_dur else "Nächste Analyse")}
        {wt_card("Completion Rate", f"{completion}%" if completion else "—", "Nischen-Schnitt: ~40%")}
        {wt_card("Bestes Video", f"{best_wt:.1f}s" if best_wt else "—", "Höchste Watchtime")}
        {wt_card("Drop-Off", f"Sek. {int(dropoff)}" if dropoff else "—", "Optimiere deinen Hook")}
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── TOP / FLOP + ALLE ANALYSEN ──
    last_top = st.session_state.get("last_top_videos", [])
    last_flop = st.session_state.get("last_flop_videos", [])

    def video_list_html(videos, empty_msg):
        if not videos:
            return f'<div style="color:rgba(232,230,224,0.18);font-size:12px;text-align:center;padding:16px 0;">{empty_msg}</div>'
        out = ""
        for i, v in enumerate(videos[:5]):
            title = (v.get("beschreibung") or "")[:52] or "(kein Titel)"
            views = fmt(v.get("views", 0))
            eng = round((v.get("likes", 0) / max(v.get("views", 1), 1) * 100), 1)
            datum = days_ago(v.get("datum", ""))
            out += f"""<div class="video-item">
                <span class="video-rank">0{i+1}</span>
                <div style="flex:1;min-width:0;">
                    <div class="video-title">{title}</div>
                    <div style="font-size:10px;color:rgba(232,230,224,0.2);font-family:'DM Mono',monospace;margin-top:2px;">{datum}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div class="video-views">{views}</div>
                    <div class="video-eng">{eng}%</div>
                </div>
            </div>"""
        return out

    st.markdown('<div class="section-label">Top & Flop Videos</div>', unsafe_allow_html=True)
    col_top, col_flop = st.columns(2)
    with col_top:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">🏆 Top Videos</div>', unsafe_allow_html=True)
        st.markdown(video_list_html(last_top, "Nach nächster Analyse verfügbar"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col_flop:
        st.markdown('<div class="db-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,230,224,0.25);margin-bottom:12px;">📉 Flop Videos</div>', unsafe_allow_html=True)
        st.markdown(video_list_html(last_flop, "Nach nächster Analyse verfügbar"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Alle gespeicherten Analysen</div>', unsafe_allow_html=True)
    for a in analyses:
        with st.expander(f"📅 {a['created_at'][:10]}  ·  @{a['username']}  ·  {fmt(a['avg_views'])} Ø Views  ·  {a.get('engagement_rate','—')}% Eng"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<div style="font-size:10px;color:rgba(232,230,224,0.3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Nische</div><div style="font-size:14px;color:#e8e6e0;">{a.get("nische","—")}</div>', unsafe_allow_html=True)
            with c2:
                accs = ", ".join(a["top_accounts"]) if a.get("top_accounts") else "—"
                st.markdown(f'<div style="font-size:10px;color:rgba(232,230,224,0.3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Accounts</div><div style="font-size:12px;font-family:DM Mono,monospace;color:rgba(232,230,224,0.6);">{accs}</div>', unsafe_allow_html=True)
            st.markdown(a.get("analysis_text", ""))
            st.download_button("📥 Download", data=a.get("analysis_text",""), file_name=f"analyse_{a['username']}_{a['created_at'][:10]}.txt", key=f"dl_{a['id']}")


# ─── MAIN APP ─────────────────────────────────────────────────────────────────

def show_app():
    user = st.session_state.user
    user_id = user.id
    user_email = user.email
    premium = is_premium(user_id)
    used_free = has_used_free_analysis(user_id)

    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-user">
            <div class="sidebar-email">{user_email}</div>
            {'<span class="sidebar-badge-premium">⚡ Premium</span>' if premium else '<span class="sidebar-badge-free">Free</span>'}
        </div>
        """, unsafe_allow_html=True)

        if premium:
            page = st.radio("", ["🔍 Neue Analyse", "📊 Dashboard", "📈 Analytics"], label_visibility="collapsed")
        else:
            page = "🔍 Neue Analyse"

        # Quick Refresh — nur für Premium auf Dashboard
        if premium and page == "📊 Dashboard":
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown("""
            <div style="background:rgba(255,255,255,0.02);border:0.5px solid rgba(255,255,255,0.06);
                        border-radius:8px;padding:12px 14px;margin-bottom:4px;">
                <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                            color:rgba(232,230,224,0.25);margin-bottom:6px;">Quick Refresh</div>
                <div style="font-size:11px;color:rgba(232,230,224,0.3);line-height:1.7;margin-bottom:10px;">
                    Nur dein Account — kein Vergleich.<br>~30 Sek · täglich nutzen
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Get username from latest analysis
            try:
                latest_result = supabase.table("analyses").select("username").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
                qr_username = latest_result.data[0]["username"] if latest_result.data else None
            except:
                qr_username = None

            if qr_username:
                if st.button(f"⚡ @{qr_username} refreshen", use_container_width=True, key="quick_refresh_btn"):
                    result = quick_refresh(user_id, qr_username)
                    if result and result is not False:
                        _, new_views, new_eng = result
                        st.success(f"✅ Aktualisiert — {fmt(new_views)} Ø Views · {new_eng}% Eng")
                        time.sleep(1)
                        st.rerun()
            else:
                st.caption("Erst eine Analyse starten.")

        if not premium:
            tokens = get_tokens(user_id)
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.04);border:0.5px solid rgba(255,255,255,0.08);
                        border-radius:8px;padding:12px 14px;margin-bottom:8px;text-align:center;">
                <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                            color:rgba(232,230,224,0.25);margin-bottom:6px;">Analysen übrig</div>
                <div style="font-family:'DM Mono',monospace;font-size:28px;color:{'#1d9e75' if tokens > 0 else '#ff4d4d'};">
                    {tokens}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Token kaufen Buttons
            for pkg in TOKEN_PACKAGES:
                try:
                    url = create_token_checkout(user_email, user_id, pkg["price_id"], pkg["tokens"])
                    if url:
                        st.markdown(f'<a href="{url}" target="_blank"><button style="width:100%;background:rgba(255,255,255,0.04);color:rgba(232,230,224,0.6);border:0.5px solid rgba(255,255,255,0.08);padding:8px;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;margin-bottom:4px;font-family:Syne,sans-serif;">{pkg["label"]} — {pkg["preis"]}</button></a>', unsafe_allow_html=True)
                except:
                    pass
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Ausloggen", use_container_width=True):
            sign_out()

    if page == "🔍 Neue Analyse":
        st.markdown("""
        <div style="padding:22px 2px 12px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;
                        color:rgba(232,230,224,0.2);margin-bottom:6px;">TikTok AI Analyzer</div>
            <div style="font-size:24px;font-weight:800;color:#e8e6e0;">Neue Analyse starten</div>
        </div>
        """, unsafe_allow_html=True)

        if used_free and not premium:
            tokens = get_tokens(user_id)
            if tokens <= 0:
                st.markdown("""<div class="upgrade-card">
                    <div style="font-size:20px;font-weight:800;color:#e8e6e0;margin-bottom:8px;">Keine Analysen mehr übrig</div>
                    <div style="font-size:14px;color:rgba(232,230,224,0.4);margin-bottom:20px;">Kauf weitere Analysen oder upgrade auf Premium</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                # Token packages
                cols = st.columns(3)
                for i, pkg in enumerate(TOKEN_PACKAGES):
                    with cols[i]:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02);border:0.5px solid rgba(255,255,255,0.07);
                                    border-radius:10px;padding:20px;text-align:center;margin-bottom:8px;">
                            <div style="font-size:13px;font-weight:700;color:#e8e6e0;margin-bottom:4px;">{pkg['label']}</div>
                            <div style="font-family:'DM Mono',monospace;font-size:24px;color:#ff4d4d;margin-bottom:12px;">{pkg['preis']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        try:
                            url = create_token_checkout(user_email, user_id, pkg["price_id"], pkg["tokens"])
                            if url:
                                st.markdown(f'<a href="{url}" target="_blank"><button style="width:100%;background:#ff4d4d;color:white;border:none;padding:10px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;">Kaufen →</button></a>', unsafe_allow_html=True)
                        except:
                            pass

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.markdown('<div style="text-align:center;font-size:12px;color:rgba(232,230,224,0.3);">oder</div>', unsafe_allow_html=True)
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

                try:
                    checkout_url = create_checkout_session(user_email, user_id)
                    if checkout_url:
                        st.markdown(f'<div style="text-align:center;"><a href="{checkout_url}" target="_blank"><button style="background:rgba(255,255,255,0.05);color:#e8e6e0;border:0.5px solid rgba(255,255,255,0.1);padding:12px 28px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;">Premium — 19€/Monat (unlimited) →</button></a></div>', unsafe_allow_html=True)
                except:
                    pass
                return

        if "step" not in st.session_state:
            st.session_state.step = 1

        if st.session_state.step == 1:
            st.markdown('<div style="font-size:13px;color:rgba(232,230,224,0.35);margin-bottom:18px;">Analyse basiert auf den letzten 50 Videos.</div>', unsafe_allow_html=True)
            username = st.text_input("TikTok Username", placeholder="z.B. lucasbenner", label_visibility="collapsed")
            if st.button("Account scannen →", type="primary"):
                if username:
                    # Check token for non-premium
                    if not premium:
                        tokens = get_tokens(user_id)
                        if tokens <= 0 and used_free:
                            st.error("Keine Analysen mehr übrig. Kauf weitere Token.")
                            st.stop()
                    with st.spinner(f"@{username} wird gescannt..."):
                        data = scrape_tiktok_account(username)
                    if data:
                        st.session_state.main_data = data
                        st.session_state.username = username
                        st.session_state.step = 2
                        st.session_state.manual_accounts = [""] * 6
                        st.rerun()
                    else:
                        st.error("Account nicht gefunden oder privat.")

        elif st.session_state.step == 2:
            username = st.session_state.username

            st.markdown("### Schritt 2: Vergleichs-Accounts auswählen")
            st.markdown("""
            <div style="font-size:13px;color:rgba(232,230,224,0.4);margin-bottom:6px;">
                Gib bis zu 6 TikTok Usernamen ein mit denen du verglichen werden willst.
            </div>
            """, unsafe_allow_html=True)

            # Info Button
            with st.expander("❓ Was sind Vergleichs-Accounts?"):
                st.markdown("""
                Vergleichs-Accounts sind TikToker aus deiner Nische mit denen die KI deinen Account vergleicht.

                **Beispiele:**
                - Top-Performer in deiner Nische (viele Views, ähnliches Thema)
                - Accounts die gerade wachsen
                - Accounts mit ähnlicher Größe wie du

                Die KI analysiert was diese Accounts besser machen und gibt dir konkrete Tipps.
                """)

            # 6 leere Felder
            if "manual_accounts" not in st.session_state:
                st.session_state.manual_accounts = [""] * 6

            col1, col2 = st.columns(2)
            for i in range(6):
                with col1 if i % 2 == 0 else col2:
                    st.session_state.manual_accounts[i] = st.text_input(
                        f"Account {i+1}",
                        value=st.session_state.manual_accounts[i],
                        placeholder="z.B. maxmustermann",
                        key=f"manual_acc_{i}",
                        label_visibility="collapsed"
                    )

            # KI Vorschlag Button — befüllt nur leere Felder
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            col_ki, col_back, col_next = st.columns([2, 1, 2])

            with col_ki:
                if st.button("🤖 KI schlägt Accounts vor", use_container_width=True):
                    with st.spinner("KI sucht passende Accounts..."):
                        try:
                            suggestions = suggest_comparison_accounts(
                                st.session_state.main_data, username
                            )
                            st.session_state.suggestions = suggestions
                            # Nur leere Felder befüllen
                            ki_accounts = [a["username"] for a in suggestions["accounts"]]
                            ki_idx = 0
                            for i in range(6):
                                if not st.session_state.manual_accounts[i] and ki_idx < len(ki_accounts):
                                    st.session_state.manual_accounts[i] = ki_accounts[ki_idx]
                                    ki_idx += 1
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fehler: {e}")

            with col_back:
                if st.button("← Zurück", use_container_width=True):
                    st.session_state.step = 1
                    st.session_state.manual_accounts = [""] * 6
                    st.rerun()

            with col_next:
                selected = [a.strip() for a in st.session_state.manual_accounts if a.strip()]
                if st.button("Vergleich starten →", type="primary", use_container_width=True):
                    if selected:
                        st.session_state.selected_accounts = selected
                        if "suggestions" not in st.session_state:
                            st.session_state.suggestions = {"nische": "Unbekannt", "accounts": []}
                        st.session_state.step = 3
                        st.rerun()
                    else:
                        st.warning("Gib mindestens einen Account ein.")

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
                    newest_check = extracted.get("newest_30", [])
                    now = datetime.now(timezone.utc)
                    recent = []
                    for v in newest_check:
                        try:
                            dt = datetime.fromisoformat(v["datum"].replace("Z", "+00:00"))
                            if (now - dt).days <= 30:
                                recent.append(v)
                        except:
                            pass
                    if len(newest_check) == 0:
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
            top_10 = main_videos.get("top_10", [])
            bottom_10 = main_videos.get("bottom_10", [])

            analysis, avg_views, engagement = full_comparison_analysis(username, main_videos, comparison_data, suggestions["nische"])
            video_dates_list = [{"datum": v["datum"], "views": v["views"], "beschreibung": (v.get("beschreibung") or "")[:80]} for v in main_videos.get("all", []) if v.get("datum")]
            save_analysis(user_id, username, suggestions["nische"], avg_views, engagement, list(comparison_data.keys()), analysis, video_dates=video_dates_list)

            # Save watchtime + video data to session for dashboard
            watchtime_vals = [v.get("watchtime", 0) for v in newest if v.get("watchtime")]
            dur_vals = [v.get("dauer", 0) for v in newest if v.get("dauer")]
            if watchtime_vals:
                avg_wt = sum(watchtime_vals) / len(watchtime_vals)
                avg_dur_v = sum(dur_vals) / len(dur_vals) if dur_vals else 0
                by_dur = {}
                for v in newest:
                    d = v.get("dauer", 0)
                    wt = v.get("watchtime", 0)
                    if d > 0 and wt > 0:
                        bucket = "<10s" if d < 10 else "10-20s" if d < 20 else "20-30s" if d < 30 else "30-60s" if d < 60 else ">60s"
                        if bucket not in by_dur:
                            by_dur[bucket] = []
                        by_dur[bucket].append(wt / d * 100)
                by_dur_avg = {k: round(sum(vals)/len(vals), 1) for k, vals in by_dur.items()}
                st.session_state["last_watchtime"] = {
                    "avg_watchtime": round(avg_wt, 1),
                    "avg_duration": round(avg_dur_v, 1),
                    "best_watchtime": round(max(watchtime_vals), 1),
                    "dropoff_sec": round(avg_wt, 0),
                    "by_duration": by_dur_avg,
                }

            st.session_state["last_top_videos"] = top_10
            st.session_state["last_flop_videos"] = bottom_10

            progress_bar.empty()
            status_text.empty()

            # Results metrics
            total_views = sum(v["views"] for v in newest)
            total_likes = sum(v["likes"] for v in newest)
            avg_v = total_views // len(newest) if newest else 0
            eng = round((total_likes / total_views * 100) if total_views > 0 else 0, 2)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown('<div class="metric-accent-red"></div>', unsafe_allow_html=True)
                st.metric("GESAMT VIEWS", fmt(total_views))
            with c2:
                st.markdown('<div class="metric-accent-amber"></div>', unsafe_allow_html=True)
                st.metric("GESAMT LIKES", fmt(total_likes))
            with c3:
                st.markdown('<div class="metric-accent-teal"></div>', unsafe_allow_html=True)
                st.metric("Ø VIEWS", fmt(avg_v))
            with c4:
                st.markdown('<div class="metric-accent-blue"></div>', unsafe_allow_html=True)
                st.metric("ENGAGEMENT", f"{eng}%")

            st.divider()
            st.markdown("## KI Vergleichsanalyse")
            st.markdown(analysis)
            st.divider()

            if not premium:
                # Deduct token
                if used_free:
                    deduct_token(user_id)
                remaining = get_tokens(user_id)
                st.markdown(f"""<div class="upgrade-card">
                    <div style="font-size:18px;font-weight:800;color:#e8e6e0;margin-bottom:6px;">
                        {'1 Token verbraucht' if used_free else 'Gratis-Analyse verbraucht'}
                    </div>
                    <div style="font-size:13px;color:rgba(232,230,224,0.4);">
                        Noch {remaining} {'Token' if remaining != 1 else 'Token'} übrig
                    </div>
                </div>""", unsafe_allow_html=True)
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                cols = st.columns(3)
                for i, pkg in enumerate(TOKEN_PACKAGES):
                    with cols[i]:
                        try:
                            url = create_token_checkout(user_email, user_id, pkg["price_id"], pkg["tokens"])
                            if url:
                                st.markdown(f'<div style="text-align:center;"><a href="{url}" target="_blank"><button style="width:100%;background:rgba(255,255,255,0.05);color:#e8e6e0;border:0.5px solid rgba(255,255,255,0.1);padding:10px;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;">{pkg["label"]} — {pkg["preis"]}</button></a></div>', unsafe_allow_html=True)
                        except:
                            pass
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                try:
                    checkout_url = create_checkout_session(user_email, user_id)
                    if checkout_url:
                        st.markdown(f'<div style="text-align:center;margin-top:8px;"><a href="{checkout_url}" target="_blank"><button style="background:#ff4d4d;color:white;border:none;padding:10px 24px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;">Premium — 19€/Monat (unlimited) →</button></a></div>', unsafe_allow_html=True)
                except:
                    pass

            col_dl, col_new = st.columns(2)
            with col_dl:
                st.download_button("📥 Analyse downloaden", data=analysis, file_name=f"analyse_{username}.txt", mime="text/plain")
            with col_new:
                if st.button("🔄 Neue Analyse"):
                    for k in ["step", "main_data", "suggestions", "selected_accounts"]:
                        st.session_state.pop(k, None)
                    st.rerun()

    elif page == "📊 Dashboard" and premium:
        analyses = load_analyses(user_id)
        show_dashboard(user_id, user_email, premium, analyses)

    elif page == "📈 Analytics" and premium:
        analyses = load_analyses(user_id)
        show_analytics(user_id, analyses)


# ─── ROUTER ───────────────────────────────────────────────────────────────────

inject_css()

if "user" not in st.session_state:
    show_auth()
else:
    show_app()
