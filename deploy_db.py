import requests
import os
import json

CONFIG_FILE = 'deploy_config.json'
LOCAL_DB_NAME = 'protocols.db'

def reload_webapp(username, api_token, webapp_domain):
    """
    Envia uma requisição para a API do PythonAnywhere para recarregar o web app.
    """
    print("Recarregando a aplicação web...")
    reload_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{webapp_domain}/reload/"
    
    try:
        reload_response = requests.post(
            reload_url,
            headers={'Authorization': f'Token {api_token}'}
        )

        if reload_response.status_code == 200:
            print("Aplicação web recarregada com sucesso.")
        else:
            print("Erro ao recarregar a aplicação web.")
            print(f"Status Code: {reload_response.status_code}")
            print(f"Resposta: {reload_response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Ocorreu um erro de conexão ao tentar recarregar a aplicação: {e}")

def run_upload():
    """
    Lê as configurações de deploy, faz o upload do banco de dados local
    para o PythonAnywhere e recarrega a aplicação web.
    """
    # --- Carregar Configurações ---
    if not os.path.exists(CONFIG_FILE):
        print(f"Erro: Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        print("Por favor, crie o arquivo a partir de 'deploy_config.json.example' e preencha suas informações.")
        return

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    username = config.get("pythonanywhere_username")
    api_token = config.get("pythonanywhere_api_token")
    pa_path = config.get("pythonanywhere_db_path")
    webapp_domain = config.get("pythonanywhere_webapp_domain")

    if not all([username, api_token, pa_path, webapp_domain]) or "SEU_" in username or "SEU_" in api_token:
        print(f"Erro: As configurações em '{CONFIG_FILE}' não estão preenchidas corretamente.")
        print("Certifique-se de substituir os valores de exemplo.")
        return

    # --- Lógica do Upload ---
    local_db_path = os.path.abspath(LOCAL_DB_NAME)

    if not os.path.exists(local_db_path):
        print(f"Erro: O arquivo de banco de dados não foi encontrado em '{local_db_path}'")
        return
    
    print(f"Iniciando o upload de '{local_db_path}' para '{pa_path}'...")

    api_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path{pa_path}"

    try:
        with open(local_db_path, 'rb') as f_db:
            files = {'content': f_db}
            
            response = requests.post(
                api_url,
                files=files,
                headers={'Authorization': f'Token {api_token}'}
            )

        if response.status_code in [200, 201]:
            print("Upload realizado com sucesso!")
            # Se o upload deu certo, recarrega a aplicação
            reload_webapp(username, api_token, webapp_domain)
        else:
            print("Ocorreu um erro durante o upload.")
            print(f"Status Code: {response.status_code}")
            print(f"Resposta: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Ocorreu um erro de conexão: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("A biblioteca 'requests' não está instalada. Instalando...")
        os.system('pip install requests')
        import requests
    run_upload()