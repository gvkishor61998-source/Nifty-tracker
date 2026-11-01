import time
import math
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Nifty 50 Master Command Center", layout="wide")

# IST Timezone Helper
def get_ist_now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))

@st.cache_data(ttl=55)
def fetch_market_metrics():
    tickers = {
        "Nifty 50": "^NSEI",
        "India VIX": "^INDIAVIX",
        "Bank Nifty": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Reliance": "RELIANCE.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "S&P 500": "^GSPC",
        "S&P Futures": "ES=F",
        "US 10Y Yield": "^TNX",
        "Dollar Index": "DX-Y.NYB",
        "Brent Crude": "BZ=F",
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI"
    }
    results = {}
    for label, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            hist_daily = t.history(period="5d", interval="1d")
            hist_intra = t.history(period="1d", interval="5m")
            if len(hist_daily) >= 2:
                prev_row = hist_daily.iloc[-2]
                curr_row = hist_daily.iloc[-1]
                last_price = float(curr_row["Close"])
                prev_close = float(prev_row["Close"])
                open_price = float(curr_row["Open"])
                chg_pct = ((last_price - prev_close) / prev_close) * 100
                
                vwap = last_price
                orh, orl = float(curr_row["High"]), float(curr_row["Low"])
                vix_920 = open_price
                if not hist_intra.empty:
                    typ_price = (hist_intra["High"] + hist_intra["Low"] + hist_intra["Close"]) / 3
                    vol = hist_intra["Volume"].replace(0, 1)
                    vwap = float((typ_price * vol).cumsum().iloc[-1] / vol.cumsum().iloc[-1])
                    vix_920 = float(hist_intra.iloc[0]["Close"])
                    if len(hist_intra) >= 3:
                        orh = float(hist_intra.iloc[:3]["High"].max())
                        orl = float(hist_intra.iloc[:3]["Low"].min())

                results[label] = {
                    "price": round(last_price, 2),
                    "prev_close": round(prev_close, 2),
                    "open": round(open_price, 2),
                    "vix_920": round(vix_920, 2),
                    "chg_pct": round(chg_pct, 2),
                    "pdh": round(float(prev_row["High"]), 2),
                    "pdl": round(float(prev_row["Low"]), 2),
                    "vwap": round(vwap, 2),
                    "orh": round(orh, 2),
                    "orl": round(orl, 2)
                }
        except Exception:
            results[label] = None
    return results

@st.cache_data(ttl=60)
def fetch_nse_oi_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=4)
        r = s.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY", headers=headers, timeout=4)
        if r.status_code == 200:
            records = r.json()["records"]["data"]
            tot_ce = sum(x.get("CE", {}).get("openInterest", 0) for x in records)
            tot_pe = sum(x.get("PE", {}).get("openInterest", 0) for x in records)
            pcr = round(tot_pe / tot_ce, 2) if tot_ce > 0 else 0.90
            return pcr, True
    except Exception:
        pass
    return None, False

# ---------------- SIDEBAR: EOD SMART MONEY & ELECTION MODE ----------------
st.sidebar.header("⚙️ Phase 2: EOD Smart Money Inputs")
st.sidebar.caption("Pre-loaded with Friday Oct 30, 2026 EOD Data")

election_mode = st.sidebar.selectbox(
    "US Election Cycle Tracker",
    ["T-1 Monday (Pre-Election Day)", "T-0 Tuesday (US Election Day)", "Normal Trading Day"],
    index=0
)
fii_cash = st.sidebar.number_input("FII Cash Flow (₹ Cr)", value=3598.54, step=100.0)
dii_cash = st.sidebar.number_input("DII Cash Flow (₹ Cr)", value=-817.51, step=100.0)
fii_ls_ratio = st.sidebar.number_input("FII Index Futures Long %", value=11.12, step=0.5)
client_ls_ratio = st.sidebar.number_input("Retail (Client) Futures Long %", value=80.47, step=0.5)
fii_pro_net_calls = st.sidebar.number_input("FII + Pro Net Call Change", value=-68868, step=1000)
fii_net_puts = st.sidebar.number_input("FII Net Put Change", value=60729, step=1000)

