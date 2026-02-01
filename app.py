import streamlit as st
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("Chave API não configurada.")
    st.stop()

genai.configure(api_key=api_key)
st.set_page_config(page_title="Dispensa Pro", page_icon="🛒")

# --- 2. CONEXÃO GOOGLE SHEETS ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds).open("Estoque Dispensa").sheet1
        return None
    except Exception as e:
        st.error(f"Erro na planilha: {e}")
        return None

# --- 3. LÓGICA DA IA ---
def processar_cupom(image_buffer):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """Analise o cupom fiscal e extraia: produto, quantidade, categoria, preco. 
    Retorne apenas JSON PURO: [{"produto": "X", "quantidade": 1, "categoria": "Alimentação", "preco": 5.50}]"""
    
    image_parts = [{"mime_type": "image/jpeg", "data": image_buffer.getvalue()}]
    response = model.generate_content([prompt, image_parts[0]])
    return response.text

# --- 4. INTERFACE ---
st.title("🛒 Minha Dispensa Pro")

if 'dados' not in st.session_state:
    st.session_state['dados'] = None

# Opções de entrada simples
metodo = st.radio("Como deseja adicionar?", ["Foto do Cupom", "Câmera ao Vivo"])

foto_para_processar = None

if metodo == "Foto do Cupom":
    foto_para_processar = st.file_uploader("Escolha a foto", type=['jpg', 'png', 'jpeg'])
else:
    foto_para_processar = st.camera_input("Tire a foto do cupom")

if foto_para_processar and st.button("✨ Ler Cupom"):
    try:
        res = processar_cupom(foto_para_processar)
        clean = res.replace("```json", "").replace("```", "").strip()
        st.session_state['dados'] = pd.DataFrame(json.loads(clean))
    except Exception as e:
        st.error(f"Erro ao processar: {e}")

# --- 5. TABELA E SALVAMENTO ---
if st.session_state['dados'] is not None:
    st.divider()
    df_editado = st.data_editor(st.session_state['dados'], num_rows="dynamic")
    
    if st.button("☁️ Salvar no Google Sheets"):
        sheet = conectar_gsheets()
        if sheet:
            for linha in df_editado.values.tolist():
                # Adiciona a data de hoje na última coluna
                linha.append(datetime.now().strftime('%d/%m/%Y'))
                sheet.append_row(linha)
            st.balloons()
            st.success("Salvo!")
            st.session_state['dados'] = None

# --- 6. VISUALIZADOR ---
st.divider()
if st.button("📊 Ver Meu Estoque"):
    sheet = conectar_gsheets()
    if sheet:
        df_view = pd.DataFrame(sheet.get_all_records())
        st.dataframe(df_view)
        st.metric("Total", f"R$ {df_view['preco'].sum():.2f}")
