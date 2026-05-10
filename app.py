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
        df_caixa = pd.DataFrame([{
            "ID": 0,
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
        df_caixa["Data"] = pd.to_datetime(df_caixa["Data"])
        if "ID" not in df_caixa.columns:
            df_caixa.insert(0, "ID", range(len(df_caixa)))
    
    if not os.path.exists("historico_jogadores.csv"):
        df_jogadores = pd.DataFrame(columns=["Data_Evento", "Nome_Jogador", "Tipo_Participacao", "Valor_Pago", "Status"])
        df_jogadores.to_csv("historico_jogadores.csv", index=False)
    else:
        df_jogadores = pd.read_csv("historico_jogadores.csv")
        df_jogadores["Data_Evento"] = pd.to_datetime(df_jogadores["Data_Evento"])
        
    if not os.path.exists("jogadores_base.csv"):
        df_base = pd.DataFrame(columns=["Nome_Oficial"])
        df_base.to_csv("jogadores_base.csv", index=False)
    else:
        df_base = pd.read_csv("jogadores_base.csv")
        
    return df_caixa, df_jogadores, df_base

def save_data(df_caixa, df_jogadores, df_base):
    # Recalcular saldo acumulado antes de salvar para garantir consistência
    df_caixa = df_caixa.sort_values(["Data", "ID"]).reset_index(drop=True)
    saldo = 0
    saldos_acumulados = []
    for _, row in df_caixa.iterrows():
        if row["Tipo"] == "Entrada":
            saldo += row["Valor"]
        else:
            saldo -= row["Valor"]
        saldos_acumulados.append(saldo)
    df_caixa["Saldo_Acumulado"] = saldos_acumulados
    
    df_caixa.to_csv("historico_caixa.csv", index=False)
    df_jogadores.to_csv("historico_jogadores.csv", index=False)
    df_base.to_csv("jogadores_base.csv", index=False)
    return df_caixa

# Inteligência de Reconhecimento de Nomes e Listas
def match_player_name(input_name, base_names):
    if not base_names: return input_name
    clean_name = re.sub(r'\(.*?\)', '', input_name)
    clean_name = re.sub(r'[\d\-\.\⭐️\✅]', '', clean_name).strip()
    match = process.extractOne(clean_name.upper(), base_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 70: return match[0]
    return clean_name.upper()

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
        if ignorar_secao: continue
        if re.match(r'^\d+[\s\.\-\)]+', line.strip()) or (line.strip() and not any(x in upper_line for x in ["PIX", "CPF", "R$", "HORÁRIO", "ATENÇÃO", "QUADRA"])):
            has_check = "✅" in line
            raw_name = re.sub(r'^\d+[\s\.\-\)]*', '', line).strip()
            raw_name = raw_name.replace("✅", "").strip()
            raw_name = re.split(r'[\(\-\–]', raw_name)[0].strip()
            if raw_name and len(raw_name) > 2:
                official_name = match_player_name(raw_name, base_names)
                players.append({"Nome": official_name, "Confirmado": has_check, "Nome_Original": raw_name})
    return players

# Interface
st.sidebar.title("⚽ Gestão Pelada Segunda")
menu = st.sidebar.radio("Navegação", ["Lançamentos", "Histórico & Ajustes", "Dashboard & Frequência", "Configurações"])

df_caixa, df_jogadores, df_base = load_data()
base_names = df_base["Nome_Oficial"].tolist()

if menu == "Lançamentos":
    st.header("📝 Novos Lançamentos")
    
    tipo_lanc = st.selectbox("O que deseja lançar?", ["Processar Listas (Semanal)", "Lançamento Avulso (Manual)"])
    
    if tipo_lanc == "Processar Listas (Semanal)":
        data_evento = st.date_input("Data do Evento", datetime.now())
        col1, col2 = st.columns(2)
        with col1:
            wa_pelada = st.text_area("Lista da PELADA", height=150)
            wa_churras = st.text_area("Lista do CHURRASCO", height=150)
        with col2:
            v_pelada = st.number_input("Valor Pelada", value=20.0)
            v_churras = st.number_input("Valor Churrasco", value=25.0)
            aluguel = st.number_input("Aluguel Quadra", value=270.0)
            custo_carne = st.number_input("Custos Churrasco", value=0.0)
            
        if st.button("Analisar Listas"):
            players_p = process_whatsapp_list(wa_pelada, base_names)
            players_c = process_whatsapp_list(wa_churras, base_names)
            
            all_p = {}
            for p in players_p: all_p[p['Nome']] = {'p': p['Confirmado'], 'c': False}
            for p in players_c:
                if p['Nome'] in all_p: all_p[p['Nome']]['c'] = p['Confirmado']
                else: all_p[p['Nome']] = {'p': False, 'c': p['Confirmado']}
            
            # Criar tabela de rascunho
            rascunho = []
            total_arrec = 0
            for nome, part in all_p.items():
                valor = (v_pelada if part['p'] else 0) + (v_churras if part['c'] else 0)
                total_arrec += valor
                rascunho.append({"Nome": nome, "Pago Pelada": part['p'], "Pago Churras": part['c'], "Total R$": valor})
            
            st.subheader("Resumo para Conferência")
            st.table(rascunho)
            st.write(f"**Total Arrecadado: R$ {total_arrec:.2f}**")
            
            if st.button("Confirmar e Salvar no Caixa"):
                # Salvar Jogadores
                novos_regs = []
                for r in rascunho:
                    novos_regs.append({"Data_Evento": pd.to_datetime(data_evento), "Nome_Jogador": r['Nome'], "Tipo_Participacao": "Evento", "Valor_Pago": r['Total R$'], "Status": "Pago" if r['Total R$'] > 0 else "Devedor"})
                df_jogadores = pd.concat([df_jogadores, pd.DataFrame(novos_regs)], ignore_index=True)
                
                # Salvar Caixa
                new_id = df_caixa["ID"].max() + 1
                lancamentos = [
                    {"ID": new_id, "Data": pd.to_datetime(data_evento), "Descricao": "Arrecadação Lista", "Categoria": "Pelada", "Tipo": "Entrada", "Valor": total_arrec},
                    {"ID": new_id+1, "Data": pd.to_datetime(data_evento), "Descricao": "Aluguel Quadra", "Categoria": "Fixo", "Tipo": "Saída", "Valor": aluguel}
                ]
                if custo_carne > 0:
                    lancamentos.append({"ID": new_id+2, "Data": pd.to_datetime(data_evento), "Descricao": "Custos Churrasco", "Categoria": "Churrasco", "Tipo": "Saída", "Valor": custo_carne})
                
                df_caixa = pd.concat([df_caixa, pd.DataFrame(lancamentos)], ignore_index=True)
                df_caixa = save_data(df_caixa, df_jogadores, df_base)
                st.success("Lançado com sucesso!")
                st.balloons()

    else:
        st.subheader("Lançamento Manual")
        with st.form("form_manual"):
            d_man = st.date_input("Data", datetime.now())
            desc_man = st.text_input("Descrição (ex: Compra de Bolas, Pagamento Atrasado João)")
            cat_man = st.selectbox("Categoria", ["Pelada", "Churrasco", "Fixo", "Equipamento", "Outros"])
            tipo_man = st.radio("Tipo", ["Entrada", "Saída"])
            val_man = st.number_input("Valor R$", min_value=0.0)
            if st.form_submit_button("Salvar Lançamento"):
                new_id = df_caixa["ID"].max() + 1
                novo_item = {"ID": new_id, "Data": pd.to_datetime(d_man), "Descricao": desc_man, "Categoria": cat_man, "Tipo": tipo_man, "Valor": val_man}
                df_caixa = pd.concat([df_caixa, pd.DataFrame([novo_item])], ignore_index=True)
                df_caixa = save_data(df_caixa, df_jogadores, df_base)
                st.success("Lançado com sucesso!")

elif menu == "Histórico & Ajustes":
    st.header("📜 Histórico de Caixa")
    st.write("Aqui você pode visualizar, editar e excluir lançamentos.")
    
    # Exibir tabela com opção de exclusão
    df_display = df_caixa.sort_values(["Data", "ID"], ascending=False)
    st.dataframe(df_display, use_container_width=True)
    
    st.subheader("🗑️ Excluir Lançamento")
    id_excluir = st.number_input("Digite o ID do lançamento para excluir", min_value=0, step=1)
    if st.button("Excluir"):
        if id_excluir == 0:
            st.error("Não é possível excluir o saldo inicial.")
        else:
            df_caixa = df_caixa[df_caixa["ID"] != id_excluir]
            df_caixa = save_data(df_caixa, df_jogadores, df_base)
            st.success(f"Lançamento {id_excluir} excluído. Saldo recalculado.")
            st.rerun()

elif menu == "Dashboard & Frequência":
    st.header("📈 Dashboard")
    if not df_caixa.empty:
        saldo_atual = df_caixa["Saldo_Acumulado"].iloc[-1]
        st.metric("Saldo Atual em Conta", f"R$ {saldo_atual:,.2f}")
        fig = px.line(df_caixa, x="Data", y="Saldo_Acumulado", title="Evolução do Caixa")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Frequência")
        if not df_jogadores.empty:
            freq = df_jogadores[df_jogadores["Status"] == "Pago"].groupby("Nome_Jogador").size().reset_index(name="Presenças")
            st.bar_chart(freq.set_index("Nome_Jogador"))

elif menu == "Configurações":
    st.header("⚙️ Configurações")
    st.subheader("Base de Jogadores")
    novo_nome = st.text_input("Novo Jogador")
    if st.button("Adicionar"):
        if novo_nome:
            df_base = pd.concat([df_base, pd.DataFrame([{"Nome_Oficial": novo_nome.upper()}])], ignore_index=True)
            save_data(df_caixa, df_jogadores, df_base)
            st.success("Adicionado!")
            st.rerun()
    st.write(", ".join(base_names))
    st.divider()
    st.download_button("Baixar Caixa CSV", df_caixa.to_csv(index=False), "caixa.csv")
