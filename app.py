import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import io
import plotly.express as px
from rapidfuzz import process, fuzz

# Configurações de Cores e Estilo
VERDE = "#458462"
AMBAR = "#FFB743"

st.set_page_config(page_title="Gestão Pelada & Churrasco", layout="wide")

# Funções de Carregamento de Dados
def load_data():
    if not os.path.exists("historico_caixa.csv"):
        df_caixa = pd.DataFrame(columns=["Data", "Descricao", "Categoria", "Tipo", "Valor", "Saldo_Acumulado"])
        df_caixa.to_csv("historico_caixa.csv", index=False)
    else:
        df_caixa = pd.read_csv("historico_caixa.csv")
        if "Tipo_Entrada_Saida" in df_caixa.columns:
            df_caixa = df_caixa.rename(columns={"Tipo_Entrada_Saida": "Tipo"})
        df_caixa["Data"] = pd.to_datetime(df_caixa["Data"])
    
    if not os.path.exists("historico_jogadores.csv"):
        df_jogadores = pd.DataFrame(columns=["Data_Evento", "Nome_Jogador", "Tipo_Participacao", "Valor_Pago", "Status"])
        df_jogadores.to_csv("historico_jogadores.csv", index=False)
    else:
        df_jogadores = pd.read_csv("historico_jogadores.csv")
        rename_map = {"Data_Pelada": "Data_Evento", "Status_Pagamento": "Status", "Tipo_Evento": "Tipo_Participacao"}
        df_jogadores = df_jogadores.rename(columns=rename_map)
        if "Tipo_Participacao" not in df_jogadores.columns:
            df_jogadores["Tipo_Participacao"] = "Pelada"
        df_jogadores["Data_Evento"] = pd.to_datetime(df_jogadores["Data_Evento"])
        
    if not os.path.exists("jogadores_base.csv"):
        # Se não existir, cria uma base vazia ou com os nomes que já conhecemos
        df_base = pd.DataFrame(columns=["Nome_Oficial"])
        df_base.to_csv("jogadores_base.csv", index=False)
    else:
        df_base = pd.read_csv("jogadores_base.csv")
        
    return df_caixa, df_jogadores, df_base

def save_data(df_caixa, df_jogadores, df_base):
    df_caixa.to_csv("historico_caixa.csv", index=False)
    df_jogadores.to_csv("historico_jogadores.csv", index=False)
    df_base.to_csv("jogadores_base.csv", index=False)

