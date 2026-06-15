from flask import Flask, render_template, request, jsonify
import os
import sqlite3
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import pandas as pd
import math
import database
from datetime import datetime
import mimetypes

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configurações
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Inicializa o banco de dados
database.init_db()

def get_db():
    return database.get_db_connection()

def send_email(file_path, filename, compra_data):
    # Verifica se o envio automático está ativado
    if os.getenv('ENVIO_AUTOMATICO', 'true').lower() not in ['true', '1', 'yes']:
        print("Envio automático desativado.")
        return

    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    adto = bool(compra_data.get('adto', False))
    
    if adto:
        destinatario = os.getenv('EMAIL_ADIANTAMENTOS', 'adiantamentos@empresa.com.br')
        assunto = f"(ADTO) Nova NF Recebida - {compra_data['loja']}"
    else:
        destinatario = os.getenv('EMAIL_FINANCEIRO', 'financeiro@empresa.com.br')
        assunto = f"Nova NF Recebida - {compra_data['loja']}"
        
    venc_str = ""
    if compra_data.get('vencimento'):
        venc_str = f"    - Vencimento: {compra_data['vencimento']}\n"
        
    adto_str = "Sim" if adto else "NÃO"

    corpo_email = f"""
    Olá,
    
    Uma nova Nota Fiscal foi enviada no sistema.
    
    Detalhes da Compra:
    - ADTO: {adto_str}
    - Loja: {compra_data['loja']}
    - Valor da Compra: R$ {compra_data['valor_compra']}
{venc_str}    - Centro de Custo: {compra_data['centro_custo']}
    - Descrição: {compra_data['descricao']}
    - Número da NF: {compra_data.get('numero_nf', '')}
    
    O arquivo da NF está em anexo.
    """
    
    msg = EmailMessage()
    msg['Subject'] = assunto
    msg['From'] = smtp_user
    msg['To'] = destinatario
    msg.set_content(corpo_email)
    
    # Anexar arquivo(s)
    try:
        filenames = filename.split('|')
        for idx, fname in enumerate(filenames):
            if not fname: continue
            f_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            if os.path.exists(f_path):
                with open(f_path, 'rb') as f:
                    file_data = f.read()
                    mime_type, _ = mimetypes.guess_type(fname)
                    if mime_type is None:
                        mime_type = 'application/octet-stream'
                    maintype, subtype = mime_type.split('/', 1)
                    
                    # Manter apenas o prefixo (nf_id ou boleto_id) e descartar o nome original
                    parts = fname.split('_', 2)
                    ext = os.path.splitext(fname)[1]
                    if len(parts) == 3 and parts[0] in ['nf', 'boleto']:
                        suffix = f"_{idx+1}" if len(filenames) > 1 else ""
                        attachment_name = f"{parts[0]}_{parts[1]}{suffix}{ext}"
                    else:
                        attachment_name = fname
                    
                    msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=attachment_name)
            
        if smtp_user and smtp_password:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            print("Email enviado com sucesso!")
        else:
            print("Aviso: Credenciais de email não configuradas. O email não foi enviado.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

def update_env_file(config_data):
    env_path = '.env'
    env_dict = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    env_dict[key] = val
    
    for k, v in config_data.items():
        if k in ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'EMAIL_ADIANTAMENTOS', 'EMAIL_FINANCEIRO', 'ENVIO_AUTOMATICO']:
            env_dict[k] = v
            os.environ[k] = str(v)
            
    with open(env_path, 'w') as f:
        for k, v in env_dict.items():
            f.write(f"{k}={v}\n")

@app.route('/api/config_email', methods=['GET'])
def get_config():
    return jsonify({
        'SMTP_SERVER': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        'SMTP_PORT': os.getenv('SMTP_PORT', '587'),
        'SMTP_USER': os.getenv('SMTP_USER', ''),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD', ''),
        'EMAIL_ADIANTAMENTOS': os.getenv('EMAIL_ADIANTAMENTOS', 'adiantamentos@empresa.com.br'),
        'EMAIL_FINANCEIRO': os.getenv('EMAIL_FINANCEIRO', 'financeiro@empresa.com.br'),
        'ENVIO_AUTOMATICO': os.getenv('ENVIO_AUTOMATICO', 'true')
    })

@app.route('/api/config_email', methods=['POST'])
def save_config():
    data = request.json
    update_env_file(data)
    return jsonify({'message': 'Configurações atualizadas com sucesso!'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/compras', methods=['GET'])
def get_compras():
    conn = get_db()
    compras = conn.execute('SELECT * FROM compras ORDER BY data_compra DESC, id DESC').fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in compras])

