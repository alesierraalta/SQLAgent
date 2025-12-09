"""Script para generar datos de prueba en PostgreSQL."""

import os
import random
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

# Cargar variables de entorno
load_dotenv()

# Configuración de conexión
DB_USER = "postgres"
DB_PASSWORD = "050403"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "postgres"  # Cambiar si tienes otra base de datos


def get_connection_string() -> str:
    """
    Genera la cadena de conexión a PostgreSQL.

    Returns:
        Connection string para SQLAlchemy
    """
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def create_tables(engine: Engine) -> None:
    """
    Crea las tablas si no existen.

    Args:
        engine: SQLAlchemy Engine
    """
    print("Creando tablas...")

    # Crear tabla products
    products_sql = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        category VARCHAR(100),
        price DECIMAL(10,2) NOT NULL
    );
    """

    # Crear tabla sales
    # Nota: Usamos SERIAL para auto-increment aunque el schema dice INTEGER
    # porque es más práctico para datos de prueba
    sales_sql = """
    CREATE TABLE IF NOT EXISTS sales (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        country VARCHAR(100) NOT NULL,
        product_id INTEGER NOT NULL,
        revenue DECIMAL(10,2) NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """

    with engine.connect() as conn:
        conn.execute(text(products_sql))
        conn.execute(text("COMMIT;"))
        print("✓ Tabla 'products' creada")

        conn.execute(text(sales_sql))
        conn.execute(text("COMMIT;"))
        print("✓ Tabla 'sales' creada")


def generate_products(engine: Engine, num_products: int = 20) -> list[int]:
    """
    Genera productos de prueba.

    Args:
        engine: SQLAlchemy Engine
        num_products: Número de productos a generar

    Returns:
        Lista de IDs de productos generados
    """
    print(f"\nGenerando {num_products} productos...")

    # Categorías de productos
    categories = [
        "Electrónica",
        "Ropa",
        "Hogar",
        "Deportes",
        "Libros",
        "Juguetes",
        "Alimentación",
        "Belleza",
    ]

    # Nombres de productos por categoría
    product_names = {
        "Electrónica": ["Laptop", "Smartphone", "Tablet", "Auriculares", "Smartwatch"],
        "Ropa": ["Camiseta", "Pantalón", "Zapatos", "Chaqueta", "Vestido"],
        "Hogar": ["Sofá", "Mesa", "Silla", "Lámpara", "Alfombra"],
        "Deportes": ["Pelota", "Raqueta", "Bicicleta", "Pesas", "Yoga Mat"],
        "Libros": ["Novela", "Ciencia", "Historia", "Biografía", "Cocina"],
        "Juguetes": ["Puzzle", "Muñeca", "Coche", "Lego", "Juego de Mesa"],
        "Alimentación": ["Café", "Té", "Chocolate", "Snacks", "Bebidas"],
        "Belleza": ["Crema", "Shampoo", "Perfume", "Maquillaje", "Serum"],
    }

    product_ids = []
    with engine.connect() as conn:
        # Limpiar tabla primero
        conn.execute(text("TRUNCATE TABLE products CASCADE;"))
        conn.execute(text("COMMIT;"))

        for i in range(1, num_products + 1):
            category = random.choice(categories)
            base_names = product_names.get(category, ["Producto"])
            name = f"{random.choice(base_names)} {category} {i}"
            price = round(random.uniform(10.0, 500.0), 2)

            insert_sql = text(
                """
                INSERT INTO products (id, name, category, price)
                VALUES (:id, :name, :category, :price)
                """
            )

            conn.execute(
                insert_sql,
                {"id": i, "name": name, "category": category, "price": price},
            )
            product_ids.append(i)

        conn.execute(text("COMMIT;"))
        print(f"✓ {num_products} productos generados")

    return product_ids


def generate_sales(engine: Engine, product_ids: list[int], num_sales: int = 100) -> None:
    """
    Genera ventas de prueba.

    Args:
        engine: SQLAlchemy Engine
        product_ids: Lista de IDs de productos disponibles
        num_sales: Número de ventas a generar
    """
    print(f"\nGenerando {num_sales} ventas...")

    # Países
    countries = [
        "España",
        "México",
        "Argentina",
        "Colombia",
        "Chile",
        "Perú",
        "Ecuador",
        "Venezuela",
    ]

    # Fechas: últimos 6 meses
    end_date = date.today()
    start_date = end_date - timedelta(days=180)

    with engine.connect() as conn:
        # Limpiar tabla primero
        conn.execute(text("TRUNCATE TABLE sales;"))
        conn.execute(text("COMMIT;"))

        for i in range(1, num_sales + 1):
            # Fecha aleatoria en el rango
            days_diff = random.randint(0, 180)
            sale_date = start_date + timedelta(days=days_diff)

            # Producto aleatorio
            product_id = random.choice(product_ids)

            # Cantidad aleatoria
            quantity = random.randint(1, 10)

            # Obtener precio del producto
            price_query = text("SELECT price FROM products WHERE id = :product_id")
            result = conn.execute(price_query, {"product_id": product_id})
            product_price = result.fetchone()[0]

            # Revenue = precio * cantidad (con variación aleatoria)
            revenue = round(product_price * quantity * random.uniform(0.9, 1.1), 2)

            country = random.choice(countries)

            insert_sql = text(
                """
                INSERT INTO sales (date, country, product_id, revenue, quantity)
                VALUES (:date, :country, :product_id, :revenue, :quantity)
                """
            )

            conn.execute(
                insert_sql,
                {
                    "date": sale_date,
                    "country": country,
                    "product_id": product_id,
                    "revenue": revenue,
                    "quantity": quantity,
                },
            )

            if i % 20 == 0:
                print(f"  Generadas {i}/{num_sales} ventas...")

        conn.execute(text("COMMIT;"))
        print(f"✓ {num_sales} ventas generadas")


def verify_data(engine: Engine) -> None:
    """
    Verifica que los datos se hayan insertado correctamente.

    Args:
        engine: SQLAlchemy Engine
    """
    print("\nVerificando datos...")

    with engine.connect() as conn:
        # Contar productos
        result = conn.execute(text("SELECT COUNT(*) FROM products"))
        product_count = result.fetchone()[0]
        print(f"✓ Productos en BD: {product_count}")

        # Contar ventas
        result = conn.execute(text("SELECT COUNT(*) FROM sales"))
        sales_count = result.fetchone()[0]
        print(f"✓ Ventas en BD: {sales_count}")

        # Mostrar algunos productos
        result = conn.execute(text("SELECT id, name, category, price FROM products LIMIT 5"))
        print("\nPrimeros 5 productos:")
        for row in result:
            print(f"  - {row[1]} ({row[2]}) - ${row[3]}")

        # Mostrar estadísticas de ventas
        result = conn.execute(
            text(
                """
                SELECT 
                    country,
                    COUNT(*) as total_ventas,
                    SUM(revenue) as total_revenue
                FROM sales
                GROUP BY country
                ORDER BY total_revenue DESC
                LIMIT 5
                """
            )
        )
        print("\nTop 5 países por revenue:")
        for row in result:
            print(f"  - {row[0]}: {row[1]} ventas, ${row[2]:.2f} revenue")


def main():
    """Función principal."""
    print("=" * 60, flush=True)
    print("Generador de Datos de Prueba para LLM Data Warehouse", flush=True)
    print("=" * 60, flush=True)

    # Crear engine
    connection_string = get_connection_string()
    print(f"\nConectando a: postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        engine = create_engine(connection_string, echo=False)

        # Probar conexión
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Conexión exitosa\n")

        # Crear tablas
        create_tables(engine)

        # Generar productos
        product_ids = generate_products(engine, num_products=20)

        # Generar ventas
        generate_sales(engine, product_ids, num_sales=200)

        # Verificar datos
        verify_data(engine)

        print("\n" + "=" * 60)
        print("✓ Datos de prueba generados exitosamente!")
        print("=" * 60)
        print("\nAhora puedes actualizar tu .env con:")
        print(f"DATABASE_URL={connection_string}")
        print("\nY probar el sistema con:")
        print('python -m src.cli query "¿Cuál es el total de revenue por país?"')

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nVerifica:")
        print("  1. Que PostgreSQL esté corriendo")
        print("  2. Que las credenciales sean correctas")
        print("  3. Que la base de datos exista")
        raise


if __name__ == "__main__":
    main()
