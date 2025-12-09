"""Script simple para probar la conexión a PostgreSQL."""

from sqlalchemy import create_engine, text

DB_USER = "postgres"
DB_PASSWORD = "050403"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "postgres"

connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print("Probando conexión a PostgreSQL...")
print(f"URL: postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")

try:
    engine = create_engine(connection_string, echo=False)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✓ Conexión exitosa!")
        print(f"PostgreSQL version: {version[:50]}...")
except Exception as e:
    print(f"✗ Error de conexión: {e}")
    import traceback
    traceback.print_exc()
