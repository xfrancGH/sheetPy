import streamlit as st
import io
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload

# 1. Configurazione Sheet (Streamlit legge in automatico dai secrets)
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Configurazione Drive (Manuale tramite i secrets condivisi)
def get_drive_service():
    # Creiamo le credenziali partendo dal dizionario memorizzato nei secrets
    # Assicurati che i nomi delle chiavi nei secrets corrispondano a quelli del JSON
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(info)
    
    # Definiamo lo scope per Drive (se non è già incluso nei secrets)
    scoped_creds = creds.with_scopes(['https://www.googleapis.com/auth/drive'])
    
    return build('drive', 'v3', credentials=scoped_creds)

def upload_to_drive(file):
    service = get_drive_service()
    
    # ID della cartella che hai creato e CONDIVISO con l'email del service account
    FOLDER_ID = '1Rcl6R2nu-Ph8E2mdBTggnm67n9yL-bjv' 
    
    file_metadata = {
        'name': file.name,
        'parents': [FOLDER_ID]
    }
    
    # Importante: riavvolgi il file se è stato già letto
    file.seek(0)
    media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.type, resumable=True)
    
    # Esecuzione del caricamento
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id',
        # Questa riga è fondamentale se lavori in contesti Workspace/Shared Drives
        supportsAllDrives=True 
    ).execute()
    
    file_id = uploaded_file.get('id')
    
    # Rendi il file leggibile per la funzione =IMAGE() di Sheets
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
        supportsAllDrives=True
    ).execute()
    
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