@app.route('/api/compras', methods=['POST'])
def add_compra():
    if request.content_type.startswith('multipart/form-data'):
        data = request.form
        nf_files = request.files.getlist('arquivo_nf')
        boleto_file = request.files.get('arquivo_boleto')
    else:
        data = request.json
        nf_files = []
        boleto_file = None

    try:
        conn = get_db()
        cursor = conn.cursor()
        vencimento = data.get('vencimento') or None
        
        cursor.execute('''
            INSERT INTO compras (data_compra, loja, valor_compra, centro_custo, adto, descricao, status, vencimento)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?)
        ''', (
            data['data_compra'],
            data['loja'],
            data['valor_compra'],
            data['centro_custo'],
            1 if str(data.get('adto')).lower() in ['true', '1'] else 0,
            data.get('descricao', ''),
            vencimento
        ))
        compra_id = cursor.lastrowid
        
        filename_nf = None
        filename_boleto = None
        
        filename_nf_list = []
        for f in nf_files:
            if f and f.filename != '':
                fn = f"nf_{compra_id}_{f.filename}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                filename_nf_list.append(fn)
        if filename_nf_list:
            filename_nf = '|'.join(filename_nf_list)
            
        if boleto_file and boleto_file.filename != '':
            filename_boleto = f"boleto_{compra_id}_{boleto_file.filename}"
            boleto_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_boleto))
            
        numero_nf = data.get('numero_nf', '')
        status = 'Concluido' if filename_nf or numero_nf else 'Pendente'
        
        if filename_nf or filename_boleto or numero_nf:
            cursor.execute('''
                UPDATE compras 
                SET arquivo_nf = ?, arquivo_boleto = ?, numero_nf = ?, status = ?
                WHERE id = ?
            ''', (filename_nf, filename_boleto, numero_nf, status, compra_id))

        conn.commit()
        
        # --- ENVIO AUTOMÁTICO NA NOVA COMPRA ---
        # Só enviar email automático se tiver a NF e o número da NF preenchidos
        if filename_nf and numero_nf:
            envio_automatico = os.getenv('ENVIO_AUTOMATICO', 'true').lower() in ['true', '1', 'yes']
            if envio_automatico:
                arquivo_enviar = filename_nf
                caminho_enviar = os.path.join(app.config['UPLOAD_FOLDER'], arquivo_enviar)
                
                compra_dict = {
                    'id': compra_id,
                    'loja': data['loja'],
                    'valor_compra': data['valor_compra'],
                    'centro_custo': data['centro_custo'],
                    'descricao': data.get('descricao', ''),
                    'numero_nf': numero_nf,
                    'vencimento': vencimento,
                    'adto': 1 if str(data.get('adto')).lower() in ['true', '1'] else 0
                }
                
                # Aproveitar a função legada
                send_email(caminho_enviar, arquivo_enviar, compra_dict)
                
        conn.close()
        return jsonify({'message': 'Compra adicionada com sucesso!', 'id': compra_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/compras/<int:compra_id>', methods=['PUT'])
def edit_compra(compra_id):
    if request.content_type.startswith('multipart/form-data'):
        data = request.form
        nf_files = request.files.getlist('arquivo_nf')
        boleto_file = request.files.get('arquivo_boleto')
    else:
        data = request.json
        nf_files = []
        boleto_file = None

    try:
        conn = get_db()
        cursor = conn.cursor()
        vencimento = data.get('vencimento') or None
        
        cursor.execute('''
            UPDATE compras
            SET data_compra = ?, loja = ?, valor_compra = ?, centro_custo = ?, adto = ?, descricao = ?, vencimento = ?
            WHERE id = ?
        ''', (
            data['data_compra'],
            data['loja'],
            data['valor_compra'],
            data['centro_custo'],
            1 if str(data.get('adto')).lower() in ['true', '1'] else 0,
            data.get('descricao', ''),
            vencimento,
            compra_id
        ))
        
        filename_nf = None
        filename_boleto = None
        
        filename_nf_list = []
        for f in nf_files:
            if f and f.filename != '':
                fn = f"nf_{compra_id}_{f.filename}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                filename_nf_list.append(fn)
        if filename_nf_list:
            filename_nf = '|'.join(filename_nf_list)
            cursor.execute('UPDATE compras SET arquivo_nf = ? WHERE id = ?', (filename_nf, compra_id))
            
        if boleto_file and boleto_file.filename != '':
            filename_boleto = f"boleto_{compra_id}_{boleto_file.filename}"
            boleto_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_boleto))
            cursor.execute('UPDATE compras SET arquivo_boleto = ? WHERE id = ?', (filename_boleto, compra_id))
            
        numero_nf = data.get('numero_nf')
        if numero_nf is not None:
            cursor.execute('UPDATE compras SET numero_nf = ? WHERE id = ?', (numero_nf, compra_id))

        # Update status if needed based on the new NF number
        cursor.execute('SELECT arquivo_nf, numero_nf FROM compras WHERE id = ?', (compra_id,))
        row = cursor.fetchone()
        if row:
            has_nf_file = bool(row['arquivo_nf'])
            has_nf_num = bool(row['numero_nf'])
            new_status = 'Concluido' if has_nf_file or has_nf_num else 'Pendente'
            cursor.execute('UPDATE compras SET status = ? WHERE id = ?', (new_status, compra_id))

        conn.commit()
        conn.close()
        return jsonify({'message': 'Compra atualizada com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/compras/<int:compra_id>', methods=['DELETE'])
def delete_compra(compra_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM compras WHERE id = ?', (compra_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Compra removida com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/lojas', methods=['GET'])
def get_lojas():
    conn = get_db()
    lojas = conn.execute('SELECT * FROM lojas ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in lojas])

@app.route('/api/lojas', methods=['POST'])
def add_loja():
    data = request.json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO lojas (nome) VALUES (?)', (data['nome'].strip(),))
        conn.commit()
        loja_id = cursor.lastrowid
        conn.close()
        return jsonify({'message': 'Loja adicionada com sucesso!', 'id': loja_id, 'nome': data['nome'].strip()}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Loja já cadastrada'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/centros_custo', methods=['GET'])
def get_centros_custo():
    conn = get_db()
    centros = conn.execute('SELECT * FROM centros_custo ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in centros])

@app.route('/api/centros_custo', methods=['POST'])
def add_centro_custo():
    data = request.json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO centros_custo (nome) VALUES (?)', (data['nome'].strip(),))
        conn.commit()
        centro_id = cursor.lastrowid
        conn.close()
        return jsonify({'message': 'Centro de Custo adicionado!', 'id': centro_id, 'nome': data['nome'].strip()}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Centro de custo já cadastrado'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/centros_custo/<int:centro_id>', methods=['PUT'])
def edit_centro_custo_api(centro_id):
    data = request.json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE centros_custo SET nome = ? WHERE id = ?', (data['nome'].strip(), centro_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Atualizado com sucesso!'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Já existe outro centro com esse nome'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/centros_custo/<int:centro_id>', methods=['DELETE'])
def delete_centro_custo_api(centro_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM centros_custo WHERE id = ?', (centro_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Centro de custo deletado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_nf/<int:compra_id>', methods=['POST'])
def upload_nf(compra_id):
    if 'nf_file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
    file = request.files['nf_file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'}), 400
        
    numero_nf = request.form.get('numero_nf')
    data_recebimento = request.form.get('data_recebimento')
    
    if not numero_nf or not data_recebimento:
        return jsonify({'error': 'Número da NF e Data são obrigatórios'}), 400
        
    # Salvar arquivos
    nf_files = request.files.getlist('nf_file')
    filename_nf_list = []
    for f in nf_files:
        if f and f.filename != '':
            fn = f"nf_{compra_id}_{f.filename}"
            f_path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            f.save(f_path)
            filename_nf_list.append(fn)
            
    if not filename_nf_list:
        return jsonify({'error': 'Nenhum arquivo válido enviado'}), 400
        
    filename = '|'.join(filename_nf_list)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename_nf_list[0]) # Path is practically unused directly for multiples in email, but keeping for compatibility
    
    # Atualizar banco de dados
    conn = get_db()
    cursor = conn.cursor()
    
    # Buscar os dados da compra antes de atualizar, para o email
    compra = conn.execute('SELECT * FROM compras WHERE id = ?', (compra_id,)).fetchone()
    if not compra:
        return jsonify({'error': 'Compra não encontrada'}), 404
        
    cursor.execute('''
        UPDATE compras 
        SET numero_nf = ?, data_entrega_nf = ?, status = 'Concluído', arquivo_nf = ?
        WHERE id = ?
    ''', (numero_nf, data_recebimento, filename, compra_id))
    
    conn.commit()
    conn.close()
    
    # Disparar e-mail
    # Atualizar os dados para incluir o novo numero_nf na mensagem
    compra_dict = dict(compra)
    compra_dict['numero_nf'] = numero_nf
    send_email(file_path, filename, compra_dict)
    
    return jsonify({'message': 'NF salva e enviada com sucesso!'})

