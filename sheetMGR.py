import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from oauth2client.service_account import ServiceAccountCredentials
import io

# 1. Configurazione Connessioni
conn = st.connection("gsheets", type=GSheetsConnection)

# Per Drive usiamo le stesse credenziali del service account
def get_drive_service():
    scope = ["https://www.googleapis.com/auth/drive"]
    # Assicurati che il percorso del JSON sia corretto o usa i secrets
    creds = ServiceAccountCredentials.from_json_keyfile_name("credenziali_google.json", scope)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file):
    service = get_drive_service()
    file_metadata = {'name': file.name}
    media = MediaIoBaseUpload(io.BytesIO(file.getvalue()), mimetype=file.type)
    
    # Carica il file
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded_file.get('id')
    
    # Rendi il file pubblico (necessario perché la formula =IMAGE lo veda)
    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    
    return f"https://drive.google.com/uc?export=view&id={file_id}"

# 2. Interfaccia Streamlit
st.title("🧮 Admin: Inserimento Esercizi")

with st.form("upload_form", clear_on_submit=True):
    testo = st.text_area("Testo dell'esercizio (LaTeX)")
    immagine = st.file_uploader("Carica immagine", type=['png', 'jpg'])
    submit = st.form_submit_button("Salva nel Database")

if submit and testo and immagine:
    with st.spinner("Sincronizzazione in corso..."):
        # A. Carica su Drive
        url_diretto = upload_to_drive(immagine)
        
        # B. Prepara i dati per lo Sheet
        nuovo_esercizio = pd.DataFrame({
            "TESTO": [testo],
            "IMMAGINE": [f'=IMAGE("{url_diretto}")'] # Formula per vederlo nello Sheet
        })
        
        # C. Leggi, unisci e aggiorna
        data = conn.read()
        updated_df = pd.concat([data, nuovo_esercizio], ignore_index=True)
        conn.update(data=updated_df)
        
        st.success("Esercizio salvato! L'immagine è ora su Drive e il link è nello Sheet.")