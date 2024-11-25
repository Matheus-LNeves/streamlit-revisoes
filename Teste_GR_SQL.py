from datetime import datetime, timedelta
import pandas as pd
import sqlite3
import os
import shutil
import streamlit as st
import json
from streamlit_calendar import calendar
import locale
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Configura a localidade para português do Brasil
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, "pt_BR")
    except locale.Error:
        pass

# Caminho do banco de dados SQLite
db_path = os.path.expanduser("~/eventos.db")
backup_path = "/tmp/backup_eventos.db"  # Backup temporário

# Caminho do banco de dados SQLite
db_path = os.path.expanduser("~/eventos.db")
backup_path = "/tmp/backup_eventos.db"  # Backup temporário

# Função para autenticar e criar conexão com o Google Drive
def autenticar_google_drive():
    """
    Autentica o Google Drive usando as credenciais armazenadas no Streamlit Secrets.
    """
    # Acessa as credenciais do bloco 'GOOGLE_CREDENTIALS' nos secrets
    credentials_data = {
        "client_id": st.secrets["GOOGLE_CREDENTIALS"]["client_id"],
        "project_id": st.secrets["GOOGLE_CREDENTIALS"]["project_id"],
        "auth_uri": st.secrets["GOOGLE_CREDENTIALS"]["auth_uri"],
        "token_uri": st.secrets["GOOGLE_CREDENTIALS"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["auth_provider_x509_cert_url"],
        "client_secret": st.secrets["GOOGLE_CREDENTIALS"]["client_secret"],
        "redirect_uris": st.secrets["GOOGLE_CREDENTIALS"]["redirect_uris"]
    }

    # Escreve as credenciais em um arquivo JSON temporário
    credentials_path = "/tmp/credentials.json"
    with open(credentials_path, "w") as f:
        f.write(json.dumps({"web": credentials_data}))

    gauth = GoogleAuth()

    # Tenta carregar o token salvo ou autenticar pela primeira vez
    try:
        if os.path.exists("/tmp/token.json"):
            gauth.LoadCredentialsFile("/tmp/token.json")
        else:
            gauth.LoadClientConfigFile(credentials_path)
            gauth.CommandLineAuth()
            gauth.SaveCredentialsFile("/tmp/token.json")
    except Exception as e:
        st.error(f"Erro ao autenticar no Google Drive: {e}")
        st.stop()

    return GoogleDrive(gauth)

# Função para realizar backup no Google Drive
def realizar_backup_google_drive():
    """
    Realiza um backup do banco de dados SQLite e envia para o Google Drive.
    """
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        st.info(f"Backup salvo localmente em {backup_path}")

        # Autentica e envia o backup ao Google Drive
        drive = autenticar_google_drive()
        if not drive:
            return

        # Remove backups antigos
        try:
            file_list = drive.ListFile({'q': "title='backup_eventos.db'"}).GetList()
            for file in file_list:
                file.Delete()
        except Exception as e:
            st.error(f"Erro ao limpar backups antigos no Google Drive: {e}")
            return

        # Envia o novo backup
        try:
            file = drive.CreateFile({'title': 'backup_eventos.db'})
            file.SetContentFile(backup_path)
            file.Upload()
            st.success("Backup enviado para o Google Drive com sucesso.")
        except Exception as e:
            st.error(f"Erro ao enviar backup para o Google Drive: {e}")
    else:
        st.error("Banco de dados não encontrado para realizar o backup.")

# Função para inicializar o banco de dados
def inicializar_banco():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Criação das tabelas de eventos e cancelados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cancelados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

# Função para carregar clientes de um arquivo Excel
def carregar_clientes():
    file_path = "lista de contatos.xlsx"
    if not os.path.exists(file_path):
        st.error("Erro: Arquivo de contatos não encontrado.")
        return []
    xls = pd.ExcelFile(file_path)
    planilha2 = pd.read_excel(xls, 'Planilha2')
    nomes_encontrados = list(set(planilha2['a'].dropna().loc[planilha2['a.3'] != "Não encontrado"]))
    return sorted(nomes_encontrados)

# Funções para manipulação do banco de dados
def carregar_eventos():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM eventos")
    eventos = cursor.fetchall()
    conn.close()
    return [{"id": e[0], "cliente": e[1], "data": e[2], "observacao": e[3]} for e in eventos]

def salvar_evento(cliente, data, observacao=""):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO eventos (cliente, data, observacao) VALUES (?, ?, ?)",
        (cliente, data, observacao)
    )
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Realiza backup após salvar evento

def atualizar_evento(evento_id, observacao):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE eventos SET observacao = ? WHERE id = ?",
        (observacao, evento_id)
    )
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Realiza backup após atualizar evento

