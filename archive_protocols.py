import sqlite3
import unicodedata

def normalize_text(text):
    """
    Normaliza o texto: minúsculas, remove acentos, vírgulas e pontos.
    """
    if not text:
        return ""
    # Remover acentos
    nfkd_form = unicodedata.normalize('NFKD', text)
    text_sem_acentos = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Minúsculas e remoção de pontuação
    normalized = text_sem_acentos.lower().replace(',', '').replace('.', '')
    return normalized

def archive_protocols():
    """
    Lê o banco de dados 'protocols.db', verifica o conteúdo de cada protocolo
    e atualiza o campo 'Arquivado' se a regra for atendida.
    """
    db_name = 'protocols.db'
    updated_count = 0
    
    print(f"Conectando ao banco de dados '{db_name}'...")
    try:
        conn = sqlite3.connect(db_name)
        # Usar row_factory para acessar colunas pelo nome
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("Lendo todos os protocolos...")
        cursor.execute("SELECT rowid, content, Arquivado FROM protocols")
        
        rows = cursor.fetchall()
        total_rows = len(rows)
        print(f"Total de {total_rows} protocolos encontrados.")

        protocols_to_update = []

        for row in rows:
            content = row['content']
            
            # Pula se o conteúdo for nulo ou vazio
            if not content:
                continue

            # Normaliza o conteúdo para a verificação
            normalized_content = normalize_text(content)
            
            # Condição para arquivamento
            rule_phrase = "conforme andamento arquiva-se o protocolo"
            
            # O campo 'Arquivado' já está como 'yes'?
            is_already_archived = row['Arquivado'] == 'yes'

            # Se a regra for encontrada e o protocolo ainda não estiver arquivado
            if rule_phrase in normalized_content and not is_already_archived:
                protocols_to_update.append((row['rowid'],))
                print(f"  - Protocolo (rowid: {row['rowid']}) marcado para arquivamento.")
        
        if not protocols_to_update:
            print("\nNenhum protocolo precisou ser atualizado.")
        else:
            print(f"\nAtualizando {len(protocols_to_update)} protocolos no banco de dados...")
            
            update_query = "UPDATE protocols SET Arquivado = 'yes' WHERE rowid = ?"
            cursor.executemany(update_query, protocols_to_update)
            
            conn.commit()
            updated_count = cursor.rowcount
            print(f"Concluído! {updated_count} protocolos foram atualizados para 'Arquivado = yes'.")

    except sqlite3.Error as e:
        print(f"Erro ao acessar o banco de dados: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")

if __name__ == "__main__":
    archive_protocols()
