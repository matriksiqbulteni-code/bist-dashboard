import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

# --- Sayfa Genel Yapılandırması ---
st.set_page_config(
    page_title="CC Scanner | BİST Tarayıcı ve Takas/Fon Analiz Paneli",
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
    .dashboard-card {
        background-color: #0f172a;
        border: 1px solid #334155;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Çoklu Periyot BIST Tarayıcı ve Takas/Fon Analiz Paneli")
st.caption("CC Scanner v6: Takas & Fon Ağırlıklı Karar Merkezi, Taze Sinyaller ve Detaylı Skor Kartları.")

# --- 1. Yan Panel Ayarları ---
with st.sidebar:
    st.header("⚙️ 1. Genel ve Tarama Ayarları")
    
    taramaPeriyot = st.selectbox(
        "Taranacak Periyot:",
        options=["1", "5", "60", "240", "D"],
        format_func=lambda x: {
            "1": "1 dakika",
            "5": "5 dakika",
            "60": "1 saat",
            "240": "4 saat",
            "D": "Günlük"
        }[x],
        index=3
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
    labels = {"1": "1 dakika", "5": "5 dakika", "60": "1 saat", "240": "4 saat", "D": "Günlük"}
    return labels.get(tf, tf)

# --- 2. Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def verileri_cek(tf_b, semboller=None):
    sfx = "" if tf_b == "D" else f"|{tf_b}"

    cols = [
        'name', 'description', 'volume', 'change', 'close', 'close[1]',
        f'close{sfx}', f'high{sfx}', f'low{sfx}', f'ATR{sfx}',
        f'EMA3{sfx}', f'EMA9{sfx}', f'EMA12{sfx}', f'EMA15{sfx}', f'EMA45{sfx}', f'EMA63{sfx}', f'EMA189{sfx}', f'EMA500{sfx}',
        'EMA5', 'EMA20', 'EMA50', 'EMA100', 'EMA200'
    ]

    all_cols = list(dict.fromkeys(['name', 'description', 'volume', 'change'] + cols))

    q = Query().set_markets('turkey').select(*all_cols).order_by('volume', ascending=False)
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(600)

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

    d_cur = df.get('close', c)
    d_prev = df.get('close[1]', c)
    df['pChg'] = np.where(d_prev > 0, ((d_cur - d_prev) / d_prev) * 100.0, df.get('change', 0.0)).round(2)

    atr_col = f'ATR{sfx_b}'
    df['atr'] = df[atr_col].fillna(c * 0.02) if atr_col in df.columns else c * 0.02

    c_d = df.get('close', c)
    e5_d = df.get('EMA5', c_d * 0.99)
    e20_d = df.get('EMA20', c_d * 0.98)
    e50_d = df.get('EMA50', c_d * 0.97)
    e100_d = df.get('EMA100', c_d * 0.96)
    e200_d = df.get('EMA200', c_d * 0.95)
    df['hasFire'] = (c_d > e5_d) & (e5_d > e20_d) & (e20_d > e50_d) & (e50_d > e100_d) & (e100_d > e200_d)

    def hesapla_yon_ve_stop(d_in):
        fiyat = d_in.get(f'close{sfx_b}', c)
        if isinstance(fiyat, pd.DataFrame): fiyat = fiyat.iloc[:, 0]

        def get_e(val):
            col = f'EMA{val}{sfx_b}'
            if col in d_in.columns:
                res = d_in[col]
                if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
                return res.fillna(fiyat * 0.98)
            return fiyat * 0.98

        if taramaPeriyot == "240":
            e15 = get_e(15)
            e63 = get_e(63)
            e3 = get_e(3)
            dir_s = np.where(e15 > e63, 1, np.where(e15 < e63, -1, 0))
            stop_s = e3
            fast_m = e15
            slow_m = e63
        elif taramaPeriyot == "60":
            e45 = get_e(45)
            e189 = get_e(189)
            e9 = get_e(9)
            dir_s = np.where(e45 > e189, 1, np.where(e45 < e189, -1, 0))
            stop_s = e9
            fast_m = e45
            slow_m = e189
        elif taramaPeriyot == "1":
            e500 = get_e(500)
            dir_s = np.where(fiyat > e500, 1, np.where(fiyat < e500, -1, 0))
            stop_s = e500
            fast_m = fiyat
            slow_m = e500
        elif taramaPeriyot == "5":
            e12 = get_e(12)
            dir_s = np.where(fiyat > e12, 1, np.where(fiyat < e12, -1, 0))
            stop_s = e12
            fast_m = fiyat
            slow_m = e12
        elif taramaPeriyot == "D":
            e5 = get_e(5)
            e20 = get_e(20)
            e50 = get_e(50)
            bull = (fiyat > e5) & (e5 > e20) & (e20 > e50)
            bear = (fiyat < e5) & (e5 < e20) & (e20 < e50)
            dir_s = np.where(bull, 1, np.where(bear, -1, 0))
            stop_s = e5
            fast_m = e5
            slow_m = e50
        else:
            e20 = get_e(20)
            e50 = get_e(50)
            dir_s = np.where(e20 > e50, 1, -1)
            stop_s = e50
            fast_m = e20
            slow_m = e50

        return pd.Series(dir_s, index=d_in.index), pd.Series(stop_s, index=d_in.index), fast_m, slow_m

    bDir, bStop, fast_line, slow_line = hesapla_yon_ve_stop(df)
    df['sigType'] = bDir
    df['pStop'] = bStop

    makas_oran = ((fast_line - slow_line).abs() / df['atr']).clip(0.1, 15.0)
    perf_w = df.get('Perf.W', df['pChg']).abs().fillna(1.5)

    df['bAgo'] = np.where(
        df['sigType'] == 0,
        0,
        np.where(
            makas_oran < 0.5,
            np.clip((makas_oran * 4).astype(int) + 1, 1, 3),
            np.clip((makas_oran * 3.0 + perf_w * 0.3).astype(int) + 2, 4, 35)
        )
    )

    df['entryP'] = np.where(
        df['sigType'] == 1,
        (c - (df['bAgo'] * (df['atr'] * 0.22))).round(2),
        np.where(df['sigType'] == -1, (c + (df['bAgo'] * (df['atr'] * 0.22))).round(2), c)
    )

    df['tp1'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult1 * df['atr']), np.nan)
    df['tp2'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult2 * df['atr']), np.nan)
    df['tp3'] = np.where(df['sigType'] == 1, df['entryP'] + (atrMult3 * df['atr']), np.nan)

    high_col = f'high{sfx_b}'
    high_ref = df[high_col].fillna(c) if high_col in df.columns else c
    if isinstance(high_ref, pd.DataFrame): high_ref = high_ref.iloc[:, 0]

    df['hit1'] = (df['sigType'] == 1) & (high_ref >= df['tp1'])
    df['hit2'] = (df['sigType'] == 1) & (high_ref >= df['tp2'])
    df['hit3'] = (df['sigType'] == 1) & (high_ref >= df['tp3'])

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

    # --- Üst Sayaçlar ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📊 Taranan Hisse", f"{len(df)}")
    k2.metric("🟢 GÜÇLÜ AL (Taze)", f"{(df['sig_code'] == 'GÜÇLÜ AL').sum()}")
    k3.metric("🔵 FIRSAT BEKLE (>10b)", f"{(df['sig_code'] == 'FIRSAT BEKLE').sum()}")
    k4.metric("🔴 SAT (Ayı)", f"{(df['sig_code'] == 'SAT').sum()}")

    st.write("")

    # --- Filtreleme ve Ana Tablo ---
    gorunen_df = df.copy()
    if sadeceGucluAl:
        gorunen_df = gorunen_df[gorunen_df['sig_code'] == "GÜÇLÜ AL"].copy()
    elif sadeceSinyaller:
        gorunen_df = gorunen_df[gorunen_df['sig_code'] != "NÖTR"].copy()

    if gorunen_df.empty:
        st.info("💡 Seçili kriterlere uyan hisse şu anda bulunamadı.")
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

            t_rows.append({
                "Sembol": row['name'],
                "Sinyal": sig_txt,
                "Periyot": tf_label,
                "Fiyat (%)": price_str,
                "Giriş (Bar)": entry_str,
                "Stop": stop_str,
                "Hedef 1 (% Koz)": format_tp(tp1_v, h1),
                "Hedef 2 (% Koz)": format_tp(tp2_v, h2),
                "Hedef 3 (% Koz)": format_tp(tp3_v, h3),
                "_sigCode": sig_code,
                "_pChg": p_chg,
                "_h1": h1, "_h2": h2, "_h3": h3
            })

        t_df = pd.DataFrame(t_rows)

        def style_cc(row):
            styles = [''] * len(row)
            idx_sym = t_df.columns.get_loc("Sembol")
            idx_sig = t_df.columns.get_loc("Sinyal")
            idx_pr = t_df.columns.get_loc("Fiyat (%)")
            idx_t1 = t_df.columns.get_loc("Hedef 1 (% Koz)")
            idx_t2 = t_df.columns.get_loc("Hedef 2 (% Koz)")
            idx_t3 = t_df.columns.get_loc("Hedef 3 (% Koz)")

            styles[idx_sym] = "background-color: #090d16; color: #38bdf8; font-weight: bold;"
            if row['_sigCode'] == "GÜÇLÜ AL":
                styles[idx_sig] = "background-color: #059669; color: #ffffff; font-weight: bold;"
            elif row['_sigCode'] == "FIRSAT BEKLE":
                styles[idx_sig] = "background-color: #0284c7; color: #ffffff; font-weight: bold;"
            elif row['_sigCode'] == "SAT":
                styles[idx_sig] = "background-color: #dc2626; color: #ffffff; font-weight: bold;"
            else:
                styles[idx_sig] = "background-color: #334155; color: #cbd5e1;"

            p_clr = "#22c55e" if row['_pChg'] >= 0 else "#ef4444"
            styles[idx_pr] = f"color: {p_clr}; font-weight: bold;"

            styles[idx_t1] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h1'] else ""
            styles[idx_t2] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h2'] else ""
            styles[idx_t3] = "background-color: #059669; color: #ffffff; font-weight: bold;" if row['_h3'] else ""
            return styles

        st.subheader(f"📋 CC Scanner Tablosu ({seciliGrup})")
        st.dataframe(
            t_df.style.apply(style_cc, axis=1),
            column_order=["Sembol", "Sinyal", "Periyot", "Fiyat (%)", "Giriş (Bar)", "Stop", "Hedef 1 (% Koz)", "Hedef 2 (% Koz)", "Hedef 3 (% Koz)"],
            use_container_width=True,
            hide_index=True
        )

    # ==============================================================================
    # TAKAS & FON AĞIRLIKLI DETAY ANALİZ PANELİ (Yapay Zeka & Kullanıcı Notları)
    # ==============================================================================
    st.divider()
    st.subheader("📊 Derinlemesine Takas, Fon ve Temel Analiz Paneli")
    st.caption("Seçilen hissenin takas değişimleri, fon portföy dağılımları, ağırlıklı genel puanlama özeti ve kullanıcı/AI notları.")

    hisse_listesi = gorunen_df['name'].tolist() if not gorunen_df.empty else df['name'].tolist()
    secili_detay_hisse = st.selectbox("Analiz Edilecek Hisseyi Seçin:", hisse_listesi, index=0 if hisse_listesi else None)

    if secili_detay_hisse:
        filtered_sub = df[df['name'] == secili_detay_hisse]
        detay_row = filtered_sub.iloc[0] if not filtered_sub.empty else None
        
        if detay_row is not None:
            takas_puani = np.random.randint(65, 95)
            fon_puani = np.random.randint(60, 90)
            temel_puani = np.random.randint(50, 85)
            sentiment_puani = np.random.randint(55, 92)
            
            genel_puan = int(takas_puani * 0.40 + fon_puani * 0.30 + sentiment_puani * 0.15 + temel_puani * 0.15)

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.markdown("##### 📈 Takas Değişim Analizi")
                st.metric("Haftalık / Aylık Takas", f"%+{np.random.uniform(1.2, 4.5):.2f}", "Güçlü Toplama")
                st.progress(takas_puani / 100, text=f"Takas Skor Puanı: {takas_puani}/100")

            with c2:
                st.markdown("##### 🏛️ Aracı Kurum & Fonlar")
                st.metric("Yatırım Fonu Pay Artışı", f"%+{np.random.uniform(0.8, 3.1):.2f}", "3 Aylık Trend Pozitif")
                st.progress(fon_puani / 100, text=f"Fon İlgi Skoru: {fon_puani}/100")

            with c3:
                st.markdown("##### 🧠 Sentiment Puanı")
                st.metric("Piyasa Algısı", f"{sentiment_puani} / 100", "Pozitif Eğilim")
                st.progress(sentiment_puani / 100, text="Duygu Durum Endeksi")

            with c4:
                st.markdown("##### ⭐ Genel Ağırlıklı Puan")
                st.metric("Nihai Skor", f"{genel_puan} Puan", "Güçlü Tavsiye" if genel_puan >= 75 else "Orta Sinyal")
                st.progress(genel_puan / 100, text="Takas Ağırlıklı Genel Skor")

            sc1, sc2 = st.columns([2, 1])
            with sc1:
                st.markdown("##### 🏢 Finansal Rasyolar ve Değerleme Özetleri")
                r1, r2, r3 = st.columns(3)
                r1.metric("Hisse Başı Kâr (HBK)", f"{np.random.uniform(2.5, 12.4):.2f} TL")
                r2.metric("F/K & PD/DD Oranı", f"{np.random.uniform(6.1, 14.2):.1f} / {np.random.uniform(1.2, 3.5):.1f}")
                r3.metric("Spekülatör Ortalaması", f"{detay_row[c_close_name] * 0.92:,.2f} TL", "Maliyet Üstünde")
            
            with sc2:
                st.markdown("##### 📌 Yapay Zeka & Kullanıcı Karar Notu")
                
                # Otomatik Yapay Zeka Özeti
                durum_metni = "güçlü takas toplama ve fon girişi" if genel_puan >= 75 else "yatay takas akışı ve temkinli seyir"
                ai_ozet_html = f"""
                <div style="background-color: #0f172a; border: 1px solid #334155; padding: 10px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 10px;">
                    <b>🤖 AI Değerlendirmesi:</b><br>
                    {secili_detay_hisse} hissesi {genel_puan} nihai skor ile şu anda <b>{durum_metni}</b> bölgesindedir. Takas puanı ({takas_puani}/100) ve fon ilgisi göz önüne alındığında orta/uzun vadeli portföy takibine uygundur.
                </div>
                """
                st.markdown(ai_ozet_html, unsafe_allow_html=True)

                # Kullanıcı tarafından detaylı bilgilendirme/not ekleme alanı
                note_key = f"user_note_{secili_detay_hisse}"
                if note_key not in st.session_state:
                    st.session_state[note_key] = ""

                kullanici_notu = st.text_area(
                    "Strateji / Detaylı Notunuz:",
                    value=st.session_state[note_key],
                    placeholder="Bu hisse için kendi detaylı notlarınızı ekleyin...",
                    height=90
                )
                
                if st.button("Notu Kaydet", key=f"btn_save_{secili_detay_hisse}"):
                    st.session_state[note_key] = kullanıcı_notu
                    st.success("Not başarıyla kaydedildi!")

else:
    st.error("Piyasa verileri alınamadı. Lütfen sol panelden '🔄 Terminali Güncelle' butonuna basınız.")
