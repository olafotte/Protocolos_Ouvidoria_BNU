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

def get_single_protocol_details(pid):
    try:
        year, number = pid.split('/')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, Arquivado, Last_update FROM protocols WHERE year = ? AND number = ?", (int(year), int(number)))
        row = cursor.fetchone()
        conn.close()
        return row
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

    search_term = request.args.get('search', '').strip()
    sort_order = request.args.get('sort_order', 'asc').lower()
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    # --- Base Query ---
    from_clause = "FROM protocols p"
    where_clauses = []
    params = []
    order_by_clause = f"ORDER BY p.year {sort_order}, p.number {sort_order}"

    if search_term:
        from_clause = "FROM protocols_fts fts JOIN protocols p ON fts.rowid = p.rowid"
        where_clauses.append("fts.content MATCH ?")
        params.append(search_term)

    # --- Keyword Filter ---
    if request.args.get('filter_keywords') == 'true':
        keyword_clauses_list = [f"p.content LIKE ?" for _ in LISTA_NORMALIZADA]
        where_clauses.append("(" + " OR ".join(keyword_clauses_list) + ")")
        params.extend([f"%{kw}%" for kw in LISTA_NORMALIZADA])

    # --- Status Filter ---
    status = request.args.get('status')
    if status == 'arch':
        where_clauses.append("p.Arquivado = 'yes'")
    elif status == 'notarch':
        where_clauses.append("p.Arquivado = 'no'")

    # --- Amabre Filter ---
    if request.args.get('amabre') == 'true':
        where_clauses.append("p.content LIKE '%amabre%'")

    # --- Build Final Query ---
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # --- Get Total Counts ---
    # We need to get the totals from the same query to respect all filters
    totals_sql = f"""
        SELECT 
            COUNT(p.rowid) as todos,
            SUM(CASE WHEN p.Arquivado = 'yes' THEN 1 ELSE 0 END) as arch,
            SUM(CASE WHEN p.content LIKE '%amabre%' THEN 1 ELSE 0 END) as amabre
        {from_clause}
        {where_sql}
    """
    
    # We need a separate query for totals because the main query might have a LIMIT/OFFSET later
    total_cursor = conn.cursor()
    total_cursor.execute(totals_sql, params)
    totals_row = total_cursor.fetchone()
    total_cursor.close()

    total_todos = totals_row['todos'] or 0
    total_arch = totals_row['arch'] or 0
    total_amabre = totals_row['amabre'] or 0
    total_notarch = total_todos - total_arch
    
    # --- Get Results ---
    results_sql = f"SELECT p.year, p.number, p.Arquivado {from_clause} {where_sql} {order_by_clause}"
    
    cursor.execute(results_sql, params)
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
            'has_archivado': row['Arquivado'] == 'yes',
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
    details = get_single_protocol_details(pid)

    if not details:
        return jsonify({'html': '<em>Protocolo não encontrado.</em>'})

    content = details['content']
    arquivado = details['Arquivado']
    last_update = details['Last_update']

    # Format date for display
    if last_update:
        try:
            date_obj = datetime.datetime.strptime(last_update, '%Y-%m-%d')
            last_update = date_obj.strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            last_update = "Data inválida"

    # Highlight search term and the main keyword list
    palavras_destaque = LISTA_NORMALIZADA.copy()
    if search:
        palavras_destaque.append(remover_acentos(search).lower())
        
    html = highlight(content, palavras_destaque)
    return jsonify({
        'html': html,
        'arquivado': arquivado,
        'last_update': last_update
    })

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
        details = get_single_protocol_details(pid)
        if details and details['content']:
            blocos.append(f"---\"{pid}\"---{details['content']}")
            
    file_content = '\n\n'.join(blocos)
    now = datetime.datetime.now()
    filename = f"Exportados {now.strftime('%d-%m-%Y %H-%M')}.txt"
    
    buf = io.BytesIO(file_content.encode('utf-8'))
    buf.seek(0)
    
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='text/plain')

@app.route('/api/db_last_update')
def db_last_update():
    try:
        mtime = os.path.getmtime(DB_NAME)
        dt_object = datetime.datetime.fromtimestamp(mtime)
        formatted_date = dt_object.strftime('%d/%m/%Y %H:%M')
        return jsonify({'last_update': formatted_date})
    except FileNotFoundError:
        return jsonify({'last_update': 'Não encontrado'})

if __name__ == '__main__':
    app.run(debug=True, port=5001) # Run on a different port to avoid conflict
