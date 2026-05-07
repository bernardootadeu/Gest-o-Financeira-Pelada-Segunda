import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import io
import plotly.express as px

# Configurações de Cores e Estilo
VERDE = "#458462"
AMBAR = "#FFB743"

st.set_page_config(page_title="Gestão Pelada & Churrasco", layout="wide")

# Funções de Carregamento de Dados com Migração Automática
def load_data():
    # 1. Carregar Histórico de Caixa
    if not os.path.exists("historico_caixa.csv"):
        df_caixa = pd.DataFrame(columns=["Data", "Descricao", "Categoria", "Tipo", "Valor", "Saldo_Acumulado"])
        df_caixa.to_csv("historico_caixa.csv", index=False)
    else:
        df_caixa = pd.read_csv("historico_caixa.csv")
        # Padronizar nomes de colunas antigos se necessário
        if "Tipo_Entrada_Saida" in df_caixa.columns:
            df_caixa = df_caixa.rename(columns={"Tipo_Entrada_Saida": "Tipo"})
        df_caixa["Data"] = pd.to_datetime(df_caixa["Data"])
    
    # 2. Carregar Histórico de Jogadores
    if not os.path.exists("historico_jogadores.csv"):
        df_jogadores = pd.DataFrame(columns=["Data_Evento", "Nome_Jogador", "Tipo_Evento", "Valor_Pago", "Status"])
        df_jogadores.to_csv("historico_jogadores.csv", index=False)
    else:
        df_jogadores = pd.read_csv("historico_jogadores.csv")
        
        # Migração de colunas da versão 1 para a versão 2
        rename_map = {
            "Data_Pelada": "Data_Evento",
            "Status_Pagamento": "Status"
        }
        df_jogadores = df_jogadores.rename(columns=rename_map)
        
        # Adicionar colunas faltantes se for arquivo antigo
        if "Tipo_Evento" not in df_jogadores.columns:
            df_jogadores["Tipo_Evento"] = "Apenas Pelada"
        if "Valor_Pago" not in df_jogadores.columns:
            # Assume R$ 20 para registros antigos que estão como "Pago"
            df_jogadores["Valor_Pago"] = df_jogadores["Status"].apply(lambda x: 20.0 if x == "Pago" else 0.0)
            
        df_jogadores["Data_Evento"] = pd.to_datetime(df_jogadores["Data_Evento"])
        
    return df_caixa, df_jogadores

def save_data(df_caixa, df_jogadores):
    df_caixa.to_csv("historico_caixa.csv", index=False)
    df_jogadores.to_csv("historico_jogadores.csv", index=False)

# Lógica de Processamento de Texto e CSV
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
            if i > 5: break
    data_content = "\n".join(lines[start_line:])
    df = pd.read_csv(io.StringIO(data_content), sep=';', on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]
    
    def parse_br_float(val):
        if pd.isna(val) or str(val).strip() == "": return 0.0
        return float(str(val).replace('.', '').replace(',', '.'))

    if 'Crédito (R$)' in df.columns:
        df['Crédito (R$)'] = df['Crédito (R$)'].apply(parse_br_float)
        return df
    return pd.DataFrame()

# Interface
st.sidebar.title("⚽ Gestão da Pelada")
menu = st.sidebar.radio("Navegação", ["Lançamento Semanal", "Dashboard & Histórico", "Configurações"])

df_caixa, df_jogadores = load_data()