live_pcr, nse_ok = fetch_nse_oi_data()
pcr_val = st.sidebar.number_input(
    f"Live Nifty PCR ({'NSE Auto' if nse_ok else 'Manual/Fallback'})",
    value=live_pcr if live_pcr else 0.88,
    step=0.02
)
auto_refresh = st.sidebar.checkbox("Auto-Refresh Every 60 Seconds", value=True)

# ---------------- HEADER & 9:15-9:30 AM CLOCK GUARD ----------------
ist_now = get_ist_now()
st.title("📊 Nifty 50 Master Command Center (All 20 Parameters)")
st.caption(f"IST Time: {ist_now.strftime('%d %b %Y, %I:%M:%S %p IST')} | Mode: {election_mode}")

if ist_now.hour == 9 and 15 <= ist_now.minute < 30:
    st.warning("⏳ **9:15–9:30 AM OPENING RANGE RULE ACTIVE:** Do NOT punch option orders yet! Let retail noise settle and wait for the 9:30 AM 15-minute candle close.")

data = fetch_market_metrics()
nifty = data.get("Nifty 50")
vix = data.get("India VIX")

if not nifty or not vix:
    st.error("Fetching live Nifty 50 & India VIX feed... Refreshing shortly.")
    st.stop()

# Expected Daily & Weekly Nifty Range Math from India VIX
daily_pct = round(vix["price"] / math.sqrt(252), 2)
daily_pts = int(round(nifty["price"] * (daily_pct / 100)))
weekly_pts = int(round(nifty["price"] * ((vix["price"] / math.sqrt(52)) / 100)))

# ---------------- PHASE 1: GLOBAL & ASIAN CUES ----------------
st.subheader("🌐 Phase 1: Global Macro, Bonds, Oil & Asian Peers")
c1, c2, c3, c4, c5, c6 = st.columns(6)
sp = data.get("S&P 500") or {"price": 7580.07, "chg_pct": -1.82}
spf = data.get("S&P Futures") or {"price": 7595.00, "chg_pct": 0.15}
brent = data.get("Brent Crude") or {"price": 117.64, "chg_pct": 2.40}
us10y = data.get("US 10Y Yield") or {"price": 4.32, "chg_pct": 0.80}
dxy = data.get("Dollar Index") or {"price": 104.25, "chg_pct": 0.20}
nikkei = data.get("Nikkei 225") or {"price": 38900.0, "chg_pct": -0.50}

c1.metric("S&P 500 (Prev)", f"{sp['price']}", f"{sp['chg_pct']}%")
c2.metric("S&P Live Futures", f"{spf['price']}", f"{spf['chg_pct']}%")
c3.metric("Brent Crude ($)", f"${brent['price']}", f"{brent['chg_pct']}%", delta_color="inverse")
c4.metric("US 10Y Yield", f"{us10y['price']}%", f"{us10y['chg_pct']}%", delta_color="inverse")
c5.metric("Dollar Index (DXY)", f"{dxy['price']}", f"{dxy['chg_pct']}%", delta_color="inverse")
c6.metric("Nikkei 225 (Asia)", f"{nikkei['price']}", f"{nikkei['chg_pct']}%")

# ---------------- PHASE 2: SMART MONEY VS RETAIL & LEVELS ----------------
st.subheader("🏦 Phase 2: FII/Pro vs. Retail Footprints & Battleground Levels")
p1, p2, p3, p4, p5, p6 = st.columns(6)
p1.metric("FII vs Retail Futures", f"{fii_ls_ratio}% Long", f"Retail: {client_ls_ratio}% Long")
p2.metric("FII+Pro Call Writing", f"{fii_pro_net_calls:,}", f"FII Puts: +{fii_net_puts:,}")
p3.metric("Prev Day High (PDH)", f"{nifty['pdh']}", f"{round(nifty['price'] - nifty['pdh'], 1)} pts")
p4.metric("Prev Day Close (PDC)", f"{nifty['prev_close']}", f"{round(nifty['price'] - nifty['prev_close'], 1)} pts")
p5.metric("Prev Day Low (PDL)", f"{nifty['pdl']}", f"{round(nifty['price'] - nifty['pdl'], 1)} pts")
p6.metric("15-Min ORH / ORL", f"{nifty['orh']}", f"Low: {nifty['orl']}")

