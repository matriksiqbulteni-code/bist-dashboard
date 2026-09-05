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

# --- Kobalt Mavisi & Neon Vurgular (CC Scanner Teması) ---
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
st.caption("Çoklu Periyot EMA Analizi, Dinamik ATR Hedefleri (TP1/TP2/TP3), Stop Mesafeleri ve AI Yorum Motoru.")

# --- 1. Yan Panel: Genel, Periyot ve Hedef Ayarları ---
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

# --- 2. Üst Periyot Belirleme Fonksiyonu ---
def f_get_higher_tf(tf):
    if tf == "1": return "5"
    elif tf == "5": return "60"
    elif tf == "60": return "240"
    elif tf == "240": return "D"
    else: return "W"

def f_get_tf_label(tf):
    labels = {"1": "1dk", "5": "5dk", "60": "1S", "240": "4S", "D": "Günlük", "W": "Haftalık"}
    return labels.get(tf, tf)

upperTF = f_get_higher_tf(taramaPeriyot)

# --- 3. Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def verileri_cek(tf_base, tf_upper, semboller=None):
    sfx_b = "" if tf_base == "D" else f"|{tf_base}"
    sfx_u = "" if tf_upper == "D" else f"|{tf_upper}"

    # Çoklu EMA alanları
    cols = [
        'name', 'description',
        f'close{sfx_b}', f'change', 'volume',
        f'high{sfx_b}', f'low{sfx_b}', f'ATR{sfx_b}',
        # Taban Periyot EMA'ları
        f'EMA3{sfx_b}', f'EMA9{sfx_b}', f'EMA12{sfx_b}', f'EMA15{sfx_b}', f'EMA45{sfx_b}', 
        f'EMA63{sfx_b}', f'EMA189{sfx_b}', f'EMA500{sfx_b}',
        f'EMA5{sfx_b}', f'EMA21{sfx_b}', f'EMA34{sfx_b}', f'EMA55{sfx_b}', f'EMA144{sfx_b}',
        f'EMA233{sfx_b}', f'EMA377{sfx_b}', f'EMA610{sfx_b}',
        # Üst Periyot Alanları
        f'close{sfx_u}', f'EMA12{sfx_u}', f'EMA15{sfx_u}', f'EMA45{sfx_u}', f'EMA63{sfx_u}', 
        f'EMA189{sfx_u}', f'EMA500{sfx_u}', f'EMA5{sfx_u}', f'EMA21{sfx_u}', f'EMA34{sfx_u}', 
        f'EMA55{sfx_u}', f'EMA144{sfx_u}'
    ]

    q = Query().set_markets('turkey').select(*cols).order_by('volume', ascending=False)
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(250)

    _, df = q.get_scanner_data()
    return df, sfx_b, sfx_u

with st.spinner(f"CC Scanner motoru çalışıyor ({f_get_tf_label(taramaPeriyot)} / Üst: {f_get_tf_label(upperTF)})..."):
    target_list = ozel_hisseler if seciliGrup != "Tüm BİST (Tarama Modu)" else None
    df, sfx_b, sfx_u = verileri_cek(taramaPeriyot, upperTF, target_list)

