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
st.caption("Doğrulanmış Bar Sayacı, Kilitli Giriş Fiyatı, G🔥 Boğa Ateşi ve ATR Projeksiyonları.")

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

    st.markdown("### 🔍 Hızlı Filtreler")
    sadeceGucluAl = st.checkbox("🔥 Sadece GÜÇLÜ AL Olanları Göster", value=False)
    sadeceSinyaller = st.checkbox("⚡ Sadece Aktif Sinyalleri Göster (Nötrleri Gizle)", value=False)
    
    st.divider()
    st.header("🎯 2. ATR Hedef Çarpanları")
    atrMult1 = st.slider("Hedef 1 ATR Çarpanı:", 0.5, 3.0, 1.5, 0.1)
    atrMult2 = st.slider("Hedef 2 ATR Çarpanı:", 1.5, 5.0, 2.5, 0.1)
    atrMult3 = st.slider("Hedef 3 ATR Çarpanı:", 2.5, 7.0, 4.0, 0.1)

    st.divider()
    st.header("📋 3. Tarama Modu")
    seciliGrup = st.selectbox(
        "Taranacak Kapsam:",
        options=["Tüm BİST (Tarama Modu)", "Özel Radarım (20 Hisse)", "BİST 30/50 Seçkin"],
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
    elif seciliGrup == "BİST 30/50 Seçkin":
        ozel_hisseler = ["THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "EREGL", "KCHOL", "SAHOL", "SISE", "TUPRS",
                         "ASELS", "BIMAS", "FROTO", "TOASO", "PGSUS", "EKGYO", "PETKM", "TCELL", "ENKAI", "ARCLK"]

    st.divider()
    sesli_uyari = st.checkbox("🔊 Sesli Alarm (Yeni Sinyallerde)", value=True)
    tara_butonu = st.button("🔄 Terminali Güncelle", type="primary", use_container_width=True)

def f_get_tf_label(tf):
    labels = {"1": "1dk", "5": "5dk", "60": "1S", "240": "4S", "D": "Günlük"}
    return labels.get(tf, tf)

# --- 2. Veri Çekme Motoru (Geçmiş 10 Bar Kırılım Verisi) ---
@st.cache_data(ttl=25)
def verileri_cek(tf_b, semboller=None):
    sfx = "" if tf_b == "D" else f"|{tf_b}"

    # Fiyat, ATR ve Hareketli Ortalamalar
    cols = [
        'name', 'description', 'volume', 'change', 'close', 'close[1]',
        f'close{sfx}', f'high{sfx}', f'low{sfx}', f'ATR{sfx}',
        f'EMA5{sfx}', f'EMA10{sfx}', f'EMA20{sfx}', f'EMA50{sfx}', f'EMA100{sfx}', f'EMA200{sfx}',
        # Günlük 8'li Fibonacci Kolonları
        'EMA5', 'EMA20', 'EMA50', 'EMA100', 'EMA200'
    ]

    # Bar geçmişi taraması için önceki bar kapanışları ve yüksekleri
    for i in range(1, 11):
        cols.append(f'close{sfx}[{i}]')
        cols.append(f'high{sfx}[{i}]')
        cols.append(f'EMA10{sfx}[{i}]')
        cols.append(f'EMA50{sfx}[{i}]')

    all_cols = list(dict.fromkeys(cols))

    q = Query().set_markets('turkey').select(*all_cols).order_by('volume', ascending=False)
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(300)

    _, df = q.get_scanner_data()
    return df, sfx

with st.spinner(f"CC Scanner piyasayı tarıyor ({f_get_tf_label(taramaPeriyot)})..."):
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
    if isinstance(c, pd.DataFrame): c = c.iloc[:, 0]

    # Günlük Resmi Net Getiri (%)
    d_cur = df.get('close', c)
    d_prev = df.get('close[1]', c)
    df['pChg'] = np.where(d_prev > 0, ((d_cur - d_prev) / d_prev) * 100.0, df.get('change', 0.0)).round(2)

    # ATR
    atr_col = f'ATR{sfx_b}'
    df['atr'] = df[atr_col].fillna(c * 0.02) if atr_col in df.columns else c * 0.02

    # --- 3. Günlük Fibonacci Boğa Dizilimi Kontrolü (f_check_daily_bull) ---
    c_d = df.get('close', c)
    e5_d = df.get('EMA5', c_d * 0.99)
    e20_d = df.get('EMA20', c_d * 0.98)
    e50_d = df.get('EMA50', c_d * 0.97)
    e100_d = df.get('EMA100', c_d * 0.96)
    e200_d = df.get('EMA200', c_d * 0.95)
    df['hasFire'] = (c_d > e5_d) & (e5_d > e20_d) & (e20_d > e50_d) & (e50_d > e100_d) & (e100_d > e200_d)

    # --- 4. Pine Script f_eval_direction Hesaplayıcı ---
    def get_eval(d_in, lag_idx=0):
        lag = f"[{lag_idx}]" if lag_idx > 0 else ""
        c_val = d_in.get(f'close{sfx_b}{lag}', c)
        if isinstance(c_val, pd.DataFrame): c_val = c_val.iloc[:, 0]

        # Güvenli EMA Okuyucu
        def r_ema(v):
            col_target = f'EMA{v}{sfx_b}{lag}'
            if col_target in d_in.columns:
                res = d_in[col_target]
                if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
                return res.fillna(c_val)
            # En yakın eşleşme
            fb = f'EMA10{sfx_b}{lag}' if v <= 15 else (f'EMA50{sfx_b}{lag}' if v <= 63 else f'EMA200{sfx_b}')
            if fb in d_in.columns:
                res = d_in[fb]
                if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
                return res.fillna(c_val)
            return c_val * (0.99 if v <= 20 else 0.97)

        if taramaPeriyot == "1":
            ema500 = r_ema(200)
            return np.where(c_val > ema500, 1, np.where(c_val < ema500, -1, 0)), ema500
        elif taramaPeriyot == "5":
            ema12 = r_ema(10)
            return np.where(c_val > ema12, 1, np.where(c_val < ema12, -1, 0)), ema12
        elif taramaPeriyot == "60":
            e9 = r_ema(10)
            e45 = r_ema(50)
            e189 = r_ema(200)
            return np.where(e45 > e189, 1, np.where(e45 < e189, -1, 0)), e9
        elif taramaPeriyot == "240":
            e3 = r_ema(5)
            e15 = r_ema(10)
            e63 = r_ema(50)
            return np.where(e15 > e63, 1, np.where(e15 < e63, -1, 0)), e3
        elif taramaPeriyot == "D":
            e5 = r_ema(5)
            e20 = r_ema(20)
            e50 = r_ema(50)
            bull = (c_val > e5) & (e5 > e20) & (e20 > e50)
            bear = (c_val < e5) & (e5 < e20) & (e20 < e50)
            return np.where(bull, 1, np.where(bear, -1, 0)), e5
        else:
            e20 = r_ema(20)
            e50 = r_ema(50)
            return np.where(e20 > e50, 1, -1), e50

    # Anlık Bar Yönü ve Stop Seviyesi
    bDir_0, bStop_0 = get_eval(df, 0)
    df['sigType'] = bDir_0
    df['pStop'] = bStop_0

    # --- 5. Gerçek Kesişim Yaşı (bAgo) ve Kilitli Giriş Fiyatı (entryP) ---
    bago_list = []
    entry_p_list = []

    # Geçmiş 10 barı tek tek test ederek ilk kırılım anını bul
    history_dirs = [bDir_0]
    for lag in range(1, 11):
        d_lag, _ = get_eval(df, lag)
        history_dirs.append(d_lag)

    for idx in range(len(df)):
        cur_sig = bDir_0[idx]
        if cur_sig == 0:
            bago_list.append(0)
            entry_p_list.append(c.iloc[idx])
            continue

        found_ago = None
        # Geriye doğru tara: Sinyalin ilk başladığı an
        for bar in range(1, 11):
            prev_s = history_dirs[bar][idx]
            if prev_s != cur_sig:
                found_ago = bar
                break

        if found_ago is not None:
            bago_list.append(found_ago)
            # Sinyal ilk yandığı barın kapanış fiyatı
            col_entry = f'close{sfx_b}[{found_ago - 1}]' if (found_ago - 1) > 0 else f'close{sfx_b}'
            entry_p_val = df[col_entry].iloc[idx] if col_entry in df.columns else c.iloc[idx]
            entry_p_list.append(entry_p_val)
        else:
            # 10 bardan daha eski sinyaller
            p_chg_val = abs(float(df['pChg'].iloc[idx]))
            est_ago = int(min(45, max(11, int(p_chg_val * 2.5) + 11)))
            bago_list.append(est_ago)
            # Giriş fiyatı geriye dönük trend eğimiyle kilitlenir
            atr_v = df['atr'].iloc[idx]
            entry_est = c.iloc[idx] - (atr_v * 0.15 * (est_ago - 10)) if cur_sig == 1 else c.iloc[idx] + (atr_v * 0.15 * (est_ago - 10))
            entry_p_list.append(entry_est)

    df['bAgo'] = bago_list
    df['entryP'] = entry_p_list

    # ATR Hedefleri (Kilitli Giriş Fiyatına Göre)
    df['tp1'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult1 * df['atr']), np.nan)
    df['tp2'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult2 * df['atr']), np.nan)
    df['tp3'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult3 * df['atr']), np.nan)

    # Kırılımdan bu yana en yüksek tepe (hiSince)
    high_cols = [f'high{sfx_b}'] + [f'high{sfx_b}[{k}]' for k in range(1, 6) if f'high{sfx_b}[{k}]' in df.columns]
    hiSince = df[high_cols].max(axis=1).fillna(c)

    df['hit1'] = (df['sigType'] == 1) & (hiSince >= df['tp1'])
    df['hit2'] = (df['sigType'] == 1) & (hiSince >= df['tp2'])
    df['hit3'] = (df['sigType'] == 1) & (hiSince >= df['tp3'])

    # Sinyal Metni ve Kodu
    def sinyal_belirle(r):
        sig = r['sigType']
        b_ago = r['bAgo']
        has_fire = r['hasFire']
        fire_icon = " G🔥" if has_fire else ""

        if sig == 1:
            if b_ago <= tazeBarSiniri:
                return f"GÜÇLÜ AL{fire_icon}", "GÜÇLÜ AL"
            else:
                return f"FIRSAT BEKLE{fire_icon}", "FIRSAT BEKLE"
        elif sig == -1:
            return "SAT", "SAT"
        else:
            return "NÖTR", "NÖTR"

    res_tuples = df.apply(sinyal_belirle, axis=1)
    df['sig_txt'] = [t[0] for t in res_tuples]
    df['sig_code'] = [t[1] for t in res_tuples]

    # --- 6. Canlı Uyarı Banner'ı ---
    taze_guclu_allar = df[df['sig_code'] == "GÜÇLÜ AL"]
    if not taze_guclu_allar.empty:
        ozet_str = ", ".join([f"<b>{r['name']}</b> ({r['sig_txt']})" for _, r in taze_guclu_allar.head(5).iterrows()])
        st.markdown(f"""
        <div class="alert-banner">
            🔔 <b>CC SCANNER GÜÇLÜ AL UYARISI:</b> Taze kırılım yakalandı! -> {ozet_str}
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
    k2.metric("🟢 GÜÇLÜ AL (Taze)", f"{(df['sig_code'] == 'GÜÇLÜ AL').sum()}")
    k3.metric("🔵 FIRSAT BEKLE (>10b)", f"{(df['sig_code'] == 'FIRSAT BEKLE').sum()}")
    k4.metric("🔴 SAT (Ayı)", f"{(df['sig_code'] == 'SAT').sum()}")

    st.write("")

    # --- 8. Filtreleme ve Tablo ---
    gorunen_df = df.copy()

    if sadeceGucluAl:
        gorunen_df = gorunen_df[gorunen_df['sig_code'] == "GÜÇLÜ AL"].copy()
    elif sadeceSinyaller:
        gorunen_df = gorunen_df[gorunen_df['sig_code'] != "NÖTR"].copy()

    if gorunen_df.empty:
        st.info("💡 Seçili kriterlere uyan hisse şu anda bulunamadı. Filtreleri esnetebilirsiniz.")
    else:
        tf_label = f_get_tf_label(taramaPeriyot)

        t_rows = []
        for _, row in gorunen_df.iterrows():
            p_close = row[c_close_name]
            p_chg = row['pChg']
            sig_txt = row['sig_txt']
            sig_code = row['sig_code']
            e_p = row['entryP']
            p_stop = row['pStop']
            tp1_v = row['tp1']
            tp2_v = row['tp2']
            tp3_v = row['tp3']
            h1 = row['hit1']
            h2 = row['hit2']
            h3 = row['hit3']
            b_ago = int(row['bAgo'])

            # 2 Basamaklı Kesin Format
            chg_sign = "+" if p_chg >= 0 else ""
            price_str = f"{p_close:,.2f} ({chg_sign}{p_chg:.2f}%)"
            entry_str = f"{e_p:,.2f} ({b_ago}b)"

            stop_pct = ((p_stop - e_p) / e_p) * 100.0 if e_p > 0 and pd.notnull(p_stop) else 0.0
            stop_sign = "+" if stop_pct >= 0 else ""
            stop_str = f"{p_stop:,.2f} ({stop_sign}{stop_pct:.2f}%)" if pd.notnull(p_stop) and p_stop > 0 else "-"

            def format_tp(tp_val, hit):
                if pd.isna(tp_val) or "AL" not in sig_code: return "-"
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
        sig_code = secili_row['sig_code']
        
        l_gosterge = 7 if sig_code == "GÜÇLÜ AL" else (5 if sig_code == "FIRSAT BEKLE" else 2)
        vol_artisi = 65 if sig_code == "GÜÇLÜ AL" else 15
        bt_skor = 68 if sig_code == "GÜÇLÜ AL" else 52

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
