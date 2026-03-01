import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
import base64
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURAZIONE CONNESSIONI ---
# Usiamo st.connection solo per la LETTURA (veloce e con cache)
conn = st.connection("gsheets", type=GSheetsConnection)

# Funzione per ottenere il client gspread per la SCRITTURA (precisa per le formule)
def get_gspread_client():
    # Estraiamo le credenziali direttamente dai secrets che hai già configurato
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

# --- 2. INTERFACCIA ---
st.title("🧮 Database Esercizi (Versione Stabile)")

with st.form("insert_form", clear_on_submit=True):
    testo_latex = st.text_area("Testo LaTeX:")
    immagine_file = st.file_uploader("Immagine:", type=['png', 'jpg', 'jpeg'])
    submit = st.form_submit_button("Salva Esercizio")

if submit and testo_latex and immagine_file:
    with st.spinner("Inviando i dati..."):
        # A. CALCOLO ID (Leggiamo lo sheet attuale)
        try:
            df_esistente = conn.read()
            df_esistente = df_esistente.dropna(how="all")
            nuovo_id = int(df_esistente['ID'].max()) + 1 if not df_esistente.empty else 1
        except:
            nuovo_id = 1

        # B. UPLOAD IMMAGINE
        url_img = upload_to_imgbb(immagine_file)

        if url_img:
            # C. SCRITTURA DIRETTA (APPEND)
            try:
                # Inizializziamo gspread
                gc = get_gspread_client()
                # Apriamo lo sheet usando l'URL presente nei secrets
                sh = gc.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"])
                worksheet = sh.get_worksheet(0) # Il primo foglio

                # Prepariamo la riga
                formula_img = f'=IMAGE("{url_img}")'
                nuova_riga = [nuovo_id, testo_latex, formula_img]

                # APPEND della riga: preserva tutto ciò che c'è già!
                # value_input_option='USER_ENTERED' è fondamentale per attivare la formula
                worksheet.append_row(nuova_riga, value_input_option='USER_ENTERED')

                st.success(f"✅ Esercizio {nuovo_id} aggiunto correttamente!")
                st.image(url_img, caption="Anteprima immagine caricata", width=300)
                
                # Puliamo la cache di Streamlit per vedere i nuovi dati al prossimo refresh
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")