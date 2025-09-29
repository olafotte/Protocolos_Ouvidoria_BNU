from flask import Flask, render_template, jsonify, request, send_file
import datetime
import io
import os
import re
import unicodedata
import sqlite3
import json

app = Flask(__name__)

# --- Load Configuration ---
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# --- Configuration ---
DB_NAME = config.get('database_name', 'protocols.db')
REMOVIDOS_FILE = 'removidos.txt'
LISTA_ORIGINAL = sorted(config.get('lista_original', []))
FAMILIAS = config.get('familias', {})


# --- Helper Functions ---

def remover_acentos(txt):
    if not txt:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

def get_lista_normalizada():
    mapa_familias = {}
    for key, variantes in FAMILIAS.items():
        for v in variantes:
            mapa_familias[remover_acentos(v).lower()] = set(remover_acentos(va).lower() for va in variantes)

    lista_normalizada = set()
    for nome in LISTA_ORIGINAL:
        nome_sem_acento = remover_acentos(nome).lower()
        if nome_sem_acento in mapa_familias:
            lista_normalizada.update(mapa_familias[nome_sem_acento])
        else:
            lista_normalizada.add(nome_sem_acento)
    return list(lista_normalizada)

LISTA_NORMALIZADA = get_lista_normalizada()

def get_removidos():
    if not os.path.exists(REMOVIDOS_FILE):
        return set()
    with open(REMOVIDOS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_single_protocol_content(pid):
    try:
        year, number = pid.split('/')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM protocols WHERE year = ? AND number = ?", (int(year), int(number)))
        row = cursor.fetchone()
        conn.close()
        return row['content'] if row else None
    except (ValueError, IndexError):
        return None

def highlight(text, keywords):
    normalized_keywords = {k.strip().lower() for k in keywords if k.strip()}
    if not normalized_keywords or not text:
        return text

    # Tokenize the text into words and non-words (punctuation, spaces)
    tokens = re.findall(r'\w+|[^\w\s]|\s+', text)
    
    output = []
    for token in tokens:
        # We only want to check actual words for highlighting
        is_word = token.isalnum()
        normalized_token = remover_acentos(token).lower()
        
        if is_word and normalized_token in normalized_keywords:
            output.append(f'<span class="highlight">{token}</span>')
        else:
            output.append(token)
            
    return "".join(output)

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index_full.html')

@app.route('/api/protocols')
def api_protocols():
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Determine base filter (keywords) ---
    keyword_filter_active = request.args.get('filter_keywords') == 'true'
    base_clauses = []
    base_params = []
    if keyword_filter_active:
        keyword_clauses_list = [f"content LIKE ?" for _ in LISTA_NORMALIZADA]
        base_clauses.append("(" + " OR ".join(keyword_clauses_list) + ")")
        base_params.extend([f"%{kw}%" for kw in LISTA_NORMALIZADA])

    # --- Calculate Totals ---
    totals_where_sql = "WHERE " + " AND ".join(base_clauses) if base_clauses else ""
    totals_sql = f"""
        SELECT 
            COUNT(*) as todos,
            SUM(CASE WHEN content LIKE '%arquiva-se o protocolo%' THEN 1 ELSE 0 END) as arch,
            SUM(CASE WHEN content LIKE '%amabre%' THEN 1 ELSE 0 END) as amabre
        FROM protocols
        {totals_where_sql}
    """
    cursor.execute(totals_sql, base_params)
    totals_row = cursor.fetchone()
    
    total_todos = totals_row['todos'] or 0
    total_arch = totals_row['arch'] or 0
    total_amabre = totals_row['amabre'] or 0
    total_notarch = total_todos - total_arch

    # --- Filter Results for Display ---
    other_clauses = []
    other_params = []

    search_term = request.args.get('search', '').strip()
    if search_term:
        other_clauses.append("content LIKE ?")
        other_params.append(f"%{search_term}%")

    status = request.args.get('status')
    if status == 'arch':
        other_clauses.append("content LIKE '%arquiva-se o protocolo%'")
    elif status == 'notarch':
        other_clauses.append("content NOT LIKE '%arquiva-se o protocolo%'")
    
    if request.args.get('amabre') == 'true':
        other_clauses.append("content LIKE '%amabre%'")

    # Combine all clauses and params
    final_clauses = base_clauses + other_clauses
    final_params = base_params + other_params
    
    results_where_sql = "WHERE " + " AND ".join(final_clauses) if final_clauses else ""
    results_sql = f"SELECT year, number, content FROM protocols {results_where_sql} ORDER BY year, number"
    
    cursor.execute(results_sql, final_params)
    rows = cursor.fetchall()
    conn.close()

    # --- Process and Return ---
    removidos = get_removidos()
    protocolos = []
    for row in rows:
        pid = f"{row['year']}/{str(row['number']).zfill(5)}"
        if pid in removidos:
            continue
        protocolos.append({
            'id': pid,
            'ano': row['year'],
            'numero': str(row['number']).zfill(5),
            'has_archivado': 'arquiva-se o protocolo' in (row['content'] or '').lower(),
        })

    return jsonify({
        'protocols': protocolos,
        'totals': {
            'todos': total_todos,
            'arch': total_arch,
            'notarch': total_notarch,
            'amabre': total_amabre
        }
    })

@app.route('/protocolo')
def protocolo_detail():
    pid = request.args.get('id')
    search = request.args.get('search', '').strip()
    content = get_single_protocol_content(pid)

    if not content:
        return jsonify({'html': '<em>Protocolo não encontrado.</em>'})

    # Highlight search term and the main keyword list
    palavras_destaque = LISTA_NORMALIZADA.copy()
    if search:
        palavras_destaque.append(remover_acentos(search).lower())
        
    html = highlight(content, palavras_destaque)
    return jsonify({'html': html})

@app.route('/remover', methods=['POST'])
def remover():
    pid = request.get_json().get('id')
    if not pid:
        return jsonify({'success': False})
    with open(REMOVIDOS_FILE, 'a', encoding='utf-8') as f:
        f.write(pid + '\n')
    return jsonify({'success': True})

@app.route('/exportar', methods=['POST'])
def exportar():
    ids = set(request.get_json().get('ids', []))
    if not ids:
        return '', 400

    blocos = []
    for pid in sorted(list(ids)):
        content = get_single_protocol_content(pid)
        if content:
            blocos.append(f"---{pid}---{content}")
            
    file_content = '\n\n'.join(blocos)
    now = datetime.datetime.now()
    filename = f"Exportados {now.strftime('%d-%m-%Y %H-%M')}.txt"
    
    buf = io.BytesIO(file_content.encode('utf-8'))
    buf.seek(0)
    
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True, port=5001) # Run on a different port to avoid conflict