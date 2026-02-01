import streamlit as st
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import cv2
import numpy as np
from streamlit_camera_input_live import camera_input_live

# --- 1. CONFIGURAÇÕES E CHAVES ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

if not api_key:
    st.error("ERRO: Chave API não configurada.")
    st.stop()

genai.configure(api_key=api_key)

st.set_page_config(page_title="Dispensa Pro", page_icon="🛒", layout="centered")

# --- 2. CONEXÃO GOOGLE SHEETS ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
        client = gspread.authorize(creds)
        return client.open("Estoque Dispensa").sheet1
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# --- 3. LOGICA DA IA ---
def processar_ia(image_file):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analise o cupom fiscal. Extraia itens: produto, quantidade, categoria, preco.
    Data hoje: {datetime.now().strftime('%d/%m/%Y')}
    Retorne JSON PURO (lista):
    [{{"produto": "Exemplo", "quantidade": 1, "categoria": "Alimentação", "preco": 5.50, "data": "DD/MM/AAAA"}}]
    """
    image_parts = [{"mime_type": image_file.type, "data": image_file.getvalue()}]
    response = model.generate_content([prompt, image_parts[0]])
    return response.text

# --- 4. LOGICA QR CODE ---
def ler_qr_code(image_buffer):
    if image_buffer:
        bytes_data = image_buffer.getvalue()
        cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        url, _, _ = detector.detectAndDecode(cv2_img)
        return url
    return None

# --- 5. INTERFACE ---
st.title("🛒 Controle de Dispensa Inteligente")

if 'dados_tabela' not in st.session_state:
    st.session_state['dados_tabela'] = None

tab1, tab2 = st.tabs(["📸 Foto (IA)", "🔍 QR Code (SEFAZ)"])

with tab1:
    arq = st.file_uploader("Subir foto do cupom", type=['jpg', 'png', 'jpeg'])
    if arq and st.button("✨ Analisar com IA"):
        res = processar_ia(arq)
        clean = res.replace("```json", "").replace("```", "").strip()
        st.session_state['dados_tabela'] = pd.DataFrame(json.loads(clean))

with tab2:
    st.write("Aponte o QR Code para a câmera:")
    img_cam = camera_input_live()
    if img_cam:
        link = ler_qr_code(img_cam)
        if link:
            st.success("QR Code lido!")
            st.link_button("🌐 Abrir no site da SEFAZ", link)
            st.info("Em breve: Importação automática via link!")

# --- 6. EXIBIÇÃO E SALVAMENTO ---
if st.session_state['dados_tabela'] is not None:
    st.divider()
    df_editado = st.data_editor(st.session_state['dados_tabela'], num_rows="dynamic")
    
    if st.button("☁️ Salvar na Planilha"):
        sheet = conectar_gsheets()
        if sheet:
            novos_dados = df_editado.values.tolist()
            for linha in novos_dados:
                sheet.append_row(linha)
            st.balloons()
            st.success("Salvo com sucesso!")
            st.session_state['dados_tabela'] = None

# --- 7. VISUALIZADOR DE ESTOQUE ---
st.divider()
if st.button("📊 Ver Estoque Atualizado"):
    sheet = conectar_gsheets()
    if sheet:
        dados = sheet.get_all_records()
        if dados:
            df_view = pd.DataFrame(dados)
            # Adiciona link de busca de imagem
            df_view['🖼️ Foto'] = df_view['produto'].apply(lambda x: f"https://www.google.com/search?q={x.replace(' ', '+')}&tbm=isch")
            
            st.dataframe(df_view, column_config={"🖼️ Foto": st.column_config.LinkColumn("Ver Foto")})
            st.metric("Total Investido", f"R$ {df_view['preco'].sum():.2f}")
