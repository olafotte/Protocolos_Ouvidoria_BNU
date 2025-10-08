import sqlite3
import json

# --- Configuração ---
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

DB_NAME = config.get('database_name', 'protocols.db')

def setup_fts():
    """
    Configura a tabela virtual FTS5 para busca de texto completo.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("Verificando a existência da tabela FTS 'protocols_fts'...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protocols_fts'")
    if cursor.fetchone():
        print("A tabela 'protocols_fts' já existe. Pulando a criação.")
    else:
        print("Criando a tabela virtual FTS 'protocols_fts'...")
        # content='protocols' faz com que a FTS table seja uma cópia da tabela protocols
        # tokenize='porter' habilita o stemming para o idioma inglês e similares
        cursor.execute("""
            CREATE VIRTUAL TABLE protocols_fts USING fts5(
                content, 
                content='protocols',
                content_rowid='rowid',
                tokenize='porter'
            );
        """)
        print("Tabela FTS criada.")

    print("\nPopulando a tabela FTS com dados existentes...")
    # A query 'rebuild' reconstrói o índice FTS a partir da tabela de conteúdo
    cursor.execute("INSERT INTO protocols_fts(protocols_fts) VALUES('rebuild');")
    print("Tabela FTS populada e índice reconstruído.")

    print("\nCriando triggers para manter a sincronização...")
    # Triggers para manter a tabela FTS sincronizada com a tabela 'protocols'
    cursor.executescript("""
        CREATE TRIGGER IF NOT EXISTS protocols_ai AFTER INSERT ON protocols BEGIN
            INSERT INTO protocols_fts(rowid, content) VALUES (new.rowid, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS protocols_ad AFTER DELETE ON protocols BEGIN
            INSERT INTO protocols_fts(protocols_fts, rowid, content) VALUES('delete', old.rowid, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS protocols_au AFTER UPDATE ON protocols BEGIN
            INSERT INTO protocols_fts(protocols_fts, rowid, content) VALUES('delete', old.rowid, old.content);
            INSERT INTO protocols_fts(rowid, content) VALUES (new.rowid, new.content);
        END;
    """)
    print("Triggers criados com sucesso.")

    conn.commit()
    conn.close()
    print("\nConfiguração do FTS5 concluída!")

if __name__ == '__main__':
    setup_fts()
