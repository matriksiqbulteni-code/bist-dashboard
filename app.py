
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

# ==============================================================================
# CC SCANNER v7
# BIST TARAMA + EMA + ATR(14) + GERÇEK KAPANIŞ MANTIĞI
# ==============================================================================

st.set_page_config(
    page_title="CC Scanner | BİST Tarayıcı ve Takas/Fon Analiz Paneli",
    page_icon="⚡",
    layout="wide"
)

# ==============================================================================
# CSS
# ==============================================================================

st.markdown("""
<style>
.main {
    background-color: #090d16;
}

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

.badge-green {
    background-color: rgba(5, 150, 105, 0.2);
    color: #34d399;
    border: 1px solid #059669;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-red {
    background-color: rgba(220, 38, 38, 0.2);
    color: #f87171;
    border: 1px solid #dc2626;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-yellow {
    background-color: rgba(202, 138, 4, 0.2);
    color: #facc15;
    border: 1px solid #ca8a04;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-blue {
    background-color: rgba(2, 132, 199, 0.2);
    color: #38bdf8;
    border: 1px solid #0284c7;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
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

# ==============================================================================
# BAŞLIK
# ==============================================================================

st.title("BIST Tarayıcı ve Takas/Fon Analiz Paneli @campCapital")
st.caption(
    "CC Scanner v7 | Kapanmış Bar + Gerçek Periyot Fiyatı + ATR(14) + "
    "Çoklu EMA Trend Motoru"
)

# ==============================================================================
# 1. SIDEBAR
# ==============================================================================

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
        help=(
            "Gerçek sinyal oluşumundan itibaren geçen bar sayısı "
            "bu sınırın altındaysa GÜÇLÜ AL kabul edilir."
        )
    )

    st.markdown("### 🔍 Hızlı Filtreler")

    sadeceGucluAl = st.checkbox(
        "🔥 Sadece GÜÇLÜ AL Olanları Göster",
        value=False
    )

    sadeceSinyaller = st.checkbox(
        "⚡ Sadece Aktif Sinyalleri Göster",
        value=False
    )

    st.divider()

    st.header("🎯 2. ATR(14) Hedef Çarpanları")

    atrMult1 = st.slider(
        "Hedef 1 ATR Çarpanı:",
        0.5, 3.0, 1.5, 0.1
    )

    atrMult2 = st.slider(
        "Hedef 2 ATR Çarpanı:",
        1.5, 5.0, 2.5, 0.1
    )

    atrMult3 = st.slider(
        "Hedef 3 ATR Çarpanı:",
        2.5, 7.0, 4.0, 0.1
    )

    st.divider()

    st.header("📋 3. Tarama Modu")

    seciliGrup = st.selectbox(
        "Taranacak Kapsam:",
        options=[
            "Tüm BİST (Tarama Modu)",
            "Özel Radarım (20 Hisse)",
            "BİST 30/50 Seçkin"
        ],
        index=0
    )

    ozel_hisseler = []

    default_radar = [
        "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK",
        "EREGL", "KCHOL", "SAHOL", "SISE", "TUPRS",
        "ASELS", "BIMAS", "FROTO", "TOASO", "PGSUS",
        "EKGYO", "PETKM", "TCELL", "ENKAI", "ARCLK"
    ]

    if seciliGrup == "Özel Radarım (20 Hisse)":

        st.markdown("### 🎯 Özel Radar Listeniz")

        c1, c2 = st.columns(2)

        for i in range(1, 21):

            col_target = c1 if i <= 10 else c2

            val = col_target.text_input(
                f"Hisse {i}",
                value=default_radar[i - 1],
                max_chars=10
            ).upper().strip()

            if val:
                ozel_hisseler.append(val)

    elif seciliGrup == "BİST 30/50 Seçkin":

        ozel_hisseler = default_radar.copy()

    st.divider()

    sesli_uyari = st.checkbox(
        "🔊 Sesli Alarm (Yeni Sinyallerde)",
        value=True
    )

    tara_butonu = st.button(
        "🔄 Terminali Güncelle",
        type="primary",
        use_container_width=True
    )


# ==============================================================================
# PERİYOT ETİKETİ
# ==============================================================================

def f_get_tf_label(tf):

    labels = {
        "1": "1 dakika",
        "5": "5 dakika",
        "60": "1 saat",
        "240": "4 saat",
        "D": "Günlük"
    }

    return labels.get(tf, tf)


# ==============================================================================
# EMA TANIMLARI
# ==============================================================================

# Günlük gerçek EMA yapısı
DAILY_EMAS = [
    5,
    21,
    34,
    55,
    144,
    233,
    377,
    610
]

# İntraday EMA'lar
INTRADAY_EMAS = [
    3,
    9,
    12,
    15,
    45,
    63,
    189,
    500
]


# ==============================================================================
# TRADINGVIEW SCANNER VERİ ÇEKME
# ==============================================================================

@st.cache_data(ttl=25)
def verileri_cek(tf_b, semboller=None):

    sfx = "" if tf_b == "D" else f"|{tf_b}"

    cols = [
        "name",
        "description",
        "volume",
        "change",
        "close",
        "close[1]",

        f"close{sfx}",
        f"close[1]{sfx}",
        f"high{sfx}",
        f"low{sfx}",

        # ATR = TradingView'in standart ATR(14) alanı
        f"ATR{sfx}",

        # Intraday EMA'lar
        f"EMA3{sfx}",
        f"EMA9{sfx}",
        f"EMA12{sfx}",
        f"EMA15{sfx}",
        f"EMA45{sfx}",
        f"EMA63{sfx}",
        f"EMA189{sfx}",
        f"EMA500{sfx}",

        # Günlük gerçek EMA yapısı
        "EMA5",
        "EMA21",
        "EMA34",
        "EMA55",
        "EMA144",
        "EMA233",
        "EMA377",
        "EMA610"
    ]

    all_cols = list(
        dict.fromkeys(
            [
                "name",
                "description",
                "volume",
                "change"
            ] + cols
        )
    )

    q = (
        Query()
        .set_markets("turkey")
        .select(*all_cols)
        .order_by("volume", ascending=False)
    )

    if semboller and len(semboller) > 0:

        q = q.where(
            Column("name").isin(semboller)
        )

    else:

        q = q.limit(600)

    _, df = q.get_scanner_data()

    return df, sfx


# ==============================================================================
# VERİ ÇEK
# ==============================================================================

with st.spinner(
    f"CC Scanner piyasayı tarıyor ({f_get_tf_label(taramaPeriyot)})..."
):

    target_list = (
        ozel_hisseler
        if seciliGrup != "Tüm BİST (Tarama Modu)"
        else None
    )

    df, sfx_b = verileri_cek(
        taramaPeriyot,
        target_list
    )


# ==============================================================================
# ANA MOTOR
# ==============================================================================

if not df.empty:

    # --------------------------------------------------------------------------
    # NUMERIC DÖNÜŞÜM
    # --------------------------------------------------------------------------

    for col in df.columns:

        if col not in ["name", "description"]:

            series = df[col]

            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]

            df[col] = pd.to_numeric(
                series,
                errors="coerce"
            )

    # --------------------------------------------------------------------------
    # SEÇİLEN PERİYODUN GERÇEK CLOSE DEĞERİ
    # --------------------------------------------------------------------------

    c_close_name = f"close{sfx_b}"

    if c_close_name not in df.columns:

        st.error(
            f"Seçilen periyoda ait {c_close_name} verisi alınamadı."
        )

        st.stop()

    df = df.dropna(
        subset=[c_close_name]
    ).copy()

    # Seçilen periyodun fiyatı
    c = df[c_close_name]

    if isinstance(c, pd.DataFrame):
        c = c.iloc[:, 0]

    c = pd.to_numeric(
        c,
        errors="coerce"
    )

    # --------------------------------------------------------------------------
    # SEÇİLEN PERİYODUN ÖNCEKİ KAPANIŞI
    # --------------------------------------------------------------------------

    prev_close_name = f"close[1]{sfx_b}"

    if prev_close_name in df.columns:

        prev_close = pd.to_numeric(
            df[prev_close_name],
            errors="coerce"
        )

    else:

        prev_close = pd.to_numeric(
            df.get("close[1]", c),
            errors="coerce"
        )

    # --------------------------------------------------------------------------
    # PERİYOT DOĞRU DEĞİŞİMİ
    # --------------------------------------------------------------------------

    fallback_change = pd.to_numeric(
        df.get("change", 0),
        errors="coerce"
    )

    df["pChg"] = np.where(
        prev_close > 0,
        ((c - prev_close) / prev_close) * 100.0,
        fallback_change
    )

    df["pChg"] = pd.to_numeric(
        df["pChg"],
        errors="coerce"
    ).round(2)

    # ==============================================================================
    # ATR(14)
    # ==============================================================================

    atr_col = f"ATR{sfx_b}"

    if atr_col in df.columns:

        df["atr"] = pd.to_numeric(
            df[atr_col],
            errors="coerce"
        )

    else:

        # Güvenli fallback
        df["atr"] = c * 0.02

    # ATR(14) bulunamadığında fiyatın %2'si
    # sadece veri eksikliği için fallback olarak kullanılır.
    df["atr"] = df["atr"].where(
        df["atr"] > 0,
        c * 0.02
    )

    # ==============================================================================
    # GÜNLÜK EMA MOTORU
    # ==============================================================================

    daily_ema_values = {}

    for period in DAILY_EMAS:

        col_name = f"EMA{period}"

        if col_name in df.columns:

            daily_ema_values[period] = pd.to_numeric(
                df[col_name],
                errors="coerce"
            )

        else:

            daily_ema_values[period] = c * np.nan

    e5_d = daily_ema_values[5]
    e21_d = daily_ema_values[21]
    e34_d = daily_ema_values[34]
    e55_d = daily_ema_values[55]
    e144_d = daily_ema_values[144]
    e233_d = daily_ema_values[233]
    e377_d = daily_ema_values[377]
    e610_d = daily_ema_values[610]

    # ==============================================================================
    # GÜNLÜK GERÇEK "TÜM EMA'LAR ÜZERİNDE" KOŞULU
    # ==============================================================================

    df["daily_all_ema_bull"] = (

        (c > e5_d) &
        (c > e21_d) &
        (c > e34_d) &
        (c > e55_d) &
        (c > e144_d) &
        (c > e233_d) &
        (c > e377_d) &
        (c > e610_d)

    )

    # ==============================================================================
    # GÜNLÜK EMA HİYERARŞİSİ
    # ==============================================================================

    df["daily_ema_stack_bull"] = (

        (c > e5_d) &
        (e5_d > e21_d) &
        (e21_d > e34_d) &
        (e34_d > e55_d) &
        (e55_d > e144_d) &
        (e144_d > e233_d) &
        (e233_d > e377_d) &
        (e377_d > e610_d)

    )

    # --------------------------------------------------------------------------
    # GÜNLÜK GÜÇLÜ AL
    #
    # Kullanıcı şartı:
    #
    # ANLIK FİYAT > EMA5 > EMA21 > EMA34 > EMA55
    # > EMA144 > EMA233 > EMA377 > EMA610
    #
    # --------------------------------------------------------------------------

    df["daily_strong_bull"] = (

        (c > e5_d) &
        (e5_d > e21_d) &
        (e21_d > e34_d) &
        (e34_d > e55_d) &
        (e55_d > e144_d) &
        (e144_d > e233_d) &
        (e233_d > e377_d) &
        (e377_d > e610_d)

    )

    # ==============================================================================
    # GÜNLÜK EMA5 STOP
    # ==============================================================================

    df["daily_stop"] = e5_d

    # ==============================================================================
    # PERİYODA GÖRE ANA SİNYAL MOTORU
    # ==============================================================================

    def hesapla_yon_ve_stop(d_in):

        fiyat = pd.to_numeric(
            d_in[c_close_name],
            errors="coerce"
        )

        def get_e(period):

            col = f"EMA{period}{sfx_b}"

            if col in d_in.columns:

                return pd.to_numeric(
                    d_in[col],
                    errors="coerce"
                )

            return pd.Series(
                np.nan,
                index=d_in.index
            )

        # ----------------------------------------------------------------------
        # 240 DAKİKA
        # ----------------------------------------------------------------------

        if taramaPeriyot == "240":

            e15 = get_e(15)
            e63 = get_e(63)
            e3 = get_e(3)

            bull = e15 > e63
            bear = e15 < e63

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            stop_s = e3
            fast_m = e15
            slow_m = e63

        # ----------------------------------------------------------------------
        # 60 DAKİKA
        # ----------------------------------------------------------------------

        elif taramaPeriyot == "60":

            e45 = get_e(45)
            e189 = get_e(189)
            e9 = get_e(9)

            bull = e45 > e189
            bear = e45 < e189

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            stop_s = e9
            fast_m = e45
            slow_m = e189

        # ----------------------------------------------------------------------
        # 1 DAKİKA
        # ----------------------------------------------------------------------

        elif taramaPeriyot == "1":

            e500 = get_e(500)

            bull = fiyat > e500
            bear = fiyat < e500

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            stop_s = e500
            fast_m = fiyat
            slow_m = e500

        # ----------------------------------------------------------------------
        # 5 DAKİKA
        # ----------------------------------------------------------------------

        elif taramaPeriyot == "5":

            e12 = get_e(12)

            bull = fiyat > e12
            bear = fiyat < e12

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            stop_s = e12
            fast_m = fiyat
            slow_m = e12

        # ----------------------------------------------------------------------
        # GÜNLÜK
        #
        # YENİ:
        # Fiyat > EMA5 > EMA21 > EMA34 > EMA55
        # > EMA144 > EMA233 > EMA377 > EMA610
        # ----------------------------------------------------------------------

        elif taramaPeriyot == "D":

            bull = (

                (fiyat > e5_d) &
                (e5_d > e21_d) &
                (e21_d > e34_d) &
                (e34_d > e55_d) &
                (e55_d > e144_d) &
                (e144_d > e233_d) &
                (e233_d > e377_d) &
                (e377_d > e610_d)

            )

            bear = (

                (fiyat < e5_d) &
                (e5_d < e21_d) &
                (e21_d < e34_d) &
                (e34_d < e55_d) &
                (e55_d < e144_d) &
                (e144_d < e233_d) &
                (e233_d < e377_d) &
                (e377_d < e610_d)

            )

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            # Kullanıcının belirttiği günlük stop
            stop_s = e5_d

            fast_m = e5_d
            slow_m = e610_d

        else:

            e20 = get_e(20)
            e50 = get_e(50)

            bull = e20 > e50
            bear = e20 < e50

            dir_s = np.where(
                bull,
                1,
                np.where(
                    bear,
                    -1,
                    0
                )
            )

            stop_s = e50
            fast_m = e20
            slow_m = e50

        return (
            pd.Series(dir_s, index=d_in.index),
            pd.Series(stop_s, index=d_in.index),
            fast_m,
            slow_m
        )

    # ==============================================================================
    # YÖN
    # ==============================================================================

    bDir, bStop, fast_line, slow_line = hesapla_yon_ve_stop(df)

    df["sigType"] = bDir
    df["pStop"] = bStop

    # ==============================================================================
    # GERÇEK ATR NORMALİZE MAKAS
    # ==============================================================================

    makas_oran = (

        (fast_line - slow_line).abs()
        / df["atr"].replace(0, np.nan)

    )

    makas_oran = makas_oran.replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(0)

    df["makasATR"] = makas_oran

    # ==============================================================================
    # GERÇEK BAR YAŞI
    #
    # ÖNEMLİ:
    #
    # TradingView Screener'ın mevcut alanları üzerinden geçmişteki bütün barları
    # güvenilir biçimde okuyamadığımız için burada artık EMA/ATR'den sahte bAgo
    # ÜRETİLMİYOR.
    #
    # Aşağıdaki alan:
    #
    # signal_age
    #
    # tarihsel OHLC veri sağlayıcısı bağlandığında gerçek olarak doldurulacaktır.
    # ==============================================================================
    
    df["signal_age"] = np.nan

    # Mevcut barın yönü için geçici olarak "0"
    # Bu değer gerçek tarihsel veri motoru ile doldurulmalıdır.
    #
    # Böylece eski koddaki:
    # makas -> bAgo
    # sahte dönüşümü tamamen kaldırılmış olur.

    # ==============================================================================
    # GİRİŞ FİYATI
    # ==============================================================================

    # Artık bAgo tahmini olmadığı için giriş:
    #
    # AL → mevcut kapanış
    # SAT → mevcut kapanış
    #
    # şeklinde gerçek piyasa fiyatına bağlanır.

    df["entryP"] = c.round(2)

    # ==============================================================================
    # STOP
    # ==============================================================================

    df["pStop"] = pd.to_numeric(
        df["pStop"],
        errors="coerce"
    )

    # ==============================================================================
    # ATR HEDEFLERİ
    # ==============================================================================

    df["tp1"] = np.where(
        df["sigType"] == 1,
        df["entryP"] + (
            atrMult1 * df["atr"]
        ),
        np.nan
    )

    df["tp2"] = np.where(
        df["sigType"] == 1,
        df["entryP"] + (
            atrMult2 * df["atr"]
        ),
        np.nan
    )

    df["tp3"] = np.where(
        df["sigType"] == 1,
        df["entryP"] + (
            atrMult3 * df["atr"]
        ),
        np.nan
    )

    # ==============================================================================
    # HIGH
    # ==============================================================================

    high_col = f"high{sfx_b}"

    if high_col in df.columns:

        high_ref = pd.to_numeric(
            df[high_col],
            errors="coerce"
        )

    else:

        high_ref = c

    # ==============================================================================
    # HEDEF KONTROLLERİ
    # ==============================================================================

    df["hit1"] = (
        (df["sigType"] == 1) &
        (high_ref >= df["tp1"])
    )

    df["hit2"] = (
        (df["sigType"] == 1) &
        (high_ref >= df["tp2"])
    )

    df["hit3"] = (
        (df["sigType"] == 1) &
        (high_ref >= df["tp3"])
    )

    # ==============================================================================
    # SİNYAL
    # ==============================================================================

    def sinyal_belirle(r):

        sig = r["sigType"]

        daily_strong = bool(
            r["daily_strong_bull"]
        )

        if sig == 1:

            if taramaPeriyot == "D":

                if daily_strong:

                    return (
                        "GÜÇLÜ AL 🔥",
                        "GÜÇLÜ AL"
                    )

                return (
                    "AL",
                    "AL"
                )

            return (
                "AL",
                "AL"
            )

        elif sig == -1:

            return (
                "SAT",
                "SAT"
            )

        else:

            return (
                "NÖTR",
                "NÖTR"
            )

    res_tuples = df.apply(
        sinyal_belirle,
        axis=1
    )

    df["sig_txt"] = [
        t[0] for t in res_tuples
    ]

    df["sig_code"] = [
        t[1] for t in res_tuples
    ]

    # ==============================================================================
    # GÜNLÜK EMA SAYACI
    # ==============================================================================

    df["daily_ema_above_count"] = (

        (c > e5_d).astype(int) +
        (c > e21_d).astype(int) +
        (c > e34_d).astype(int) +
        (c > e55_d).astype(int) +
        (c > e144_d).astype(int) +
        (c > e233_d).astype(int) +
        (c > e377_d).astype(int) +
        (c > e610_d).astype(int)

    )

    # ==============================================================================
    # ÜST SAYAÇLAR
    # ==============================================================================

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "📊 Taranan Hisse",
        f"{len(df)}"
    )

    k2.metric(
        "🟢 AL",
        f"{(df['sig_code'] == 'AL').sum()}"
    )

    k3.metric(
        "🔥 GÜÇLÜ AL",
        f"{(df['sig_code'] == 'GÜÇLÜ AL').sum()}"
    )

    k4.metric(
        "🔴 SAT",
        f"{(df['sig_code'] == 'SAT').sum()}"
    )

    st.write("")

    # ==============================================================================
    # FİLTRELEME
    # ==============================================================================

    gorunen_df = df.copy()

    if sadeceGucluAl:

        gorunen_df = gorunen_df[
            gorunen_df["sig_code"] == "GÜÇLÜ AL"
        ].copy()

    elif sadeceSinyaller:

        gorunen_df = gorunen_df[
            gorunen_df["sig_code"] != "NÖTR"
        ].copy()

    # ==============================================================================
    # ANA TABLO
    # ==============================================================================

    if gorunen_df.empty:

        st.info(
            "💡 Seçili kriterlere uyan hisse bulunamadı."
        )

    else:

        tf_label = f_get_tf_label(
            taramaPeriyot
        )

        t_rows = []

        for _, row in gorunen_df.iterrows():

            p_close = row[c_close_name]
            p_chg = row["pChg"]

            sig_txt = row["sig_txt"]
            sig_code = row["sig_code"]

            e_p = row["entryP"]
            p_stop = row["pStop"]

            tp1_v = row["tp1"]
            tp2_v = row["tp2"]
            tp3_v = row["tp3"]

            h1 = row["hit1"]
            h2 = row["hit2"]
            h3 = row["hit3"]

            daily_count = int(
                row["daily_ema_above_count"]
            )

            # ------------------------------------------------------------------
            # FİYAT
            # ------------------------------------------------------------------

            chg_sign = (
                "+"
                if p_chg >= 0
                else ""
            )

            price_str = (
                f"{p_close:,.2f} "
                f"({chg_sign}{p_chg:.2f}%)"
            )

            # ------------------------------------------------------------------
            # GİRİŞ
            # ------------------------------------------------------------------

            entry_str = (
                f"{e_p:,.2f}"
            )

            # ------------------------------------------------------------------
            # STOP
            # ------------------------------------------------------------------

            if (
                pd.notnull(p_stop)
                and p_stop > 0
            ):

                stop_pct = (
                    (p_stop - e_p)
                    / e_p
                ) * 100.0

                stop_sign = (
                    "+"
                    if stop_pct >= 0
                    else ""
                )

                stop_str = (
                    f"{p_stop:,.2f} "
                    f"({stop_sign}{stop_pct:.2f}%)"
                )

            else:

                stop_str = "-"

            # ------------------------------------------------------------------
            # HEDEF FORMAT
            # ------------------------------------------------------------------

            def format_tp(
                tp_val,
                hit
            ):

                if (
                    pd.isna(tp_val)
                    or sig_code not in [
                        "AL",
                        "GÜÇLÜ AL"
                    ]
                ):

                    return "-"

                pct = (
                    (tp_val - e_p)
                    / e_p
                ) * 100.0

                check = (
                    " ✓"
                    if hit
                    else ""
                )

                return (
                    f"{tp_val:,.2f} "
                    f"(+{pct:.2f}%){check}"
                )

            # ------------------------------------------------------------------
            # GÜNLÜK EMA DURUMU
            # ------------------------------------------------------------------

            if daily_count == 8:

                daily_ema_text = (
                    "8/8 🔥"
                )

            elif daily_count >= 6:

                daily_ema_text = (
                    f"{daily_count}/8 🟢"
                )

            elif daily_count >= 4:

                daily_ema_text = (
                    f"{daily_count}/8 🟡"
                )

            else:

                daily_ema_text = (
                    f"{daily_count}/8 🔴"
                )

            # ------------------------------------------------------------------
            # SATIR
            # ------------------------------------------------------------------

            t_rows.append({

                "Sembol":
                    row["name"],

                "Sinyal":
                    sig_txt,

                "Periyot":
                    tf_label,

                "Fiyat (%)":
                    price_str,

                "Giriş":
                    entry_str,

                "Stop":
                    stop_str,

                "Hedef 1":
                    format_tp(
                        tp1_v,
                        h1
                    ),

                "Hedef 2":
                    format_tp(
                        tp2_v,
                        h2
                    ),

                "Hedef 3":
                    format_tp(
                        tp3_v,
                        h3
                    ),

                "Günlük EMA":
                    daily_ema_text,

                "_sigCode":
                    sig_code,

                "_pChg":
                    p_chg,

                "_h1":
                    h1,

                "_h2":
                    h2,

                "_h3":
                    h3

            })

        t_df = pd.DataFrame(
            t_rows
        )

        # ==============================================================================
        # TABLO RENK MOTORU
        # ==============================================================================

        def style_cc(row):

            styles = [
                ""
            ] * len(row)

            idx_sym = t_df.columns.get_loc(
                "Sembol"
            )

            idx_sig = t_df.columns.get_loc(
                "Sinyal"
            )

            idx_pr = t_df.columns.get_loc(
                "Fiyat (%)"
            )

            idx_t1 = t_df.columns.get_loc(
                "Hedef 1"
            )

            idx_t2 = t_df.columns.get_loc(
                "Hedef 2"
            )

            idx_t3 = t_df.columns.get_loc(
                "Hedef 3"
            )

            styles[idx_sym] = (
                "background-color: #090d16;"
                "color: #38bdf8;"
                "font-weight: bold;"
            )

            if row["_sigCode"] == "GÜÇLÜ AL":

                styles[idx_sig] = (
                    "background-color: #059669;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            elif row["_sigCode"] == "AL":

                styles[idx_sig] = (
                    "background-color: #0284c7;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            elif row["_sigCode"] == "SAT":

                styles[idx_sig] = (
                    "background-color: #dc2626;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            else:

                styles[idx_sig] = (
                    "background-color: #334155;"
                    "color: #cbd5e1;"
                )

            p_clr = (
                "#22c55e"
                if row["_pChg"] >= 0
                else "#ef4444"
            )

            styles[idx_pr] = (
                f"color: {p_clr};"
                "font-weight: bold;"
            )

            if row["_h1"]:

                styles[idx_t1] = (
                    "background-color: #059669;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            if row["_h2"]:

                styles[idx_t2] = (
                    "background-color: #059669;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            if row["_h3"]:

                styles[idx_t3] = (
                    "background-color: #059669;"
                    "color: #ffffff;"
                    "font-weight: bold;"
                )

            return styles

        st.subheader(
            f"📋 CC Scanner Tablosu ({seciliGrup})"
        )

        st.dataframe(

            t_df.style.apply(
                style_cc,
                axis=1
            ),

            column_order=[
                "Sembol",
                "Sinyal",
                "Periyot",
                "Fiyat (%)",
                "Giriş",
                "Stop",
                "Hedef 1",
                "Hedef 2",
                "Hedef 3",
                "Günlük EMA"
            ],

            use_container_width=True,

            hide_index=True

        )

    # ==============================================================================
    # GÜNLÜK EMA DETAY PANELİ
    # ==============================================================================

    st.divider()

    st.subheader(
        "📈 Günlük Çoklu EMA Trend Paneli"
    )

    st.caption(
        "Günlük güçlü AL için fiyatın EMA5, EMA21, EMA34, EMA55, "
        "EMA144, EMA233, EMA377 ve EMA610'un üzerinde olması "
        "ve EMA'ların aynı sırada dizilmesi gerekir."
    )

    hisse_listesi = (
        gorunen_df["name"].tolist()
        if not gorunen_df.empty
        else df["name"].tolist()
    )

    if hisse_listesi:

        secili_detay_hisse = st.selectbox(
            "Analiz Edilecek Hisse:",
            hisse_listesi
        )

        detay_row = df[
            df["name"] == secili_detay_hisse
        ].iloc[0]

        dcols = st.columns(8)

        ema_map = {

            5: e5_d,
            21: e21_d,
            34: e34_d,
            55: e55_d,
            144: e144_d,
            233: e233_d,
            377: e377_d,
            610: e610_d

        }

        for i, period in enumerate(
            DAILY_EMAS
        ):

            value = ema_map[period].loc[
                detay_row.name
            ]

            with dcols[i]:

                if pd.notnull(value):

                    st.metric(
                        f"EMA {period}",
                        f"{value:,.2f}"
                    )

                else:

                    st.metric(
                        f"EMA {period}",
                        "-"
                    )

        # ----------------------------------------------------------------------
        # EMA KONTROL
        # ----------------------------------------------------------------------

        fiyat_detay = detay_row[
            c_close_name
        ]

        checks = {

            "EMA5":
                fiyat_detay > detay_row["EMA5"],

            "EMA21":
                fiyat_detay > detay_row["EMA21"],

            "EMA34":
                fiyat_detay > detay_row["EMA34"],

            "EMA55":
                fiyat_detay > detay_row["EMA55"],

            "EMA144":
                fiyat_detay > detay_row["EMA144"],

            "EMA233":
                fiyat_detay > detay_row["EMA233"],

            "EMA377":
                fiyat_detay > detay_row["EMA377"],

            "EMA610":
                fiyat_detay > detay_row["EMA610"]

        }

        st.write("")

        if all(checks.values()):

            st.markdown(
                '<span class="badge-green">'
                '🔥 FİYAT TÜM GÜNLÜK EMA\'LARIN ÜZERİNDE'
                '</span>',
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                '<span class="badge-yellow">'
                '⚠️ FİYAT TÜM GÜNLÜK EMA\'LARIN ÜZERİNDE DEĞİL'
                '</span>',
                unsafe_allow_html=True
            )

        # ----------------------------------------------------------------------
        # EMA STACK
        # ----------------------------------------------------------------------

        stack_ok = (

            detay_row["EMA5"] >
            detay_row["EMA21"] >

            detay_row["EMA34"] >
            detay_row["EMA55"] >

            detay_row["EMA144"] >
            detay_row["EMA233"] >

            detay_row["EMA377"] >
            detay_row["EMA610"]

        )

        if stack_ok:

            st.markdown(
                '<span class="badge-green">'
                '🔥 EMA5 > EMA21 > EMA34 > EMA55 > '
                'EMA144 > EMA233 > EMA377 > EMA610'
                '</span>',
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                '<span class="badge-red">'
                '⚠️ Günlük EMA hiyerarşisi tam olarak oluşmamış'
                '</span>',
                unsafe_allow_html=True
            )

    # ==============================================================================
    # DETAY PANELİ
    # ==============================================================================

    st.divider()

    st.subheader(
        "📊 Takas / TEFAS / Temel Analiz"
    )

    st.warning(
        "⚠️ Bu bölümde gerçek Takas ve TEFAS verisi kullanılmadan "
        "fiyat değişiminden sentetik puan üretmek kaldırılmıştır. "
        "Gerçek Takas ve TEFAS veri kaynağı bağlandığında bu panel "
        "gerçek kurum/fon hareketleriyle hesaplanmalıdır."
    )

    if hisse_listesi:

        secili_detay_hisse_2 = st.selectbox(
            "Detay Analizi:",
            hisse_listesi,
            key="detail_stock_2"
        )

        detay_row = df[
            df["name"] ==
            secili_detay_hisse_2
        ].iloc[0]

        p_chg_val = detay_row["pChg"]
        sig_type = detay_row["sigType"]

        genel_ema_skor = int(
            detay_row["daily_ema_above_count"]
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Periyot Değişimi",
                f"%{p_chg_val:+.2f}"
            )

        with c2:

            st.metric(
                "Günlük EMA Üstü",
                f"{genel_ema_skor}/8"
            )

        with c3:

            st.metric(
                "ATR(14)",
                f"{detay_row['atr']:,.2f}"
            )

        with c4:

            if detay_row["daily_strong_bull"]:

                st.metric(
                    "Günlük Trend",
                    "🔥 GÜÇLÜ AL"
                )

            elif detay_row["daily_all_ema_bull"]:

                st.metric(
                    "Günlük Trend",
                    "🟢 EMA ÜSTÜ"
                )

            else:

                st.metric(
                    "Günlük Trend",
                    "⚪ NÖTR"
                )

        st.markdown("### 🎯 Gerçek Fiyat / ATR Seviyeleri")

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Anlık / Son Fiyat",
                f"{detay_row[c_close_name]:,.2f}"
            )

        with c2:

            st.metric(
                "ATR(14)",
                f"{detay_row['atr']:,.2f}"
            )

        with c3:

            if pd.notnull(detay_row["pStop"]):

                st.metric(
                    "Stop",
                    f"{detay_row['pStop']:,.2f}"
                )

        with c4:

            if detay_row["sigType"] == 1:

                st.metric(
                    "TP1",
                    f"{detay_row['tp1']:,.2f}"
                )

        # ----------------------------------------------------------------------
        # KARAR ÖZETİ
        # ----------------------------------------------------------------------

        st.markdown(
            "### 📌 Stratejik Karar Özeti"
        )

        if detay_row["daily_strong_bull"]:

            st.success(
                f"""
🔥 **GÜNLÜK GÜÇLÜ AL KOŞULU**

{secili_detay_hisse_2} için mevcut fiyat:

**Fiyat > EMA5 > EMA21 > EMA34 > EMA55 > EMA144 > EMA233 > EMA377 > EMA610**

şeklinde tam günlük EMA hiyerarşisi içerisindedir.

**EMA5 günlük stop seviyesi olarak kullanılmaktadır.**
"""
            )

        elif detay_row["daily_all_ema_bull"]:

            st.info(
                f"""
🟢 **Fiyat 8 günlük EMA'nın tamamının üzerinde.**

Ancak EMA'ların kendi aralarındaki sıralaması
tam olarak güçlü AL hiyerarşisinde olmayabilir.

EMA5 stop seviyesi olarak takip edilmelidir.
"""
            )

        else:

            st.warning(
                f"""
⚠️ {secili_detay_hisse_2} için günlük güçlü AL
EMA koşulu şu anda tam olarak oluşmamıştır.
"""
            )

else:

    st.error(
        "Piyasa verileri alınamadı. "
        "Lütfen sol panelden Terminali Güncelle butonuna basınız."
    )

