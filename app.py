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

st.set_page_config(page_title="Gestão Pelada Segunda", layout="wide")

# SALDO INICIAL DEFINIDO NO PROJETO
SALDO_INICIAL_MARCO_ZERO = 1612.00

# Funções de Carregamento de Dados
def load_data():
    if not os.path.exists("historico_caixa.csv"):
        # Se o arquivo não existe, cria com o saldo inicial
        df_caixa = pd.DataFrame([{
            "Data": pd.to_datetime("2024-01-01"),
            "Descricao": "Saldo Inicial (Marco Zero)",
            "Categoria": "Abertura",
            "Tipo": "Entrada",
            "Valor": SALDO_INICIAL_MARCO_ZERO,
            "Saldo_Acumulado": SALDO_INICIAL_MARCO_ZERO
        }])
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
        df_base = pd.DataFrame(columns=["Nome_Oficial"])
        df_base.to_csv("jogadores_base.csv", index=False)
    else:
        df_base = pd.read_csv("jogadores_base.csv")
        
    return df_caixa, df_jogadores, df_base

def save_data(df_caixa, df_jogadores, df_base):
    df_caixa.to_csv("historico_caixa.csv", index=False)
    df_jogadores.to_csv("historico_jogadores.csv", index=False)
    df_base.to_csv("jogadores_base.csv", index=False)

