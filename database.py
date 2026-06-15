import sqlite3
import os

DB_PATH = 'compras.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_compra DATE NOT NULL,
            loja TEXT NOT NULL,
            valor_compra REAL NOT NULL,
            numero_nf TEXT,
            data_entrega_nf DATE,
            adto BOOLEAN NOT NULL CHECK (adto IN (0, 1)),
            valor_boleto REAL,
            data_entrega_boleto DATE,
            centro_custo TEXT NOT NULL,
            descricao TEXT,
            status TEXT DEFAULT 'Pendente',
            arquivo_nf TEXT,
            arquivo_boleto TEXT,
            vencimento DATE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lojas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS centros_custo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Garantir que as colunas existam caso a tabela já estivesse criada
    try:
        cursor.execute('ALTER TABLE compras ADD COLUMN arquivo_nf TEXT')
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute('ALTER TABLE compras ADD COLUMN arquivo_boleto TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute('ALTER TABLE compras ADD COLUMN vencimento DATE')
    except sqlite3.OperationalError:
        pass
    
    # Migrar lojas existentes da tabela compras se a tabela lojas estiver vazia
    cursor.execute('SELECT COUNT(*) FROM lojas')
    if cursor.fetchone()[0] == 0:
        cursor.execute('SELECT DISTINCT loja FROM compras WHERE loja IS NOT NULL AND loja != ""')
        lojas_existentes = cursor.fetchall()
        for loja in lojas_existentes:
            try:
                cursor.execute('INSERT INTO lojas (nome) VALUES (?)', (loja['loja'],))
            except sqlite3.IntegrityError:
                pass
                
    # Migrar centros de custo existentes da tabela compras se a tabela centros_custo estiver vazia
    cursor.execute('SELECT COUNT(*) FROM centros_custo')
    if cursor.fetchone()[0] == 0:
        cursor.execute('SELECT DISTINCT centro_custo FROM compras WHERE centro_custo IS NOT NULL AND centro_custo != ""')
        centros_existentes = cursor.fetchall()
        for centro in centros_existentes:
            try:
                cursor.execute('INSERT INTO centros_custo (nome) VALUES (?)', (centro['centro_custo'],))
            except sqlite3.IntegrityError:
                pass

    
    conn.commit()
    conn.close()
    print("Banco de dados inicializado com sucesso.")

if __name__ == '__main__':
    init_db()
