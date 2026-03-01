import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
import base64
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURAZIONE ESTRATTA DAI SECRETS ---
SPREADSHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]

def get_gspread_client():
    creds_info = st.secrets["connections"]["gsheets"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

def upload_to_imgbb(uploaded_file):
    api_key = st.secrets["IMGBB_API_KEY"]
    url = "https://api.imgbb.com/1/upload"
    img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
    payload = {"key": api_key, "image": img_b64, "name": uploaded_file.name}
    try:
        response = requests.post(url, data=payload)
        return response.json()["data"]["url"]
    except:
        return None

# --- 2. LOGICA DI CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. INTERFACCIA A SCHEDE ---
st.set_page_config(page_title="Math DB Manager", layout="wide")
tab1, tab2 = st.tabs(["➕ Inserimento", "🔍 Archivio e Modifica"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.header("Aggiungi Nuovo Esercizio")
    with st.form("insert_form", clear_on_submit=True):
        t_latex = st.text_area("Testo LaTeX:")
        img_file = st.file_uploader("Immagine:", type=['png', 'jpg', 'jpeg'])
        submit = st.form_submit_button("Salva nel Cloud")

    if submit and t_latex and img_file:
        with st.spinner("Salvataggio..."):
            df_check = conn.read().dropna(how="all")
            next_id = int(df_check['ID'].max()) + 1 if not df_check.empty else 1
            url_img = upload_to_imgbb(img_file)
            
            if url_img:
                gc = get_gspread_client()
                sh = gc.open_by_url(SPREADSHEET_URL)
                ws = sh.get_worksheet(0)
                ws.append_row([next_id, t_latex, f'=IMAGE("{url_img}")'], value_input_option='USER_ENTERED')
                st.success(f"Esercizio {next_id} creato!")
                st.cache_data.clear()

# --- TAB 2: ARCHIVIO E MODIFICA ---
with tab2:
    st.header("Gestione Database")
    
    # Caricamento Dati
    df = conn.read().dropna(how="all")
    
    # Filtri di ricerca
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("Cerca nel testo LaTeX (es. 'integrale', 'frazione'):")
    with col2:
        id_filter = st.number_input("Filtra per ID:", min_value=0, step=1, value=0)

    # Applicazione Filtri
    if search:
        df = df[df['TESTO'].str.contains(search, case=False, na=False)]
    if id_filter > 0:
        df = df[df['ID'].astype(int) == id_filter]

    st.divider()

    # Visualizzazione Risultati
    if df.empty:
        st.warning("Nessun esercizio trovato con questi criteri.")
    else:
        for index, row in df.iterrows():
            with st.expander(f"🆔 ID: {row['ID']} | Testo: {row['TESTO'][:50]}..."):
                c_img, c_text = st.columns([1, 2])
                
                # Estrazione URL pulito dalla formula =IMAGE("url")
                raw_url = str(row['IMMAGINE']).replace('=IMAGE("', '').replace('")', '')
                
                with c_img:
                    st.image(raw_url, width=250)
                with c_text:
                    st.latex(row['TESTO'])
                    
                    # --- FORM DI MODIFICA ---
                    with st.popover("📝 Modifica questo esercizio"):
                        new_text = st.text_area("Modifica LaTeX:", value=row['TESTO'], key=f"txt_{row['ID']}")
                        new_img = st.file_uploader("Sostituisci immagine (opzionale):", type=['png', 'jpg'], key=f"img_{row['ID']}")
                        
                        if st.button("Conferma Modifiche", key=f"btn_{row['ID']}"):
                            final_url = url_img = upload_to_imgbb(new_img) if new_img else raw_url
                            
                            # Operazione di Update Chirurgo con gspread
                            gc = get_gspread_client()
                            sh = gc.open_by_url(SPREADSHEET_URL)
                            ws = sh.get_worksheet(0)
                            
                            # Troviamo la riga esatta (ID è nella colonna A)
                            # Cerchiamo l'ID nella colonna 1 (A)
                            cell = ws.find(str(int(row['ID'])), in_column=1)
                            
                            if cell:
                                # Aggiorniamo le colonne B (Testo) e C (Immagine) di quella riga
                                ws.update_cell(cell.row, 2, new_text)
                                ws.update_cell(cell.row, 3, f'=IMAGE("{final_url}")')
                                
                                st.success("Modifica salvata! Ricarica la pagina.")
                                st.cache_data.clear()
                                st.rerun()
