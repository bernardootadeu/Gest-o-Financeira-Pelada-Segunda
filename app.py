import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os
import io

# Configurações de Cores e Estilo
VERDE = "#458462"
AMBAR = "#FFB743"

st.set_page_config(page_title="Gestão Financeira Pelada", layout="wide")

# Funções de Carregamento de Dados
def load_data():
    if not os.path.exists("historico_caixa.csv"):
        df_caixa = pd.DataFrame(columns=["Data", "Descricao", "Categoria", "Tipo_Entrada_Saida", "Valor", "Saldo_Acumulado"])
        df_caixa.to_csv("historico_caixa.csv", index=False)
    else:
        df_caixa = pd.read_csv("historico_caixa.csv")
    
    if not os.path.exists("historico_jogadores.csv"):
        df_jogadores = pd.DataFrame(columns=["Data_Pelada", "Nome_Jogador", "Status_Pagamento"])
        df_jogadores.to_csv("historico_jogadores.csv", index=False)
    else:
        df_jogadores = pd.read_csv("historico_jogadores.csv")
        
    return df_caixa, df_jogadores

def save_data(df_caixa, df_jogadores):
    df_caixa.to_csv("historico_caixa.csv", index=False)
    df_jogadores.to_csv("historico_jogadores.csv", index=False)

# Lógica de Processamento
def process_whatsapp_list(text):
    lines = text.split('\n')
    players = []
    for line in lines:
        if line.strip():
            clean_line = re.sub(r'^\d+[\s\.\-\)]*', '', line).strip()
            has_check = "✅" in clean_line
            name = clean_line.replace("✅", "").strip()
            if name:
                players.append({"Nome": name, "Confirmado": has_check})
    return players

def process_csv_extract(file_content):
    if isinstance(file_content, bytes):
        content = file_content.decode('utf-8', errors='ignore')
    else:
        content = file_content.read().decode('utf-8', errors='ignore')
        
    lines = content.splitlines()
    
    start_line = 0
    for i, line in enumerate(lines):
        if "Data;Histórico;Docto.;Crédito (R$);Débito (R$)" in line:
            start_line = i
            if i > 5: 
                break
                
    data_content = "\n".join(lines[start_line:])
    # Lendo com separador ';' e tratando linhas problemáticas (totais no final)
    df = pd.read_csv(io.StringIO(data_content), sep=';', on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]
    
    if 'Histórico' in df.columns and 'Crédito (R$)' in df.columns:
        # Tratamento robusto para valores numéricos no formato brasileiro (ex: 1.500,00 ou 20,00)
        def parse_br_float(val):
            if pd.isna(val) or str(val).strip() == "": return 0.0
            s = str(val).replace('.', '').replace(',', '.')
            try:
                return float(s)
            except:
                return 0.0

        df['Crédito (R$)'] = df['Crédito (R$)'].apply(parse_br_float)
        
        pix_payments = df[
            (df['Histórico'].str.contains('PIX', case=False, na=False)) & 
            (df['Crédito (R$)'] == 20.00)
        ]
        return len(pix_payments)
    return 0

# Interface
st.title("⚽ Gestão Financeira da Pelada")

tab1, tab2 = st.tabs(["Conciliador Semanal", "Dashboard & Inadimplência"])

df_caixa, df_jogadores = load_data()