# Inteligência de Reconhecimento de Nomes
def match_player_name(input_name, base_names):
    if not base_names:
        return input_name
    # Tenta encontrar o melhor match acima de 70% de similaridade
    match = process.extractOne(input_name.upper(), base_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70:
        return match[0]
    return input_name.upper()

def process_whatsapp_list(text, base_names):
    lines = text.split('\n')
    players = []
    for line in lines:
        if line.strip():
            clean_line = re.sub(r'^\d+[\s\.\-\)]*', '', line).strip()
            has_check = "✅" in clean_line
            raw_name = clean_line.replace("✅", "").strip()
            if raw_name:
                official_name = match_player_name(raw_name, base_names)
                players.append({"Nome": official_name, "Confirmado": has_check, "Nome_Original": raw_name})
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
st.sidebar.title("⚽ Gestão Pelada Segunda")
menu = st.sidebar.radio("Navegação", ["Lançamento Semanal", "Dashboard & Frequência", "Configurações"])

df_caixa, df_jogadores, df_base = load_data()
base_names = df_base["Nome_Oficial"].tolist()

if menu == "Lançamento Semanal":
    st.header("🔄 Lançamento da Semana")
    
    data_evento = st.date_input("Data do Evento", datetime.now())
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Lista da Pelada")
        wa_pelada = st.text_area("Cole a lista da PELADA aqui...", height=150)
        players_pelada = process_whatsapp_list(wa_pelada, base_names) if wa_pelada else []
        if players_pelada:
            st.info(f"{len(players_pelada)} na pelada.")
            
        st.subheader("🍖 Lista do Churrasco")
        wa_churras = st.text_area("Cole a lista do CHURRASCO aqui...", height=150)
        players_churras = process_whatsapp_list(wa_churras, base_names) if wa_churras else []
        if players_churras:
            st.info(f"{len(players_churras)} no churrasco.")

    with col2:
        st.subheader("💰 Valores e Custos")
        v_pelada = st.number_input("Valor Individual Pelada (R$)", value=20.0)
        v_churras = st.number_input("Valor Individual Churrasco (R$)", value=5.0)
        
        st.divider()
        aluguel = st.number_input("Aluguel da Quadra (Saída)", value=270.0)
        custo_carne = st.number_input("Custos Churrasco (Saída)", value=0.0)
        
        st.divider()
        st.subheader("🔍 Auditoria (Extrato)")
        uploaded_file = st.file_uploader("Upload do CSV do Banco", type="csv")
        if uploaded_file:
            df_ext = process_csv_extract(uploaded_file.read())
            if not df_ext.empty:
                pix_counts = df_ext[df_ext['Histórico'].str.contains('PIX', na=False)]['Crédito (R$)'].value_counts().to_dict()
                st.write("PIX no extrato:")
                for val, count in pix_counts.items():
                    st.write(f"- R$ {val:.2f}: {count} vezes")

    if st.button("🚀 Consolidar Tudo", type="primary"):
        if not players_pelada and not players_churras:
            st.error("Insira pelo menos uma lista.")
        else:
            # Unificar listas e participações
            all_participants = {} # Nome -> {pelada: bool, churrasco: bool}
            
            for p in players_pelada:
                all_participants[p['Nome']] = {'pelada': p['Confirmado'], 'churrasco': False}
            
            for p in players_churras:
                if p['Nome'] in all_participants:
                    all_participants[p['Nome']]['churrasco'] = p['Confirmado']
                else:
                    all_participants[p['Nome']] = {'pelada': False, 'churrasco': p['Confirmado']}
            
            # Gerar registros de jogadores
            novos_regs = []
            total_arrecadado = 0
            for nome, participacao in all_participants.items():
                pago_pelada = participacao['pelada']
                pago_churras = participacao['churrasco']
                
                valor_total = (v_pelada if pago_pelada else 0) + (v_churras if pago_churras else 0)
                total_arrecadado += valor_total
                
                tipo = "Pelada + Churrasco" if (pago_pelada and pago_churras) else ("Pelada" if pago_pelada else "Churrasco")
                status = "Pago" if (pago_pelada or pago_churras) else "Devedor"
                
                novos_regs.append({
                    "Data_Evento": pd.to_datetime(data_evento),
                    "Nome_Jogador": nome,
                    "Tipo_Participacao": tipo,
                    "Valor_Pago": valor_total,
                    "Status": status
                })
            
            df_jogadores = pd.concat([df_jogadores, pd.DataFrame(novos_regs)], ignore_index=True)
            
            # Atualizar Caixa
            ultimo_saldo = float(df_caixa["Saldo_Acumulado"].iloc[-1]) if not df_caixa.empty else 1612.0
            dt_ev = pd.to_datetime(data_evento)
            
            lancamentos = [
                {"Data": dt_ev, "Descricao": "Arrecadação Total", "Categoria": "Entrada", "Tipo": "Entrada", "Valor": total_arrecadado, "Saldo_Acumulado": ultimo_saldo + total_arrecadado},
                {"Data": dt_ev, "Descricao": "Aluguel Quadra", "Categoria": "Fixo", "Tipo": "Saída", "Valor": aluguel, "Saldo_Acumulado": ultimo_saldo + total_arrecadado - aluguel}
            ]
            ultimo_saldo = lancamentos[-1]["Saldo_Acumulado"]
            
            if custo_carne > 0:
                lancamentos.append({"Data": dt_ev, "Descricao": "Custos Churrasco", "Categoria": "Churrasco", "Tipo": "Saída", "Valor": custo_carne, "Saldo_Acumulado": ultimo_saldo - custo_carne})
            
            df_caixa = pd.concat([df_caixa, pd.DataFrame(lancamentos)], ignore_index=True)
            save_data(df_caixa, df_jogadores, df_base)
            st.balloons()
            st.success("Dados salvos com sucesso!")

elif menu == "Dashboard & Frequência":
    st.header("📈 Dashboard de Assiduidade e Finanças")
    
    tab_fin, tab_freq = st.tabs(["Financeiro", "Frequência dos Jogadores"])
    
    with tab_fin:
        if not df_caixa.empty:
            st.subheader("Fluxo de Caixa")
            fig_caixa = px.line(df_caixa, x="Data", y="Saldo_Acumulado", title="Evolução do Saldo")
            st.plotly_chart(fig_caixa, use_container_width=True)
            
            st.subheader("Devedores Atuais")
            devedores = df_jogadores[df_jogadores["Status"] == "Devedor"]
            if not devedores.empty:
                st.table(devedores.groupby("Nome_Jogador").size().reset_index(name="Vezes Devedor"))
            else:
                st.success("Ninguém devendo!")

    with tab_freq:
        if not df_jogadores.empty:
            st.subheader("Ranking de Presença")
            # Conta participações por jogador
            freq = df_jogadores[df_jogadores["Status"] == "Pago"].groupby("Nome_Jogador").size().reset_index(name="Presenças")
            freq = freq.sort_values("Presenças", ascending=False)
            
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                fig_freq = px.bar(freq.head(15), x="Nome_Jogador", y="Presenças", color="Presenças", title="Top 15 Mais Presentes")
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col_f2:
                st.write("**Jogadores Sumidos (Últimos 30 dias)**")
                trinta_dias_atras = datetime.now() - timedelta(days=30)
                presentes_recentes = df_jogadores[df_jogadores["Data_Evento"] >= trinta_dias_atras]["Nome_Jogador"].unique()
                sumidos = [n for n in base_names if n not in presentes_recentes]
                if sumidos:
                    st.warning(f"{len(sumidos)} jogadores não aparecem há 1 mês.")
                    st.write(", ".join(sumidos[:10]) + ("..." if len(sumidos) > 10 else ""))
                else:
                    st.success("Todos os jogadores da base apareceram recentemente!")

elif menu == "Configurações":
    st.header("⚙️ Gestão de Jogadores e Dados")
    
    st.subheader("Base de Jogadores Oficiais")
    novo_nome = st.text_input("Adicionar novo jogador à base")
    if st.button("Adicionar"):
        if novo_nome and novo_nome.upper() not in base_names:
            nova_linha = pd.DataFrame([{"Nome_Oficial": novo_nome.upper()}])
            df_base = pd.concat([df_base, nova_linha], ignore_index=True)
            save_data(df_caixa, df_jogadores, df_base)
            st.success(f"{novo_nome} adicionado!")
            st.rerun()
            
    st.write("**Jogadores Cadastrados:**")
    st.write(", ".join(base_names))
    
    st.divider()
    st.subheader("Backup")
    st.download_button("Baixar Histórico de Jogadores (CSV)", df_jogadores.to_csv(index=False), "jogadores.csv")
    st.download_button("Baixar Histórico de Caixa (CSV)", df_caixa.to_csv(index=False), "caixa.csv")
