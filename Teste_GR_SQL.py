from datetime import datetime, timedelta
import pandas as pd
import sqlite3
import os
import shutil
import streamlit as st
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

# Caminho do banco de dados SQLite em um local persistente
db_path = os.path.expanduser("~/eventos.db")
backup_path = "/tmp/backup_eventos.db"  # Backup temporário

# Função para autenticar e criar conexão com o Google Drive
def autenticar_google_drive():
    """
    Autentica o Google Drive usando o arquivo 'credentials.json'.
    """
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.json")  # Credenciais locais
    if not gauth.credentials:
        gauth.LocalWebserverAuth()  # Autenticação local via navegador
        gauth.SaveCredentialsFile("credentials.json")
    return GoogleDrive(gauth)

# Função para realizar backup no Google Drive
def realizar_backup_google_drive():
    """
    Realiza um backup do banco de dados SQLite e envia para o Google Drive.
    """
    # Copia o banco para o local de backup temporário
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        st.info(f"Backup salvo localmente em {backup_path}")

        # Autentica e envia o backup ao Google Drive
        drive = autenticar_google_drive()

        # Verifica se já existe um arquivo com o mesmo nome no Google Drive
        file_list = drive.ListFile({'q': f"title='backup_eventos.db'"}).GetList()
        if file_list:
            for file in file_list:
                file.Delete()  # Remove backups antigos para substituição

        # Envia o novo backup
        file = drive.CreateFile({'title': 'backup_eventos.db'})
        file.SetContentFile(backup_path)
        file.Upload()
        st.success("Backup enviado para o Google Drive com sucesso.")
    else:
        st.error("Banco de dados não encontrado para realizar o backup.")

# Função para sincronizar o banco com o repositório Git
def sincronizar_banco_git():
    """
    Sincroniza alterações no banco de dados com o repositório Git.
    """
    os.system("git pull")
    if os.path.exists(db_path):
        os.system(f"git add {db_path} && git commit -m 'Atualiza banco de dados eventos.db' && git push")
        st.info("Banco de dados sincronizado com o repositório.")

# Lista de clientes
def carregar_clientes():
    file_path = "lista de contatos.xlsx"
    if not os.path.exists(file_path):
        st.error("Erro: Arquivo de contatos não encontrado.")
        return []
    xls = pd.ExcelFile(file_path)
    planilha2 = pd.read_excel(xls, 'Planilha2')
    nomes_encontrados = list(set(planilha2['a'].dropna().loc[planilha2['a.3'] != "Não encontrado"]))
    return sorted(nomes_encontrados)

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
    realizar_backup_google_drive()  # Faz o backup após salvar
    sincronizar_banco_git()

def atualizar_evento(evento_id, observacao):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE eventos SET observacao = ? WHERE id = ?",
        (observacao, evento_id)
    )
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Faz o backup após atualização
    sincronizar_banco_git()

def excluir_evento(evento_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eventos WHERE id = ?", (evento_id,))
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Faz o backup após exclusão
    sincronizar_banco_git()

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
    realizar_backup_google_drive()  # Faz o backup após salvar cancelamento
    sincronizar_banco_git()

def excluir_cancelado(cancelado_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cancelados WHERE id = ?", (cancelado_id,))
    conn.commit()
    conn.close()
    realizar_backup_google_drive()  # Faz o backup após exclusão
    sincronizar_banco_git()

# Principal função da aplicação Streamlit
def main():
    st.title("Gerenciamento de Revisões")
    
    # Inicializa o banco de dados
    inicializar_banco()

    # Carregar dados
    eventos = carregar_eventos()
    cancelados = carregar_cancelados()
    clientes = carregar_clientes()

    # Seleção de Cliente e Data para Agendamento
    st.header("Agendar Revisão")
    cliente_selecionado = st.selectbox("Selecionar Cliente para Agendar", clientes)
    data_reuniao = st.date_input("Escolha a Data da Reunião", datetime.now())
    if st.button("Agendar Revisão"):
        salvar_evento(cliente_selecionado, data_reuniao.strftime('%Y-%m-%d'))
        st.success("Revisão agendada com sucesso!")

    # Seção do calendário de eventos agendados
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
