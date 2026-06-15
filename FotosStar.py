import streamlit as st
import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import json

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

# --- PERMISO DE CÁMARA UNA SOLA VEZ ---
if 'camara_ok' not in st.session_state:
    st.session_state.camara_ok = False

if not st.session_state.camara_ok:
    st.warning("📷 PASO IMPORTANTE: Da permiso a la cámara y toca 'Permitir'")
    st.info("Toma 1 foto de prueba. Con eso el navegador recuerda el permiso para todas las demás.")
    foto_test = st.camera_input("Prueba de cámara - toma cualquier foto", key="camara_test")
    if foto_test:
        st.session_state.camara_ok = True
        st.success("✅ Permiso de cámara guardado. Ya puedes continuar.")
        st.rerun()
    st.stop()

# --- CONFIGURACIÓN OAUTH ---
SCOPES = ['https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_google_service():
    token_info = json.loads(st.secrets["gcp_oauth"]["token"])
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    return build('drive', 'v3', credentials=creds)

drive_service = get_google_service()
st.success("✅ Conectado a Google Drive automáticamente")

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
    carpeta = drive_service.files().create(body=file_metadata, fields='id').execute()
    return carpeta.get('id')

def subir_a_drive(nombre_archivo, foto_bytes, carpeta_id):
    file_metadata = {'name': nombre_archivo, 'parents': [carpeta_id]}
    media = MediaIoBaseUpload(io.BytesIO(foto_bytes), mimetype='image/jpeg', resumable=False)
    archivo = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return archivo.get('id')

# PASO -1: Nombre de referencia
if st.session_state.paso == -1:
    st.subheader("Paso 1: Nombra la Referencia")
    st.info("⚠️ No salgas de la app ni bloquees el celular hasta terminar las 8 fotos")
    nombre = st.text_input("Referencia:", placeholder="Ej: Entrada_Pedido_789_Placas_XYZ")
    if st.button("Crear carpeta e iniciar", type="primary") and nombre:
        st.session_state.referencia = nombre.replace(" ", "_")
        with st.spinner('Creando carpeta en Drive...'):
            try:
                st.session_state.carpeta_referencia_id = crear_carpeta_drive(st.session_state.referencia, CARPETA_DRIVE_ID)
                st.session_state.paso = 0
                st.success(f"Carpeta creada en Drive: {st.session_state.referencia}")
                st.rerun()
            except Exception as e:
                st.error(f"Error creando carpeta: {e}")
                st.error("Verifica que el token en Secrets sea correcto")

# PASOS 0-7: Toma de fotos
elif st.session_state.paso < len(FLUJO_FOTOS):
    paso_actual = FLUJO_FOTOS[st.session_state.paso]
    st.subheader(paso_actual["titulo"])
    st.caption(f"Requisito: {paso_actual['req']}")
    st.info(f"Guardando en Drive: Fotos_Anden/{st.session_state.referencia}")
    st.progress((st.session_state.paso + 1) / len(FLUJO_FOTOS))

    if paso_actual.get("multiple"):
        st.write(f"Fotos de mercancía tomadas: {st.session_state.fotos_mercancia}")

        # CAMBIO 1: file_uploader para quitar límite de 8 fotos
        fotos = st.file_uploader(
            "Toma las fotos con tu cámara y selecciónalas todas aquí",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="uploader_mercancia"
        )

        if st.button("Guardar todas y seguir", type="primary"):
            if fotos:
                with st.spinner(f'Subiendo {len(fotos)} fotos a Drive...'):
                    try:
                        for i, foto in enumerate(fotos):
                            nombre = f"{datetime.now().strftime('%H%M%S')}_5_mercancia{st.session_state.fotos_mercancia+i+1}.jpg"
                            subir_a_drive(nombre, foto.getvalue(), st.session_state.carpeta_referencia_id)

                        st.session_state.fotos_mercancia += len(fotos)
                        st.success(f"✅ Subidas {len(fotos)} fotos a Drive")
                        st.session_state.paso += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error subiendo: {e}")
            else:
                st.warning("Sube al menos 1 foto de mercancía")

    else:
        # CAMBIO 2: key fija para que no sature memoria
        foto = st.camera_input("Toma la foto", key=f"camara_paso_{st.session_state.paso}")
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
        # CAMBIO 3: Limpiar keys para liberar memoria
        for key in list(st.session_state.keys()):
            if key.startswith('camara_') or key.startswith('uploader_'):
                del st.session_state[key]
        st.session_state.paso = -1
        st.session_state.referencia = ""
        st.session_state.fotos_mercancia = 0
        st.session_state.carpeta_referencia_id = ""
        st.rerun()
