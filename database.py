import sqlite3

DB_PATH = "matchmaking.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Tabela para perguntas de matchmaking
cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        key TEXT PRIMARY KEY,
        question TEXT,
        type TEXT,
        match_type TEXT,
        weight REAL,
        choices TEXT
    )
""")

# Tabela para armazenar as respostas gerais dos usuários
cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        user_id TEXT PRIMARY KEY,
        answers TEXT
    )
""")

# Tabela para compatibilidade entre cargos
cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_compatibility (
        role_from TEXT,
        role_to TEXT,
        score REAL,
        PRIMARY KEY(role_from, role_to)
    )
""")

# Tabela para armazenar os resultados do BDSMTest
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bdsm_responses (
        user_id TEXT PRIMARY KEY,
        test_data TEXT
    )
""")

# Tabela para registrar cargos de gênero
cursor.execute("""
    CREATE TABLE IF NOT EXISTS gender_roles (
        role_id TEXT PRIMARY KEY,
        gender TEXT
    )
""")

# Tabela para registrar cargos de orientação sexual
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orientation_roles (
        role_id TEXT PRIMARY KEY,
        orientation TEXT
    )
""")

conn.commit()

print("Conexão estabelecida e tabelas criadas:", conn)
