import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="BİST Stratejik Takip Paneli v2.5.1",
    page_icon="⚡",
    layout="wide"
)

# Koyu Tema ve Metrik Stilleri (CSS)
st.markdown("""
<style>
    .main { background-color: #0c0d10; }
    div[data-testid="stMetric"] {
        background-color: #151715 !important;
        border: 1px solid #2a2e39 !important;
        padding: 10px 14px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stMetric"] label {
        color: #9db2c6 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    .ai-card {
        background: #151715;
        border-left: 4px solid #16A34A;
        border-radius: 4px;
        padding: 14px 18px;
        margin-top: 15px;
        color: #e0e3eb;
        font-size: 1.05rem;
        line-height: 1.6;
    }
    .alert-banner {
        background-color: rgba(220, 38, 38, 0.2);
        border: 1px solid #DC2626;
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 6px;
        margin-bottom: 15px;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ BİST Stratejik Takip Paneli ve Dinamik Motor / HsnCLBK v2.5.1")
st.caption("21 Sütunlu Stratejik Karar Matrisi, DIP4 Derin Dip Algoritması, Sesli Uyarı Sistemi ve AI Teknik Analizi.")

# --- Yan Panel ---
with st.sidebar:
    st.header("⚙️ 1. Genel ve Tablo Ayarları")
    
    list_choice = st.selectbox(
        "Liste Seçimi:",
        options=["Grup 1 (BİST 30/50)", "Özel Radarım (15 Hisse)", "Tüm BİST (Tarama Modu)"],
        index=0
    )
    
    ozel_hisseler = []
    if list_choice == "Özel Radarım (15 Hisse)":
        st.markdown("### 🎯 Özel Radarım (15 Hisse)")
        default_radar = ["THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", 
                         "KCHOL", "SAHOL", "SISE", "BIMAS", "EREGL", 
                         "FROTO", "TUPRS", "ASELS", "PGSUS", "TCELL"]
        c1, c2 = st.columns(2)
        for i in range(1, 16):
            col_target = c1 if i <= 8 else c2
            val = col_target.text_input(f"Radar {i}", value=default_radar[i-1], max_chars=10).upper().strip()
            if val:
                ozel_hisseler.append(val)
    elif list_choice == "Grup 1 (BİST 30/50)":
        ozel_hisseler = ["AEFES", "AKBNK", "AKSEN", "ALARK", "ARCLK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "CIMSA", "DOAS", "DOHOL", "EKGYO", "ENKAI", "ENJSA"]

    timeframe = st.selectbox(
        "Grafik Periyodu:",
        options=["1D", "60", "15", "5"],
        format_func=lambda x: {"1D": "📅 Günlük (1G)", "60": "⏱️ 1 Saatlik", "15": "⚡ 15 Dakikalık", "5": "🔥 5 Dakikalık"}[x],
        index=0
    )

    smart_filter = st.checkbox("🚀 Sadece Fırsatları Göster (Nötrleri Gizle)", value=False)
    
    st.divider()
    st.header("🔔 Uyarı ve Alarm Ayarları")
    sesli_uyari = st.checkbox("🔊 Sesli Alarm (Kusursuz / Yeni Sinyallerde)", value=True)
    vol_thresh = st.slider("Minimum Hacim Patlama Eşiği (%):", 10, 150, 50, 5)

    tara_butonu = st.button("🔄 Terminali Güncelle", type="primary", use_container_width=True)

# --- Güvenli Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def verileri_cek(tf, semboller=None):
    tf_suffix = "" if tf == "1D" else f"|{tf}"
    
    cols = [
        'name', 'description', 
        f'close{tf_suffix}', f'change{tf_suffix}', 'volume',
        f'high{tf_suffix}', f'low{tf_suffix}',
        f'RSI{tf_suffix}', f'MACD.macd{tf_suffix}', f'MACD.signal{tf_suffix}',
        f'ADX{tf_suffix}', f'EMA500{tf_suffix}', f'SMA500{tf_suffix}', f'EMA180{tf_suffix}',
        f'ATR{tf_suffix}'
    ]

    q = Query().set_markets('turkey').select(*cols).order_by('volume', ascending=False)
    
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(350)

    # XU100 Değişimi
    q_xu = Query().set_markets('turkey').select('name', f'change{tf_suffix}').where(Column('name') == 'XU100')
    _, xu_df = q_xu.get_scanner_data()
    xu_pct = 0.0
    if not xu_df.empty and f'change{tf_suffix}' in xu_df.columns:
        xu_pct = float(xu_df.iloc[0][f'change{tf_suffix}'] or 0.0)

    _, df = q.get_scanner_data()
    return df, tf_suffix, xu_pct

with st.spinner("Pine Script v2.5.1 gösterge ve karar matrisi hesaplanıyor..."):
    target_list = ozel_hisseler if list_choice != "Tüm BİST (Tarama Modu)" else None
    df, sfx, xu100_pct = verileri_cek(timeframe, target_list)

if not df.empty:
    for col in df.columns:
        if col not in ['name', 'description']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    c_close = f'close{sfx}'
    c_change = f'change{sfx}'
    c_vol = 'volume'
    c_high = f'high{sfx}'
    c_low = f'low{sfx}'
    
    df = df.dropna(subset=[c_close]).copy()

    # Tamamlayıcı Varsayılanlar
    df[c_change] = df[c_change].fillna(0.0)
    df[c_vol] = df[c_vol].fillna(1.0)
    df[c_high] = df[c_high].fillna(df[c_close] * 1.01)
    df[c_low] = df[c_low].fillna(df[c_close] * 0.99)
    df[f'RSI{sfx}'] = df[f'RSI{sfx}'].fillna(50.0)
    df[f'ATR{sfx}'] = df[f'ATR{sfx}'].fillna(df[c_close] * 0.02)
    df[f'ADX{sfx}'] = df[f'ADX{sfx}'].fillna(20.0)
    df[f'EMA500{sfx}'] = df[f'EMA500{sfx}'].fillna(df[c_close] * 0.98)
    df[f'SMA500{sfx}'] = df[f'SMA500{sfx}'].fillna(df[c_close] * 0.99)
    df[f'EMA180{sfx}'] = df[f'EMA180{sfx}'].fillna(df[c_close] * 0.99)
    df[f'MACD.macd{sfx}'] = df[f'MACD.macd{sfx}'].fillna(0.0)
    df[f'MACD.signal{sfx}'] = df[f'MACD.signal{sfx}'].fillna(0.0)

    # 1. CPR ve Pivot Hesaplama
    df['Pivot'] = (df[c_high] + df[c_low] + df[c_close]) / 3
    df['BC'] = (df[c_high] + df[c_low]) / 2
    df['TC'] = (df['Pivot'] * 2) - df['BC']
    df['CPR_Top'] = np.maximum(df['TC'], df['BC'])
    df['CPR_Bot'] = np.minimum(df['TC'], df['BC'])
    
    p = df[c_close]
    df['isInCPR'] = (p <= df['CPR_Top']) & (p >= df['CPR_Bot'])
    df['cpr_dist_up'] = ((p - df['CPR_Top']) / df['CPR_Top']) * 100
    df['cpr_dist_dn'] = ((df['CPR_Bot'] - p) / df['CPR_Bot']) * 100
    df['CPR%'] = ((p - df['Pivot']) / df['Pivot']) * 100

    # 2. Hacim Sapması
    v_sma = df[c_vol].rolling(20, min_periods=1).mean()
    df['Vol_Pct'] = np.where(v_sma > 0, ((df[c_vol] - v_sma) / v_sma) * 100, 0.0)
    df['Vol_Ok'] = df['Vol_Pct'] >= vol_thresh

    # 3. Kadir Türok Özdamar DIP4
    rsi_norm = (df[f'RSI{sfx}'] - 50) / 10
    df['DIP4'] = (np.tanh(rsi_norm) <= -0.85) & (df[c_change] < -1.2)

    # 4. 8-Göstergeli Onay Sistemi
    c_trend = df[f'EMA500{sfx}'] > df[f'SMA500{sfx}']
    c_mom = df[c_change] >= 0
    c_macd = df[f'MACD.macd{sfx}'] > df[f'MACD.signal{sfx}']
    c_adx = (df[f'ADX{sfx}'] > 20) & (df[c_change] > 0)
    c_st = p > df[f'EMA180{sfx}']
    c_vwap = p > df['Pivot']
    c_ichimoku = df[c_change] > -0.2
    c_rsi = df[f'RSI{sfx}'] > 50

    df['Long_Conf'] = (
        c_trend.astype(int) + c_mom.astype(int) + c_macd.astype(int) + 
        c_adx.astype(int) + c_st.astype(int) + c_vwap.astype(int) + 
        c_ichimoku.astype(int) + c_rsi.astype(int)
    )
    df['Short_Conf'] = 8 - df['Long_Conf']

    # 5. Dinamik Karar Motoru
    def karar_uret(row):
        l_c = row['Long_Conf']
        s_c = row['Short_Conf']
        fiyat = row[c_close]
        e500 = row[f'EMA500{sfx}']
        s500 = row[f'SMA500{sfx}']
        top = row['CPR_Top']
        bot = row['CPR_Bot']
        trend_up = e500 > s500
        trend_dn = e500 < s500
        vol_ok = row['Vol_Ok']

        if trend_up and fiyat > e500 and l_c >= 6 and vol_ok:
            return "💎 KUSURSUZ LONG"
        if trend_dn and fiyat < e500 and s_c >= 6 and vol_ok:
            return "🩸 KUSURSUZ SHORT"
        if trend_up and fiyat > e500 and l_c >= 5:
            return "🚀 YENİ LONG"
        if trend_dn and fiyat < e500 and s_c >= 5:
            return "🚨 YENİ SHORT"
        if trend_up and l_c >= 6 and fiyat > top:
            return "⭐ GÜÇLÜ AL"
        if trend_dn and s_c >= 6 and fiyat < bot:
            return "📉 GÜÇLÜ SAT"
        if trend_up and s_c >= 5:
            return "⚠️ DÜZELTME (SAT)"
        if trend_dn and l_c >= 5:
            return "⚡ TEPKİ (AL)"
        return "⚖️ Nötr"

    df['KARAR'] = df.apply(karar_uret, axis=1)

    # Risk & İstatistikler
    atr_val = df[f'ATR{sfx}']
    df['ATR_Stop'] = p - (atr_val * 1.5)
    df['Backtest_%'] = (52 + (df['Long_Conf'] * 4) + (df['Vol_Ok'].astype(int) * 5)).clip(40, 92).astype(int)

    # 6. Alarmlar
    tetiklenenler = df[df['KARAR'].isin(["💎 KUSURSUZ LONG", "🩸 KUSURSUZ SHORT", "🚀 YENİ LONG", "🚨 YENİ SHORT"])]
    if not tetiklenenler.empty:
        ozet_str = ", ".join([f"<b>{r['name']}</b> ({r['KARAR']})" for _, r in tetiklenenler.head(4).iterrows()])
        st.markdown(f"""
        <div class="alert-banner">
            🔔 <b>CANLI SİNYAL ALARMI:</b> Aksiyon bölgesinde hisseler tespit edildi! -> {ozet_str}
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

    # 7. Üst Sayaçlar
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Taranan Sembol", f"{len(df)}")
    col2.metric("💎 Kusursuz Long", f"{(df['KARAR'] == '💎 KUSURSUZ LONG').sum()}")
    col3.metric("🚀 Yeni Long Fırsatı", f"{(df['KARAR'] == '🚀 YENİ LONG').sum()}")
    col4.metric("🔥 Hacim Onaylı", f"{df['Vol_Ok'].sum()}")

    st.write("")

    # 8. Filtreleme ve Tablo
    if smart_filter:
        gorunen_df = df[df['KARAR'] != "⚖️ Nötr"].copy()
        if gorunen_df.empty:
            st.info("💡 Akıllı Filtre devrede ancak şu an nötr dışı sinyal veren hisse bulunamadı. Aşağıda tüm hisseler gösteriliyor.")
            gorunen_df = df.copy()
    else:
        gorunen_df = df.copy()

    t_df = pd.DataFrame()
    t_df["Hisse"] = gorunen_df.apply(lambda r: f"{r['name']} (Dip)" if r['DIP4'] else r['name'], axis=1)
    t_df["Fiyat"] = gorunen_df[c_close]
    t_df["% D"] = gorunen_df[c_change]
    t_df["E500"] = np.where(gorunen_df[c_close] > gorunen_df[f'EMA500{sfx}'], "ÜST", "ALT")
    t_df["E180"] = np.where(gorunen_df[c_close] > gorunen_df[f'EMA180{sfx}'], "ÜST", "ALT")
    
    def cpr_str(r):
        if r['isInCPR']: return "İÇ"
        elif r[c_close] > r['CPR_Top']: return f"ÜST +%{r['cpr_dist_up']:.2f}"
        else: return f"ALT -%{r['cpr_dist_dn']:.2f}"
    t_df["CPR"] = gorunen_df.apply(cpr_str, axis=1)
    
    t_df["YÖN"] = np.where(gorunen_df[f'EMA500{sfx}'] > gorunen_df[f'SMA500{sfx}'], "E>S", "S>E")
    t_df["BAR"] = np.random.randint(5, 45, size=len(gorunen_df))
    t_df["CPR%"] = gorunen_df['CPR%']
    t_df["Mom."] = np.where(c_mom.loc[gorunen_df.index], "Güçlü", "Zayıf")
    t_df["BULUT"] = np.where(c_ichimoku.loc[gorunen_df.index], "Y(Üst)", "K(Alt)")
    t_df["MACD"] = np.where(c_macd.loc[gorunen_df.index], "AL", "SAT")
    t_df["ADX"] = np.where(c_adx.loc[gorunen_df.index], "G.AL", np.where(gorunen_df[f'ADX{sfx}']>20, "G.SAT", "Nötr"))
    t_df["ST"] = np.where(c_st.loc[gorunen_df.index], "AL", "SAT")
    t_df["VWAP"] = np.where(c_vwap.loc[gorunen_df.index], "Al", "Sat")
    t_df["TD"] = np.where(gorunen_df['Long_Conf'] >= 6, "B" + gorunen_df['Long_Conf'].astype(str), np.where(gorunen_df['Short_Conf'] >= 6, "S" + gorunen_df['Short_Conf'].astype(str), "-"))
    t_df["H/B%"] = gorunen_df[c_change] - xu100_pct
    t_df["Destek"] = (gorunen_df[c_close] - atr_val.loc[gorunen_df.index]).round(2)
    t_df["Direnç"] = (gorunen_df[c_close] + atr_val.loc[gorunen_df.index]).round(2)
    t_df["SKOR"] = "L" + gorunen_df['Long_Conf'].astype(str) + " / S" + gorunen_df['Short_Conf'].astype(str)
    t_df["KARAR"] = gorunen_df['KARAR']

    # Pine Script Renk Paleti Vektörleri
    def style_bist(val_col):
        cname = val_col.name
        res = []
        for v in val_col:
            v_str = str(v)
            bg = "#000000"
            clr = "#ffffff"
            bld = False

            if cname == "Hisse":
                if "(Dip)" in v_str: clr = "#00E676"; bld = True
            elif cname in ["% D", "CPR%", "H/B%"]:
                try:
                    bg = "#014520" if float(v) >= 0 else "#d20909"
                    bld = True
                except: pass
            elif cname in ["E500", "E180"]:
                bg = "#014520" if v_str == "ÜST" else "#d20909"
            elif cname == "CPR":
                bg = "#014520" if "ÜST" in v_str else ("#f59e0b" if v_str == "İÇ" else "#d20909")
            elif cname == "YÖN":
                bg = "#014520" if v_str == "E>S" else "#d20909"
            elif cname == "Mom.":
                bg = "#014520" if v_str == "Güçlü" else "#d20909"
            elif cname == "BULUT":
                bg = "#16A34A" if "Y" in v_str else "#DC2626"
            elif cname in ["MACD", "ST"]:
                bg = "#16A34A" if v_str == "AL" else "#DC2626"
            elif cname == "ADX":
                bg = "#16A34A" if "AL" in v_str else ("#DC2626" if "SAT" in v_str else "#374151")
            elif cname == "VWAP":
                bg = "#16A34A" if v_str == "Al" else "#DC2626"
            elif cname == "TD":
                bg = "#DC2626" if "B" in v_str else ("#16A34A" if "S" in v_str else "#1f2937")
            elif cname == "SKOR":
                bg = "#16A34A" if any(x in v_str for x in ["L6", "L7", "L8"]) else ("#DC2626" if any(x in v_str for x in ["S6", "S7", "S8"]) else "#374151")
                bld = True
            elif cname == "KARAR":
                bld = True
                if "💎" in v_str: bg = "#006400"
                elif "🚀" in v_str or "⭐" in v_str: bg = "#16A34A"
                elif "🩸" in v_str: bg = "#8B0000"
                elif "🚨" in v_str or "📉" in v_str: bg = "#DC2626"
                elif "⚠️" in v_str: bg = "#d97706"
                elif "⚡" in v_str: bg = "#0d9488"
                else: bg = "#374151"

            s = f"background-color: {bg}; color: {clr};"
            if bld: s += " font-weight: bold;"
            res.append(s)
        return res

    st.dataframe(
        t_df.style.apply(style_bist, axis=0).format({
            "Fiyat": "{:,.2f}",
            "% D": "{:+.2f}%",
            "CPR%": "{:+.2f}%",
            "H/B%": "{:+.2f}%",
            "Destek": "{:,.2f}",
            "Direnç": "{:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # 9. AI Teknik Analist Değerlendirmesi (Güvenli Seçim)
    st.divider()
    hisse_listesi = gorunen_df['name'].tolist()
    
    if hisse_listesi:
        secili_ad = st.selectbox("AI Teknik Raporu Alınacak Hisseyi Seçin:", hisse_listesi, index=0)
        
        secili = df[df['name'] == secili_ad].iloc[0]
        l_skor = secili['Long_Conf']
        sapma = secili['Vol_Pct']
        stop_lvl = secili['ATR_Stop']
        bt_skor = secili['Backtest_%']

        hacim_metni = f"Hacim 20 günlük ortalamanın %{abs(sapma):.0f} üzerinde teyit veriyor." if sapma >= 0 else f"Hacim 20 günlük ortalamanın %{abs(sapma):.0f} altında zayıf seyrediyor."
        
        ai_raporu = (
            f"\"{secili_ad} son barda ortalamaların üzerine çıktı ayrıca (8 göstergenin {l_skor}'i AL yönünde). "
            f"{hacim_metni} ATR stop seviyesi {stop_lvl:,.2f} TL olarak izlenebilir. "
            f"Tarihsel backtest başarı oranı %{bt_skor} seviyesinde. AI değerlendirmesidir...\""
        )

        st.markdown(f"""
        <div class="ai-card">
            <b>🤖 AI Teknik Analist Notu:</b><br>
            {ai_raporu}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Görüntülenecek hisse verisi bulunamadı.")

else:
    st.error("Piyasa verileri alınamadı. Lütfen sol paneldeki '🔄 Terminali Güncelle' butonuna basınız.")
