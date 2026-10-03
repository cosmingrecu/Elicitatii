import streamlit as st
import pandas as pd
import subprocess

def afiseaza_pagina_detalii(conn, identificator_ales):
    # Zonă superioară cu butoane de navigație și acțiune
    col_nav, col_ext = st.columns([2, 1])
    with col_nav:
        if st.button("← Înapoi la Panoul Principal"):
            st.query_params.clear()
            st.rerun()
            
    with col_ext:
        if st.button("🔄 Rulează Extractor pentru acest Anunț", type="primary", use_container_width=True):
            with st.spinner("Se rulează extractorul pentru preluarea datelor în timp real..."):
                try:
                    # Aici poți apela scriptul tău extern de scraping, de exemplu:
                    # subprocess.run(["python", "extractor.py", str(identificator_ales)], check=True)
                    
                    st.success("Datele au fost actualizate cu succes de la ANAF!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Eroare la rularea extractorului: {e}")

    if not identificator_ales:
        st.warning("Nu a fost furnizat niciun identificator valid.")
        return

    # Forțăm căutarea ca text curat, eliminând orice spațiu accidental
    query_detalii = """
        SELECT *
        FROM anunturi_detalii
        WHERE TRIM(CAST(identificator AS TEXT)) = TRIM(CAST(%s AS TEXT))
        LIMIT 1;
    """
    
    df_detalii = pd.read_sql(
        query_detalii,
        conn,
        params=(str(identificator_ales),)
    )

    if df_detalii.empty:
        st.error(f"Licitația cu identificatorul '{identificator_ales}' nu a fost găsită în baza de date.")
    else:
        row = df_detalii.iloc[0]
        st.title(f"📋 Detalii Licitație: {row.get('titlu', 'Fără titlu')}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Identificator", row.get('identificator', 'N/A'))
        c2.metric("Preț Pornire", f"{row.get('pret_pornire', 'N/A')}")
        c3.metric("Preț Evaluare", f"{row.get('pret_evaluare', 'N/A')}")
        
        if 'url' in row and row['url']:
            st.markdown(f"🔗 **Link Anunț ANAF Original:** [{row['url']}]({row['url']})")

        st.markdown("---")
        st.subheader("👥 Istoric Licitatori și Oferte")
        
        istoric_raw = row.get('istoric_oferte', '')
        oferte_parseate = []
        
        if istoric_raw and isinstance(istoric_raw, str):
            sclise = istoric_raw.split(" | ")
            for item in sclise:
                item_clean = item.strip("[]")
                if " la " in item_clean and " -> " in item_clean:
                    part_left, suma = item_clean.split(" -> ")
                    ofertant_part, data_ora = part_left.split(" la ")
                    ofertant_id = ofertant_part.strip().replace("Ofertant ", "")
                    
                    oferte_parseate.append({
                        "ofertant_id": ofertant_id,
                        "ofertant_full": ofertant_part.strip(),
                        "data_ora": data_ora.strip(),
                        "suma": suma.strip()
                    })

        if oferte_parseate:
            for index, o in enumerate(oferte_parseate):
                col_a, col_b, col_c = st.columns([2, 2, 2])
                with col_a:
                    if st.button(f"👤 {o['ofertant_full']}", key=f"btn_of_{identificator_ales}_{index}"):
                        st.query_params.clear()
                        st.query_params["page"] = "licitant"
                        st.query_params["ofertant"] = o['ofertant_id']
                        st.rerun()
                with col_b:
                    st.write(f"🕒 {o['data_ora']}")
                with col_c:
                    st.markdown(f"💰 **{o['suma']}**")
                st.divider()
        else:
            st.info("Nu există oferte înregistrate pentru acest anunț.")

def afiseaza_pagina_licitant(conn, selected_ofertant):
    if st.button("← Înapoi la Panoul Principal"):
        st.query_params.clear()
        st.rerun()

    st.title(f"👤 Profil Licitant: {selected_ofertant}")
    
    query_licitant = "SELECT identificator, titlu, pret_pornire, istoric_oferte FROM anunturi_detalii WHERE istoric_oferte ILIKE %s;"
    df_lic = pd.read_sql(query_licitant, conn, params=(f'%Ofertant {selected_ofertant}%',))

    toate_ofertele_lui = []
    for _, anunt in df_lic.iterrows():
        istoric_raw = anunt.get('istoric_oferte', '')
        if not istoric_raw or not isinstance(istoric_raw, str):
            continue
            
        for item in istoric_raw.split(" | "):
            item_clean = item.strip("[]")
            if f"Ofertant {selected_ofertant}" in item_clean:
                part_left, suma = item_clean.split(" -> ")
                _, data_ora = part_left.split(" la ")
                
                toate_ofertele_lui.append({
                    "identificator": anunt['identificator'],
                    "titlu": anunt['titlu'],
                    "data_ora": data_ora.strip(),
                    "suma": suma.strip()
                })

    toate_ofertele_lui = sorted(toate_ofertele_lui, key=lambda x: x['data_ora'], reverse=True)
    
    st.metric("Total Licitații cu oferte active", len(toate_ofertele_lui))
    st.subheader("📋 Toate ofertele plasate în sistem")

    if toate_ofertele_lui:
        for index, o in enumerate(toate_ofertele_lui):
            col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
            with col1:
                st.write(f"🕒 {o['data_ora']}")
            with col2:
                st.write(f"📌 {o['titlu']}")
            with col3:
                st.markdown(f"💰 **{o['suma']}**")
            with col4:
                if st.button("Vezi Bunul", key=f"btn_bun_{o['identificator']}_{index}"):
                    st.query_params.clear()
                    st.query_params["page"] = "detalii"
                    st.query_params["identificator"] = str(o['identificator'])
                    st.rerun()
            st.divider()
    else:
        st.warning("Nu s-au găsit oferte înregistrate pentru acest licitant.")