@app.route('/api/enviar_emails_manuais', methods=['POST'])
def enviar_emails_manuais():
    data = request.json
    emails = data.get('emails', [])
    compra_ids = data.get('compra_ids', [])
    
    if not emails or not compra_ids:
        return jsonify({'error': 'E-mails e compras são obrigatórios'}), 400
        
    conn = get_db()
    compras = []
    for cid in compra_ids:
        compra = conn.execute('SELECT * FROM compras WHERE id = ?', (cid,)).fetchone()
        if compra:
            compras.append(dict(compra))
    conn.close()
    
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if not smtp_user or not smtp_password:
        return jsonify({'error': 'Credenciais de e-mail (remetente) não configuradas. Verifique as configurações.'}), 400
        
    sucesso_count = 0
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            
            for compra in compras:
                assunto = f"Detalhes da Compra / NF / Boleto - Loja {compra['loja']}"
                
                venc_str = ""
                if compra.get('vencimento'):
                    venc_str = f"- Vencimento: {compra['vencimento']}\n"
                    
                adto_str = "Sim" if compra.get('adto') else "NÃO"
                    
                corpo_email = f"""
Olá,

Seguem os detalhes da compra:

- ADTO: {adto_str}
- Loja: {compra['loja']}
- Valor da Compra: R$ {compra['valor_compra']}
{venc_str}- Centro de Custo: {compra['centro_custo']}
- Descrição: {compra['descricao']}
- Número da NF: {compra.get('numero_nf') or 'N/A'}
- Status: {compra['status']}

Os arquivos anexos (se houver) acompanham este e-mail.
                """
                
                msg = EmailMessage()
                msg['Subject'] = assunto
                msg['From'] = smtp_user
                msg['To'] = ", ".join(emails)
                msg.set_content(corpo_email)
                
                # Anexar NF(s)
                if compra.get('arquivo_nf'):
                    filenames = compra['arquivo_nf'].split('|')
                    for idx, fname in enumerate(filenames):
                        if not fname: continue
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                mime_type, _ = mimetypes.guess_type(fname)
                                if mime_type is None:
                                    mime_type = 'application/octet-stream'
                                maintype, subtype = mime_type.split('/', 1)
                                
                                parts = fname.split('_', 2)
                                ext = os.path.splitext(fname)[1]
                                if len(parts) == 3 and parts[0] in ['nf', 'boleto']:
                                    suffix = f"_{idx+1}" if len(filenames) > 1 else ""
                                    attachment_name = f"{parts[0]}_{parts[1]}{suffix}{ext}"
                                else:
                                    attachment_name = fname
                                
                                msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=attachment_name)
                
                # Anexar Boleto
                if compra.get('arquivo_boleto'):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], compra['arquivo_boleto'])
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            filename = compra['arquivo_boleto']
                            mime_type, _ = mimetypes.guess_type(filename)
                            if mime_type is None:
                                mime_type = 'application/octet-stream'
                            maintype, subtype = mime_type.split('/', 1)
                            
                            parts = filename.split('_', 2)
                            ext = os.path.splitext(filename)[1]
                            if len(parts) == 3 and parts[0] in ['nf', 'boleto']:
                                attachment_name = f"{parts[0]}_{parts[1]}{ext}"
                            else:
                                attachment_name = filename
                            
                            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=attachment_name)
                            
                server.send_message(msg)
                sucesso_count += 1
                
        return jsonify({'message': f'{sucesso_count} e-mails enviados com sucesso para {len(emails)} destinatário(s)!'})
    except Exception as e:
        return jsonify({'error': f'Erro ao enviar e-mails: {str(e)}'}), 500


