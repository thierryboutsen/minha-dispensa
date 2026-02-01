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
    st.error("ERRO: Chave API não encontrada.")
    st.stop()

genai.configure(api_key=api_key)
st.set_page_config(page_title="Minha Dispensa Pro", page_icon="🛒")

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
def processar_com_gemini(image_buffer, prompt_text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    image_parts = [{"mime_type": "image/jpeg", "data": image_buffer.getvalue()}]
    response = model.generate_content([prompt_text, image_parts[0]])
    return response.text

# --- 4. INTERFACE ---
st.title("🛒 Minha Dispensa Inteligente")

if 'dados_temp' not in st.session_state:
    st.session_state['dados_temp'] = None

tab_add, tab_relatorio = st.tabs(["➕ Adicionar Itens", "📊 Relatório de Gastos"])

with tab_add:
    # Seletor de Modo e Fonte do Arquivo (FOTO OU ARQUIVO)
    opcao = st.radio("Como deseja adicionar?", ["📸 Foto do Cupom", "🔍 Escanear QR Code"])
    fonte = st.radio("Fonte da imagem:", ["📷 Câmera ao Vivo", "📁 Escolher Arquivo/Galeria"], horizontal=True)

    st.divider()
    imagem_final = None

    if fonte == "📷 Câmera ao Vivo":
        imagem_final = st.camera_input("Capturar imagem")
    else:
        imagem_final = st.file_uploader("Selecione uma imagem do cupom", type=['jpg', 'png', 'jpeg'])

    if imagem_final:
        if "Foto do Cupom" in opcao:
            if st.button("✨ Analisar com IA"):
                with st.spinner("Processando..."):
                    prompt = "Analise o cupom e extraia: produto, quantidade, categoria, preco. Retorne JSON PURO: [{'produto': 'X', 'quantidade': 1, 'categoria': 'Limpeza', 'preco': 5.50}]"
                    res = processar_com_gemini(imagem_final, prompt)
                    clean = res.replace("```json", "").replace("```", "").strip()
                    st.session_state['dados_temp'] = pd.DataFrame(json.loads(clean))
        else:
            if st.button("🔗 Ler QR Code"):
                with st.spinner("Lendo link..."):
                    prompt = "Extraia apenas o link (URL) contido neste QR Code. Retorne apenas o texto da URL."
                    link = processar_com_gemini(imagem_final, prompt)
                    st.success("Link detectado!")
                    st.link_button("🌐 Abrir site da SEFAZ", link.strip())

    # Confirmação e Salvamento
    if st.session_state['dados_temp'] is not None:
        st.divider()
        st.write("### ✅ Confira e edite os dados:")
        df_editado = st.data_editor(st.session_state['dados_temp'], num_rows="dynamic")
        
        if st.button("☁️ Salvar no Google Sheets"):
            sheet = conectar_gsheets()
            if sheet:
                data_hoje = datetime.now().strftime('%d/%m/%Y')
                for linha in df_editado.values.tolist():
                    linha.append(data_hoje)
                    sheet.append_row(linha)
                st.balloons()
                st.success("Tudo salvo!")
                st.session_state['dados_temp'] = None

with tab_relatorio:
    st.subheader("📊 Resumo de Gastos")
    if st.button("🔄 Carregar Dados Atualizados"):
        sheet = conectar_gsheets()
        if sheet:
            dados = sheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                
                # Normaliza nomes de colunas para evitar o KeyError
                df.columns = [c.strip().lower() for c in df.columns]
                
                if 'preco' in df.columns:
                    # Garante que preco seja numérico
                    df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0)
                    st.metric("Total Gasto", f"R$ {df['preco'].sum():.2f}")
                    st.write("### Gastos por Categoria")
                    st.bar_chart(df.groupby('categoria')['preco'].sum())
                else:
                    st.error("Coluna 'preco' não encontrada na planilha. Verifique o cabeçalho.")
                
                st.write("### Histórico de Compras")
                st.dataframe(df)
            else:
                st.info("Planilha vazia.")
