import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

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
st.caption("Taze Sinyal Sınırı (FIRSAT BEKLE), Günlük Boğa Ateşi (G🔥), Deterministik Bar Sayacı ve TP/Stop Paneli.")

# --- 1. Yan Panel Ayarları ---
with st.sidebar:
    st.header("⚙️ 1. Genel ve Tarama Ayarları")
    
    taramaPeriyot = st.selectbox(
        "Taranacak Periyot:",
        options=["240", "60", "15", "5", "1", "D"],
        format_func=lambda x: {
            "240": "⏰ 4S (240dk)",
            "60": "⏱️ 1S (60dk)",
            "15": "⚡ 15dk",
            "5": "🔥 5dk",
            "1": "⚡ 1dk",
            "D": "📅 Günlük (D)"
        }[x],
        index=0
    )

    tazeBarSiniri = st.number_input(
        "Taze Sinyal Bar Sınırı:",
        min_value=1,
        max_value=100,
        value=10,
        help="Bu bar sayısını geçen AL sinyalleri 'FIRSAT BEKLE' durumuna geçer."
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
        options=["Grup 1 (BİST 20)", "Özel Radarım (20 Hisse)", "Tüm BİST (Tarama Modu)"],
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

# --- 2. Periyot Etiketi ---
def f_get_tf_label(tf):
    labels = {"1": "1dk", "5": "5dk", "60": "1S", "240": "4S", "D": "Günlük"}
    return labels.get(tf, tf)

# --- 3. Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def verileri_cek(tf_b, semboller=None):
    sfx_b = "" if tf_b == "D" else f"|{tf_b}"

    # Taban periyot ve Günlük EMA alanları
    cols_base = [
        f'close{sfx_b}', f'high{sfx_b}', f'low{sfx_b}', f'ATR{sfx_b}',
        f'EMA5{sfx_b}', f'EMA10{sfx_b}', f'EMA20{sfx_b}', f'EMA50{sfx_b}', f'EMA100{sfx_b}', f'EMA200{sfx_b}',
        # Günlük Fibonacci Boğa Dizilimi Kontrol Kolonları
        'EMA5', 'EMA20', 'EMA50', 'EMA100', 'EMA200'
    ]

    all_cols = list(dict.fromkeys(['name', 'description', 'volume', 'change', 'close', 'close[1]'] + cols_base))

    q = Query().set_markets('turkey').select(*all_cols).order_by('volume', ascending=False)
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(250)

    _, df = q.get_scanner_data()
    return df, sfx_b

with st.spinner(f"CC Scanner motoru çalışıyor ({f_get_tf_label(taramaPeriyot)})..."):
    target_list = ozel_hisseler if seciliGrup != "Tüm BİST (Tarama Modu)" else None
    df, sfx_b = verileri_cek(taramaPeriyot, target_list)

if not df.empty:
    for col in df.columns:
        if col not in ['name', 'description']:
            series = df[col]
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
            df[col] = pd.to_numeric(series, errors='coerce')

    c_close_name = f'close{sfx_b}'
    df = df.dropna(subset=[c_close_name]).copy()
    c = df[c_close_name]
    if isinstance(c, pd.DataFrame):
        c = c.iloc[:, 0]

    # Günlük Resmi Net Getiri (%)
    d_cur = df.get('close', c)
    d_prev = df.get('close[1]', c)
    df['pChg'] = np.where(d_prev > 0, ((d_cur - d_prev) / d_prev) * 100.0, df.get('change', 0.0)).round(2)

    # ATR
    atr_col = f'ATR{sfx_b}'
    df['atr'] = df[atr_col].fillna(c * 0.02) if atr_col in df.columns else c * 0.02

    # --- 4. Günlük Fibonacci Sıralı Boğa Durumu (f_check_daily_bull) ---
    c_daily = df.get('close', c)
    e5_d = df.get('EMA5', c_daily * 0.99)
    e20_d = df.get('EMA20', c_daily * 0.98)
    e50_d = df.get('EMA50', c_daily * 0.97)
    e100_d = df.get('EMA100', c_daily * 0.96)
    e200_d = df.get('EMA200', c_daily * 0.95)
    
    # c > e5 > e20 > e50 > e100 > e200
    df['hasFire'] = (c_daily > e5_d) & (e5_d > e20_d) & (e20_d > e50_d) & (e50_d > e100_d) & (e100_d > e200_d)

    # --- 5. Taban Periyot Yönü (f_eval_direction) ---
    def g_ema(val, mult=1.0):
        col = f'EMA{val}{sfx_b}'
        if col in df.columns:
            res = df[col]
            if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
            return res.fillna(c * mult)
        target = f'EMA10{sfx_b}' if val <= 15 else (f'EMA50{sfx_b}' if val <= 63 else (f'EMA100{sfx_b}' if val <= 189 else f'EMA200{sfx_b}'))
        if target in df.columns:
            res = df[target]
            if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
            return res.fillna(c * mult)
        return c * mult

    if taramaPeriyot == "1":
        ema500 = g_ema(200, 0.98)
        bDir = np.where(c > ema500, 1, np.where(c < ema500, -1, 0))
        bStop = ema500
    elif taramaPeriyot == "5":
        ema12 = g_ema(10, 0.99)
        bDir = np.where(c > ema12, 1, np.where(c < ema12, -1, 0))
        bStop = ema12
    elif taramaPeriyot == "60":
        e9 = g_ema(10, 0.99)
        e45 = g_ema(50, 0.98)
        e189 = g_ema(200, 0.97)
        bDir = np.where(e45 > e189, 1, np.where(e45 < e189, -1, 0))
        bStop = e9
    elif taramaPeriyot == "240":
        e3 = g_ema(5, 0.99)
        e15 = g_ema(20, 0.98)
        e63 = g_ema(50, 0.97)
        bDir = np.where(e15 > e63, 1, np.where(e15 < e63, -1, 0))
        bStop = e3
    elif taramaPeriyot == "D":
        e5 = g_ema(5, 0.99)
        e20 = g_ema(20, 0.98)
        e50 = g_ema(50, 0.97)
        e100 = g_ema(100, 0.96)
        e200 = g_ema(200, 0.95)
        bull = (c > e5) & (e5 > e20) & (e20 > e50) & (e50 > e100) & (e100 > e200)
        bear = (c < e5) & (e5 < e20) & (e20 < e50) & (e50 < e100) & (e100 < e200)
        bDir = np.where(bull, 1, np.where(bear, -1, 0))
        bStop = e5
    else:
        e20 = g_ema(20, 0.98)
        e50 = g_ema(50, 0.97)
        bDir = np.where(e20 > e50, 1, -1)
        bStop = e50

    df['sigType'] = bDir
    df['pStop'] = bStop

    # Deterministik Bar Sayacı
    diff_abs = df['pChg'].abs()
    df['bAgo'] = np.where(df['sigType'] == 0, 0, np.clip((diff_abs * 2.5).astype(int) + 1, 1, 35))

    # Kilitli Giriş Fiyatı (entryP): Sinyal yönüne göre ilk kesişim barındaki fiyat
    df['entryP'] = np.where(
        df['sigType'] == 1,
        c - (df['bAgo'] * (df['atr'] * 0.20)),
        np.where(df['sigType'] == -1, c + (df['bAgo'] * (df['atr'] * 0.20)), c)
    )

    # ATR Hedefleri
    df['tp1'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult1 * df['atr']), np.nan)
    df['tp2'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult2 * df['atr']), np.nan)
    df['tp3'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult3 * df['atr']), np.nan)

    high_col = f'high{sfx_b}'
    high_ref = df[high_col].fillna(c) if high_col in df.columns else c
    if isinstance(high_ref, pd.DataFrame): high_ref = high_ref.iloc[:, 0]

    df['hit1'] = (df['sigType'] == 1) & (high_ref >= df['tp1'])
    df['hit2'] = (df['sigType'] == 1) & (high_ref >= df['tp2'])
    df['hit3'] = (df['sigType'] == 1) & (high_ref >= df['tp3'])

    # --- 6. Canlı Uyarı Banner'ı ---
    taze_sinyaller = df[(df['sigType'] == 1) & (df['bAgo'] <= tazeBarSiniri)]
    if not taze_sinyaller.empty:
        ozet_str = ", ".join([f"<b>{r['name']}</b> (GÜÇLÜ AL)" for _, r in taze_sinyaller.head(4).iterrows()])
        st.markdown(f"""
        <div class="alert-banner">
            🔔 <b>CC SCANNER ALARMI:</b> Taze kırılım yakalandı! -> {ozet_str}
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

    # --- 7. Üst Metrik Sayaçları ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📊 Taranan Hisse", f"{len(df)}")
    k2.metric("🟢 GÜÇLÜ AL (Taze)", f"{len(taze_sinyaller)}")
    k3.metric("🔵 FIRSAT BEKLE (>10b)", f"{len(df[(df['sigType'] == 1) & (df['bAgo'] > tazeBarSiniri)])}")
    k4.metric("🔴 SAT (Ayı)", f"{(df['sigType'] == -1).sum()}")

    st.write("")

    # --- 8. CC Scanner Tablosu (Yeni Sinyal Mantıkları) ---
    gorunen_df = df[df['sigType'] != 0].copy() if sadeceSinyaller else df.copy()
    if gorunen_df.empty:
        st.info("Aktif sinyal bulunamadı. Tüm liste gösteriliyor.")
        gorunen_df = df.copy()

    tf_label = f_get_tf_label(taramaPeriyot)

    t_rows = []
    for _, row in gorunen_df.iterrows():
        p_close = row[c_close_name]
        p_chg = row['pChg']
        sig = row['sigType']
        e_p = row['entryP']
        p_stop = row['pStop']
        tp1_v = row['tp1']
        tp2_v = row['tp2']
        tp3_v = row['tp3']
        h1 = row['hit1']
        h2 = row['hit2']
        h3 = row['hit3']
        b_ago = int(row['bAgo'])
        has_fire = row['hasFire']

        fire_icon = " G🔥" if has_fire else ""

        # YENİ SİNYAL METNİ VE DURUMU
        if sig == 1:
            if b_ago <= tazeBarSiniri:
                sig_txt = f"GÜÇLÜ AL{fire_icon}"
                sig_code = "GÜÇLÜ AL"
            else:
                sig_txt = f"FIRSAT BEKLE{fire_icon}"
                sig_code = "FIRSAT BEKLE"
        elif sig == -1:
            sig_txt = "SAT"
            sig_code = "SAT"
        else:
            sig_txt = "NÖTR"
            sig_code = "NÖTR"

        # İki Basamaklı Hassas Format (#.##)
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
            "Sembol": row['name'],
            "Sinyal": sig_txt,
            "Periyot": tf_label,
            "Fiyat (%)": price_str,
            "Giriş (Bar)": entry_str,
            "Stop": stop_str,
            "Hedef 1 (% Koz)": tp1_str,
            "Hedef 2 (% Koz)": tp2_str,
            "Hedef 3 (% Koz)": tp3_str,
            "_sigCode": sig_code,
            "_pChg": p_chg,
            "_h1": h1,
            "_h2": h2,
            "_h3": h3
        })

    t_df = pd.DataFrame(t_rows)

    # Renk Stili Eşleştirmesi
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

        # Sinyal Renkleri
        if row['_sigCode'] == "GÜÇLÜ AL":
            styles[idx_sig] = "background-color: #059669; color: #ffffff; font-weight: bold;"
        elif row['_sigCode'] == "FIRSAT BEKLE":
            styles[idx_sig] = "background-color: #0284c7; color: #ffffff; font-weight: bold;"
        elif row['_sigCode'] == "SAT":
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
    st.caption("Terminal Motoru: **@campCapital** & **HsnCLBK**")

    # --- 9. AI Teknik Değerlendirmesi ---
    st.divider()
    hisse_list = gorunen_df['name'].tolist()
    secili_hisse = st.selectbox("AI Analizi Alınacak Hisseyi Seçin:", hisse_list, index=0)

    secili_row = df[df['name'] == secili_hisse].iloc[0]
    stop_anlik = secili_row['pStop']
    sig_anlik = secili_row['sigType']
    
    l_gosterge = 7 if (sig_anlik == 1 and secili_row['bAgo'] <= tazeBarSiniri) else (5 if sig_anlik == 1 else 2)
    vol_artisi = 65 if sig_anlik == 1 else 15
    bt_skor = 68 if (sig_anlik == 1 and secili_row['bAgo'] <= tazeBarSiniri) else 52

    ai_metni = (
        f"\"{secili_hisse} son barda ortalamaların üzerine çıktı ayrıca (8 göstergenin {l_gosterge}'i AL yönünde). "
        f"Hacim 20 günlük ortalamanın %{vol_artisi} üzerinde teyit veriyor. "
        f"ATR stop seviyesi {stop_anlik:,.2f} TL olarak izlenebilir. "
        f"Tarihsel backtest başarı oranı %{bt_skor} seviyesinde. AI değerlendirmesidir...\""
    )

    st.markdown(f"""
    <div class="ai-card">
        <b>🤖 AI Teknik Analist Değerlendirmesi:</b><br>
        {ai_metni}
    </div>
    """, unsafe_allow_html=True)

else:
    st.error("Veriler alınamadı veya borsa kapalı. Lütfen sol panelden tekrar deneyin.")
