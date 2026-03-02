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
    if uploaded_file is None: return None
    api_key = st.secrets["IMGBB_API_KEY"]
    url = "https://api.imgbb.com/1/upload"
    img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
    payload = {"key": api_key, "image": img_b64, "name": uploaded_file.name}
    try:
        response = requests.post(url, data=payload)
        return response.json()["data"]["url"]
    except: return None

def extract_url(value):
    v = str(value).strip()
    if not v or v.lower() in ['nan', 'none', '']: return None
    if '"' in v:
        parts = v.split('"')
        for p in parts:
            if p.startswith('http'): return p
    if v.startswith('http'): return v
    return None

# --- 2. CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

st.set_page_config(page_title="Math DB Manager", layout="wide")
tab1, tab2 = st.tabs(["➕ Inserimento", "🔍 Archivio e Modifica"])

# --- TAB 1: INSERIMENTO (Invariata, usa st.connection per velocità) ---
with tab1:
    st.header("Nuovo Esercizio")
    with st.form("insert_form", clear_on_submit=True):
        t_latex = st.text_area("Testo LaTeX (Obbligatorio):")
        img_file = st.file_uploader("Immagine (Opzionale):", type=['png', 'jpg', 'jpeg'])
        submit = st.form_submit_button("Salva")

    if submit and t_latex:
        with st.spinner("Salvataggio..."):
            df_check = conn.read().dropna(how="all")
            df_check.columns = [c.upper().strip() for c in df_check.columns]
            next_id = int(df_check['ID'].max()) + 1 if ('ID' in df_check.columns and not df_check.empty) else 1
            url_img = upload_to_imgbb(img_file)
            valore_img = f'=IMAGE("{url_img}")' if url_img else ""
            
            gc = get_gspread_client()
            ws = gc.open_by_url(SPREADSHEET_URL).get_worksheet(0)
            ws.append_row([next_id, t_latex, valore_img], value_input_option='USER_ENTERED')
            st.success(f"Salvato ID {next_id}!")
            st.cache_data.clear()

# --- TAB 2: ARCHIVIO E MODIFICA (Usa gspread per la lettura sicura delle formule) ---
with tab2:
    st.header("Gestione Database")
    
    with st.spinner("Caricamento dati in corso..."):
        try:
            gc = get_gspread_client()
            ws = gc.open_by_url(SPREADSHEET_URL).get_worksheet(0)
            # Forza la lettura delle FORMULE invece dei risultati
            data = ws.get_all_records(value_render_option='FORMULA')
            df = pd.DataFrame(data).dropna(how="all")
            df.columns = [c.upper().strip() for c in df.columns]
        except Exception as e:
            st.error(f"Errore caricamento: {e}")
            df = pd.DataFrame()

    if not df.empty:
        search = st.text_input("Cerca LaTeX:")
        if search:
            df = df[df['TESTO'].str.contains(search, case=False, na=False)]

        for index, row in df.iterrows():
            url_display = extract_url(row['IMMAGINE'])
            
            with st.expander(f"🆔 ID: {row['ID']} | {str(row['TESTO'])[:50]}..."):
                c_img, c_text = st.columns([1, 2])
                with c_img:
                    if url_display:
                        # Usiamo un checkbox come interruttore "Mostra/Nascondi"
                        show_img = st.checkbox("👁️ Vedi Immagine", key=f"show_{row['ID']}")
                        if show_img:
                            st.image(url_display, width=300)
                    else:
                        st.info("Nessuna immagine")
                                
                with c_text:
                    st.latex(row['TESTO'])
                    with st.popover("📝 Modifica"):
                        new_t = st.text_area("Testo:", value=row['TESTO'], key=f"t_{row['ID']}")
                        new_i = st.file_uploader("Sostituisci immagine:", type=['png', 'jpg'], key=f"i_{row['ID']}")
                        
                        if st.button("Aggiorna", key=f"b_{row['ID']}"):
                            with st.spinner("Aggiornamento..."):
                                f_val = f'=IMAGE("{upload_to_imgbb(new_i)}")' if new_i else row['IMMAGINE']
                                cell = ws.find(str(int(row['ID'])), in_column=1)
                                if cell:
                                    ws.update_cell(cell.row, 2, new_t)
                                    ws.update_cell(cell.row, 3, f_val)
                                    st.cache_data.clear()
                                    st.rerun()