def excluir_evento(evento_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eventos WHERE id = ?", (evento_id,))
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Realiza backup após excluir evento

def carregar_cancelados():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cancelados")
    cancelados = cursor.fetchall()
    conn.close()
    return [{"id": c[0], "cliente": c[1], "data": c[2], "observacao": c[3]} for c in cancelados]

def salvar_cancelado(cliente, data, observacao=""):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cancelados (cliente, data, observacao) VALUES (?, ?, ?)",
        (cliente, data, observacao)
    )
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Realiza backup após salvar cancelamento

def excluir_cancelado(cancelado_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cancelados WHERE id = ?", (cancelado_id,))
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Realiza backup após excluir cancelamento

# Função corrigida para gerar próximos eventos
def gerar_proximos_eventos(cliente, data_inicial):
    novos_eventos = []
    data_base = data_inicial
    while len(novos_eventos) < 3:
        data_base += timedelta(days=90)
        while data_base.weekday() >= 5:  # Ajusta para dias úteis
            data_base += timedelta(days=1)
        novos_eventos.append({
            "cliente": cliente,
            "data": data_base.strftime('%Y-%m-%d'),
            "observacao": ""
        })
    return novos_eventos

# Principal função da aplicação Streamlit
def main():
    st.title("Gerenciamento de Revisões")
    
    # Inicializa o banco de dados
    inicializar_banco()

    # Carregar dados
    eventos = carregar_eventos()
    cancelados = carregar_cancelados()
    clientes = carregar_clientes()

    # Seção de agendamento
    st.header("Agendar Revisão")
    cliente_selecionado = st.selectbox("Selecionar Cliente para Agendar", clientes)
    data_inicial = st.date_input("Escolha a Data da Reunião", datetime.now())
    if st.button("Agendar Revisão"):
        salvar_evento(cliente_selecionado, data_inicial.strftime('%Y-%m-%d'))
        proximos_eventos = gerar_proximos_eventos(cliente_selecionado, data_inicial)
        for evento in proximos_eventos:
            salvar_evento(evento["cliente"], evento["data"], evento["observacao"])
        st.success("Revisão agendada com sucesso!")

    # Exibe o calendário de eventos agendados
    st.header("Calendário de Eventos Agendados")
    eventos_calendario = [{"title": e['cliente'], "start": e['data']} for e in eventos]
    calendar(events=eventos_calendario)

    # Lista de Eventos Agendados
    with st.expander("Lista de Eventos Agendados"):
        cliente_agendado_selecionado = st.selectbox("Filtrar por Cliente", ["Selecione um Cliente"] + clientes, key="agendados")
        if cliente_agendado_selecionado != "Selecione um Cliente":
            agendados_filtrados = [e for e in eventos if e['cliente'] == cliente_agendado_selecionado]
            if agendados_filtrados:
                for evento in agendados_filtrados:
                    st.write(f"Cliente: {evento['cliente']}, Data: {evento['data']}")
                    observacao = st.text_area("Observações", value=evento['observacao'], key=f"obs_{evento['id']}")
                    if st.button("Salvar Observação", key=f"salvar_obs_{evento['id']}"):
                        atualizar_evento(evento['id'], observacao)
                        st.success("Observação salva com sucesso!")
                    if st.button(f"Cancelar evento de {evento['cliente']}", key=f"cancelar_{evento['id']}"):
                        salvar_cancelado(evento['cliente'], evento['data'], evento['observacao'])
                        excluir_evento(evento['id'])
                        st.success("Evento cancelado com sucesso!")

    # Lista de Eventos Cancelados
    with st.expander("Eventos Cancelados"):
        cliente_cancelado_selecionado = st.selectbox("Filtrar por Cliente na Lista de Cancelados", ["Selecione um Cliente"] + clientes, key="cancelado")
        if cliente_cancelado_selecionado != "Selecione um Cliente":
            cancelados_filtrados = [c for c in cancelados if c['cliente'] == cliente_cancelado_selecionado]
            if cancelados_filtrados:
                for evento in cancelados_filtrados:
                    st.write(f"Cliente: {evento['cliente']}, Data Cancelada: {evento['data']}")
                    nova_data = st.date_input(f"Nova Data para {evento['cliente']}", datetime.now(), key=f"nova_data_{evento['id']}")
                    if st.button(f"Reagendar {evento['cliente']}", key=f"reagendar_{evento['id']}"):
                        salvar_evento(evento['cliente'], nova_data.strftime('%Y-%m-%d'), evento['observacao'])
                        excluir_cancelado(evento['id'])
                        st.success("Evento reagendado com sucesso!")

if __name__ == "__main__":
    main()