@app.route('/api/importar_planilha', methods=['POST'])
def importar_planilha():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'}), 400
        
    try:
        # Lê a planilha sem cabeçalho definido inicialmente
        df_raw = pd.read_excel(file, header=None)
        
        # Procura a linha que contém os cabeçalhos (procurando pela palavra 'loja' ou 'comprado')
        header_idx = 0
        for i, row in df_raw.iterrows():
            row_str = ' '.join(str(x).lower() for x in row.values)
            if 'loja' in row_str or 'comprado dia' in row_str:
                header_idx = i
                break
                
        # Define o cabeçalho e descarta as linhas acima dele
        df = df_raw.copy()
        df.columns = df.iloc[header_idx]
        df = df[header_idx + 1:].reset_index(drop=True)
        
        # Helper to get the first column name containing a substring
        def get_col(substring):
            for col in df.columns:
                if substring.lower() in str(col).lower():
                    return col
            return None
            
        col_data = get_col('comprado') or get_col('data')
        col_loja = get_col('loja') or get_col('fornecedor')
        col_valor = get_col('valor da') or get_col('valor')
        col_nf = get_col('nº nf') or get_col('nf')
        col_data_nf = get_col('entregue nf') or get_col('data nf')
        col_adto = get_col('adiantamento') or get_col('adto')
        col_valor_bol = get_col('valor do boleto')
        col_data_bol = get_col('entregue boleto')
        col_cc = get_col('centro de custo')
        col_desc = get_col('descrição') or get_col('descricao')
        
        conn = get_db()
        cursor = conn.cursor()
        
        count = 0
        for index, row in df.iterrows():
            # Skip if basic required fields are completely null
            if pd.isna(row.get(col_loja)) and pd.isna(row.get(col_valor)):
                continue
                
            # Handle dates
            data_compra = row.get(col_data)
            if pd.notna(data_compra):
                if isinstance(data_compra, datetime):
                    data_compra = data_compra.strftime('%Y-%m-%d')
                else:
                    data_compra = str(data_compra)
            else:
                data_compra = datetime.now().strftime('%Y-%m-%d')
                
            data_entrega_nf = row.get(col_data_nf)
            if pd.notna(data_entrega_nf):
                if isinstance(data_entrega_nf, datetime):
                    data_entrega_nf = data_entrega_nf.strftime('%Y-%m-%d')
                else:
                    data_entrega_nf = str(data_entrega_nf)
            else:
                data_entrega_nf = None
                
            data_entrega_boleto = row.get(col_data_bol)
            if pd.notna(data_entrega_boleto):
                if isinstance(data_entrega_boleto, datetime):
                    data_entrega_boleto = data_entrega_boleto.strftime('%Y-%m-%d')
                else:
                    data_entrega_boleto = str(data_entrega_boleto)
            else:
                data_entrega_boleto = None
                
            # Values
            valor = row.get(col_valor)
            if pd.isna(valor):
                valor = 0.0
            elif isinstance(valor, str):
                valor = valor.replace('R$', '').replace('.', '').replace(',', '.').strip()
                try: valor = float(valor)
                except: valor = 0.0
                
            valor_bol = row.get(col_valor_bol)
            if pd.isna(valor_bol):
                valor_bol = None
            elif isinstance(valor_bol, str):
                valor_bol = valor_bol.replace('R$', '').replace('.', '').replace(',', '.').strip()
                try: valor_bol = float(valor_bol)
                except: valor_bol = None
                
            # Adto
            adto_val = str(row.get(col_adto)).strip().lower()
            adto = 1 if adto_val in ['sim', 's', 'true', '1'] else 0
            
            # Outros
            loja = str(row.get(col_loja)) if pd.notna(row.get(col_loja)) else 'Desconhecida'
            nf = str(row.get(col_nf)) if pd.notna(row.get(col_nf)) else None
            if nf == 'nan' or nf == '': nf = None
            
            cc = str(row.get(col_cc)) if pd.notna(row.get(col_cc)) else 'Não Informado'
            if cc == 'nan': cc = 'Não Informado'
            
            desc = str(row.get(col_desc)) if pd.notna(row.get(col_desc)) else ''
            if desc == 'nan': desc = ''
            
            status = 'Pendente' if not nf else 'Concluído'
            
            cursor.execute('''
                INSERT INTO compras (data_compra, loja, valor_compra, numero_nf, data_entrega_nf, adto, valor_boleto, data_entrega_boleto, centro_custo, descricao, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data_compra, loja, valor, nf, data_entrega_nf, adto, valor_bol, data_entrega_boleto, cc, desc, status))
            
            count += 1
            
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'{count} linhas importadas com sucesso!'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao processar planilha: {str(e)}'}), 400

if __name__ == '__main__':
    # Hospedar na rede usando 0.0.0.0 na porta solicitada
    app.run(host='0.0.0.0', port=5015, debug=True)