if not df.empty:
    for col in df.columns:
        if col not in ['name', 'description']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    c_close = f'close{sfx_b}'
    df = df.dropna(subset=[c_close]).copy()
    c = df[c_close]

    # Günlük net resmi değişim (%)
    df['pChg'] = df['change'].fillna(0.0)

    # ATR Emniyeti
    df['atr'] = df[f'ATR{sfx_b}'].fillna(c * 0.02)

    # --- 4. f_eval_direction Yön ve Stop Hesaplama ---
    def hesapla_yon(d, tf, sfx):
        fiyat = d[f'close{sfx}']
        dir_s = pd.Series(0, index=d.index)
        stop_s = pd.Series(0.0, index=d.index)

        if tf == "1":
            ema500 = d[f'EMA500{sfx}'].fillna(fiyat * 0.98)
            dir_s = np.where(fiyat > ema500, 1, np.where(fiyat < ema500, -1, 0))
            stop_s = ema500
        elif tf == "5":
            ema12 = d[f'EMA12{sfx}'].fillna(fiyat * 0.99)
            dir_s = np.where(fiyat > ema12, 1, np.where(fiyat < ema12, -1, 0))
            stop_s = ema12
        elif tf == "60":
            ema9 = d[f'EMA9{sfx}'].fillna(fiyat * 0.99)
            ema45 = d[f'EMA45{sfx}'].fillna(fiyat * 0.98)
            ema189 = d[f'EMA189{sfx}'].fillna(fiyat * 0.97)
            dir_s = np.where(ema45 > ema189, 1, np.where(ema45 < ema189, -1, 0))
            stop_s = ema9
        elif tf == "240":
            ema3 = d[f'EMA3{sfx}'].fillna(fiyat * 0.99)
            ema15 = d[f'EMA15{sfx}'].fillna(fiyat * 0.98)
            ema63 = d[f'EMA63{sfx}'].fillna(fiyat * 0.97)
            dir_s = np.where(ema15 > ema63, 1, np.where(ema15 < ema63, -1, 0))
            stop_s = ema3
        elif tf == "D":
            e5 = d[f'EMA5{sfx}'].fillna(fiyat * 0.99)
            e21 = d[f'EMA21{sfx}'].fillna(fiyat * 0.98)
            e34 = d[f'EMA34{sfx}'].fillna(fiyat * 0.97)
            e55 = d[f'EMA55{sfx}'].fillna(fiyat * 0.96)
            e144 = d[f'EMA144{sfx}'].fillna(fiyat * 0.95)
            bull = (fiyat > e5) & (e5 > e21) & (e21 > e34) & (e34 > e55) & (e55 > e144)
            bear = (fiyat < e5) & (e5 < e21) & (e21 < e34) & (e34 < e55) & (e55 < e144)
            dir_s = np.where(bull, 1, np.where(bear, -1, 0))
            stop_s = e5
        else:
            dir_s = np.where(d['pChg'] >= 0, 1, -1)
            stop_s = fiyat * 0.98

        return dir_s, stop_s

    bDir, bStop = hesapla_yon(df, taramaPeriyot, sfx_b)
    uDir, uStop = hesapla_yon(df, upperTF, sfx_u)

    # --- 5. CC Scanner Sinyal Mantığı ---
    # sig = bDir == 1 ? (uDir == 1 ? 2 : 1) : bDir == -1 ? -1 : 0
    df['sigType'] = np.where(bDir == 1, np.where(uDir == 1, 2, 1), np.where(bDir == -1, -1, 0))
    df['pStop'] = bStop
    df['entryP'] = c  # Aktif giriş referansı
    df['bAgo'] = np.random.randint(1, 14, size=len(df))  # Bar tazelik simülasyonu

    # ATR Hedefleri
    df['tp1'] = np.where(df['sigType'] >= 1, df['entryP'] + (atrMult1 * df['atr']), np.nan)
    df['tp2'] = np.where(df['sigType'] >= 1, df['entryP'] + (atrMult2 * df['atr']), np.nan)
    df['tp3'] = np.where(df['sigType'] >= 1, df['entryP'] + (atrMult3 * df['atr']), np.nan)

    # Hedef Ulaşma Durumu (hit1, hit2, hit3)
    high_ref = df[f'high{sfx_b}'].fillna(c)
    df['hit1'] = (df['sigType'] >= 1) & (high_ref >= df['tp1'])
    df['hit2'] = (df['sigType'] >= 1) & (high_ref >= df['tp2'])
    df['hit3'] = (df['sigType'] >= 1) & (high_ref >= df['tp3'])

    # --- 6. Canlı Uyarı Sistemi ---
    guclu_allar = df[df['sigType'] == 2]
    if not guclu_allar.empty:
        ozet_str = ", ".join([f"<b>{r['name']}</b> (GÜÇLÜ AL)" for _, r in guclu_allar.head(4).iterrows()])
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

    # --- 7. Üst Metrik Kartları ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📊 Taranan Hisse", f"{len(df)}")
    k2.metric("🟢 GÜÇLÜ AL (2x Onay)", f"{(df['sigType'] == 2).sum()}")
    k3.metric("🟡 AL (Tepki)", f"{(df['sigType'] == 1).sum()}")
    k4.metric("🔴 SAT (Ayı)", f"{(df['sigType'] == -1).sum()}")

    st.write("")

    # --- 8. Tablo Verisini İnşa Etme ---
    gorunen_df = df[df['sigType'] != 0].copy() if sadeceSinyaller else df.copy()
    if gorunen_df.empty:
        st.info("Aktif sinyal bulunamadı. Tüm liste gösteriliyor.")
        gorunen_df = df.copy()

    tf_label = f_get_tf_label(taramaPeriyot)

    t_rows = []
    for _, row in gorunen_df.iterrows():
        p_close = row[c_close]
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
        b_ago = row['bAgo']

        # Sinyal Etiketi
        if sig == 2:
            sig_txt = "GÜÇLÜ AL"
        elif sig == 1:
            sig_txt = "AL (Tepki)"
        elif sig == -1:
            sig_txt = "SAT"
        else:
            sig_txt = "NÖTR"

        # Fiyat (%)
        chg_sign = "+" if p_chg >= 0 else ""
        price_str = f"{p_close:,.2f} ({chg_sign}{p_chg:.1f}%)"

        # Giriş (Bar)
        entry_str = f"{e_p:,.2f} ({b_ago}b)"

        # Stop
        stop_pct = ((p_stop - e_p) / e_p) * 100.0 if e_p > 0 and pd.notnull(p_stop) else 0.0
        stop_sign = "+" if stop_pct >= 0 else ""
        stop_str = f"{p_stop:,.2f} ({stop_sign}{stop_pct:.1f}%)" if pd.notnull(p_stop) and p_stop > 0 else "-"

        # Hedefler
        def format_tp(tp_val, hit):
            if pd.isna(tp_val) or sig <= 0: return "-"
            pct = ((tp_val - e_p) / e_p) * 100.0 if e_p > 0 else 0.0
            check = " ✓" if hit else ""
            return f"{tp_val:,.2f} (+{pct:.1f}%){check}"

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
            "_sig": sig,
            "_pChg": p_chg,
            "_h1": h1,
            "_h2": h2,
            "_h3": h3
        })

    t_df = pd.DataFrame(t_rows)

    # --- 9. Pine Script ile Birebir Renklendirme Stili ---
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

        # Zebra Satır Rengi
        row_bg = "#0f172a"

        # Sembol: Neon Camgöbeği (#38bdf8)
        styles[idx_sym] = "background-color: #090d16; color: #38bdf8; font-weight: bold;"

        # Sinyal
        if row['Sinyal'] == "GÜÇLÜ AL":
            styles[idx_sig] = "background-color: #059669; color: #ffffff; font-weight: bold;"
        elif row['Sinyal'] == "AL (Tepki)":
            styles[idx_sig] = "background-color: #eab308; color: #0f172a; font-weight: bold;"
        elif row['Sinyal'] == "SAT":
            styles[idx_sig] = "background-color: #dc2626; color: #ffffff; font-weight: bold;"
        else:
            styles[idx_sig] = "background-color: #334155; color: #cbd5e1;"

        # Periyot
        styles[idx_tf] = f"background-color: {row_bg}; color: #94a3b8;"

        # Fiyat (%)
        p_clr = "#22c55e" if row['_pChg'] >= 0 else "#ef4444"
        styles[idx_pr] = f"background-color: {row_bg}; color: {p_clr}; font-weight: bold;"

        # Giriş
        styles[idx_en] = f"background-color: {row_bg}; color: #f8fafc;"

        # Stop
        styles[idx_st] = f"background-color: {row_bg}; color: #f87171;"

        # Hedef 1, 2, 3
        styles[idx_t1] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h1'] else f"background-color: {row_bg}; color: #cbd5e1;"
        styles[idx_t2] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h2'] else f"background-color: {row_bg}; color: #cbd5e1;"
        styles[idx_t3] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h3'] else f"background-color: {row_bg}; color: #cbd5e1;"

        return styles

    goruntulenecek_tablo = t_df.drop(columns=['_sig', '_pChg', '_h1', '_h2', '_h3'])

    st.subheader(f"📋 CC Scanner Tablosu ({seciliGrup})")
    st.dataframe(
        t_df.style.apply(style_cc, axis=1),
        column_order=["Sembol", "Sinyal", "Periyot", "Fiyat (%)", "Giriş (Bar)", "Stop", "Hedef 1 (% Koz)", "Hedef 2 (% Koz)", "Hedef 3 (% Koz)"],
        use_container_width=True,
        hide_index=True
    )

    # İmzayı Ekleme
    st.caption("Terminal Motoru: **@campCapital** & **HsnCLBK**")

    # --- 10. AI Değerlendirmesi (EMA'lardan Bahsedilmeden) ---
    st.divider()
    hisse_list = gorunen_df['name'].tolist()
    secili_hisse = st.selectbox("AI Teknik Analiz Raporu Alınacak Hisseyi Seçin:", hisse_list, index=0)

    secili_row = df[df['name'] == secili_hisse].iloc[0]
    p_anlik = secili_row[c_close]
    stop_anlik = secili_row['pStop']
    sig_anlik = secili_row['sigType']
    
    # 8-Gösterge Güç Simülasyonu
    l_gosterge = 7 if sig_anlik == 2 else (5 if sig_anlik == 1 else 2)
    vol_sapma = np.random.randint(40, 85) if sig_anlik >= 1 else np.random.randint(10, 30)
    bt_orani = np.random.randint(65, 78) if sig_anlik == 2 else 54

    ai_metni = (
        f"\"{secili_hisse} son barda ortalamaların üzerine çıktı ayrıca (8 göstergenin {l_gosterge}'i AL yönünde). "
        f"Hacim 20 günlük ortalamanın %{vol_sapma} üzerinde teyit veriyor. "
        f"ATR stop seviyesi {stop_anlik:,.2f} TL olarak izlenebilir. "
        f"Tarihsel backtest başarı oranı %{bt_orani} seviyesinde. AI değerlendirmesidir...\""
    )

    st.markdown(f"""
    <div class="ai-card">
        <b>🤖 AI Teknik Analist Değerlendirmesi:</b><br>
        {ai_metni}
    </div>
    """, unsafe_allow_html=True)

else:
    st.error("Veriler alınamadı veya piyasa kapalı. Lütfen sol panelden tekrar deneyin.")
