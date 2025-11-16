import subprocess
import sys
import time

def run_script(script_path, *args):
    """Executa um script Python e retorna True em sucesso, False em erro."""
    command = [sys.executable, script_path] + list(args)
    print(f"\n--- Executando: {' '.join(command)} ---")
    
    try:
        # O `check=True` faz com que uma exceção seja levantada se o script retornar um erro.
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"--- Script '{script_path}' concluido com sucesso. ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! ERRO ao executar o script '{script_path}'. !!!")
        print(f"Saida de erro:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"!!! ERRO: O script '{script_path}' nao foi encontrado. !!!")
        return False

def main():
    """Funcao principal que orquestra a execucao dos scripts."""
    scripts_to_run = [
        ("enhanced_protocol_scraper.py", "scrape"),
        ("setup_fts.py",),
        ("deploy_db.py",)
    ]

    print("Iniciando sequencia de atualizacao e deploy...")

    all_success = True
    for i, script_info in enumerate(scripts_to_run):
        print(f"\n[Passo {i+1}/{len(scripts_to_run)}]")
        
        script_path = script_info[0]
        script_args = script_info[1:]
        
        if not run_script(script_path, *script_args):
            print("\n!!! A sequencia foi interrompida devido a um erro. !!!")
            all_success = False
            break
    
    if all_success:
        print("\n*** Todos os scripts foram executados com sucesso! ***")
        
def countdown_progress_bar(duration_seconds):
    """Exibe uma barra de progresso e contagem regressiva."""
    print(f"\nAguardando 24 horas para a proxima execucao...")
    total_steps = duration_seconds
    
    for i in range(total_steps, -1, -1):
        hours, remainder = divmod(i, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_left = f"{hours:02}:{minutes:02}:{seconds:02}"
        
        progress = (total_steps - i) / total_steps
        bar_length = 50
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        sys.stdout.write(f'\rTempo restante: {time_left} |{bar}| {progress*100:.2f}%')
        sys.stdout.flush()
        
        time.sleep(1)

    print() # Nova linha no final da barra de progresso

if __name__ == "__main__":
    while True:
        main()
        try:
            # 24 horas = 86400 segundos
            countdown_progress_bar(86400)
        except KeyboardInterrupt:
            print("\nContagem regressiva interrompida pelo usuario. Saindo...")
            break
