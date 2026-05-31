import streamlit as st
import os
from datetime import datetime
from pathlib import Path

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

# SE GUARDA EN TU ESCRITORIO
RUTA_BASE = Path.home() / "Desktop" / "Fotos_Anden"

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
if 'carpeta' not in st.session_state: st.session_state.carpeta = ""
if 'fotos_mercancia' not in st.session_state: st.session_state.fotos_mercancia = 0
if 'ruta_lote' not in st.session_state: st.session_state.ruta_lote = ""

def guardar_local(nombre_archivo, foto_bytes):
    ruta_completa = st.session_state.ruta_lote / nombre_archivo
    with open(ruta_completa, "wb") as f:
        f.write(foto_bytes)
    return ruta_completa

# PASO -1: Nombre de carpeta
if st.session_state.paso == -1:
    st.subheader("Paso 1: Nombra el lote")
    nombre = st.text_input("Nombre de la carpeta:", placeholder="Ej: Entrada_Pedido_789_Placas_XYZ")
    if st.button("Crear carpeta e iniciar", type="primary") and nombre:
        st.session_state.carpeta = nombre.replace(" ", "_")
        st.session_state.ruta_lote = RUTA_BASE / st.session_state.carpeta
        os.makedirs(st.session_state.ruta_lote, exist_ok=True)
        st.session_state.paso = 0
        st.success(f"Carpeta creada en: {st.session_state.ruta_lote}")
        st.rerun()

# PASOS 0-7: Toma de fotos
elif st.session_state.paso < len(FLUJO_FOTOS):
    paso_actual = FLUJO_FOTOS[st.session_state.paso]
    st.subheader(paso_actual["titulo"])
    st.caption(f"Requisito: {paso_actual['req']}")
    st.info(f"Guardando en: {st.session_state.ruta_lote}")
    st.progress((st.session_state.paso + 1) / len(FLUJO_FOTOS))

    if paso_actual.get("multiple"):
        st.write(f"Fotos de mercancía tomadas: {st.session_state.fotos_mercancia}")
        foto = st.camera_input("Toma una foto de tarima/caja/etiqueta", key=f"foto_{st.session_state.paso}_{st.session_state.fotos_mercancia}")
        col1, col2 = st.columns(2)
        if col1.button("Guardar foto y tomar otra"):
            if foto:
                nombre = f"{datetime.now().strftime('%H%M%S')}5_mercancia{st.session_state.fotos_mercancia+1}.jpg"
                ruta = guardar_local(nombre, foto.getvalue())
                st.session_state.fotos_mercancia += 1
                st.toast(f"✅ Guardada: {ruta.name}")
                st.rerun()
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
                nombre = f"{st.session_state.paso+1}_{paso_actual['key']}.jpg"
                ruta = guardar_local(nombre, foto.getvalue())
                st.success(f"✅ Guardada: {ruta.name}")
                st.session_state.paso += 1
                st.rerun()
            else: st.warning("Toma la foto primero")

# PASO FINAL
else:
    st.success(f"🎉 Lote completo guardado en tu Escritorio")
    st.balloons()
    st.code(f"{st.session_state.ruta_lote}")
    if st.button("Abrir carpeta"):
        os.startfile(st.session_state.ruta_lote)
    if st.button("Empezar nuevo lote"):
        st.session_state.paso = -1
        st.session_state.carpeta = ""
        st.session_state.fotos_mercancia = 0
        st.session_state.ruta_lote = ""
        st.rerun()