# Inteligência de Reconhecimento de Nomes e Listas
def match_player_name(input_name, base_names):
    if not base_names:
        return input_name
    clean_name = re.sub(r'\(.*?\)', '', input_name)
    clean_name = re.sub(r'[\d\-\.\⭐️\✅]', '', clean_name).strip()
    match = process.extractOne(clean_name.upper(), base_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70:
        return match[0]
    return clean_name.upper()

def extract_value_from_text(text):
    match = re.search(r'R\$\s?(\d+,\d{2})', text)
    if match:
        return float(match.group(1).replace(',', '.'))
    return None

def process_whatsapp_list(text, base_names):
    lines = text.split('\n')
    players = []
    ignorar_secao = False
    palavras_parada = ["LISTA DE ESPERA", "AUSENTES", "GK -"]
    for line in lines:
        upper_line = line.upper().strip()
        if any(p in upper_line for p in palavras_parada):
            ignorar_secao = True
            continue
        if ignorar_secao:
            continue
        if re.match(r'^\d+[\s\.\-\)]+', line.strip()) or (line.strip() and not any(x in upper_line for x in ["PIX", "CPF", "R$", "HORÁRIO", "ATENÇÃO", "QUADRA"])):
            has_check = "✅" in line
            raw_name = re.sub(r'^\d+[\s\.\-\)]*', '', line).strip()
            raw_name = raw_name.replace("✅", "").strip()
            raw_name = re.split(r'[\(\-\–]', raw_name)[0].strip()
            if raw_name and len(raw_name) > 2:
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
        wa_pelada = st.text_area("Cole a lista da PELADA aqui...", height=250)
        val_pelada_sugerido = extract_value_from_text(wa_pelada) or 20.0
        players_pelada = process_whatsapp_list(wa_pelada, base_names) if wa_pelada else []
        if players_pelada:
            st.info(f"{len(players_pelada)} jogadores identificados.")
            with st.expander("Ver nomes identificados"):
                for p in players_pelada:
                    status = "✅" if p['Confirmado'] else "❌"
                    st.write(f"{status} {p['Nome']} (Original: {p['Nome_Original']})")
        st.subheader("🍖 Lista do Churrasco")
        wa_churras = st.text_area("Cole a lista do CHURRASCO aqui...", height=200)
        val_churras_sugerido = extract_value_from_text(wa_churras) or 25.0
        players_churras = process_whatsapp_list(wa_churras, base_names) if wa_churras else []
        if players_churras:
            st.info(f"{len(players_churras)} no churrasco.")
    with col2:
        st.subheader("💰 Valores e Custos")
        v_pelada = st.number_input("Valor Individual Pelada (R$)", value=val_pelada_sugerido)
        v_churras = st.number_input("Valor Individual Churrasco (R$)", value=val_churras_sugerido)
        st.divider()
        aluguel = st.number_input("Aluguel da Quadra (Saída)", value=270.0)
        custo_carne = st.number_input("Custos Churrasco (Saída)", value=0.0)
        st.divider()
        st.subheader("🔍 Auditoria (Extrato)")
        uploaded_file = st.file_uploader("Upload do CSV do Banco", type="csv")
        if uploaded_file:
            try:
                df_ext = process_csv_extract(uploaded_file.read())
                if not df_ext.empty:
                    pix_counts = df_ext[df_ext['Histórico'].str.contains('PIX', na=False)]['Crédito (R$)'].value_counts().to_dict()
                    st.write("PIX no extrato:")
                    for val, count in pix_counts.items():
                        st.write(f"- R$ {val:.2f}: {count} vezes")
            except Exception as e:
                st.error(f"Erro ao ler extrato: {e}")

    if st.button("🚀 Consolidar Tudo", type="primary"):
        if not players_pelada and not players_churras:
            st.error("Insira pelo menos uma lista.")
        else:
            all_participants = {} 
            for p in players_pelada:
                all_participants[p['Nome']] = {'pelada': p['Confirmado'], 'churrasco': False}
            for p in players_churras:
                if p['Nome'] in all_participants:
                    all_participants[p['Nome']]['churrasco'] = p['Confirmado']
                else:
                    all_participants[p['Nome']] = {'pelada': False, 'churrasco': p['Confirmado']}
            novos_regs = []
            total_arrecadado = 0
            for nome, participacao in all_participants.items():
                pago_pelada = participacao['pelada']
                pago_churras = participacao['churrasco']
                valor_real_pago = (v_pelada if pago_pelada else 0) + (v_churras if pago_churras else 0)
                total_arrecadado += valor_real_pago
                tipo = "Pelada + Churrasco" if (pago_pelada and pago_churras) else ("Pelada" if pago_pelada else "Churrasco")
                status = "Pago" if valor_real_pago >= 20 else "Devedor"
                novos_regs.append({"Data_Evento": pd.to_datetime(data_evento), "Nome_Jogador": nome, "Tipo_Participacao": tipo, "Valor_Pago": valor_real_pago, "Status": status})
            df_jogadores = pd.concat([df_jogadores, pd.DataFrame(novos_regs)], ignore_index=True)
            ultimo_saldo = float(df_caixa["Saldo_Acumulado"].iloc[-1]) if not df_caixa.empty else SALDO_INICIAL_MARCO_ZERO
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
            saldo_atual = df_caixa["Saldo_Acumulado"].iloc[-1]
            st.metric("Saldo Atual em Conta", f"R$ {saldo_atual:,.2f}")
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
    st.subheader("Resetar Saldo Inicial")
    novo_saldo_init = st.number_input("Definir novo Saldo Inicial (Cuidado!)", value=SALDO_INICIAL_MARCO_ZERO)
    if st.button("Resetar Saldo para este valor"):
        if st.checkbox("Confirmo que quero resetar o saldo"):
            df_caixa = pd.DataFrame([{
                "Data": pd.to_datetime("2024-01-01"),
                "Descricao": "Saldo Inicial (Marco Zero)",
                "Categoria": "Abertura",
                "Tipo": "Entrada",
                "Valor": novo_saldo_init,
                "Saldo_Acumulado": novo_saldo_init
            }])
            save_data(df_caixa, df_jogadores, df_base)
            st.success("Saldo resetado!")
            st.rerun()
    st.divider()
    st.subheader("Backup")
    st.download_button("Baixar Histórico de Jogadores (CSV)", df_jogadores.to_csv(index=False), "jogadores.csv")
    st.download_button("Baixar Histórico de Caixa (CSV)", df_caixa.to_csv(index=False), "caixa.csv")
