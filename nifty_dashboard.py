import time
import math
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Nifty 50 Master Command Center", layout="wide")

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
                orh = float(curr_row["High"])
                orl = float(curr_row["Low"])
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=4)
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        r = s.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            records = r.json()["records"]["data"]
            tot_ce = sum(x.get("CE", {}).get("openInterest", 0) for x in records)
            tot_pe = sum(x.get("PE", {}).get("openInterest", 0) for x in records)
            pcr = round(tot_pe / tot_ce, 2) if tot_ce > 0 else 0.90
            return pcr, True
    except Exception:
        pass
    return None, False

st.sidebar.header("Phase 2: EOD Smart Money Inputs")
st.sidebar.caption("Pre-loaded with Oct 30, 2026 EOD Data")

election_mode = st.sidebar.selectbox(
    "US Election Cycle Tracker",
    ["T-1 Monday (Pre-Election Day)", "T-0 Tuesday (US Election Day)", "Normal Trading Day"],
    index=0
)
fii_cash = st.sidebar.number_input("FII Cash Flow (Cr)", value=3598.54, step=100.0)
dii_cash = st.sidebar.number_input("DII Cash Flow (Cr)", value=-817.51, step=100.0)
fii_ls_ratio = st.sidebar.number_input("FII Index Futures Long %", value=11.12, step=0.5)
client_ls_ratio = st.sidebar.number_input("Retail Futures Long %", value=80.47, step=0.5)
fii_pro_net_calls = st.sidebar.number_input("FII + Pro Net Call Change", value=-68868, step=1000)
fii_net_puts = st.sidebar.number_input("FII Net Put Change", value=60729, step=1000)

live_pcr, nse_ok = fetch_nse_oi_data()
pcr_label = "Live Nifty PCR (NSE Auto)" if nse_ok else "Live Nifty PCR (Manual)"
pcr_val = st.sidebar.number_input(pcr_label, value=live_pcr if live_pcr else 0.88, step=0.02)
auto_refresh = st.sidebar.checkbox("Auto-Refresh Every 60 Seconds", value=True)

ist_now = get_ist_now()
st.title("Nifty 50 Master Command Center (All 20 Parameters)")
st.caption("IST Time: " + ist_now.strftime("%d %b %Y, %I:%M:%S %p IST") + " | Mode: " + election_mode)

if ist_now.hour == 9 and 15 <= ist_now.minute < 30:
    st.warning("9:15-9:30 AM OPENING RANGE RULE: Wait for 9:30 AM 15-min candle close before entering!")

data = fetch_market_metrics()
nifty = data.get("Nifty 50")
vix = data.get("India VIX")

if not nifty or not vix:
    st.error("Fetching live Nifty 50 and India VIX feed... Please refresh in 10 seconds.")
    st.stop()

daily_pct = round(vix["price"] / math.sqrt(252), 2)
daily_pts = int(round(nifty["price"] * (daily_pct / 100)))
weekly_pts = int(round(nifty["price"] * ((vix["price"] / math.sqrt(52)) / 100)))

st.subheader("Phase 1: Global Macro, Bonds, Oil & Asian Peers")
c1, c2, c3, c4, c5, c6 = st.columns(6)
sp = data.get("S&P 500") or {"price": 7580.07, "chg_pct": -1.82}
spf = data.get("S&P Futures") or {"price": 7595.00, "chg_pct": 0.15}
brent = data.get("Brent Crude") or {"price": 117.64, "chg_pct": 2.40}
us10y = data.get("US 10Y Yield") or {"price": 4.32, "chg_pct": 0.80}
dxy = data.get("Dollar Index") or {"price": 104.25, "chg_pct": 0.20}
nikkei = data.get("Nikkei 225") or {"price": 38900.0, "chg_pct": -0.50}

c1.metric("S&P 500 (Prev)", str(sp["price"]), str(sp["chg_pct"]) + "%")
c2.metric("S&P Live Futures", str(spf["price"]), str(spf["chg_pct"]) + "%")
c3.metric("Brent Crude ($)", "$" + str(brent["price"]), str(brent["chg_pct"]) + "%", delta_color="inverse")
c4.metric("US 10Y Yield", str(us10y["price"]) + "%", str(us10y["chg_pct"]) + "%", delta_color="inverse")
c5.metric("Dollar Index", str(dxy["price"]), str(dxy["chg_pct"]) + "%", delta_color="inverse")
c6.metric("Nikkei 225", str(nikkei["price"]), str(nikkei["chg_pct"]) + "%")