if menu == "Lançamento Semanal":
    st.header("🔄 Conciliação e Lançamento")
    
    data_evento = st.date_input("Data do Evento", datetime.now())
    tipo_evento = st.selectbox("Tipo de Evento", ["Apenas Pelada", "Pelada + Churrasco"])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Entradas (WhatsApp)")
        wa_text = st.text_area("Cole a lista do WhatsApp aqui...", height=200)
        players = process_whatsapp_list(wa_text) if wa_text else []
        
        if players:
            st.info(f"{len(players)} jogadores identificados.")
            valor_pelada = st.number_input("Valor da Pelada (R$)", value=20.0)
            valor_churras = 0.0
            if tipo_evento == "Pelada + Churrasco":
                valor_churras = st.number_input("Valor Adicional Churrasco (R$)", value=5.0)
            
            total_por_pessoa = valor_pelada + valor_churras
            st.write(f"**Total por pessoa confirmado: R$ {total_por_pessoa:.2f}**")

    with col2:
        st.subheader("2. Auditoria (Opcional)")
        uploaded_file = st.file_uploader("Upload do Extrato para conferência", type="csv")
        pix_counts = {}
        if uploaded_file:
            try:
                df_extrato = process_csv_extract(uploaded_file.read())
                if not df_extrato.empty:
                    pix_counts = df_extrato[df_extrato['Histórico'].str.contains('PIX', na=False)]['Crédito (R$)'].value_counts().to_dict()
                    st.write("PIX encontrados no extrato:")
                    for val, count in pix_counts.items():
                        st.write(f"- R$ {val:.2f}: {count} vezes")
            except Exception as e:
                st.error(f"Erro ao ler extrato: {e}")

    st.divider()
    
    st.subheader("3. Custos e Saídas")
    c1, c2, c3 = st.columns(3)
    aluguel = c1.number_input("Aluguel da Quadra (Fixo)", value=270.0)
    custo_churras = 0.0
    desc_churras = ""
    if tipo_evento == "Pelada + Churrasco":
        custo_churras = c2.number_input("Custos Churrasco (Carne, Carvão, etc)", value=0.0)
        desc_churras = c3.text_input("Descrição dos custos churrasco", "Carnes e Bebidas")
    
    if st.button("🚀 Consolidar e Salvar Semana", type="primary"):
        if not players:
            st.error("Por favor, cole a lista do WhatsApp primeiro.")
        else:
            novos_jogadores = []
            total_arrecadado_pelada = 0
            total_arrecadado_churras = 0
            
            for p in players:
                pago = p['Confirmado']
                valor_pago = total_por_pessoa if pago else 0.0
                status = "Pago" if pago else "Devedor"
                
                if pago:
                    total_arrecadado_pelada += valor_pelada
                    total_arrecadado_churras += valor_churras
                
                novos_jogadores.append({
                    "Data_Evento": data_evento,
                    "Nome_Jogador": p['Nome'],
                    "Tipo_Evento": tipo_evento,
                    "Valor_Pago": valor_pago,
                    "Status": status
                })
            
            df_jogadores = pd.concat([df_jogadores, pd.DataFrame(novos_jogadores)], ignore_index=True)
            
            ultimo_saldo = float(df_caixa["Saldo_Acumulado"].iloc[-1]) if not df_caixa.empty else 1612.0
            novos_lancamentos = []
            
            # Converter data_evento para datetime64[ns] para compatibilidade com o CSV
            dt_evento = pd.to_datetime(data_evento)
            
            ultimo_saldo += total_arrecadado_pelada
            novos_lancamentos.append({"Data": dt_evento, "Descricao": f"Arrecadação Pelada", "Categoria": "Pelada", "Tipo": "Entrada", "Valor": total_arrecadado_pelada, "Saldo_Acumulado": ultimo_saldo})
            
            if total_arrecadado_churras > 0:
                ultimo_saldo += total_arrecadado_churras
                novos_lancamentos.append({"Data": dt_evento, "Descricao": f"Arrecadação Churrasco", "Categoria": "Churrasco", "Tipo": "Entrada", "Valor": total_arrecadado_churras, "Saldo_Acumulado": ultimo_saldo})
            
            ultimo_saldo -= aluguel
            novos_lancamentos.append({"Data": dt_evento, "Descricao": "Aluguel Quadra", "Categoria": "Fixo", "Tipo": "Saída", "Valor": aluguel, "Saldo_Acumulado": ultimo_saldo})
            
            if custo_churras > 0:
                ultimo_saldo -= custo_churras
                novos_lancamentos.append({"Data": dt_evento, "Descricao": desc_churras, "Categoria": "Churrasco", "Tipo": "Saída", "Valor": custo_churras, "Saldo_Acumulado": ultimo_saldo})
            
            df_caixa = pd.concat([df_caixa, pd.DataFrame(novos_lancamentos)], ignore_index=True)
            
            save_data(df_caixa, df_jogadores)
            st.balloons()
            st.success("Semana consolidada com sucesso!")

