import streamlit as st
import psycopg2
import pandas as pd
import unicodedata
import re
from datetime import datetime
import os

from pages_detalii import afiseaza_pagina_detalii, afiseaza_pagina_licitant

st.set_page_config(
    page_title="ANAF Deal Flow Dashboard",
    page_icon="🎯",
    layout="wide"
)

# Design curat, modern, cu carduri bine definite și contrast excelent pentru a elimina orice text invizibil sau hașurat
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        .main { background-color: #f8fafc; }
        
        /* Stil personalizat pentru cardurile KPI (evită orice efect de text șters sau confuz) */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .kpi-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease-in-out;
        }
        .kpi-card:hover {
            border-color: #cbd5e1;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
        }
        .kpi-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .kpi-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.2;
        }
        .quick-filter-box { 
            background-color: #ffffff; 
            padding: 20px; 
            border-radius: 12px; 
            border: 1px solid #e2e8f0; 
            margin-bottom: 25px; 
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.02);
        }
        h1, h2, h3, h4, h5, h6 { color: #0f172a !important; }
        div.stButton > button { background-color: #0f172a; color: #ffffff; border-radius: 8px; border: none; font-weight: 600; padding: 0.5rem 1rem; }
        div.stButton > button:hover { background-color: #1e293b; color: #ffffff; }
    </style>
""", unsafe_allow_html=True)

def elimina_diacritice(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    nfkd_form = unicodedata.normalize('NFKD', text_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

def curata_pret(serie_text):
    if serie_text is None:
        return pd.Series(dtype=float)
    s = serie_text.astype(str).str.strip()
    s = s.str.replace(r'(?i)(ron|lei)', '', regex=True)
    s = s.str.replace('.', '', regex=False)
    s = s.str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce')

@st.cache_resource
def ia_conexiunea():
    try:
        db_host = st.secrets.get("NEON_DB_HOST", os.getenv("NEON_DB_HOST", "db"))
        db_name = st.secrets.get("NEON_DB_NAME", os.getenv("NEON_DB_NAME", "anaf_warehouse"))
        db_user = st.secrets.get("NEON_DB_USER", os.getenv("NEON_DB_USER", "postgres"))
        db_password = st.secrets.get("NEON_DB_PASSWORD", os.getenv("NEON_DB_PASSWORD", "parola_ta_secreta"))
        db_port = st.secrets.get("NEON_DB_PORT", os.getenv("NEON_DB_PORT", "5432"))
    except Exception:
        db_host = os.getenv("NEON_DB_HOST", "db")
        db_name = os.getenv("NEON_DB_NAME", "anaf_warehouse")
        db_user = os.getenv("NEON_DB_USER", "postgres")
        db_password = os.getenv("NEON_DB_PASSWORD", "parola_ta_secreta")
        db_port = os.getenv("NEON_DB_PORT", "5432")

    return psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )

@st.cache_data(ttl=60)
def incarca_date(_conn):
    query = """
        SELECT identificator, titlu, pret_pornire, pret_evaluare, numar_licitatie, timp_ramas, url, 
               istoric_oferte, judet, descriere, tip_sectiune 
        FROM anunturi_detalii;
    """
    df = pd.read_sql(query, _conn)
    if not df.empty:
        if 'pret_pornire' in df.columns:
            df['pret_pornire'] = curata_pret(df['pret_pornire'])
        if 'pret_evaluare' in df.columns:
            df['pret_evaluare'] = curata_pret(df['pret_evaluare'])
    return df

try:
    conn = ia_conexiunea()
    
    query_params = st.query_params
    current_page = query_params.get("page", "home")
    selected_identificator = query_params.get("identificator", None)  
    selected_ofertant = query_params.get("ofertant", None)

    if current_page == "detalii" and selected_identificator:
        afiseaza_pagina_detalii(conn, selected_identificator)
    elif current_page == "licitant" and selected_ofertant:
        afiseaza_pagina_licitant(conn, selected_ofertant)
    else:
        st.title("🎯 Centralizator Publicitate & Licitații ANAF")
        st.markdown("Panou de control optimizat pentru identificarea activă a oportunităților.")

        df = incarca_date(conn)
        
        if df.empty:
            st.warning("Baza de date este goală momentan. Rulează scraperul pentru a aduce date!")
        else:
            df_filtrat = df.copy()

            min_pret_val = float(df_filtrat['pret_pornire'].min()) if 'pret_pornire' in df_filtrat.columns and not df_filtrat['pret_pornire'].dropna().empty else 0.0
            max_pret_val = float(df_filtrat['pret_pornire'].max()) if 'pret_pornire' in df_filtrat.columns and not df_filtrat['pret_pornire'].dropna().empty else 1000000.0
            if min_pret_val >= max_pret_val:
                max_pret_val = min_pret_val + 1.0

            with st.sidebar:
                st.header("🔍 Filtre Avansate")
                st.caption("Rafinare detaliată portofoliu")
                
                st.markdown("---")
                st.subheader("📂 Tip Secțiune")
                tip_selectat = st.radio(
                    "Filtrează după tipul anunțului",
                    options=["Toate", "Licitații", "Publicitate"],
                    index=0,
                    key="f_tip_sectiune"
                )

                st.markdown("---")
                st.subheader("💰 Preț Pornire (RON)")
                pret_min, pret_max = st.slider(
                    "Alege intervalul",
                    min_value=min_pret_val,
                    max_value=max_pret_val,
                    value=(min_pret_val, max_pret_val),
                    step=100.0,
                    format="%.0f RON"
                )

                st.markdown("---")
                st.subheader("⏳ Status Licitație")
                ascunde_expirate = st.checkbox("Ascunde licitațiile încheiate / expirate", value=False)

                st.markdown("---")
                st.subheader("📋 Criterii Specifice")
                fil_tva = st.text_input("TVA / Altele", "", key="f_tva", placeholder="ex: 19, inclus")
                
                coloane_disponibile = [c for c in df_filtrat.columns if c not in ['url', 'titlu', 'descriere', 'judet', 'pret_pornire', 'pret_evaluare', 'tip_sectiune']]
                fil_suplimentar = st.text_input("Alte mențiuni", "", key="f_supl", placeholder="ex: garantat")

                st.markdown("---")
                if st.button("🔄 Resetează filtrele", use_container_width=True):
                    st.rerun()

            st.markdown('<div class="quick-filter-box">', unsafe_allow_html=True)
            qcol1, qcol2, qcol3 = st.columns(3)
            with qcol1:
                fil_text_quick = st.text_input("🔍 Căutare rapidă text", "", key="f_text_quick", placeholder="ex: bijuterii, teren")
            with qcol2:
                fil_judet_quick = st.text_input("📍 Județ", "", key="f_judet_quick", placeholder="ex: botosani")
            with qcol3:
                fil_lic_quick = st.text_input("🔢 Nr. Licitație", "", key="f_lic_quick", placeholder="ex: 4")
            st.markdown('</div>', unsafe_allow_html=True)

            # --- APLICARE FILTRE ---
            if tip_selectat == "Licitații":
                if 'tip_sectiune' in df_filtrat.columns:
                    df_filtrat = df_filtrat[df_filtrat['tip_sectiune'].str.contains("licitatie", case=False, na=False)]
            elif tip_selectat == "Publicitate":
                if 'tip_sectiune' in df_filtrat.columns:
                    df_filtrat = df_filtrat[df_filtrat['tip_sectiune'].str.contains("publicitate", case=False, na=False)]

            if ascunde_expirate and 'timp_ramas' in df_filtrat.columns:
                data_azi = datetime.now()
                def este_licitatie_activa(val):
                    if pd.isna(val):
                        return True
                    val_str = str(val).lower()
                    if "nu mai puteti face oferte" in val_str or "expirat" in val_str:
                        return False
                    date_gasite = re.findall(r'(\d{2})\.(\d{2})\.(\d{4})', val_str)
                    if date_gasite:
                        zi, luna, an = date_gasite[-1]
                        try:
                            data_sfarsit = datetime(int(an), int(luna), int(zi))
                            if data_sfarsit < data_azi:
                                return False
                        except ValueError:
                            pass
                    return True

                df_filtrat = df_filtrat[df_filtrat['timp_ramas'].apply(este_licitatie_activa)]

            if fil_text_quick:
                termen_cautat = elimina_diacritice(fil_text_quick)
                coloane_cautare = [c for c in ['titlu', 'descriere', 'identificator'] if c in df_filtrat.columns]
                if coloane_cautare:
                    masca_txt = df_filtrat[coloane_cautare].astype(str).apply(
                        lambda col: col.apply(elimina_diacritice).str.contains(termen_cautat, na=False)
                    ).any(axis=1)
                    df_filtrat = df_filtrat[masca_txt]

            if fil_judet_quick and 'judet' in df_filtrat.columns:
                termen_judet = elimina_diacritice(fil_judet_quick)
                masca_judet = df_filtrat['judet'].apply(elimina_diacritice).str.contains(termen_judet, na=False)
                df_filtrat = df_filtrat[masca_judet]

            if fil_lic_quick:
                coloane_lic = [c for c in df_filtrat.columns if 'licitatie' in c.lower() or 'nr' in c.lower() or 'numar' in c.lower()]
                if coloane_lic:
                    masca_lic = df_filtrat[coloane_lic].apply(
                        lambda col: col.astype(str).str.contains(fil_lic_quick, case=False, na=False)
                    ).any(axis=1)
                    df_filtrat = df_filtrat[masca_lic]

            if 'pret_pornire' in df_filtrat.columns:
                df_filtrat = df_filtrat[
                    (df_filtrat['pret_pornire'] >= pret_min) & 
                    (df_filtrat['pret_pornire'] <= pret_max) | 
                    (df_filtrat['pret_pornire'].isna())
                ]

            if fil_tva:
                termen_tva = elimina_diacritice(fil_tva)
                coloane_tva = [c for c in df_filtrat.columns if 'tva' in c.lower()]
                if coloane_tva:
                    masca_tva = df_filtrat[coloane_tva].astype(str).apply(
                        lambda col: col.apply(elimina_diacritice).str.contains(termen_tva, na=False)
                    ).any(axis=1)
                    df_filtrat = df_filtrat[masca_tva]

            # --- KPI METRICS CU DESIGN PROFESIONAL (Fără hașuri sau text invizibil) ---
            medie_pret_val = "N/A"
            if 'pret_pornire' in df_filtrat.columns and not df_filtrat['pret_pornire'].dropna().empty:
                medie_pret = df_filtrat['pret_pornire'].mean()
                medie_pret_val = f"{medie_pret:,.0f} RON"

            st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-card">
                        <div class="kpi-label">Anunțuri Filtrate</div>
                        <div class="kpi-value">{len(df_filtrat):,}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Preț Mediu Pornire</div>
                        <div class="kpi-value">{medie_pret_val}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Total Bază Date</div>
                        <div class="kpi-value">{len(df):,}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Sursa</div>
                        <div class="kpi-value" style="font-size: 1.5rem; color: #0284c7;">ANAF Online</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("📋 Lista Oportunităților")
            
            if df_filtrat.empty:
                st.info("Nu există anunțuri care să corespundă filtrelor selectate.")
            else:
                # Limităm afișarea la maxim 250 de anunțuri în tabel
                df_de_afisat = df_filtrat.head(250)
                if len(df_filtrat) > 250:
                    st.caption(f"⚠️ Se afișează primele 250 de anunțuri din totalul de {len(df_filtrat)} rezultate filtrate.")
                
                st.dataframe(
                    df_de_afisat,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "url": st.column_config.LinkColumn("Link Anunț ANAF", display_text="Vezi Anunțul 🔗"),
                        "pret_pornire": st.column_config.NumberColumn("Preț Pornire (RON)", format="%.2f RON"),
                        "pret_evaluare": st.column_config.NumberColumn("Preț Evaluare (RON)", format="%.2f RON"),
                    }
                )

            st.markdown("---")
            st.markdown("##### 🔍 Deschide pagina dedicată pentru un Anunț:")
            col_sel_id, col_btn_id = st.columns([3, 1])
            with col_sel_id:
                identificator_ales = st.selectbox(
                    "Alege Identificatorul Anunțului",
                    options=df_filtrat['identificator'].dropna().tolist() if 'identificator' in df_filtrat.columns and not df_filtrat.empty else [],
                    format_func=lambda x: f"Identificator: {x}",
                    label_visibility="collapsed"
                )
            with col_btn_id:
                if st.button("Vezi Detalii", use_container_width=True):
                    if identificator_ales:
                        st.query_params["page"] = "detalii"
                        st.query_params["identificator"] = str(identificator_ales)
                        st.rerun()

except Exception as e:
    st.error(f"Eroare la procesarea interfeței sau conexiunea la baza de date: {e}")