# ---------------- PHASE 3: LIVE EXECUTION, VIX MATH & HEAVYWEIGHTS ----------------
st.subheader("⚡ Phase 3: Live Price Action, India VIX Rules & Heavyweights")
l1, l2, l3, l4, l5, l6 = st.columns(6)
bnk = data.get("Bank Nifty") or {"price": 54686.95, "chg_pct": -0.41}
it_idx = data.get("Nifty IT") or {"price": 41200.0, "chg_pct": 2.32}
rel = data.get("Reliance") or {"price": 1160.60, "chg_pct": -0.50}

l1.metric("Nifty 50 Spot", f"{nifty['price']}", f"{nifty['chg_pct']}%")
l2.metric("Intraday VWAP", f"{nifty['vwap']}", "Above VWAP" if nifty['price'] >= nifty['vwap'] else "Below VWAP")
l3.metric("India VIX (9:20 Check)", f"{vix['price']}", f"{vix['chg_pct']}% (9:20: {vix['vix_920']})", delta_color="inverse")
l4.metric("VIX Expected Daily Range", f"±{daily_pts} pts", f"±{daily_pct}% (Wk: ±{weekly_pts})")
l5.metric("Live Option PCR", f"{pcr_val}", "Bullish >1.15" if pcr_val > 1.15 else ("Bearish <0.85" if pcr_val < 0.85 else "Neutral"))
l6.metric("BankNifty / IT / Rel", f"BN:{bnk['chg_pct']}%", f"IT:{it_idx['chg_pct']}% | R:{rel['chg_pct']}%")

# ---------------- 50-YEAR MASTER ENGINE ----------------
st.markdown("---")
st.subheader("🎯 Master Trade Verdict, VIX Pattern & Strike Selector")

score = 0
reasons = []

# 1. Global & Oil Check
if brent["price"] > 110 or brent["chg_pct"] > 1.5:
    score -= 1
    reasons.append(f"🔴 **Macro Headwind:** Brent Crude elevated at ${brent['price']} ({brent['chg_pct']}%).")
if sp["chg_pct"] < -1.0 and spf["chg_pct"] < 0.3:
    score -= 1
    reasons.append(f"🔴 **US Tech/Index Drag:** S&P 500 dropped {sp['chg_pct']}% and US futures ({spf['chg_pct']}%) remain muted.")

# 2. Phase 2 Smart Money vs Retail Contrarian Check
if fii_pro_net_calls < -25000 and fii_net_puts > 25000:
    score -= 2
    reasons.append(f"🔴 **FII + Pro Bearish Trap:** Smart money sold {abs(fii_pro_net_calls):,} Calls & bought +{fii_net_puts:,} Puts while Retail is {client_ls_ratio}% Long.")
elif fii_ls_ratio < 12.0 and nifty["price"] > nifty["pdh"]:
    score += 2
    reasons.append(f"🟢 **FII Short-Covering Squeeze Alert:** FIIs are extreme short ({100-fii_ls_ratio:.1f}%) and Nifty broke above PDH ({nifty['pdh']})!")

# 3. 4 Visual India VIX Rules (From 62-Day Study)
if nifty["chg_pct"] > 0.2 and vix["chg_pct"] <= -5.0:
    score += 3
    reasons.append(f"🟢 **VIX Rule #2 (Real Bull Rally):** Nifty is green and India VIX crashed {vix['chg_pct']}% (>-5% threshold). Put sellers in full control.")