st.subheader("Phase 2: FII/Pro vs. Retail Footprints & Key Levels")
p1, p2, p3, p4, p5, p6 = st.columns(6)
p1.metric("FII Futures Long", str(fii_ls_ratio) + "%", "Retail: " + str(client_ls_ratio) + "%")
p2.metric("FII+Pro Call Writing", str(fii_pro_net_calls), "FII Puts: +" + str(fii_net_puts))
p3.metric("Prev Day High (PDH)", str(nifty["pdh"]), str(round(nifty["price"] - nifty["pdh"], 1)) + " pts")
p4.metric("Prev Day Close (PDC)", str(nifty["prev_close"]), str(round(nifty["price"] - nifty["prev_close"], 1)) + " pts")
p5.metric("Prev Day Low (PDL)", str(nifty["pdl"]), str(round(nifty["price"] - nifty["pdl"], 1)) + " pts")
p6.metric("15-Min ORH / ORL", str(nifty["orh"]), "Low: " + str(nifty["orl"]))

st.subheader("Phase 3: Live Price Action, India VIX Rules & Heavyweights")
l1, l2, l3, l4, l5, l6 = st.columns(6)
bnk = data.get("Bank Nifty") or {"price": 54686.95, "chg_pct": -0.41}
it_idx = data.get("Nifty IT") or {"price": 41200.0, "chg_pct": 2.32}
rel = data.get("Reliance") or {"price": 1160.60, "chg_pct": -0.50}

vwap_status = "Above VWAP" if nifty["price"] >= nifty["vwap"] else "Below VWAP"
pcr_status = "Bullish" if pcr_val > 1.15 else ("Bearish" if pcr_val < 0.85 else "Neutral")

l1.metric("Nifty 50 Spot", str(nifty["price"]), str(nifty["chg_pct"]) + "%")
l2.metric("Intraday VWAP", str(nifty["vwap"]), vwap_status)
l3.metric("India VIX", str(vix["price"]), str(vix["chg_pct"]) + "% (9:20: " + str(vix["vix_920"]) + ")", delta_color="inverse")
l4.metric("VIX Daily Range", "+/- " + str(daily_pts) + " pts", "+/- " + str(daily_pct) + "%")
l5.metric("Live Option PCR", str(pcr_val), pcr_status)
l6.metric("Bank / IT / Rel", "BN:" + str(bnk["chg_pct"]) + "%", "IT:" + str(it_idx["chg_pct"]) + "% R:" + str(rel["chg_pct"]) + "%")

st.markdown("---")
st.subheader("Master Trade Verdict, VIX Pattern & Strike Selector")

score = 0
reasons = []

if brent["price"] > 110 or brent["chg_pct"] > 1.5:
    score -= 1
    reasons.append("Bearish Macro: Brent Crude is elevated at $" + str(brent["price"]) + " (" + str(brent["chg_pct"]) + "%).")
if sp["chg_pct"] < -1.0 and spf["chg_pct"] < 0.3:
    score -= 1
    reasons.append("US Drag: S&P 500 dropped " + str(sp["chg_pct"]) + "% and US futures remain muted.")

if fii_pro_net_calls < -25000 and fii_net_puts > 25000:
    score -= 2
    reasons.append("FII + Pro Bearish Trap: Smart money sold Calls & bought Puts while Retail is " + str(client_ls_ratio) + "% Long.")
elif fii_ls_ratio < 12.0 and nifty["price"] > nifty["pdh"]:
    score += 2
    reasons.append("FII Short Squeeze Alert: FIIs are extreme short and Nifty broke above PDH (" + str(nifty["pdh"]) + ")!")

if nifty["chg_pct"] > 0.2 and vix["chg_pct"] <= -5.0:
    score += 3
    reasons.append("VIX Rule #2 (Real Bull Rally): Nifty is green and VIX fell " + str(vix["chg_pct"]) + "% (below -5% rule).")
elif nifty["chg_pct"] < -0.2 and vix["chg_pct"] >= 6.0:
    score -= 3
    reasons.append("VIX Rule #2 (Real Sell-Off): Nifty is red and VIX spiked +" + str(vix["chg_pct"]) + "% (above +6% rule).")
elif nifty["chg_pct"] > 0.2 and vix["chg_pct"] > 1.5:
    reasons.append("VIX Rule #3 (Nifty Up + VIX Up = Event Caution): Expect sharp two-way swings!")
elif nifty["chg_pct"] < -0.2 and vix["chg_pct"] <= 0:
    score += 1
    reasons.append("VIX Rule #3 (Harmless Pullback): Nifty is down but VIX is flat/down. No institutional panic.")

if vix["price"] >= 22.0:
    reasons.append("VIX Rule #4 (Fear Ceiling > 22): Watch for an -8% VIX drop to catch a relief bounce.")

if nifty["price"] > nifty["vwap"] and nifty["price"] > nifty["orh"]:
    score += 2
    reasons.append("ORB + VWAP Breakout: Nifty is holding above VWAP (" + str(nifty["vwap"]) + ") and 15-Min High (" + str(nifty["orh"]) + ").")