elif menu == "Dashboard & Histórico":
    st.header("📊 Monitoramento Financeiro")
    
    if not df_caixa.empty:
        periodo = st.radio("Visão Temporal", ["Semanal", "Anual"], horizontal=True)
        
        if periodo == "Semanal":
            ultima_data = df_caixa["Data"].max()
            df_filtrado = df_caixa[df_caixa["Data"] == ultima_data]
            st.subheader(f"Resumo da Semana: {ultima_data.strftime('%d/%m/%Y')}")
        else:
            ano_atual = datetime.now().year
            df_filtrado = df_caixa[df_caixa["Data"].dt.year == ano_atual]
            st.subheader(f"Resumo do Ano: {ano_atual}")

        entradas = df_filtrado[df_filtrado["Tipo"] == "Entrada"]["Valor"].sum()
        saidas = df_filtrado[df_filtrado["Tipo"] == "Saída"]["Valor"].sum()
        saldo_periodo = entradas - saidas
        saldo_total = df_caixa["Saldo_Acumulado"].iloc[-1]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Entradas no Período", f"R$ {entradas:,.2f}")
        m2.metric("Saídas no Período", f"R$ {saidas:,.2f}")
        m3.metric("Saldo do Período", f"R$ {saldo_periodo:,.2f}")
        m4.metric("Saldo Total em Conta", f"R$ {saldo_total:,.2f}", delta=f"{saldo_periodo:,.2f}")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Evolução do Saldo**")
            fig_saldo = px.line(df_caixa, x="Data", y="Saldo_Acumulado", title="Fluxo de Caixa Acumulado")
            st.plotly_chart(fig_saldo, use_container_width=True)
        
        with col_g2:
            st.write("**Distribuição de Gastos**")
            df_gastos = df_caixa[df_caixa["Tipo"] == "Saída"].groupby("Categoria")["Valor"].sum().reset_index()
            if not df_gastos.empty:
                fig_pizza = px.pie(df_gastos, values='Valor', names='Categoria', hole=.3)
                st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.write("Sem saídas registradas no período.")

        st.divider()
        st.subheader("⚠️ Controle de Inadimplência")
        devedores = df_jogadores[df_jogadores["Status"] == "Devedor"]
        if not devedores.empty:
            resumo_dev = devedores.groupby("Nome_Jogador").agg(
                Vezes_Devedor=('Status', 'count')
            ).reset_index()
            resumo_dev["Estimativa_Divida"] = resumo_dev["Vezes_Devedor"] * 20
            st.dataframe(resumo_dev.sort_values("Vezes_Devedor", ascending=False), use_container_width=True)
        else:
            st.success("Ninguém devendo! Todos os pagamentos em dia.")

        st.divider()
        st.subheader("📜 Histórico de Movimentações")
        st.dataframe(df_caixa.sort_values("Data", ascending=False), use_container_width=True)
    else:
        st.info("Aguardando dados para exibir o dashboard.")

elif menu == "Configurações":
    st.header("⚙️ Configurações do Sistema")
    st.write("Aqui você pode resetar os dados ou exportar os backups.")
    
    if st.button("Limpar Histórico (Cuidado!)"):
        if st.checkbox("Confirmo que quero apagar todos os dados"):
            if os.path.exists("historico_caixa.csv"): os.remove("historico_caixa.csv")
            if os.path.exists("historico_jogadores.csv"): os.remove("historico_jogadores.csv")
            st.warning("Dados apagados. Recarregue a página.")
    
    if not df_caixa.empty:
        st.download_button("Baixar Backup Caixa (CSV)", df_caixa.to_csv(index=False), "caixa.csv")
    if not df_jogadores.empty:
        st.download_button("Baixar Backup Jogadores (CSV)", df_jogadores.to_csv(index=False), "jogadores.csv")
