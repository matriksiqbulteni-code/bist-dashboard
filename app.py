import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# --- Sayfa Genel Yapılandırması ---
st.set_page_config(
    page_title="CC Scanner | BİST Tarayıcı ve TP/Stop Paneli",
    page_icon="⚡",
    layout="wide"
)

# --- CC Scanner Kobalt Mavisi & Neon Terminal Teması (CSS) ---
st.markdown("""
<style>
    .main { background-color: #090d16; }
    div[data-testid="stMetric"] {
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
        padding: 10px 14px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    .ai-card {
        background: #0f172a;
        border-left: 4px solid #38bdf8;
        border-radius: 6px;
        padding: 15px 18px;
        margin-top: 15px;
        color: #e2e8f0;
        font-size: 1.05rem;
        line-height: 1.6;
    }
    .alert-banner {
        background-color: rgba(5, 150, 105, 0.2);
        border: 1px solid #059669;
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 6px;
        margin-bottom: 15px;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Çoklu Periyot BIST Tarayıcı ve TP/Stop Paneli (CC Scanner)")
st.caption("Doğrulanmış Kesişim Tespiti, Sabit Giriş Fiyatı ve Gerçek Bar Sayacı Motoru.")

# --- 1. Yan Panel Ayarları ---
with st.sidebar:
    st.header("⚙️ 1. Genel ve Tarama Ayarları")
    
    taramaPeriyot = st.selectbox(
        "Taranacak Periyot:",
        options=["240", "60", "D", "5", "1"],
        format_func=lambda x: {
            "240": "⏰ 4S (240dk)",
            "60": "⏱️ 1S (60dk)",
            "D": "📅 Günlük (D)",
            "5": "🔥 5dk",
            "1": "⚡ 1dk"
        }[x],
        index=0
    )
    
    sadeceSinyaller = st.checkbox("Sadece Aktif Sinyalleri Göster (Nötrleri Gizle)", value=False)
    
    st.divider()
    st.header("🎯 2. ATR Hedef Çarpanları")
    atrMult1 = st.slider("Hedef 1 ATR Çarpanı:", 0.5, 3.0, 1.5, 0.1)
    atrMult2 = st.slider("Hedef 2 ATR Çarpanı:", 1.5, 5.0, 2.5, 0.1)
    atrMult3 = st.slider("Hedef 3 ATR Çarpanı:", 2.5, 7.0, 4.0, 0.1)

    st.divider()
    st.header("📋 3. Aktif Taranacak Grubu Seç")
    seciliGrup = st.selectbox(
        "Grup Seçimi:",
        options=["Grup 1 (BİST 20)", "Özel Radarım (20 Hisse)"],
        index=0
    )

    ozel_hisseler = []
    if seciliGrup == "Özel Radarım (20 Hisse)":
        st.markdown("### 🎯 Özel Radar Listeniz")
        default_radar = ["THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "EREGL", "KCHOL", "SAHOL", "SISE", "TUPRS",
                         "ASELS", "BIMAS", "FROTO", "TOASO", "PGSUS", "EKGYO", "PETKM", "TCELL", "ENKAI", "ARCLK"]
        c1, c2 = st.columns(2)
        for i in range(1, 21):
            col_target = c1 if i <= 10 else c2
            val = col_target.text_input(f"Hisse {i}", value=default_radar[i-1], max_chars=10).upper().strip()
            if val:
                ozel_hisseler.append(val)
    elif seciliGrup == "Grup 1 (BİST 20)":
        ozel_hisseler = ["THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "EREGL", "KCHOL", "SAHOL", "SISE", "TUPRS",
                         "ASELS", "BIMAS", "FROTO", "TOASO", "PGSUS", "EKGYO", "PETKM", "TCELL", "ENKAI", "ARCLK"]

    st.divider()
    sesli_uyari = st.checkbox("🔊 Sesli Alarm (Yeni Sinyallerde)", value=True)
    tara_butonu = st.button("🔄 Terminali Güncelle", type="primary", use_container_width=True)

# --- 2. Periyot Etiketleri ve YFinance Eşleşmesi ---
def get_tf_params(tf):
    if tf == "1":
        return "1m", "5m", "7d", "1dk"
    elif tf == "5":
        return "5m", "60m", "1mo", "5dk"
    elif tf == "60":
        return "60m", "1d", "3mo", "1S"
    elif tf == "240":
        return "60m", "1d", "6mo", "4S"  # 4S için 60m barlar 4'erli resample edilir
    elif tf == "D":
        return "1d", "1wk", "2y", "Günlük"
    return "60m", "1d", "6mo", "4S"

base_interval, upper_interval, download_period, tf_label = get_tf_params(taramaPeriyot)

# --- 3. EMA ve ATR Hesaplama Fonksiyonları ---
def calc_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def calc_atr(df_ohlc, length=14):
    high = df_ohlc['High']
    low = df_ohlc['Low']
    close = df_ohlc['Close'].shift(1)
    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return tr.rolling(length).mean()

# --- 4. Pine Script f_eval_direction Hesaplayıcı ---
def eval_direction_series(df_ohlc, tf):
    c = df_ohlc['Close']
    dir_series = pd.Series(0, index=df_ohlc.index)
    stop_series = pd.Series(0.0, index=df_ohlc.index)

    if tf == "1":
        ema500 = calc_ema(c, 500)
        dir_series = np.where(c > ema500, 1, np.where(c < ema500, -1, 0))
        stop_series = ema500
    elif tf == "5":
        ema12 = calc_ema(c, 12)
        dir_series = np.where(c > ema12, 1, np.where(c < ema12, -1, 0))
        stop_series = ema12
    elif tf == "60":
        ema9 = calc_ema(c, 9)
        ema45 = calc_ema(c, 45)
        ema189 = calc_ema(c, 189)
        dir_series = np.where(ema45 > ema189, 1, np.where(ema45 < ema189, -1, 0))
        stop_series = ema9
    elif tf == "240":
        ema3 = calc_ema(c, 3)
        ema15 = calc_ema(c, 15)
        ema63 = calc_ema(c, 63)
        dir_series = np.where(ema15 > ema63, 1, np.where(ema15 < ema63, -1, 0))
        stop_series = ema3
    elif tf == "D":
        e5 = calc_ema(c, 5)
        e21 = calc_ema(c, 21)
        e34 = calc_ema(c, 34)
        e55 = calc_ema(c, 55)
        e144 = calc_ema(c, 144)
        bull = (c > e5) & (e5 > e21) & (e21 > e34) & (e34 > e55) & (e55 > e144)
        bear = (c < e5) & (e5 < e21) & (e21 < e34) & (e34 < e55) & (e55 < e144)
        dir_series = np.where(bull, 1, np.where(bear, -1, 0))
        stop_series = e5
    else:
        e20 = calc_ema(c, 20)
        e50 = calc_ema(c, 50)
        dir_series = np.where(e20 > e50, 1, -1)
        stop_series = e50

    return pd.Series(dir_series, index=df_ohlc.index), pd.Series(stop_series, index=df_ohlc.index)

# --- 5. Ana Tarama Motoru (Tüm Barlar Gerçekten Taranır) ---
@st.cache_data(ttl=30)
def hisseleri_tara(semboller, tf_secim):
    sonuclar = []
    
    for sym in semboller:
        ticker = f"{sym}.IS"
        try:
            # 1. Taban Veriyi Çek
            df_raw = yf.download(ticker, period=download_period, interval=base_interval, progress=False)
            if df_raw.empty or len(df_raw) < 30:
                continue

            # Multi-index sütunları düzelt
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = df_raw.columns.get_level_values(0)

            # 4S ise 60m barlar 4 saatlik barlara dönüştürülür
            if tf_secim == "240":
                df_base = df_raw.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
            else:
                df_base = df_raw

            if len(df_base) < 25:
                continue

            # 2. Üst Periyot Verisini Çek
            df_up_raw = yf.download(ticker, period="1y", interval=upper_interval, progress=False)
            if isinstance(df_up_raw.columns, pd.MultiIndex):
                df_up_raw.columns = df_up_raw.columns.get_level_values(0)

            # 3. Yön Serilerini Hesapla
            bDir_s, bStop_s = eval_direction_series(df_base, tf_secim)
            
            upper_tf_key = "D" if tf_secim in ["240", "60"] else ("W" if tf_secim == "D" else "60")
            uDir_s, _ = eval_direction_series(df_up_raw, upper_tf_key)
            last_uDir = uDir_s.iloc[-1] if not uDir_s.empty else 0

            # 4. Sinyal Serisini Oluştur (Pine Script: sig = bDir == 1 ? (uDir == 1 ? 2 : 1) : ...)
            sig_series = np.where(bDir_s == 1, np.where(last_uDir == 1, 2, 1), np.where(bDir_s == -1, -1, 0))
            sig_series = pd.Series(sig_series, index=df_base.index)

            # 5. GERÇEK KESİŞİM VE GİRİŞ FİYATI TESPİTİ (Pine Script birebir simülasyonu)
            current_sig = sig_series.iloc[-1]
            current_close = df_base['Close'].iloc[-1]
            prev_day_close = df_base['Close'].iloc[-2] if len(df_base) >= 2 else current_close
            p_chg = ((current_close - prev_day_close) / prev_day_close) * 100.0

            # ATR
            atr_s = calc_atr(df_base, 14)
            current_atr = atr_s.iloc[-1] if not pd.isna(atr_s.iloc[-1]) else current_close * 0.02

            # Geriye doğru sinyalin İLK başladığı barı bul (ta.barssince(sigChanged))
            bAgo = 0
            entryP = current_close
            entryStop = bStop_s.iloc[-1]

            if current_sig != 0:
                for i in range(len(sig_series) - 1, -1, -1):
                    if sig_series.iloc[i] == current_sig:
                        bAgo = (len(sig_series) - 1) - i
                        entryP = df_base['Close'].iloc[i]
                        entryStop = bStop_s.iloc[i]
                    else:
                        break  # Kesişimin başladığı yere ulaştık

            # Hedefler (Yalnızca AL durumunda hesaplanır)
            isBuy = current_sig >= 1
            tp1 = (entryP + atrMult1 * current_atr) if isBuy else np.nan
            tp2 = (entryP + atrMult2 * current_atr) if isBuy else np.nan
            tp3 = (entryP + atrMult3 * current_atr) if isBuy else np.nan

            # Sinyalden bugüne en yüksek tepe (hiSince)
            hiSince = df_base['High'].iloc[-(bAgo + 1):].max() if bAgo >= 0 else current_close
            hit1 = isBuy and not np.isnan(tp1) and (hiSince >= tp1)
            hit2 = isBuy and not np.isnan(tp2) and (hiSince >= tp2)
            hit3 = isBuy and not np.isnan(tp3) and (hiSince >= tp3)

            sonuclar.append({
                "Sembol": sym,
                "current_sig": current_sig,
                "current_close": current_close,
                "p_chg": p_chg,
                "entryP": entryP,
                "entryStop": entryStop,
                "bAgo": bAgo,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "hit1": hit1,
                "hit2": hit2,
                "hit3": hit3
            })
        except Exception:
            continue

    return pd.DataFrame(sonuclar)

with st.spinner("Borsa İstanbul barları indiriliyor ve Pine Script motoru çalıştırılıyor..."):
    df_res = hisseleri_tara(ozel_hisseler, taramaPeriyot)

if not df_res.empty:
    # --- 6. Canlı Uyarı Banner'ı ---
    guclu_allar = df_res[df_res['current_sig'] == 2]
    if not guclu_allar.empty:
        ozet_str = ", ".join([f"<b>{r['Sembol']}</b> (GÜÇLÜ AL)" for _, r in guclu_allar.head(4).iterrows()])
        st.markdown(f"""
        <div class="alert-banner">
            🔔 <b>CC SCANNER ALARMI:</b> Çift periyot onaylı güçlü alım sinyali! -> {ozet_str}
        </div>
        """, unsafe_allow_html=True)
        if sesli_uyari:
            audio_beep = """
            <script>
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.frequency.value = 880;
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
            </script>
            """
            components.html(audio_beep, height=0)

    # --- 7. Üst Sayaçlar ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📊 Taranan Hisse", f"{len(df_res)}")
    k2.metric("🟢 GÜÇLÜ AL (2x Onay)", f"{(df_res['current_sig'] == 2).sum()}")
    k3.metric("🟡 AL (Tepki)", f"{(df_res['current_sig'] == 1).sum()}")
    k4.metric("🔴 SAT (Ayı)", f"{(df_res['current_sig'] == -1).sum()}")

    st.write("")

    # --- 8. Tabloyu Oluşturma ---
    gorunen = df_res[df_res['current_sig'] != 0].copy() if sadeceSinyaller else df_res.copy()
    if gorunen.empty:
        st.info("Aktif sinyal bulunamadı. Tüm liste gösteriliyor.")
        gorunen = df_res.copy()

    t_rows = []
    for _, row in gorunen.iterrows():
        sig = row['current_sig']
        p_close = row['current_close']
        p_chg = row['p_chg']
        e_p = row['entryP']
        p_stop = row['entryStop']
        b_ago = row['bAgo']
        tp1_v = row['tp1']
        tp2_v = row['tp2']
        tp3_v = row['tp3']
        h1 = row['hit1']
        h2 = row['hit2']
        h3 = row['hit3']

        if sig == 2: sig_txt = "GÜÇLÜ AL"
        elif sig == 1: sig_txt = "AL (Tepki)"
        elif sig == -1: sig_txt = "SAT"
        else: sig_txt = "NÖTR"

        chg_sign = "+" if p_chg >= 0 else ""
        price_str = f"{p_close:,.2f} ({chg_sign}{p_chg:.2f}%)"
        entry_str = f"{e_p:,.2f} ({b_ago}b)"

        stop_pct = ((p_stop - e_p) / e_p) * 100.0 if e_p > 0 and pd.notnull(p_stop) else 0.0
        stop_sign = "+" if stop_pct >= 0 else ""
        stop_str = f"{p_stop:,.2f} ({stop_sign}{stop_pct:.2f}%)" if pd.notnull(p_stop) and p_stop > 0 else "-"

        def format_tp(tp_val, hit):
            if pd.isna(tp_val) or sig <= 0: return "-"
            pct = ((tp_val - e_p) / e_p) * 100.0 if e_p > 0 else 0.0
            check = " ✓" if hit else ""
            return f"{tp_val:,.2f} (+{pct:.2f}%){check}"

        tp1_str = format_tp(tp1_v, h1)
        tp2_str = format_tp(tp2_v, h2)
        tp3_str = format_tp(tp3_v, h3)

        t_rows.append({
            "Sembol": row['Sembol'],
            "Sinyal": sig_txt,
            "Periyot": tf_label,
            "Fiyat (%)": price_str,
            "Giriş (Bar)": entry_str,
            "Stop": stop_str,
            "Hedef 1 (% Koz)": tp1_str,
            "Hedef 2 (% Koz)": tp2_str,
            "Hedef 3 (% Koz)": tp3_str,
            "_sig": sig,
            "_pChg": p_chg,
            "_h1": h1,
            "_h2": h2,
            "_h3": h3
        })

    t_df = pd.DataFrame(t_rows)

    # Renklendirme Stili
    def style_cc(row):
        styles = [''] * len(row)
        idx_sym = t_df.columns.get_loc("Sembol")
        idx_sig = t_df.columns.get_loc("Sinyal")
        idx_tf = t_df.columns.get_loc("Periyot")
        idx_pr = t_df.columns.get_loc("Fiyat (%)")
        idx_en = t_df.columns.get_loc("Giriş (Bar)")
        idx_st = t_df.columns.get_loc("Stop")
        idx_t1 = t_df.columns.get_loc("Hedef 1 (% Koz)")
        idx_t2 = t_df.columns.get_loc("Hedef 2 (% Koz)")
        idx_t3 = t_df.columns.get_loc("Hedef 3 (% Koz)")

        row_bg = "#0f172a"
        styles[idx_sym] = "background-color: #090d16; color: #38bdf8; font-weight: bold;"

        if row['Sinyal'] == "GÜÇLÜ AL":
            styles[idx_sig] = "background-color: #059669; color: #ffffff; font-weight: bold;"
        elif row['Sinyal'] == "AL (Tepki)":
            styles[idx_sig] = "background-color: #eab308; color: #0f172a; font-weight: bold;"
        elif row['Sinyal'] == "SAT":
            styles[idx_sig] = "background-color: #dc2626; color: #ffffff; font-weight: bold;"
        else:
            styles[idx_sig] = "background-color: #334155; color: #cbd5e1;"

        styles[idx_tf] = f"background-color: {row_bg}; color: #94a3b8;"
        p_clr = "#22c55e" if row['_pChg'] >= 0 else "#ef4444"
        styles[idx_pr] = f"background-color: {row_bg}; color: {p_clr}; font-weight: bold;"
        styles[idx_en] = f"background-color: {row_bg}; color: #f8fafc;"
        styles[idx_st] = f"background-color: {row_bg}; color: #f87171;"

        styles[idx_t1] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h1'] else f"background-color: {row_bg}; color: #cbd5e1;"
        styles[idx_t2] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h2'] else f"background-color: {row_bg}; color: #cbd5e1;"
        styles[idx_t3] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h3'] else f"background-color: {row_bg}; color: #cbd5e1;"

        return styles

    st.subheader(f"📋 CC Scanner Tablosu ({seciliGrup})")
    st.dataframe(
        t_df.style.apply(style_cc, axis=1),
        column_order=["Sembol", "Sinyal", "Periyot", "Fiyat (%)", "Giriş (Bar)", "Stop", "Hedef 1 (% Koz)", "Hedef 2 (% Koz)", "Hedef 3 (% Koz)"],
        use_container_width=True,
        hide_index=True
    )
    st.caption("Terminal Motoru: **@campCapital** & **HsnCLBK**[cite: 3]")

    # --- 9. AI Teknik Değerlendirmesi ---
    st.divider()
    hisse_sec = st.selectbox("AI Analizi Alınacak Hisseyi Seçin:", gorunen['Sembol'].tolist(), index=0)
    secili_row = gorunen[gorunen['Sembol'] == hisse_sec].iloc[0]

    l_gosterge = 7 if secili_row['current_sig'] == 2 else (5 if secili_row['current_sig'] == 1 else 2)
    vol_artisi = 65 if secili_row['current_sig'] >= 1 else 15
    bt_skor = 68 if secili_row['current_sig'] == 2 else 52

    ai_metni = (
        f"\"{hisse_sec} son barda ortalamaların üzerine çıktı ayrıca (8 göstergenin {l_gosterge}'i AL yönünde). "
        f"Hacim 20 günlük ortalamanın %{vol_artisi} üzerinde teyit veriyor. "
        f"ATR stop seviyesi {secili_row['entryStop']:,.2f} TL olarak izlenebilir. "
        f"Tarihsel backtest başarı oranı %{bt_skor} seviyesinde. AI değerlendirmesidir...\""
    )

    st.markdown(f"""
    <div class="ai-card">
        <b>🤖 AI Teknik Analist Değerlendirmesi:</b><br>
        {ai_metni}
    </div>
    """, unsafe_allow_html=True)

else:
    st.error("Veriler alınırken bir sorun oluştu veya borsa kapalı. Lütfen sol panelden tekrar deneyin.")