with tab1:
    st.header("🔄 Conciliação Semanal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Extrato Bancário")
        uploaded_file = st.file_uploader("Upload do CSV do Banco", type="csv")
        num_pix = 0
        if uploaded_file:
            try:
                content = uploaded_file.read()
                num_pix = process_csv_extract(content)
                st.success(f"Encontrados {num_pix} pagamentos de R$ 20,00 via PIX.", icon="✅")
            except Exception as e:
                st.error(f"Erro ao processar CSV: {e}")

    with col2:
        st.subheader("2. Lista do WhatsApp")
        whatsapp_text = st.text_area("Cole a lista aqui...", height=150)
        players_list = []
        if whatsapp_text:
            players_list = process_whatsapp_list(whatsapp_text)
            num_confirmados = sum(1 for p in players_list if p['Confirmado'])
            st.info(f"{len(players_list)} jogadores identificados. {num_confirmados} com check ✅.")

    st.divider()
    
    if players_list:
        st.subheader("3. Comparação e Consolidação")
        num_confirmados = sum(1 for p in players_list if p['Confirmado'])
        divergencia = num_confirmados - num_pix
        
        if divergencia == 0:
            st.success("Tudo certo! O número de PIX bate com os checks da lista.", icon="✅")
        elif divergencia > 0:
            st.warning(f"Atenção: Existem {divergencia} checks a mais na lista do que PIX no extrato.", icon="⚠️")
        else:
            st.info(f"Existem {abs(divergencia)} PIX a mais no extrato do que checks na lista.")
            
        data_pelada = st.date_input("Data da Pelada", datetime.now())
        
        if st.button("Consolidar Semana", type="primary"):
            novos_registros_jogadores = []
            total_arrecadado = 0
            for p in players_list:
                status = "Pago" if p['Confirmado'] else "Devedor"
                if p['Confirmado']: total_arrecadado += 20
                novos_registros_jogadores.append({
                    "Data_Pelada": data_pelada,
                    "Nome_Jogador": p['Nome'],
                    "Status_Pagamento": status
                })
            
            df_jogadores = pd.concat([df_jogadores, pd.DataFrame(novos_registros_jogadores)], ignore_index=True)
            
            ultimo_saldo = float(df_caixa["Saldo_Acumulado"].iloc[-1]) if not df_caixa.empty else 1612.0
            
            novo_saldo = ultimo_saldo + total_arrecadado
            entrada_row = {
                "Data": data_pelada,
                "Descricao": f"Arrecadação Pelada {data_pelada}",
                "Categoria": "Pelada",
                "Tipo_Entrada_Saida": "Entrada",
                "Valor": total_arrecadado,
                "Saldo_Acumulado": novo_saldo
            }
            
            novo_saldo -= 270
            saida_row = {
                "Data": data_pelada,
                "Descricao": "Aluguel da Quadra",
                "Categoria": "Custo Fixo",
                "Tipo_Entrada_Saida": "Saída",
                "Valor": 270,
                "Saldo_Acumulado": novo_saldo
            }
            
            df_caixa = pd.concat([df_caixa, pd.DataFrame([entrada_row, saida_row])], ignore_index=True)
            
            save_data(df_caixa, df_jogadores)
            st.balloons()
            st.success("Dados consolidados com sucesso!")

with tab2:
    st.header("📊 Dashboard Anual")
    
    if not df_caixa.empty:
        df_caixa["Valor"] = pd.to_numeric(df_caixa["Valor"])
        df_caixa["Saldo_Acumulado"] = pd.to_numeric(df_caixa["Saldo_Acumulado"])
        
        saldo_atual = df_caixa["Saldo_Acumulado"].iloc[-1]
        total_arrecadado_ano = df_caixa[df_caixa["Tipo_Entrada_Saida"] == "Entrada"]["Valor"].sum()
        
        devedores_df = df_jogadores[df_jogadores["Status_Pagamento"] == "Devedor"]
        divida_ativa = len(devedores_df) * 20
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Saldo Atual", f"R$ {saldo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        m2.metric("Total Arrecadado (Ano)", f"R$ {total_arrecadado_ano:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        m3.metric("Dívida Ativa", f"R$ {divida_ativa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta_color="inverse")
        
        st.subheader("Evolução do Saldo")
        st.line_chart(df_caixa.set_index("Data")["Saldo_Acumulado"])
        
        st.subheader("📋 Tabela de Devedores")
        if not devedores_df.empty:
            resumo_devedores = devedores_df.groupby("Nome_Jogador").size().reset_index(name="Qtd_Dividas")
            resumo_devedores["Total_Devido"] = resumo_devedores["Qtd_Dividas"] * 20
            st.table(resumo_devedores.sort_values("Total_Devido", ascending=False))
        else:
            st.write("Nenhum devedor encontrado. Ótima notícia!")
    else:
        st.info("Aguardando dados para exibir o dashboard.")
