import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

# --- Sayfa Genel Ayarları ---
st.set_page_config(
    page_title="BİST Terminal | EMA Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Finans Terminali Koyu Tema Tasarımı (CSS) ---
st.markdown("""
<style>
    .metric-container {
        background: linear-gradient(135deg, #1e222d 0%, #131722 100%);
        border: 1px solid #2a2e39;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .stMetric {
        background-color: #1e222d;
        border: 1px solid #2a2e39;
        padding: 10px;
        border-radius: 8px;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #2a2e39;
        border-radius: 8px;
        background-color: #131722;
    }
</style>
""", unsafe_allow_html=True)

# --- Başlık Alanı ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("⚡ BİST Algoritmik EMA 15 / 63 Terminali")
    st.caption("Borsa İstanbul anlık piyasa taraması, taze trend kesişimleri ve yaklaşan sinyaller.")
with header_col2:
    st.write("")
    st.write(f"🕒 **Son Güncelleme:** `{datetime.now().strftime('%H:%M:%S')}`")

# --- Yan Panel (Filtreler & Ayarlar) ---
with st.sidebar:
    st.markdown("### 🎛️ Terminal Ayarları")
    
    timeframe = st.selectbox(
        "Grafik Periyodu:",
        options=["1D", "240", "60", "15", "5"],
        format_func=lambda x: {
            "1D": "📅 Günlük (1G)",
            "240": "⏰ 4 Saatlik",
            "60": "⏱️ 1 Saatlik",
            "15": "⚡ 15 Dakikalık",
            "5": "🔥 5 Dakikalık"
        }[x],
        index=0
    )
    
    min_volume = st.number_input(
        "Min. Hacim (Milyon ₺):",
        value=5,
        min_value=0,
        step=5
    ) * 1_000_000

    yaklasma_esigi = st.slider(
        "Kesişime Yaklaşma Eşiği (%):",
        min_value=0.1,
        max_value=3.0,
        value=1.0,
        step=0.1,
        help="EMA 15 ile EMA 63 arasındaki makas bu orandan daha darsa 'Yaklaşan Sinyal' olarak listelenir."
    )

    tara_butonu = st.button("🔄 Terminali Güncelle", type="primary", use_container_width=True)

# --- Veri Çekme Motoru ---
@st.cache_data(ttl=25)
def veri_getir(tf, min_vol):
    tf_suffix = "" if tf == "1D" else f"|{tf}"
    
    col_close = f"close{tf_suffix}"
    col_ema15 = f"EMA15{tf_suffix}"
    col_ema63 = f"EMA63{tf_suffix}"
    col_ema15_prev = f"EMA15{tf_suffix}[1]"
    col_ema63_prev = f"EMA63{tf_suffix}[1]"
    col_change = f"change{tf_suffix}"
    col_vol = "volume"

    query = (
        Query()
        .set_markets('turkey')
        .select('name', 'description', col_close, col_change, col_ema15, col_ema63, col_ema15_prev, col_ema63_prev, col_vol)
        .where(
            Column(col_vol) >= min_vol
        )
        .order_by(col_vol, ascending=False)
        .limit(300)
    )
    
    _, df = query.get_scanner_data()
    return df, col_close, col_change, col_ema15, col_ema63, col_ema15_prev, col_ema63_prev, col_vol

# --- Tarama ve Analiz ---
with st.spinner("Piyasa verileri çekiliyor ve göstergeler hesaplanıyor..."):
    raw_df, col_c, col_ch, col_e15, col_e63, col_e15_p, col_e63_p, col_v = veri_getir(timeframe, min_volume)

if not raw_df.empty:
    # Sayısal değerleri garantiye al ve eksik (NaN) verileri temizle
    numeric_cols = [col_c, col_ch, col_e15, col_e63, col_e15_p, col_e63_p, col_v]
    for col in numeric_cols:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce')

    # Yeterli mum verisi olmayan hisseleri filtre dışı bırak
    raw_df = raw_df.dropna(subset=[col_e15, col_e63, col_e15_p, col_e63_p, col_c]).copy()

    # 1. Kesişim Sinyalleri (Tip güvenli mantıksal hesaplama)
    raw_df['AL_Kesisim'] = (raw_df[col_e15] > raw_df[col_e63]) & (raw_df[col_e15_p] <= raw_df[col_e63_p])
    raw_df['SAT_Kesisim'] = (raw_df[col_e15] < raw_df[col_e63]) & (raw_df[col_e15_p] >= raw_df[col_e63_p])
    
    # 2. Makas Oranı: |EMA15 - EMA63| / EMA63 * 100
    raw_df['Makas_%'] = ((raw_df[col_e15] - raw_df[col_e63]).abs() / raw_df[col_e63]) * 100
    raw_df['Boga_Trendi'] = raw_df[col_e15] > raw_df[col_e63]

    # --- ÜST DASHBOARD KPI KARTLARI ---
    toplam_hisse = len(raw_df)
    al_sayisi = int(raw_df['AL_Kesisim'].sum())
    sat_sayisi = int(raw_df['SAT_Kesisim'].sum())
    boga_yuzdesi = (raw_df['Boga_Trendi'].sum() / toplam_hisse * 100) if toplam_hisse > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📊 Taranan Hisse", f"{toplam_hisse}")
    kpi2.metric("🟢 Yeni AL Kesişimi", f"{al_sayisi}", delta="Alış Sinyali" if al_sayisi > 0 else None)
    kpi3.metric("🔴 Yeni SAT Kesişimi", f"{sat_sayisi}", delta="-Satış Sinyali" if sat_sayisi > 0 else None, delta_color="inverse")
    kpi4.metric("⚖️ Piyasa Boğa Oranı", f"%{boga_yuzdesi:.1f}", delta=f"{'Pozitif' if boga_yuzdesi >= 50 else 'Negatif'}")

    st.divider()

    # --- ANA PANELLER (SEKMELER) ---
    tab1, tab2, tab3 = st.tabs(["🔥 Canlı Kesişim Tablosu", "🎯 Kesişime Yaklaşanlar (Radar)", "📊 Hacim & Trend Analizi"])

    with tab1:
        kesisimler = raw_df[raw_df['AL_Kesisim'] | raw_df['SAT_Kesisim']].copy()
        
        if not kesisimler.empty:
            kesisimler['Sinyal'] = kesisimler['AL_Kesisim'].apply(lambda x: "🟢 AL (Yukarı Kesti)" if x else "🔴 SAT (Aşağı Kesti)")
            
            tablo_df = kesisimler[['name', 'description', 'Sinyal', col_c, col_ch, col_e15, col_e63, col_v]].copy()
            tablo_df.columns = ["Sembol", "Şirket Adı", "Sinyal Türü", "Son Fiyat", "Değişim %", "EMA 15", "EMA 63", "Hacim (₺)"]
            
            st.dataframe(
                tablo_df.style.format({
                    "Son Fiyat": "{:,.2f} ₺",
                    "Değişim %": "%{:+.2f}",
                    "EMA 15": "{:,.2f}",
                    "EMA 63": "{:,.2f}",
                    "Hacim (₺)": "{:,.0f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("💡 Şu anda seçilen periyotta yeni kesişim yapmış hisse bulunmuyor. Kesişime yaklaşan hisseler için yandaki **🎯 Radar** sekmesini kontrol edebilirsiniz.")

    with tab2:
        st.markdown(f"**EMA 15 ile EMA 63 arasındaki makasın %{yaklasma_esigi} altına indiği, kesişmek üzere olan hisseler:**")
        yaklasanlar = raw_df[(raw_df['Makas_%'] <= yaklasma_esigi) & (~raw_df['AL_Kesisim']) & (~raw_df['SAT_Kesisim'])].sort_values('Makas_%').copy()
        
        if not yaklasanlar.empty:
            yaklasanlar['Potansiyel'] = yaklasanlar['Boga_Trendi'].apply(lambda x: "🟡 SAT yönünde daralma" if x else "🟢 AL yönünde daralma")
            
            radar_df = yaklasanlar[['name', 'description', 'Potansiyel', 'Makas_%', col_c, col_e15, col_e63, col_v]].head(15)
            radar_df.columns = ["Sembol", "Şirket", "Potansiyel Yön", "Makas Daralması %", "Son Fiyat", "EMA 15", "EMA 63", "Hacim (₺)"]
            
            st.dataframe(
                radar_df.style.format({
                    "Makas Daralması %": "%{:.2f}",
                    "Son Fiyat": "{:,.2f} ₺",
                    "EMA 15": "{:,.2f}",
                    "EMA 63": "{:,.2f}",
                    "Hacim (₺)": "{:,.0f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("Eşik dahilinde daralan hisse bulunamadı. Sol panelden 'Kesişime Yaklaşma Eşiği' değerini artırabilirsiniz.")

    with tab3:
        st.subheader("İşlem Hacmi Dağılımı (İlk 10)")
        top_hacim = raw_df.nlargest(10, col_v)[['name', col_v, 'Boga_Trendi']].copy()
        top_hacim['Trend'] = top_hacim['Boga_Trendi'].apply(lambda x: "Boğa (EMA15>63)" if x else "Ayı (EMA15<63)")
        
        fig = px.bar(
            top_hacim, 
            x='name', 
            y=col_v, 
            color='Trend',
            color_discrete_map={"Boğa (EMA15>63)": "#26a69a", "Ayı (EMA15<63)": "#ef5350"},
            labels={'name': 'Hisse', col_v: 'İşlem Hacmi (₺)'},
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- ALT BÖLÜM: ETKİLEŞİMLİ TRADINGVIEW GRAFİĞİ ---
    st.divider()
    st.subheader("🔍 Hızlı Grafik İnceleme")
    
    secilen_hisse = st.selectbox(
        "Grafiğini incelemek istediğiniz hisseyi seçin:",
        options=raw_df['name'].tolist(),
        index=0
    )
    
    tv_widget_html = f"""
    <div class="tradingview-widget-container" style="height:500px;width:100%">
      <div id="tradingview_embed" style="height:500px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "BIST:{secilen_hisse}",
        "interval": "{'D' if timeframe == '1D' else timeframe}",
        "timezone": "Europe/Istanbul",
        "theme": "dark",
        "style": "1",
        "locale": "tr",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_embed"
      }}
      );
      </script>
    </div>
    """
    components.html(tv_widget_html, height=520)

else:
    st.error("Veriler alınırken bir hata oluştu veya borsa kapalı. Lütfen tekrar deneyin.")
