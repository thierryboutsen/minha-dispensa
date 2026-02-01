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
    st.error("ERRO: Chave API não encontrada. Verifique os Secrets.")
    st.stop()

genai.configure(api_key=api_key)
st.set_page_config(page_title="Minha Dispensa Pro", page_icon="🛒", layout="wide")

# --- 2. CONEXÃO GOOGLE SHEETS ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds).open("Estoque Dispensa").sheet1
        return None
    except Exception as e:
        st.error(f"Erro ao conectar na planilha: {e}")
        return None

# --- 3. FUNÇÃO PROCESSAR COM IA (FOTO OU QR CODE) ---
def processar_com_gemini(image_buffer, modo="foto"):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    if modo == "foto":
        prompt = "Analise este cupom e extraia: produto, quantidade, categoria, preco. Retorne JSON PURO: [{'produto': 'X', 'quantidade': 1, 'categoria': 'Limpeza', 'preco': 5.50}]"
    else:
        prompt = "Extraia o link (URL) contido neste QR Code de Cupom Fiscal. Retorne apenas o link."

    image_parts = [{"mime_type": "image/jpeg", "data": image_buffer.getvalue()}]
    response = model.generate_content([prompt, image_parts[0]])
    return response.text

# --- 4. INTERFACE PRINCIPAL ---
st.title("🛒 Minha Dispensa Inteligente")

if 'dados_temp' not in st.session_state:
    st.session_state['dados_temp'] = None

tab_add, tab_relatorio = st.tabs(["➕ Adicionar Itens", "📊 Relatório de Gastos"])

with tab_add:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📸 Via Cupom")
        foto = st.camera_input("Tirar foto do cupom", key="camera_foto")
        if foto and st.button("✨ Processar Cupom"):
            res = processar_com_gemini(foto, "foto")
            clean = res.replace("```json", "").replace("```", "").strip()
            st.session_state['dados_temp'] = pd.DataFrame(json.loads(clean))

    with col2:
        st.subheader("🔍 Via QR Code")
        qr_foto = st.camera_input("Fotografar QR Code", key="camera_qr")
        if qr_foto and st.button("🔗 Ler Link SEFAZ"):
            link = processar_com_gemini(qr_foto, "qr")
            st.success("Link Extraído!")
            st.link_button("🌐 Abrir no site da SEFAZ", link.strip())

    # Tabela de Edição e Salvamento
    if st.session_state['dados_temp'] is not None:
        st.divider()
        st.write("### ✅ Confira e Edite os dados:")
        df_editado = st.data_editor(st.session_state['dados_temp'], num_rows="dynamic")
        
        if st.button("☁️ Confirmar e Salvar na Planilha"):
            sheet = conectar_gsheets()
            if sheet:
                data_hoje = datetime.now().strftime('%d/%m/%Y')
                for linha in df_editado.values.tolist():
                    linha.append(data_hoje)
                    sheet.append_row(linha)
                st.balloons()
                st.success("Dados salvos com sucesso!")
                st.session_state['dados_temp'] = None

with tab_relatorio:
    st.subheader("📈 Resumo Mensal")
    if st.button("🔄 Atualizar Relatório"):
        sheet = conectar_gsheets()
        if sheet:
            dados_planilha = sheet.get_all_records()
            if dados_planilha:
                df = pd.DataFrame(dados_planilha)
                
                # Métricas Rápidas
                total = df['preco'].sum()
                st.metric("Gasto Total Acumulado", f"R$ {total:.2f}")
                
                # Gráfico por Categoria
                st.write("### Gastos por Categoria")
                gastos_cat = df.groupby('categoria')['preco'].sum().sort_values(ascending=False)
                st.bar_chart(gastos_cat)
                
                # Tabela Detalhada com busca de fotos
                st.write("### Itens no Estoque")
                df['🖼️'] = df['produto'].apply(lambda x: f"https://www.google.com/search?q={x.replace(' ', '+')}&tbm=isch")
                st.dataframe(df, column_config={"🖼️": st.column_config.LinkColumn("Foto")})
            else:
                st.warning("Nenhum dado encontrado na planilha.")