elif nifty["chg_pct"] < -0.2 and vix["chg_pct"] >= 6.0:
    score -= 3
    reasons.append(f"🔴 **VIX Rule #2 (Real Sell-Off):** Nifty is red and India VIX spiked +{vix['chg_pct']}% (>+6% threshold). Do NOT buy dips!")
elif nifty["chg_pct"] > 0.2 and vix["chg_pct"] > 1.5:
    reasons.append(f"⚠️ **VIX Rule #3 (Nifty Up + VIX Up = Event Caution):** Both Nifty (+{nifty['chg_pct']}%) and VIX (+{vix['chg_pct']}%) are rising together. Expect violent two-way swings!")
elif nifty["chg_pct"] < -0.2 and vix["chg_pct"] <= 0:
    score += 1
    reasons.append(f"🟢 **VIX Rule #3 (Harmless Pullback):** Nifty is down ({nifty['chg_pct']}%) but VIX is flat/down ({vix['chg_pct']}%). No institutional panic.")

if vix["price"] >= 22.0:
    reasons.append(f"⚠️ **VIX Rule #4 (Fear Ceiling > 22):** VIX is at {vix['price']}. Watch for an -8% VIX drop to catch a massive relief bounce.")

# 4. Price Action: VWAP + 15-Min ORB + PDH/PDL
if nifty["price"] > nifty["vwap"] and nifty["price"] > nifty["orh"]:
    score += 2
    reasons.append(f"🟢 **ORB + VWAP Breakout:** Nifty ({nifty['price']}) is holding above both VWAP ({nifty['vwap']}) and 15-Min High ({nifty['orh']}).")
elif nifty["price"] < nifty["vwap"] and nifty["price"] < nifty["orl"]:
    score -= 2
    reasons.append(f"🔴 **ORB + VWAP Breakdown:** Nifty ({nifty['price']}) broke below both VWAP ({nifty['vwap']}) and 15-Min Low ({nifty['orl']}).")

if nifty["price"] < nifty["pdl"]:
    score -= 2
    reasons.append(f"🔴 **PDL Breakdown:** Trading below Previous Day Low ({nifty['pdl']}), forcing yesterday's Put writers to unwind.")
elif nifty["price"] > nifty["pdh"]:
    score += 2
    reasons.append(f"🟢 **PDH Breakout:** Trading above Previous Day High ({nifty['pdh']}), forcing yesterday's Call writers to cover.")

# 5. PCR & Heavyweight Check
if pcr_val >= 1.15:
    score += 1
    reasons.append(f"🟢 **PCR Bullish ({pcr_val}):** Heavy Put writing support below current spot.")
elif pcr_val <= 0.85:
    score -= 1
    reasons.append(f"🔴 **PCR Bearish ({pcr_val}):** Aggressive Call writing overhead.")

if bnk["chg_pct"] < -0.3 and (it_idx["chg_pct"] < -0.5 or rel["chg_pct"] < -0.3):
    score -= 1
    reasons.append("🔴 **Heavyweights Dragging:** Bank Nifty and IT/Reliance are aligned on the downside.")
elif bnk["chg_pct"] > 0.4 and (it_idx["chg_pct"] > 0.5 or rel["chg_pct"] > 0.3):
    score += 1
    reasons.append("🟢 **Heavyweights Leading:** Bank Nifty and IT/Reliance are aligned on the upside.")

# 6. Election Cycle Context Note
if "T-1 Monday" in election_mode:
    reasons.append("🗳️ **Election T-1 Context:** Monday absorbs weekend/US Friday shocks (Nifty fell -1.27% in 2024 T-1 & -0.28% in 2018 T-1). Respect downside breakdowns.")
elif "T-0 Tuesday" in election_mode:
    reasons.append("🗳️ **Election T-0 Context:** Watch for afternoon VIX Crush short-covering bounce once US voting begins.")

atm_strike = int(round(nifty["price"] / 50.0) * 50)
upper_range = int(round(nifty["prev_close"] + daily_pts))
lower_range = int(round(nifty["prev_close"] - daily_pts))

if score <= -3:
    st.error(f"### 🚨 VERDICT: BUY PUT OPTION (PE)
