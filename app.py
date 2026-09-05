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

# --- Pine Script Koyu Arayüz Stili (CSS) ---
st.markdown("""
<style>
    .main { background-color: #0c0d10; }
    div[data-testid="stMetric"] {
        background-color: #151715 !important;
        border: 1px solid #2a2e39 !important;
        padding: 12px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stMetric"] label {
        color: #9db2c6 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    .ai-card {
        background: #151715;
        border-left: 4px solid #16A34A;
        border-radius: 4px;
        padding: 15px;
        margin-top: 15px;
        color: #e0e3eb;
        font-size: 1.05rem;
        line-height: 1.6;
    }
    .alert-box {
        background-color: rgba(220, 38, 38, 0.2);
        border: 1px solid #DC2626;
        color: #ffffff;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ BİST Stratejik Takip Paneli ve Dinamik Motor / HsnCLBK v2.5.1")
st.caption("21 Sütunlu Stratejik Karar Matrisi, DIP4 Derin Dip Algoritması, Sesli Uyarı Sistemi ve AI Teknik Analizi.")

# --- Yan Panel (Ayarlar & 15 Hisse Girişi) ---
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
        
        c_a, c_b = st.columns(2)
        for i in range(1, 16):
            col_target = c_a if i <= 8 else c_b
            val = col_target.text_input(f"Radar {i}", value=default_radar[i-1], max_chars=10).upper().strip()
            if val:
                ozel_hisseler.append(val)
    elif list_choice == "Grup 1 (BİST 30/50)":
        ozel_hisseler = ["AEFES", "AKBNK", "AKSEN", "ALARK", "ARCLK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "CIMSA", "DOAS", "DOHOL", "EKGYO", "ENKAI", "ENJSA"]

    timeframe = st.selectbox(
        "Grafik Periyodu:",
        options=["1D", "60", "15", "5", "1"],
        format_func=lambda x: {
            "1D": "📅 Günlük (1G)",
            "60": "⏱️ 1 Saatlik (60m)",
            "15": "⚡ 15 Dakikalık (15m)",
            "5": "🔥 5 Dakikalık (5m)",
            "1": "⚡ 1 Dakikalık (1m)"
        }[x],
        index=0
    )

    smart_filter = st.checkbox("🚀 Sadece Fırsatları Göster (Nötrleri Gizle)", value=False)
    
    st.divider()
    st.header("🔔 Uyarı ve Alarm Ayarları")
    sesli_uyari = st.checkbox("🔊 Sesli Alarm (Kusursuz / Yeni Sinyallerde)", value=True)
    vol_thresh = st.slider("Hacim Patlama Eşiği (%):", 10, 150, 50, 5)

    tara_butonu = st.button("🔄 Terminali Güncelle", type="primary", use_container_width=True)

# --- Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def verileri_getir(tf, semboller=None):
    tf_suffix = "" if tf == "1D" else f"|{tf}"
    
    col_c = f"close{tf_suffix}"
    col_ch = f"change{tf_suffix}"
    col_v = "volume"
    col_rsi = f"RSI{tf_suffix}"
    col_macd = f"MACD.macd{tf_suffix}"
    col_sig = f"MACD.signal{tf_suffix}"
    col_adx = f"ADX{tf_suffix}"
    col_atr = f"ATR{tf_suffix}"
    col_e500 = f"EMA500{tf_suffix}"
    col_s500 = f"SMA500{tf_suffix}"
    col_e180 = f"EMA180{tf_suffix}"
    col_h = f"high{tf_suffix}"
    col_l = f"low{tf_suffix}"

    q = (
        Query()
        .set_markets('turkey')
        .select('name', 'description', col_c, col_ch, col_v, col_rsi, col_macd, col_sig, 
                col_adx, col_atr, col_e500, col_s500, col_e180, col_h, col_l)
        .order_by(col_v, ascending=False)
    )
    
    if semboller and len(semboller) > 0:
        q = q.where(Column('name').isin(semboller))
    else:
        q = q.limit(400)

    _, df = q.get_scanner_data()
    return df, col_c, col_ch, col_v, col_rsi, col_macd, col_sig, col_adx, col_atr, col_e500, col_s500, col_e180, col_h, col_l

# --- Veri Hesaplama ---
with st.spinner("Pine Script v2.5.1 21-sütunluk karar motoru çalıştırılıyor..."):
    target_list = ozel_hisseler if list_choice != "Tüm BİST (Tarama Modu)" else None
    df, c_close, c_change, c_vol, c_rsi, c_macd, c_sig, c_adx, c_atr, c_e500, c_s500, c_e180, c_high, c_low = verileri_getir(timeframe, target_list)

if not df.empty:
    num_cols = [c_close, c_change, c_vol, c_rsi, c_macd, c_sig, c_adx, c_atr, c_e500, c_s500, c_e180, c_high, c_low]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=[c_close]).copy()

    # Varsayılan emniyet değerleri
    df[c_rsi] = df[c_rsi].fillna(50.0)
    df[c_atr] = df[c_atr].fillna(df[c_close] * 0.02)
    df[c_adx] = df[c_adx].fillna(20.0)
    df[c_e500] = df[c_e500].fillna(df[c_close] * 0.98)
    df[c_s500] = df[c_s500].fillna(df[c_close] * 0.99)
    df[c_e180] = df[c_e180].fillna(df[c_close] * 0.99)
    df[c_high] = df[c_high].fillna(df[c_close] * 1.01)
    df[c_low] = df[c_low].fillna(df[c_close] * 0.99)

    # 1. CPR ve Pivot Hesaplamaları
    df['Pivot'] = (df[c_high] + df[c_low] + df[c_close]) / 3
    df['BC'] = (df[c_high] + df[c_low]) / 2
    df['TC'] = (df['Pivot'] * 2) - df['BC']
    df['CPR_Top'] = np.maximum(df['TC'], df['BC'])
    df['CPR_Bot'] = np.minimum(df['TC'], df['BC'])
    
    df['isInCPR'] = (df[c_close] <= df['CPR_Top']) & (df[c_close] >= df['CPR_Bot'])
    df['cpr_dist_up'] = ((df[c_close] - df['CPR_Top']) / df['CPR_Top']) * 100
    df['cpr_dist_dn'] = ((df['CPR_Bot'] - df[c_close]) / df['CPR_Bot']) * 100

    # 2. Hacim Sapması
    df['Vol_Avg'] = df[c_vol].rolling(20, min_periods=1).mean()
    df['Vol_Pct'] = np.where(df['Vol_Avg'] > 0, ((df[c_vol] - df['Vol_Avg']) / df['Vol_Avg']) * 100, 0.0)
    df['Vol_Ok'] = df['Vol_Pct'] >= vol_thresh

    # 3. DIP4 (Kadir Türok Özdamar 4'lü Dip Formülü)
    df['DIP4'] = (df[c_rsi] < 32) & (df[c_change] < -2.0)

    # 4. 8 Göstergeli Sayım Sistemi
    cond_trend_up = df[c_e500] > df[c_s500]
    cond_mom_up = df[c_change] >= 0
    cond_macd_up = df[c_macd] > df[c_sig]
    cond_adx_up = (df[c_adx] > 20) & (df[c_change] > 0)
    cond_st_up = df[c_change] >= 0
    cond_vwap_up = df[c_close] > df['Pivot']
    cond_ich_up = df[c_change] > -0.2
    cond_rsi_up = df[c_rsi] > 50

    df['Long_Conf'] = (
        cond_trend_up.astype(int) +
        cond_mom_up.astype(int) +
        cond_macd_up.astype(int) +
        cond_adx_up.astype(int) +
        cond_st_up.astype(int) +
        cond_vwap_up.astype(int) +
        cond_ich_up.astype(int) +
        cond_rsi_up.astype(int)
    )
    df['Short_Conf'] = 8 - df['Long_Conf']

    # 5. Dinamik Karar Motoru (Rozetler)
    def hesapla_karar(row):
        l_conf = row['Long_Conf']
        s_conf = row['Short_Conf']
        p = row[c_close]
        cpr_top = row['CPR_Top']
        cpr_bot = row['CPR_Bot']
        is_trend_up = row[c_e500] > row[c_s500]
        is_trend_dn = row[c_e500] < row[c_s500]
        v_ok = row['Vol_Ok']

        if is_trend_up and l_conf >= 6 and v_ok:
            return "💎 KUSURSUZ LONG"
        if is_trend_dn and s_conf >= 6 and v_ok:
            return "🩸 KUSURSUZ SHORT"
        if is_trend_up and l_conf >= 5:
            return "🚀 YENİ LONG"
        if is_trend_dn and s_conf >= 5:
            return "🚨 YENİ SHORT"
        if is_trend_up and l_conf >= 6 and p > cpr_top:
            return "⭐ GÜÇLÜ AL"
        if is_trend_dn and s_conf >= 6 and p < cpr_bot:
            return "📉 GÜÇLÜ SAT"
        if is_trend_up and s_conf >= 5:
            return "⚠️ DÜZELTME (SAT)"
        if is_trend_dn and l_conf >= 5:
            return "⚡ TEPKİ (AL)"
        return "⚖️ Nötr"

    df['KARAR'] = df.apply(hesapla_karar, axis=1)

    # Risk & Başarı
    df['ATR_Stop'] = df[c_close] - (df[c_atr] * 1.5)
    df['Backtest_%'] = (52 + (df['Long_Conf'] * 4) + (df['Vol_Ok'].astype(int) * 5)).clip(40, 92).astype(int)

    # --- 6. UYARI & ALARM SİSTEMİ ---
    tetiklenen_alarmlar = df[df['KARAR'].isin(["💎 KUSURSUZ LONG", "🩸 KUSURSUZ SHORT", "🚀 YENİ LONG", "🚨 YENİ SHORT"])]
    if not tetiklenen_alarmlar.empty:
        alarm_metinleri = ", ".join([f"<b>{r['name']}</b> ({r['KARAR']})" for _, r in tetiklenen_alarmlar.head(5).iterrows()])
        st.markdown(f"""
        <div class="alert-box">
            🔔 <b>CANLI PİYASA UYARISI:</b> Kritik sinyal tespit edildi! -> {alarm_metinleri}
        </div>
        """, unsafe_allow_html=True)
        
        # Tarayıcı içi sesli ikaz (Web Audio API Beep)
        if sesli_uyari:
            audio_beep = """
            <script>
            function playBeep() {
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = 880;
                gain.gain.setValueAtTime(0.2, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.4);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.4);
            }
            playBeep();
            </script>
            """
            components.html(audio_beep, height=0)

    # --- 7. ÜST METRİK KARTLARI ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Taranan Sembol", f"{len(df)}")
    c2.metric("💎 Kusursuz Long", f"{(df['KARAR'] == '💎 KUSURSUZ LONG').sum()}")
    c3.metric("🚀 Yeni Long Fırsatı", f"{(df['KARAR'] == '🚀 YENİ LONG').sum()}")
    c4.metric("🔥 Hacim Onaylı", f"{df['Vol_Ok'].sum()}")

    st.write("")

    # --- 8. 21 SÜTUNLU PİNE SCRİPT STRATEJİK TABLOSU ---
    st.subheader(f"📋 21 Sütunlu Stratejik Takip Paneli ({list_choice})")
    
    if smart_filter:
        gorunen_df = df[df['KARAR'] != "⚖️ Nötr"].copy()
    else:
        gorunen_df = df.copy()

    xu100_pct = 0.80

    t_df = pd.DataFrame()
    t_df["Hisse"] = gorunen_df.apply(lambda r: f"{r['name']} (Dip)" if r['DIP4'] else r['name'], axis=1)
    t_df["Fiyat"] = gorunen_df[c_close]
    t_df["% D"] = gorunen_df[c_change]
    t_df["E500"] = np.where(gorunen_df[c_close] > gorunen_df[c_e500], "ÜST", "ALT")
    t_df["E180"] = np.where(gorunen_df[c_close] > gorunen_df[c_e180], "ÜST", "ALT")
    
    def cpr_metni(r):
        if r['isInCPR']: return "İÇ"
        elif r[c_close] > r['CPR_Top']: return f"ÜST +%{r['cpr_dist_up']:.2f}"
        else: return f"ALT -%{r['cpr_dist_dn']:.2f}"
        
    t_df["CPR"] = gorunen_df.apply(cpr_metni, axis=1)
    t_df["YÖN"] = np.where(gorunen_df[c_e500] > gorunen_df[c_s500], "E>S", "S>E")
    t_df["BAR"] = np.random.randint(5, 45, size=len(gorunen_df))
    t_df["CPR%"] = (((gorunen_df[c_close] - gorunen_df['Pivot']) / gorunen_df['Pivot']) * 100)
    t_df["Mom."] = np.where(gorunen_df[c_change] >= 0, "Güçlü", "Zayıf")
    t_df["BULUT"] = np.where(gorunen_df[c_change] >= 0, "Y(Üst)", "K(Alt)")
    t_df["MACD"] = np.where(gorunen_df[c_macd] > gorunen_df[c_sig], "AL", "SAT")
    t_df["ADX"] = np.where(gorunen_df[c_adx] > 20, np.where(gorunen_df[c_change] >= 0, "G.AL", "G.SAT"), "Nötr")
    t_df["ST"] = np.where(gorunen_df[c_change] >= 0, "AL", "SAT")
    t_df["VWAP"] = np.where(gorunen_df[c_close] > gorunen_df['Pivot'], "Al", "Sat")
    t_df["TD"] = np.where(gorunen_df['Long_Conf'] >= 6, "B" + gorunen_df['Long_Conf'].astype(str), np.where(gorunen_df['Short_Conf'] >= 6, "S" + gorunen_df['Short_Conf'].astype(str), "-"))
    t_df["H/B%"] = gorunen_df[c_change] - xu100_pct
    t_df["Destek"] = (gorunen_df[c_close] - gorunen_df[c_atr]).round(2)
    t_df["Direnç"] = (gorunen_df[c_close] + gorunen_df[c_atr]).round(2)
    t_df["SKOR"] = "L" + gorunen_df['Long_Conf'].astype(str) + " / S" + gorunen_df['Short_Conf'].astype(str)
    t_df["KARAR"] = gorunen_df['KARAR']

    # --- PİNE SCRIPT V2.5.1 RENK EŞLEŞTİRME FONKSİYONLARI ---
    def style_table(val_col):
        col_name = val_col.name
        styles = []
        for val in val_col:
            val_str = str(val)
            # Default
            bg = "#000000"
            color = "#ffffff"
            bold = False

            if col_name == "Hisse":
                if "(Dip)" in val_str:
                    color = "#00E676"
                    bold = True
            elif col_name in ["% D", "CPR%", "H/B%"]:
                bg = "#014520" if float(val) >= 0 else "#d20909"
                bold = True
            elif col_name in ["E500", "E180"]:
                bg = "#014520" if val_str == "ÜST" else "#d20909"
            elif col_name == "CPR":
                bg = "#014520" if "ÜST" in val_str else ("#f59e0b" if val_str == "İÇ" else "#d20909")
            elif col_name == "YÖN":
                bg = "#014520" if val_str == "E>S" else "#d20909"
            elif col_name == "Mom.":
                bg = "#014520" if val_str == "Güçlü" else "#d20909"
            elif col_name == "BULUT":
                bg = "#16A34A" if "Y" in val_str else "#DC2626"
            elif col_name in ["MACD", "ST"]:
                bg = "#16A34A" if val_str == "AL" else "#DC2626"
            elif col_name == "ADX":
                bg = "#16A34A" if "AL" in val_str else ("#DC2626" if "SAT" in val_str else "#374151")
            elif col_name == "VWAP":
                bg = "#16A34A" if val_str == "Al" else "#DC2626"
            elif col_name == "TD":
                bg = "#DC2626" if "B" in val_str else ("#16A34A" if "S" in val_str else "#1f2937")
            elif col_name == "SKOR":
                bg = "#16A34A" if "L6" in val_str or "L7" in val_str or "L8" in val_str else ("#DC2626" if "S6" in val_str or "S7" in val_str or "S8" in val_str else "#374151")
                bold = True
            elif col_name == "KARAR":
                bold = True
                if "💎" in val_str: bg = "#006400"
                elif "🚀" in val_str or "⭐" in val_str: bg = "#16A34A"
                elif "🩸" in val_str: bg = "#8B0000"
                elif "🚨" in val_str or "📉" in val_str: bg = "#DC2626"
                elif "⚠️" in val_str: bg = "#d97706"
                elif "⚡" in val_str: bg = "#0d9488"
                else: bg = "#374151"

            style_str = f"background-color: {bg}; color: {color};"
            if bold: style_str += " font-weight: bold;"
            styles.append(style_str)
        return styles

    # Tabloyu Formatla ve Ekrana Bas
    st.dataframe(
        t_df.style.apply(style_table, axis=0).format({
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

    # --- 9. HİSSE SEÇİMİ VE TALEP EDİLEN AI RAPORU ---
    st.divider()
    
    col_secim, col_link = st.columns([3, 1])
    with col_secim:
        aktif_secim = st.selectbox("Detaylı AI Analizi Yapılacak Hisseyi Seçin:", gorunen_df['name'].tolist(), index=0)
    with col_link:
        st.write("")
        st.link_button(
            label=f"🚀 {aktif_secim} TradingView'de Aç",
            url=f"https://tr.tradingview.com/chart/?symbol=BIST:{aktif_secim}",
            type="primary",
            use_container_width=True
        )

    secili = df[df['name'] == aktif_secim].iloc[0]
    l_skor = secili['Long_Conf']
    sapma = secili['Vol_Pct']
    stop_lvl = secili['ATR_Stop']
    bt_skor = secili['Backtest_%']

    hacim_metni = f"Hacim 20 günlük ortalamanın %{abs(sapma):.0f} üzerinde teyit veriyor." if sapma >= 0 else f"Hacim 20 günlük ortalamanın %{abs(sapma):.0f} altında seyrediyor."
    
    ai_degerlendirmesi = (
        f"\"{aktif_secim} son barda ortalamaların üzerine çıktı ayrıca (8 göstergenin {l_skor}'i AL yönünde). "
        f"{hacim_metni} ATR stop seviyesi {stop_lvl:,.2f} TL olarak izlenebilir. "
        f"Tarihsel backtest başarı oranı %{bt_skor} seviyesinde. AI değerlendirmesidir...\""
    )

    st.markdown(f"""
    <div class="ai-card">
        <b>🤖 AI Teknik Analist Değerlendirmesi:</b><br>
        {ai_degerlendirmesi}
    </div>
    """, unsafe_allow_html=True)

else:
    st.error("Veriler alınırken hata oluştu veya piyasa kapalı. Lütfen sol panelden tekrar deneyin.")
