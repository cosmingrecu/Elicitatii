import streamlit as st
import psycopg2
import pandas as pd
import unicodedata
import re
from datetime import datetime

from pages_detalii import afiseaza_pagina_detalii, afiseaza_pagina_licitant

st.set_page_config(
    page_title="ANAF Deal Flow Dashboard",
    page_icon="🎯",
    layout="wide"
)

st.markdown("""
    <style>
        .main { background-color: #f4f6f9; }
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .quick-filter-box { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 20px; }
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
    return psycopg2.connect(
        dbname="anaf_warehouse",
        user="postgres",
        password="parola_ta_secreta",
        host="db",
        port="5432"
    )

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
        st.markdown("Panou de control avansat pentru identificarea activă a oportunităților de achiziție.")

        query = """
            SELECT identificator, titlu, pret_pornire, pret_evaluare, numar_licitatie, timp_ramas, url, 
                   istoric_oferte, judet, descriere 
            FROM anunturi_detalii;
        """
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("Baza de date este goală momentan. Rulează scraperul pentru a aduce date!")
        else:
            df_filtrat = df.copy()

            if 'pret_pornire' in df_filtrat.columns:
                df_filtrat['pret_pornire'] = curata_pret(df_filtrat['pret_pornire'])
            if 'pret_evaluare' in df_filtrat.columns:
                df_filtrat['pret_evaluare'] = curata_pret(df_filtrat['pret_evaluare'])

            min_pret_val = float(df_filtrat['pret_pornire'].min()) if 'pret_pornire' in df_filtrat.columns and not df_filtrat['pret_pornire'].dropna().empty else 0.0
            max_pret_val = float(df_filtrat['pret_pornire'].max()) if 'pret_pornire' in df_filtrat.columns and not df_filtrat['pret_pornire'].dropna().empty else 1000000.0
            if min_pret_val >= max_pret_val:
                max_pret_val = min_pret_val + 1.0

            with st.sidebar:
                st.header("🔍 Filtre Avansate")
                st.caption("Panou retractabil pentru rafinarea detaliată a portofoliului.")
                
                st.markdown("---")
                st.subheader("💰 Interval Preț Pornire (RON)")
                pret_min, pret_max = st.slider(
                    "Alege intervalul de preț",
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
                fil_tva = st.text_input("TVA / Altele", "", key="f_tva", placeholder="ex: '19', 'inclus'")
                
                coloane_disponibile = [c for c in df_filtrat.columns if c not in ['url', 'titlu', 'descriere', 'judet', 'pret_pornire', 'pret_evaluare']]
                fil_suplimentar = st.text_input("Alte mențiuni (căutare extinsă)", "", key="f_supl", placeholder="ex: 'garantat', 'executare'")

                st.markdown("---")
                if st.button("🔄 Resetează toate filtrele", use_container_width=True):
                    st.rerun()

            st.markdown('<div class="quick-filter-box">', unsafe_allow_html=True)
            qcol1, qcol2, qcol3 = st.columns(3)
            
            with qcol1:
                fil_text_quick = st.text_input("🔍 Căutare rapidă text / cuvinte", "", key="f_text_quick", placeholder="ex: 'bijuterii', 'teren'")
            with qcol2:
                fil_judet_quick = st.text_input("📍 Județ", "", key="f_judet_quick", placeholder="ex: 'botosani'")
            with qcol3:
                fil_lic_quick = st.text_input("🔢 A cata licitație e (Nr. Licitație)", "", key="f_lic_quick", placeholder="ex: '4'")
                
            st.markdown('</div>', unsafe_allow_html=True)

            # --- APLICARE FILTRE ---

            # 1. Filtru Expirate
            if ascunde_expirate and 'timp_ramas' in df_filtrat.columns:
                data_azi = datetime(2026, 8, 8)
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

            # 2. Căutare rapidă text
            if fil_text_quick:
                termen_cautat = elimina_diacritice(fil_text_quick)
                coloane_text = df_filtrat.select_dtypes(include=['object', 'string']).columns
                masca_txt = df_filtrat[coloane_text].apply(
                    lambda col: col.apply(elimina_diacritice).str.contains(termen_cautat, na=False)
                ).any(axis=1)
                df_filtrat = df_filtrat[masca_txt]

            # 3. Județ
            if fil_judet_quick and 'judet' in df_filtrat.columns:
                termen_judet = elimina_diacritice(fil_judet_quick)
                masca_judet = df_filtrat['judet'].apply(elimina_diacritice).str.contains(termen_judet, na=False)
                df_filtrat = df_filtrat[masca_judet]

            # 4. Număr licitație
            if fil_lic_quick:
                coloane_lic = [c for c in df_filtrat.columns if 'licitatie' in c.lower() or 'nr' in c.lower() or 'numar' in c.lower()]
                if coloane_lic:
                    masca_lic = df_filtrat[coloane_lic].apply(
                        lambda col: col.astype(str).str.contains(fil_lic_quick, case=False, na=False)
                    ).any(axis=1)
                    df_filtrat = df_filtrat[masca_lic]

            # 5. Preț pornire
            if 'pret_pornire' in df_filtrat.columns:
                df_filtrat = df_filtrat[
                    (df_filtrat['pret_pornire'] >= pret_min) & 
                    (df_filtrat['pret_pornire'] <= pret_max) | 
                    (df_filtrat['pret_pornire'].isna())
                ]

            # 6. TVA / Altele
            if fil_tva:
                termen_tva = elimina_diacritice(fil_tva)
                coloane_tva = [c for c in df_filtrat.columns if 'tva' in c.lower()]
                if not coloane_tva:
                    coloane_tva = df_filtrat.select_dtypes(include=['object', 'string', 'number']).columns
                masca_tva = df_filtrat[coloane_tva].apply(
                    lambda col: col.apply(elimina_diacritice).str.contains(termen_tva, na=False)
                ).any(axis=1)
                df_filtrat = df_filtrat[masca_tva]

            # 7. Mențiuni suplimentare
            if fil_suplimentar and coloane_disponibile:
                termen_supl = elimina_diacritice(fil_suplimentar)
                masca_supl = df_filtrat[coloane_disponibile].apply(
                    lambda col: col.apply(elimina_diacritice).str.contains(termen_supl, na=False)
                ).any(axis=1)
                df_filtrat = df_filtrat[masca_supl]

            # --- KPI METRICS ---
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Anunțuri Filtrate", len(df_filtrat))
            
            if 'pret_pornire' in df_filtrat.columns and not df_filtrat.empty:
                medie_pret = df_filtrat['pret_pornire'].mean()
                kpi2.metric("Preț Mediu Pornire", f"{medie_pret:,.0f} RON")
            else:
                kpi2.metric("Preț Mediu Pornire", "N/A")
                
            kpi3.metric("Total Bază Date", len(df))
            kpi4.metric("Sursa", "ANAF Online")

            st.markdown("---")
            st.subheader("📋 Lista Oportunităților")
            st.caption("💡 *Prețurile au fost corectate din formatul nativ ANAF în format numeric standard.*")
            
            # --- TABEL ---
            st.dataframe(
                df_filtrat,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "url": st.column_config.LinkColumn("Link Anunț ANAF", display_text="Vezi Anunțul 🔗"),
                    "pret_pornire": st.column_config.NumberColumn("Preț Pornire (RON)", format="%.2f RON"),
                    "pret_evaluare": st.column_config.NumberColumn("Preț Evaluare (RON)", format="%.2f RON"),
                    "procent_reducere": st.column_config.ProgressColumn("Reducere (%)", min_value=0, max_value=100, format="%d%%"),
                }
            )

            st.markdown("---")
            st.markdown("##### 🔍 Deschide pagina dedicată pentru un Anunț (după Identificator):")
            col_sel_id, col_btn_id = st.columns([3, 1])
            with col_sel_id:
                identificator_ales = st.selectbox(
                    "Alege Identificatorul Anunțului",
                    options=df_filtrat['identificator'].dropna().tolist() if 'identificator' in df_filtrat.columns and not df_filtrat.empty else [],
                    format_func=lambda x: f"Identificator: {x}",
                    label_visibility="collapsed"
                )
            with col_btn_id:
                if st.button("Vezi Detalii Licitație", use_container_width=True):
                    if identificator_ales:
                        st.query_params["page"] = "detalii"
                        st.query_params["identificator"] = str(identificator_ales)
                        st.rerun()

except Exception as e:
    st.error(f"Eroare la procesarea interfeței sau conexiunea la baza de date: {e}")