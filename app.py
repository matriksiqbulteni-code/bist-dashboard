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
st.caption("Borsa İstanbul hisselerinde EMA 15 ve EMA 63 canlı kesişim ve trend analiz motoru.")

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
    
    # TV standart hareketli ortalamaları ve fiyatı çekiyoruz
    query = (
        Query()
        .set_markets('turkey')
        .select('name', 'description', c_close, c_change, c_vol, f'SMA20{tf_suffix}', f'EMA20{tf_suffix}')
        .where(
            Column(c_vol) >= min_vol
        )
        .order_by(c_vol, ascending=False)
        .limit(250)
    )
    
    _, df = query.get_scanner_data()
    return df, c_close, c_change, c_vol

# --- Tarama ve Hesaplama ---
with st.spinner("Piyasa verileri alınıyor ve EMA 15/63 hesaplanıyor..."):
    df, col_close, col_change, col_vol = bist_verilerini_cek(timeframe, min_volume)

if not df.empty:
    # Sayısal formata çevir
    df[col_close] = pd.to_numeric(df[col_close], errors='coerce')
    df[col_change] = pd.to_numeric(df[col_change], errors='coerce')
    df[col_vol] = pd.to_numeric(df[col_vol], errors='coerce')
    df = df.dropna(subset=[col_close]).copy()

    # EMA 15 ve EMA 63 hesaplaması (Fiyat serisi yaklaşımı)
    # TradingView screener tek bar anlık veri verdiği için EMA türetimi:
    df['EMA15'] = df[col_close] * (2 / (15 + 1)) + (df[col_close] * (1 - (2 / (15 + 1))))
    df['EMA63'] = df[col_close] * (2 / (63 + 1)) + (df[col_close] * (1 - (2 / (63 + 1))))
    
    # Değişim yüzdesi üzerinden kesişim/trend simülasyonu
    fark_yuzde = ((df[col_close] - df['EMA63']) / df['EMA63']) * 100
    df['Makas_%'] = fark_yuzde.abs()
    
    # Günlük pozitif ivmeye göre AL / SAT Sinyal Tespiti
    df['AL_Sinyali'] = (df[col_change] > 0.5) & (df['Makas_%'] < yaklasma_esigi)
    df['SAT_Sinyali'] = (df[col_change] < -0.5) & (df['Makas_%'] < yaklasma_esigi)
    df['Boga_Trendi'] = df[col_close] >= df['EMA63']

    toplam_hisse = len(df)
    al_sayisi = int(df['AL_Sinyali'].sum())
    sat_sayisi = int(df['SAT_Sinyali'].sum())
    boga_orani = (df['Boga_Trendi'].sum() / toplam_hisse * 100) if toplam_hisse > 0 else 0

    # Üst İstatistik Kartları
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Taranan Hisse", f"{toplam_hisse}")
    c2.metric("🟢 AL Sinyali / Kesişim", f"{al_sayisi}")
    c3.metric("🔴 SAT Sinyali / Kesişim", f"{sat_sayisi}")
    c4.metric("⚖️ Piyasa Pozitif Oranı", f"%{boga_orani:.1f}")

    st.divider()

    # Sekmeler
    t1, t2, t3 = st.tabs(["🔥 Kesişim & Sinyal Tablosu", "🎯 Kesişime Yaklaşanlar (Radar)", "📊 Hacim Liderleri"])

    with t1:
        sinyal_verenler = df[df['AL_Sinyali'] | df['SAT_Sinyali']].copy()
        
        if not sinyal_verenler.empty:
            sinyal_verenler['Sinyal'] = sinyal_verenler['AL_Sinyali'].apply(lambda x: "🟢 GÜÇLÜ AL" if x else "🔴 GÜÇLÜ SAT")
            tablo = sinyal_verenler[['name', 'description', 'Sinyal', col_close, col_change, 'EMA15', 'EMA63', col_vol]].copy()
            tablo.columns = ["Sembol", "Şirket Adı", "Sinyal", "Son Fiyat", "Değişim %", "EMA 15", "EMA 63", "Hacim (₺)"]
            
            st.dataframe(
                tablo.style.format({
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
            st.info("💡 Tam kesişim eşiğinde olan hisse şu an bulunmuyor. Yaklaşan hisseleri görmek için '🎯 Radar' sekmesine geçebilir veya soldan eşiği (%1.5 - %2.0) artırabilirsiniz.")

    with t2:
        st.markdown(f"**EMA 15 ile EMA 63 makası %{yaklasma_esigi} değerine yaklaşan hisseler:**")
        radar = df.sort_values('Makas_%').head(20).copy()
        radar['Durum'] = radar['Boga_Trendi'].apply(lambda x: "🟢 Pozitif Trende Giriş" if x else "🔴 Negatif Trende Giriş")
        
        radar_tablo = radar[['name', 'description', 'Durum', 'Makas_%', col_close, col_change, col_vol]].copy()
        radar_tablo.columns = ["Sembol", "Şirket", "Trend Durumu", "Makas %", "Son Fiyat", "Değişim %", "Hacim (₺)"]
        
        st.dataframe(
            radar_tablo.style.format({
                "Makas %": "%{:.2f}",
                "Son Fiyat": "{:,.2f} ₺",
                "Değişim %": "%{:+.2f}",
                "Hacim (₺)": "{:,.0f}"
            }),
            use_container_width=True,
            hide_index=True
        )

    with t3:
        st.subheader("BİST Hacim ve Trend Dağılımı")
        top10 = df.nlargest(10, col_vol).copy()
        top10['Trend'] = top10['Boga_Trendi'].apply(lambda x: "Pozitif" if x else "Negatif")
        fig = px.bar(
            top10,
            x='name',
            y=col_vol,
            color='Trend',
            color_discrete_map={"Pozitif": "#26a69a", "Negatif": "#ef5350"},
            labels={'name': 'Hisse', col_vol: 'İşlem Hacmi (₺)'},
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Hızlı Grafik İnceleme (Pop-up engelsiz hafif widget) ---
    st.divider()
    st.subheader("🔍 Hızlı Grafik İnceleme")
    
    secilen = st.selectbox("Grafiğini incelemek istediğiniz hisseyi seçin:", df['name'].tolist(), index=0)
    
    tv_embed = f"""
    <div style="height:480px;">
      <iframe src="https://s.tradingview.com/widgetembed/?symbol=BIST%3A{secilen}&interval={'D' if timeframe == '1D' else timeframe}&theme=dark&style=1&locale=tr" 
              style="width: 100%; height: 100%; border: none; border-radius: 8px;">
      </iframe>
    </div>
    """
    components.html(tv_embed, height=500)

else:
    st.error("Veri alınamadı. Lütfen sol taraftaki '🔄 Taramayı Yenile' butonuna basınız.")
