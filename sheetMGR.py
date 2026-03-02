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
        st.error("Errore durante il caricamento dell'immagine su ImgBB.")
        return None

def extract_url(formula):
    """Estrae l'URL pulito dalla formula =IMAGE("url")"""
    formula_str = str(formula)
    if 'http' in formula_str:
        return formula_str.split('"')[1] if '"' in formula_str else formula_str
    return None

# --- 2. LOGICA DI CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. INTERFACCIA ---
st.set_page_config(page_title="Math DB Manager", layout="wide")
tab1, tab2 = st.tabs(["➕ Inserimento", "🔍 Archivio e Modifica"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.header("Aggiungi Nuovo Esercizio")
    with st.form("insert_form", clear_on_submit=True):
        t_latex = st.text_area("Testo LaTeX (Obbligatorio):")
        img_file = st.file_uploader("Immagine (Opzionale):", type=['png', 'jpg', 'jpeg'])
        submit = st.form_submit_button("Salva nel Cloud")

    if submit:
        if not t_latex:
            st.error("Il testo dell'esercizio è obbligatorio!")
        else:
            with st.spinner("Salvataggio..."):
                df_check = conn.read().dropna(how="all")
                next_id = int(df_check['ID'].max()) + 1 if not df_check.empty else 1
                
                # Gestione immagine opzionale
                url_img = upload_to_imgbb(img_file) if img_file else ""
                valore_img = f'=IMAGE("{url_img}")' if url_img else ""
                
                try:
                    gc = get_gspread_client()
                    sh = gc.open_by_url(SPREADSHEET_URL)
                    ws = sh.get_worksheet(0)
                    ws.append_row([next_id, t_latex, valore_img], value_input_option='USER_ENTERED')
                    st.success(f"Esercizio {next_id} creato correttamente!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Errore durante l'invio a Google Sheets: {e}")

# --- TAB 2: ARCHIVIO E MODIFICA ---
with tab2:
    st.header("Gestione Database")
    df = conn.read().dropna(how="all")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("Cerca nel testo LaTeX:")
    with col2:
        id_filter = st.number_input("Filtra per ID:", min_value=0, step=1)

    if search:
        df = df[df['TESTO'].str.contains(search, case=False, na=False)]
    if id_filter > 0:
        df = df[df['ID'].astype(int) == id_filter]

    st.divider()

    if df.empty:
        st.warning("Nessun esercizio trovato.")
    else:
        for index, row in df.iterrows():
            with st.expander(f"🆔 ID: {row['ID']} | {row['TESTO'][:60]}..."):
                c_img, c_text = st.columns([1, 2])
                
                current_url = extract_url(row['IMMAGINE'])
                
                with c_img:
                    if current_url:
                        st.image(current_url, width=250)
                    else:
                        st.info("Nessuna immagine")
                
                with c_text:
                    st.latex(row['TESTO'])
                    
                    with st.popover("📝 Modifica"):
                        new_text = st.text_area("Modifica LaTeX:", value=row['TESTO'], key=f"t_{row['ID']}")
                        new_img = st.file_uploader("Sostituisci immagine:", type=['png', 'jpg'], key=f"i_{row['ID']}")
                        
                        if st.button("Conferma Modifiche", key=f"b_{row['ID']}"):
                            if not new_text:
                                st.error("Il testo non può essere vuoto.")
                            else:
                                with st.spinner("Aggiornamento..."):
                                    # Se carichi una nuova immagine, usa quella, altrimenti tieni la vecchia
                                    if new_img:
                                        final_url = upload_to_imgbb(new_img)
                                        final_val = f'=IMAGE("{final_url}")' if final_url else ""
                                    else:
                                        final_val = row['IMMAGINE']

                                    gc = get_gspread_client()
                                    sh = gc.open_by_url(SPREADSHEET_URL)
                                    ws = sh.get_worksheet(0)
                                    
                                    cell = ws.find(str(int(row['ID'])), in_column=1)
                                    if cell:
                                        ws.update_cell(cell.row, 2, new_text)
                                        ws.update_cell(cell.row, 3, final_val)
                                        st.cache_data.clear()
                                        st.rerun()
