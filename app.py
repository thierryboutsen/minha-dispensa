import streamlit as st
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
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
    # SELETOR DE MODO (Resolve o erro das câmeras)
    opcao = st.radio(
        "Como deseja adicionar os dados?",
        ["📸 Tirar foto do Cupom (IA)", "🔍 Escanear QR Code (Link SEFAZ)"],
        index=0
    )

    st.divider()

    if "Tirar foto do Cupom" in opcao:
        st.subheader("📸 Leitura por IA")
        foto = st.camera_input("Fotografe o cupom fiscal")
        if foto and st.button("✨ Analisar Itens"):
            prompt = "Analise o cupom e extraia: produto, quantidade, categoria, preco. Retorne JSON PURO: [{'produto': 'X', 'quantidade': 1, 'categoria': 'Limpeza', 'preco': 5.50}]"
            res = processar_com_gemini(foto, prompt)
            clean = res.replace("```json", "").replace("```", "").strip()
            st.session_state['dados_temp'] = pd.DataFrame(json.loads(clean))

    else:
        st.subheader("🔍 Leitura de QR Code")
        qr_foto = st.camera_input("Fotografe o QR Code do cupom")
        if qr_foto and st.button("🔗 Extrair Link"):
            prompt = "Extraia apenas o link (URL) contido neste QR Code. Retorne apenas o texto da URL."
            link = processar_com_gemini(qr_foto, prompt)
            st.success("Link detectado!")
            st.link_button("🌐 Abrir no site da SEFAZ", link.strip())

    # Exibição da Tabela para Salvar
    if st.session_state['dados_temp'] is not None:
        st.divider()
        st.write("### ✅ Confira os dados antes de salvar:")
        df_editado = st.data_editor(st.session_state['dados_temp'], num_rows="dynamic")
        
        if st.button("☁️ Salvar Agora na Nuvem"):
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
    st.subheader("📊 Seu Resumo Financeiro")
    if st.button("🔄 Carregar Dados da Planilha"):
        sheet = conectar_gsheets()
        if sheet:
            dados = sheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                st.metric("Total Gasto", f"R$ {df['preco'].sum():.2f}")
                
                st.write("### Gastos por Categoria")
                st.bar_chart(df.groupby('categoria')['preco'].sum())
                
                st.write("### Itens Comprados")
                st.dataframe(df)
            else:
                st.info("Sua planilha ainda está vazia.")
