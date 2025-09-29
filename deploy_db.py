import requests
import os
import json
import glob

CONFIG_FILE = 'deploy_config.json'
LOCAL_DB_NAME = 'protocols.db'


def split_file(file_path, chunk_size_mb=99):
    """Divide um arquivo em partes menores."""
    print(f"Dividindo o arquivo {file_path} em partes de {chunk_size_mb}MB...")
    chunk_size_bytes = chunk_size_mb * 1024 * 1024
    file_number = 1
    parts = []
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size_bytes)
            if not chunk:
                break
            chunk_filename = f"{file_path}.part{file_number}"
            parts.append(chunk_filename)
            with open(chunk_filename, 'wb') as chunk_file:
                chunk_file.write(chunk)
            print(f" -> Criado chunk: {os.path.basename(chunk_filename)}")
            file_number += 1
    return parts


def reload_webapp(username, api_token, webapp_domain):
    """
    Envia uma requisição para a API do PythonAnywhere para recarregar o web app.
    """
    print("\nRecarregando a aplicação web...")
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
    Lê as configurações, divide o banco de dados em partes, faz o upload
    para o PythonAnywhere e instrui o usuário a juntar os arquivos.
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
    pa_path = config.get("pythonanywhere_db_path")  # Caminho completo para o arquivo DB no PA
    webapp_domain = config.get("pythonanywhere_webapp_domain")

    if not all([username, api_token, pa_path, webapp_domain]) or "SEU_" in username or "SEU_" in api_token:
        print(f"Erro: As configurações em '{CONFIG_FILE}' não estão preenchidas corretamente.")
        print("Certifique-se de substituir os valores de exemplo.")
        return

    # --- Lógica do Upload em Partes ---
    local_db_path = os.path.abspath(LOCAL_DB_NAME)

    if not os.path.exists(local_db_path):
        print(f"Erro: O arquivo de banco de dados não foi encontrado em '{local_db_path}'")
        return

    # 1. Dividir o arquivo localmente
    db_parts = split_file(local_db_path)
    if not db_parts:
        print("Nenhuma parte foi criada. Verifique se o arquivo original não está vazio.")
        return

    # Diretório de destino no PythonAnywhere
    pa_directory = os.path.dirname(pa_path)
    
    all_uploads_succeeded = True
    for part_path in db_parts:
        part_name = os.path.basename(part_path)
        # No PA, o caminho no files API começa com /home/username/
        # O pa_directory já deve conter isso.
        remote_part_path = f"{pa_directory}/{part_name}"
        
        print(f"\nIniciando o upload de '{part_name}' para '{remote_part_path}'...")
        
        api_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path{remote_part_path}"

        try:
            with open(part_path, 'rb') as f_part:
                files = {'content': f_part}
                response = requests.post(
                    api_url,
                    files=files,
                    headers={'Authorization': f'Token {api_token}'}
                )

            if response.status_code in [200, 201]:
                print(f"Upload de '{part_name}' realizado com sucesso!")
            else:
                print(f"Ocorreu um erro durante o upload de '{part_name}'.")
                print(f"Status Code: {response.status_code}")
                print(f"Resposta: {response.text}")
                all_uploads_succeeded = False
                break  # Interrompe o loop se um upload falhar

        except requests.exceptions.RequestException as e:
            print(f"Ocorreu um erro de conexão: {e}")
            all_uploads_succeeded = False
            break
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
            all_uploads_succeeded = False
            break
            
    # 3. Limpar partes locais
    print("\nLimpando arquivos de parte locais...")
    for part_path in db_parts:
        try:
            os.remove(part_path)
            print(f" -> Removido: {os.path.basename(part_path)}")
        except OSError as e:
            print(f"Erro ao remover {part_path}: {e}")
    print("Limpeza concluída.")

    # 4. Instruções finais se tudo deu certo
    if all_uploads_succeeded:
        print("\n\n--- AÇÃO NECESSÁRIA ---")
        print("Todos os arquivos foram enviados com sucesso!")
        print("Agora, você precisa juntar os arquivos no PythonAnywhere.")
        print("1. Abra um console Bash no PythonAnywhere.")
        print(f"2. Navegue até o diretório: cd {pa_directory}")
        
        part_names_for_cat = " ".join([os.path.basename(p) for p in db_parts])
        db_filename = os.path.basename(pa_path)
        
        print(f"3. Execute o comando abaixo para juntar os arquivos:")
        print(f"   cat {part_names_for_cat} > {db_filename}")
        print(f"4. (Opcional) Após juntar, você pode remover as partes do servidor com:")
        print(f"   rm {part_names_for_cat}")
        
        # Recarrega a aplicação web
        reload_webapp(username, api_token, webapp_domain)
    else:
        print("\nO deploy falhou porque um ou mais arquivos não puderam ser enviados.")


if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("A biblioteca 'requests' não está instalada. Instalando...")
        # Usar sys.executable para garantir que está usando o pip do ambiente certo
        import sys
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests'])
        import requests
    run_upload()
