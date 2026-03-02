import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
import base64
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURAZIONE ---
SPREADSHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]

def get_gspread_client():
    creds_info = st.secrets["connections"]["gsheets"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

def upload_to_imgbb(uploaded_file):
    if uploaded_file is None:
        return None
    api_key = st.secrets["IMGBB_API_KEY"]
    url = "https://api.imgbb.com/1/upload"
    img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
    payload = {"key": api_key, "image": img_b64, "name": uploaded_file.name}
    try:
        response = requests.post(url, data=payload)
        return response.json()["data"]["url"]
    except:
        return None

def extract_url(formula):
    f = str(formula).strip()
    if not f or f == 'nan' or f == 'None':
        return None
    if 'http' in f:
        return f.split('"')[1] if '"' in f else f
    return None

# --- 2. CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

st.set_page_config(page_title="Math DB Manager", layout="wide")
tab1, tab2 = st.tabs(["➕ Inserimento", "🔍 Archivio e Modifica"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.header("Nuovo Esercizio")
    with st.form("insert_form", clear_on_submit=True):
        t_latex = st.text_area("Testo LaTeX (Obbligatorio):")
        img_file = st.file_uploader("Immagine (Opzionale):", type=['png', 'jpg', 'jpeg'])
        submit = st.form_submit_button("Salva")

    if submit:
        if not t_latex:
            st.error("Inserisci il testo!")
        else:
            with st.spinner("Salvataggio..."):
                df_raw = conn.read().dropna(how="all")
                # Normalizziamo i nomi delle colonne per il calcolo ID
                df_raw.columns = [c.upper().strip() for c in df_raw.columns]
                next_id = int(df_raw['ID'].max()) + 1 if 'ID' in df_raw.columns and not df_raw.empty else 1
                
                url_img = upload_to_imgbb(img_file)
                valore_img = f'=IMAGE("{url_img}")' if url_img else ""
                
                gc = get_gspread_client()
                sh = gc.open_by_url(SPREADSHEET_URL)
                ws = sh.get_worksheet(0)
                ws.append_row([next_id, t_latex, valore_img], value_input_option='USER_ENTERED')
                st.success(f"Creato esercizio {next_id}")
                st.cache_data.clear()

# --- TAB 2: ARCHIVIO E MODIFICA ---
with tab2:
    st.header("Gestione Database")
    df = conn.read().dropna(how="all")
    
    # TRUCCO: Normalizziamo i nomi delle colonne per evitare KeyError
    df.columns = [c.upper().strip() for c in df.columns]

    if 'ID' not in df.columns or 'TESTO' not in df.columns or 'IMMAGINE' not in df.columns:
        st.error(f"Colonne non trovate! Assicurati che il foglio abbia: ID, TESTO, IMMAGINE. Trovate: {list(df.columns)}")
    else:
        search = st.text_input("Cerca nel testo:")
        if search:
            df = df[df['TESTO'].str.contains(search, case=False, na=False)]

        for index, row in df.iterrows():
            url_visualizzazione = extract_url(row['IMMAGINE'])
            
            with st.expander(f"🆔 ID: {row['ID']} | {str(row['TESTO'])[:50]}..."):
                c_img, c_text = st.columns([1, 2])
                with c_img:
                    if url_visualizzazione:
                        st.image(url_visualizzazione, width=300)
                    else:
                        st.info("No immagine")
                
                with c_text:
                    st.latex(row['TESTO'])
                    with st.popover("📝 Modifica"):
                        edit_t = st.text_area("Testo:", value=row['TESTO'], key=f"t_{row['ID']}")
                        edit_i = st.file_uploader("Nuova immagine:", type=['png', 'jpg'], key=f"i_{row['ID']}")
                        
                        if st.button("Salva", key=f"b_{row['ID']}"):
                            with st.spinner("Aggiornamento..."):
                                if edit_i:
                                    nuovo_url = upload_to_imgbb(edit_i)
                                    f_val = f'=IMAGE("{nuovo_url}")' if nuovo_url else ""
                                else:
                                    f_val = row['IMMAGINE']

                                gc = get_gspread_client()
                                sh = gc.open_by_url(SPREADSHEET_URL)
                                ws = sh.get_worksheet(0)
                                cell = ws.find(str(int(row['ID'])), in_column=1)
                                if cell:
                                    ws.update_cell(cell.row, 2, edit_t)
                                    ws.update_cell(cell.row, 3, f_val)
                                    st.cache_data.clear()
                                    st.rerun()