elif nifty["price"] < nifty["vwap"] and nifty["price"] < nifty["orl"]:
    score -= 2
    reasons.append("ORB + VWAP Breakdown: Nifty broke below VWAP (" + str(nifty["vwap"]) + ") and 15-Min Low (" + str(nifty["orl"]) + ").")

if nifty["price"] < nifty["pdl"]:
    score -= 2
    reasons.append("PDL Breakdown: Trading below Previous Day Low (" + str(nifty["pdl"]) + ").")
elif nifty["price"] > nifty["pdh"]:
    score += 2
    reasons.append("PDH Breakout: Trading above Previous Day High (" + str(nifty["pdh"]) + ").")

if pcr_val >= 1.15:
    score += 1
    reasons.append("PCR Bullish (" + str(pcr_val) + "): Strong Put writing support.")
elif pcr_val <= 0.85:
    score -= 1
    reasons.append("PCR Bearish (" + str(pcr_val) + "): Heavy Call writing overhead.")

if bnk["chg_pct"] < -0.3 and (it_idx["chg_pct"] < -0.5 or rel["chg_pct"] < -0.3):
    score -= 1
    reasons.append("Heavyweights Dragging: Bank Nifty and IT/Reliance are negative.")
elif bnk["chg_pct"] > 0.4 and (it_idx["chg_pct"] > 0.5 or rel["chg_pct"] > 0.3):
    score += 1
    reasons.append("Heavyweights Leading: Bank Nifty and IT/Reliance are positive.")

if "T-1 Monday" in election_mode:
    reasons.append("Election T-1 Context: Monday absorbs weekend/US Friday shocks. Respect downside breakdowns.")
elif "T-0 Tuesday" in election_mode:
    reasons.append("Election T-0 Context: Watch for afternoon VIX Crush short-covering bounce.")

atm_strike = int(round(nifty["price"] / 50.0) * 50)
upper_range = int(round(nifty["prev_close"] + daily_pts))
lower_range = int(round(nifty["prev_close"] - daily_pts))

if score <= -3:
    pe_sl = int(round(max(nifty["vwap"], nifty["orh"]) + 15))
    pe_t1 = int(round(nifty["price"] - 75))
    pe_t2 = max(lower_range, int(round(nifty["price"] - 140)))
    st.error("VERDICT: BUY PUT OPTION (PE) | Conviction Score: " + str(score))
    st.write("1. **Best Strike to Buy:** Nifty " + str(atm_strike) + " PE (or " + str(atm_strike - 50) + " PE below " + str(nifty["pdl"]) + ")")
    st.write("2. **Entry Rule:** Wait past 9:30 AM. Enter below VWAP (" + str(nifty["vwap"]) + ") or PDL (" + str(nifty["pdl"]) + ").")
    st.write("3. **Strict Stop-Loss:** Spot Nifty 5-min close above " + str(pe_sl))
    st.write("4. **Targets:** Target 1: " + str(pe_t1) + " | Target 2: " + str(pe_t2) + " (VIX Lower Band: " + str(lower_range) + ")")
elif score >= 3:
    ce_sl = int(round(min(nifty["vwap"], nifty["pdh"]) - 20))
    ce_t1 = int(round(nifty["price"] + 75))
    ce_t2 = min(upper_range, int(round(nifty["price"] + 140)))
    st.success("VERDICT: BUY CALL OPTION (CE) | Conviction Score: +" + str(score))
    st.write("1. **Best Strike to Buy:** Nifty " + str(atm_strike) + " CE")
    st.write("2. **Entry Rule:** Wait past 9:30 AM. Enter above VWAP (" + str(nifty["vwap"]) + ") and 15-Min High (" + str(nifty["orh"]) + ").")
    st.write("3. **Strict Stop-Loss:** Spot Nifty 5-min close below " + str(ce_sl))
    st.write("4. **Targets:** Target 1: " + str(ce_t1) + " | Target 2: " + str(ce_t2) + " (VIX Upper Band: " + str(upper_range) + ")")
else:
    vix_up_trig = round(vix["open"] * 1.04, 2)
    st.warning("VERDICT: WAIT / NO-TRADE ZONE (Protect Capital from Theta) | Score: " + str(score))
    st.write("1. **Expected VIX Daily Range Today:** " + str(lower_range) + " to " + str(upper_range) + " (+/- " + str(daily_pts) + " pts)")
    st.write("2. **To Buy " + str(atm_strike) + " CE:** Wait for breakout above PDH (" + str(nifty["pdh"]) + ") or 15-Min High (" + str(nifty["orh"]) + ").")
    st.write("3. **To Buy " + str(atm_strike) + " PE:** Wait for breakdown below PDL (" + str(nifty["pdl"]) + ") with VIX rising above " + str(vix_up_trig) + ".")

st.subheader("Complete 20-Point Live Checklist:")
for r in reasons:
    st.write("- " + r)

if auto_refresh:
    time.sleep(60)
    st.rerun()
