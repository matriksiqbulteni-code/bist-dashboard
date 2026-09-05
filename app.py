import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from tradingview_screener import Query, Column
import streamlit.components.v1 as components

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="BİST Canlı EMA 15/63 Terminali",
    page_icon="📈",
    layout="wide"
)

# Koyu Tema CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #1e222d;
        border: 1px solid #2a2e39;
        padding: 12px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ BİST Algoritmik EMA 15 / 63 Terminali")
st.caption("Tablodan dilediğiniz hisseye tıklayarak anında alttaki canlı grafikte inceleyebilirsiniz.")

# --- Yan Panel ---
with st.sidebar:
    st.header("🎛️ Terminal Filtreleri")
    
    timeframe = st.selectbox(
        "Grafik Periyodu:",
        options=["1D", "60", "15", "5"],
        format_func=lambda x: {
            "1D": "📅 Günlük (1G)",
            "60": "⏱️ 1 Saatlik",
            "15": "⚡ 15 Dakikalık",
            "5": "🔥 5 Dakikalık"
        }[x],
        index=0
    )
    
    min_volume = st.number_input(
        "Min. İşlem Hacmi (Milyon ₺):",
        value=1.0,
        min_value=0.0,
        step=1.0
    ) * 1_000_000

    yaklasma_esigi = st.slider(
        "Kesişime Yaklaşma Eşiği (%):",
        min_value=0.1,
        max_value=3.0,
        value=1.0,
        step=0.1
    )

    tara_butonu = st.button("🔄 Taramayı Yenile", type="primary", use_container_width=True)

# --- Veri Çekme Motoru ---
@st.cache_data(ttl=30)
def bist_verilerini_cek(tf, min_vol):
    tf_suffix = "" if tf == "1D" else f"|{tf}"
    
    c_close = f"close{tf_suffix}"
    c_change = f"change{tf_suffix}"
    c_vol = "volume"
    
    query = (
        Query()
        .set_markets('turkey')
        .select('name', 'description', c_close, c_change, c_vol)
        .where(
            Column(c_vol) >= min_vol
        )
        .order_by(c_vol, ascending=False)
        .limit(250)
    )
    
    _, df = query.get_scanner_data()
    return df, c_close, c_change, c_vol

# --- Tarama ve Hesaplama ---
with st.spinner("Piyasa verileri alınıyor..."):
    df, col_close, col_change, col_vol = bist_verilerini_cek(timeframe, min_volume)

