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
# --- 1. CONFIGURAÇÕES INICIAIS ---
# --- 1. CONFIGURAÇÕES INICIAIS ---
load_dotenv() # Tenta carregar localmente

# 1º tenta pegar do sistema (PC)
api_key = os.getenv("GOOGLE_API_KEY")

# 2º Se estiver vazio, tenta pegar dos Secrets (Nuvem)
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

if not api_key:
    st.error("Chave API não encontrada. Verifique os Secrets no painel do Streamlit.")
    st.stop()

genai.configure(api_key=api_key)

# Configuração da página do app
st.set_page_config(page_title="Minha Dispensa Cloud", page_icon="☁️", layout="centered")

# --- 2. FUNÇÃO PARA CONECTAR NO GOOGLE SHEETS (HÍBRIDA) ---
def conectar_gsheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        # TENTATIVA 1: Conexão via Streamlit Cloud (Segredos)
        # Se estiver rodando na nuvem, ele busca no st.secrets
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # TENTATIVA 2: Conexão Local (Arquivo físico)
        # Se não achar na nuvem, busca o arquivo na pasta
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("Estoque Dispensa").sheet1
        return sheet
        
    except Exception as e:
        st.error(f"Erro na conexão com Planilha: {e}")
        return None

# --- 3. FUNÇÃO DA IA (GEMINI) ---
def processar_cupom(image_file):
    # Modelo rápido e estável
    modelo_nome = 'gemini-flash-latest' 
    
    try:
        model = genai.GenerativeModel(modelo_nome)
        
        # Prepara a imagem
        bytes_data = image_file.getvalue()
        image_parts = [{"mime_type": image_file.type, "data": bytes_data}]

        # O comando detalhado para garantir o JSON
        prompt = f"""
        Você é um sistema de OCR para supermercado. Analise esta imagem.
        Extraia APENAS os itens comprados.
        Data de hoje: {datetime.now().strftime('%d/%m/%Y')} (Use esta se não achar data no cupom).
        
        Retorne estritamente um JSON neste formato de lista:
        [
            {{"produto": "Nome do Item", "quantidade": 1, "categoria": "Alimentação", "preco": 10.50, "data": "DD/MM/AAAA"}}
        ]
        
        Regras:
        1. Ignore troco, impostos e endereço.
        2. Categorias permitidas: Alimentação, Limpeza, Higiene, Bebidas, Outros.
        3. NÃO use crases (```json). Apenas o texto cru.
        """

        with st.spinner('A Inteligência Artificial está lendo o cupom...'):
            response = model.generate_content([prompt, image_parts[0]])
            return response.text

    except Exception as e:
        return f"Erro: {e}"

# --- 4. INTERFACE DO USUÁRIO ---
st.title("☁️ Minha Dispensa na Nuvem")
st.write("Escaneie o cupom e envie direto para o Google Sheets.")

# Inicializa a memória para os dados não sumirem ao clicar nos botões
if 'dados_tabela' not in st.session_state:
    st.session_state['dados_tabela'] = None

uploaded_file = st.file_uploader("Tire uma foto do cupom fiscal", type=["jpg", "jpeg", "png"])

# --- LÓGICA DE PROCESSAMENTO ---
if uploaded_file is not None:
    st.image(uploaded_file, caption="Imagem do Cupom", width=200)
    
    if st.button("🔍 Ler Cupom com IA"):
        resultado_texto = processar_cupom(uploaded_file)
        
        # Tenta limpar o texto caso a IA tenha colocado formatação extra
        resultado_limpo = resultado_texto.replace("```json", "").replace("```", "").strip()
        
        try:
            dados = json.loads(resultado_limpo)
            # Salva na memória
            st.session_state['dados_tabela'] = pd.DataFrame(dados)
        except json.JSONDecodeError:
            st.error("A IA leu o cupom mas não conseguiu estruturar os dados.")
            with st.expander("Ver o que a IA tentou responder (Debug)"):
                st.text(resultado_texto)

# --- ÁREA DE CONFIRMAÇÃO E ENVIO ---
if st.session_state['dados_tabela'] is not None:
    st.divider()
    st.success("✅ Leitura realizada! Confira os dados abaixo:")
    
    # Tabela editável (permite corrigir erros da IA antes de enviar)
    df_editado = st.data_editor(
        st.session_state['dados_tabela'], 
        num_rows="dynamic", 
        key="editor_google_sheets"
    )
    
    st.write("") # Espaço visual
    
    # Botão de Enviar para a Nuvem
    if st.button("☁️ Enviar para Google Sheets"):
        sheet = conectar_gsheets()
        
        if sheet:
            try:
                # Prepara os dados
                novas_linhas = df_editado.values.tolist()
                
                # Se a planilha estiver vazia, adiciona o cabeçalho
                if not sheet.get_all_values():
                    cabecalho = df_editado.columns.tolist()
                    sheet.append_row(cabecalho)
                
                # Adiciona cada produto como uma nova linha
                with st.spinner("Salvando na nuvem..."):
                    for linha in novas_linhas:
                        sheet.append_row(linha)
                
                st.balloons()
                st.success("Sucesso! Estoque atualizado na nuvem.")
                st.link_button("📊 Ver Meu Estoque Online", "https://docs.google.com/spreadsheets/d/1hfq1LDxiOblaT7Z0zMf0u8fhtYDoEjuLxrS8yNoTjV0/edit?usp=sharing")
                
                # Limpa a memória para o próximo cupom
                st.session_state['dados_tabela'] = None
                # st.rerun() # Opcional: Recarrega a página para limpar tudo
                
            except Exception as e:

                st.error(f"Erro ao gravar na planilha: {e}")


