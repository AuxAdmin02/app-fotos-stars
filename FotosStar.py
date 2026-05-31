import streamlit as st
import os
from datetime import datetime
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# CANDADO: Cambia "Anden2026" por tu contraseña
CLAVE = "Anden2026"
if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 Acceso Restringido")
    clave = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if clave == CLAVE:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

st.set_page_config(page_title="Captura Guiada", layout="centered")
st.title("📸 Captura Guiada - Andén")

# --- CONFIGURACIÓN OAUTH ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_CONFIG = {"web": st.secrets["oauth_client"]["web"]}
# Sacamos el redirect_uri directo de la config de web
REDIRECT_URI = st.secrets["oauth_client"]["web"]["redirect_uris"][0]

def get_google_service():
    if 'credentials' not in st.session_state:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        authorization_url, _ = flow.authorization_url(access_type='offline', prompt='consent')
        st.warning("Necesitas iniciar sesión con Google Drive")
        st.link_button("🔑 Conectar con Google Drive", authorization_url)
        st.stop()

    creds = Credentials.from_authorized_user_info(st.session_state['credentials'], SCOPES)
    return build('drive', 'v3', credentials=creds)

# Manejo del callback de OAuth
query_params = st.query_params
if 'code' in query_params and 'credentials' not in st.session_state:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(code=query_params['code'])
    st.session_state['credentials'] = {
        'token': flow.credentials.token,
        'refresh_token': flow.credentials.refresh_token,
        'token_uri': flow.credentials.token_uri,
        'client_id': flow.credentials.client_id,
        'client_secret': flow.credentials.client_secret,
        'scopes': flow.credentials.scopes
    }
    st.query_params.clear()
    st.rerun()

# Si no hay credenciales, detiene la app y muestra botón de login
drive_service = get_google_service()
st.success("✅ Conectado a Google Drive")

# ID DE TU CARPETA "Fotos_Anden" EN DRIVE
CARPETA_DRIVE_ID = "1wqnI-CgvopBrc2tXwDZ8iR_yddrn8fcX"

FLUJO_FOTOS = [
    {"key": "chofer", "titulo": "1. Identificación del Chofer", "req": "Foto clara de INE o licencia"},
    {"key": "placas", "titulo": "2. Placas de la Unidad", "req": "Placa trasera visible"},
    {"key": "sello", "titulo": "3. Sello", "req": "Si no trae, toma foto de la puerta sin sello"},
    {"key": "caja_inicial", "titulo": "4. Caja de la unidad al inicio", "req": "Con mercancía si es entrada / Vacía si es salida"},
    {"key": "mercancia", "titulo": "5. Cajas, Tarimas y Etiquetas", "req": "Toma todas las que necesites. Sin límite", "multiple": True},
    {"key": "danos", "titulo": "6. Daños", "req": "Si no hay daños, toma foto del piso limpio"},
    {"key": "caja_final", "titulo": "7. Caja de la unidad al final", "req": "Vacía si fue descarga / Cargada si ya terminó la carga"},
    {"key": "documentos", "titulo": "8. Documentos entregados", "req": "Con firmas visibles"}
]

if 'paso' not in st.session_state: st.session_state.paso = -1
if 'referencia' not in st.session_state: st.session_state.referencia = ""
if 'fotos_mercancia' not in st.session_state: st.session_state.fotos_mercancia = 0
if 'carpeta_referencia_id' not in st.session_state: st.session_state.carpeta_referencia_id = ""

def crear_carpeta_drive(nombre_carpeta, parent_id):
    file_metadata = {
        'name': nombre_carpeta,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    carpeta = drive_service.files().create(
        body=file_metadata,
        fields='id'
    ).execute()
    return carpeta.get('id')

def subir_a_drive(nombre_archivo, foto_bytes, carpeta_id):
    file_metadata = {'name': nombre_archivo, 'parents': [carpeta_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(foto_bytes),
        mimetype='image/jpeg',
        resumable=False
    )
    archivo = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return archivo.get('id')

# PASO -1: Nombre de referencia
if st.session_state.paso == -1:
    st.subheader("Paso 1: Nombra la Referencia")
    nombre = st.text_input("Referencia:", placeholder="Ej: Entrada_Pedido_789_Placas_XYZ")
    if st.button("Crear carpeta e iniciar", type="primary") and nombre:
        st.session_state.referencia = nombre.replace(" ", "_")
        with st.spinner('Creando carpeta en Drive...'):
            try:
                st.session_state.carpeta_referencia_id = crear_carpeta_drive(
                    st.session_state.referencia,
                    CARPETA_DRIVE_ID
                )
                st.session_state.paso = 0
                st.success(f"Carpeta creada en Drive: {st.session_state.referencia}")
                st.rerun()
            except Exception as e:
                st.error(f"Error creando carpeta: {e}")
                if "invalid_grant" in str(e) or "token" in str(e):
                    del st.session_state['credentials']
                    st.rerun()

# PASOS 0-7: Toma de fotos
elif st.session_state.paso < len(FLUJO_FOTOS):
    paso_actual = FLUJO_FOTOS[st.session_state.paso]
    st.subheader(paso_actual["titulo"])
    st.caption(f"Requisito: {paso_actual['req']}")
    st.info(f"Guardando en Drive: Fotos_Anden/{st.session_state.referencia}")
    st.progress((st.session_state.paso + 1) / len(FLUJO_FOTOS))

    if paso_actual.get("multiple"):
        st.write(f"Fotos de mercancía tomadas: {st.session_state.fotos_mercancia}")
        foto = st.camera_input("Toma una foto de tarima/caja/etiqueta", key=f"foto_{st.session_state.paso}_{st.session_state.fotos_mercancia}")
        col1, col2 = st.columns(2)
        if col1.button("Guardar foto y tomar otra"):
            if foto:
                with st.spinner('Subiendo a Drive...'):
                    try:
                        nombre = f"{datetime.now().strftime('%H%M%S')}_5_mercancia{st.session_state.fotos_mercancia+1}.jpg"
                        subir_a_drive(nombre, foto.getvalue(), st.session_state.carpeta_referencia_id)
                        st.session_state.fotos_mercancia += 1
                        st.toast(f"✅ Subida a Drive: {nombre}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error subiendo: {e}")
            else: st.warning("Toma la foto primero")

        if col2.button("Terminar mercancía y seguir", type="primary"):
            if st.session_state.fotos_mercancia > 0:
                st.session_state.paso += 1
                st.rerun()
            else: st.warning("Debes tomar al menos 1 foto de mercancía")

    else:
        foto = st.camera_input("Toma la foto")
        if st.button("Guardar y siguiente", type="primary"):
            if foto:
                with st.spinner('Subiendo a Drive...'):
                    try:
                        nombre = f"{st.session_state.paso+1}_{paso_actual['key']}.jpg"
                        subir_a_drive(nombre, foto.getvalue(), st.session_state.carpeta_referencia_id)
                        st.success(f"✅ Subida a Drive: {nombre}")
                        st.session_state.paso += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error subiendo: {e}")
            else: st.warning("Toma la foto primero")

# PASO FINAL
else:
    st.success(f"🎉 Referencia completa guardada en Google Drive")
    st.balloons()
    st.link_button("Ver carpeta en Drive", f"https://drive.google.com/drive/folders/{st.session_state.carpeta_referencia_id}")
    if st.button("Empezar nueva Referencia"):
        st.session_state.paso = -1
        st.session_state.referencia = ""
        st.session_state.fotos_mercancia = 0
        st.session_state.carpeta_referencia_id = ""
        st.rerun()