if not df.empty:
    df[col_close] = pd.to_numeric(df[col_close], errors='coerce')
    df[col_change] = pd.to_numeric(df[col_change], errors='coerce')
    df[col_vol] = pd.to_numeric(df[col_vol], errors='coerce')
    df = df.dropna(subset=[col_close]).copy()

    # EMA 15 ve EMA 63 hesaplama
    df['EMA15'] = df[col_close] * (2 / (15 + 1)) + (df[col_close] * (1 - (2 / (15 + 1))))
    df['EMA63'] = df[col_close] * (2 / (63 + 1)) + (df[col_close] * (1 - (2 / (63 + 1))))
    
    fark_yuzde = ((df[col_close] - df['EMA63']) / df['EMA63']) * 100
    df['Makas_%'] = fark_yuzde.abs()
    
    df['AL_Sinyali'] = (df[col_change] > 0.5) & (df['Makas_%'] < yaklasma_esigi)
    df['SAT_Sinyali'] = (df[col_change] < -0.5) & (df['Makas_%'] < yaklasma_esigi)
    df['Boga_Trendi'] = df[col_close] >= df['EMA63']

    toplam_hisse = len(df)
    al_sayisi = int(df['AL_Sinyali'].sum())
    sat_sayisi = int(df['SAT_Sinyali'].sum())
    boga_orani = (df['Boga_Trendi'].sum() / toplam_hisse * 100) if toplam_hisse > 0 else 0

    # Üst Sayaçlar
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Taranan Hisse", f"{toplam_hisse}")
    c2.metric("🟢 AL Sinyali / Kesişim", f"{al_sayisi}")
    c3.metric("🔴 SAT Sinyali / Kesişim", f"{sat_sayisi}")
    c4.metric("⚖️ Piyasa Pozitif Oranı", f"%{boga_orani:.1f}")

    st.divider()

    # Tablo ve Seçim Alanı
    t1, t2, t3 = st.tabs(["🔥 Kesişim & Sinyal Tablosu", "🎯 Kesişime Yaklaşanlar (Radar)", "📊 Hacim Dağılımı"])

    # Varsayılan seçili hisse oturumu
    if "aktif_hisse" not in st.session_state:
        st.session_state["aktif_hisse"] = df['name'].iloc[0]

    with t1:
        sinyal_verenler = df[df['AL_Sinyali'] | df['SAT_Sinyali']].copy()
        if not sinyal_verenler.empty:
            sinyal_verenler['Sinyal'] = sinyal_verenler['AL_Sinyali'].apply(lambda x: "🟢 GÜÇLÜ AL" if x else "🔴 GÜÇLÜ SAT")
            t1_df = sinyal_verenler[['name', 'description', 'Sinyal', col_close, col_change, col_vol]].copy()
            t1_df.columns = ["Sembol", "Şirket Adı", "Sinyal", "Son Fiyat (₺)", "Değişim %", "Hacim (₺)"]
            
            secim1 = st.dataframe(
                t1_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            if secim1.selection.rows:
                secilen_indeks = secim1.selection.rows[0]
                st.session_state["aktif_hisse"] = t1_df.iloc[secilen_indeks]["Sembol"]
        else:
            st.info("💡 Tam kesişim eşiğinde olan hisse şu an bulunmuyor. Radar sekmesine göz atabilirsiniz.")

    with t2:
        st.markdown(f"**Aşağıdaki tablodan herhangi bir hisseye tıklayarak alttaki grafiği güncelleyebilirsiniz:**")
        radar = df.sort_values('Makas_%').head(25).copy()
        radar['Durum'] = radar['Boga_Trendi'].apply(lambda x: "🟢 Pozitif Trend" if x else "🔴 Negatif Trend")
        
        t2_df = radar[['name', 'description', 'Durum', 'Makas_%', col_close, col_change, col_vol]].copy()
        t2_df.columns = ["Sembol", "Şirket Adı", "Trend Durumu", "Makas %", "Son Fiyat (₺)", "Değişim %", "Hacim (₺)"]
        
        secim2 = st.dataframe(
            t2_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        if secim2.selection.rows:
            secilen_indeks = secim2.selection.rows[0]
            st.session_state["aktif_hisse"] = t2_df.iloc[secilen_indeks]["Sembol"]

    with t3:
        top10 = df.nlargest(10, col_vol).copy()
        top10['Trend'] = top10['Boga_Trendi'].apply(lambda x: "Pozitif" if x else "Negatif")
        fig = px.bar(
            top10, x='name', y=col_vol, color='Trend',
            color_discrete_map={"Pozitif": "#26a69a", "Negatif": "#ef5350"},
            labels={'name': 'Hisse', col_vol: 'İşlem Hacmi (₺)'},
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- ALT BÖLÜM: SEÇİLEN HİSSENİN GRAFİĞİ ---
    st.divider()
    aktif = st.session_state["aktif_hisse"]

    col_grafik_baslik, col_harici_link = st.columns([3, 1])
    with col_grafik_baslik:
        st.subheader(f"🔍 Canlı Grafik: BIST:{aktif}")
    with col_harici_link:
        st.link_button(f"🔗 {aktif} Grafiğini TradingView'de Aç", f"https://tr.tradingview.com/chart/?symbol=BIST:{aktif}")

    # Doğru BİST parametreleriyle TradingView Advanced Widget
    tv_widget = f"""
    <div class="tradingview-widget-container" style="height:550px;width:100%">
      <div id="tv_chart_container" style="height:550px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 550,
        "symbol": "BIST:{aktif}",
        "interval": "{'D' if timeframe == '1D' else timeframe}",
        "timezone": "Europe/Istanbul",
        "theme": "dark",
        "style": "1",
        "locale": "tr",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tv_chart_container"
      }});
      </script>
    </div>
    """
    components.html(tv_widget, height=560)

else:
    st.error("Veri alınamadı. Lütfen sol paneldeki '🔄 Taramayı Yenile' butonuna basınız.")
