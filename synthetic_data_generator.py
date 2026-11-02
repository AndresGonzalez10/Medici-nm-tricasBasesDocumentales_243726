"""
synthetic_data_generator.py
BDA en la Nube 2026 — IT2iD | Universidad Politécnica de Chiapas

Punto de Venta de Cafetería (POS):
Genera catálogos del sistema (usuarios, productos, recetas, insumos, cortes_caja)
y 500,000 documentos de VENTAS anidadas para el benchmark en MongoDB y PostgreSQL.

Uso:
  python synthetic_data_generator.py --target mongo   --batch 5000
  python synthetic_data_generator.py --target postgres --batch 5000
  python synthetic_data_generator.py --target both    --batch 5000
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from faker import Faker
from pymongo import MongoClient, InsertOne
from tqdm import tqdm

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "benchmark"
PG_DSN = "host=localhost port=5432 dbname=benchmark user=bench password=bench1234"

TOTAL_RECORDS = 500_000
DEFAULT_BATCH = 5_000

# ─────────────────────────────────────────
# Catálogos de Cafetería
# ─────────────────────────────────────────
CATEGORIES = [
    "cafe_caliente", "cafe_frio", "reposteria", "panaderia",
    "alimentos_preparados", "bebidas_especiales", "combos_desayuno",
    "te_infusiones", "snacks", "cafe_grano"
]

CAFE_PRODUCTS = [
    ("Espresso Chiapaneco", "cafe_caliente", 38.00),
    ("Americano Tostado Intenso", "cafe_caliente", 45.00),
    ("Cappuccino Tradicional", "cafe_caliente", 58.00),
    ("Latte Vainilla y Canela", "cafe_caliente", 65.00),
    ("Mocha Chocolate Oscuro", "cafe_caliente", 68.00),
    ("Cold Brew Nitro", "cafe_frio", 72.00),
    ("Iced Caramel Macchiato", "cafe_frio", 75.00),
    ("Frappé Moka Avellana", "cafe_frio", 78.00),
    ("Matcha Latte Frito", "bebidas_especiales", 82.00),
    ("Chai Latte Especiado", "bebidas_especiales", 64.00),
    ("Croissant de Mantequilla", "panaderia", 42.00),
    ("Panqué de Plátano y Nuez", "panaderia", 48.00),
    ("Muffin de Arándanos", "reposteria", 52.00),
    ("Cheesecake Frutos Rojos", "reposteria", 79.00),
    ("Bagel Jamón Serrano y Queso", "alimentos_preparados", 89.00),
    ("Ciabatta Pavo y Pesto", "alimentos_preparados", 95.00),
    ("Combo Desayuno Artesanal", "combos_desayuno", 135.00),
    ("Combo Brunch Cafetero", "combos_desayuno", 155.00),
    ("Té Verde Jazmín", "te_infusiones", 45.00),
    ("Bolsa Café de Altura 500g", "cafe_grano", 195.00),
]

PAYMENT_METHODS = ["efectivo", "tarjeta_debito", "tarjeta_credito", "transferencia", "monedero_digital"]
PAYMENT_STATUSES = ["completed", "completed", "completed", "refunded"]  # Mayoría completed
CHANNELS = ["pos_caja_1", "pos_caja_2", "barra_takeaway", "mesas_sala", "app_pickup"]
TIERS = ["estudiante", "frecuente", "vip", "general"]
DISCOUNT_CODES = ["PROMO_MANANA", "DESCUENTO_ESTUDIANTE", "LEALTAD10", "", "", ""]


# ─────────────────────────────────────────
# Generador de una Venta de Cafetería
# ─────────────────────────────────────────
def make_order(fake: Faker) -> dict:
    num_items = random.randint(1, 5)  # Promedio ~3 ítems
    items = []
    subtotal = 0.0

    for _ in range(num_items):
        prod_name, category, base_price = random.choice(CAFE_PRODUCTS)
        qty = random.randint(1, 4)
        price = round(base_price * random.uniform(0.95, 1.10), 2)
        tax_pct = 0.16
        discount = random.choice(DISCOUNT_CODES)
        subtotal += qty * price

        items.append({
            "sku": f"CAFE-{random.randint(100, 999)}",
            "name": prod_name,
            "category": category,
            "qty": qty,
            "price": price,
            "tax_pct": tax_pct,
            "discounts": [discount] if discount else [],
        })

    tax_amount = round(subtotal * 0.16, 2)
    final_total = round(subtotal + tax_amount, 2)

    # Rango de fechas entre 2025 y 2026
    start_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_dt   = datetime(2026, 10, 31, tzinfo=timezone.utc)
    ts = start_dt + timedelta(seconds=random.randint(0, int((end_dt - start_dt).total_seconds())))

    return {
        "order_id": str(uuid.uuid4()),
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "customer": {
            "id": f"cli-{fake.numerify('#####')}",
            "tier": random.choice(TIERS),
            "segment": "consumo_cafeteria",
            "geo": {
                "country": "MX",
                "state": "Chiapas",
                "city": "Tuxtla Gutiérrez",
                "zip": "29000",
                "coordinates": {"lat": 16.753, "lon": -93.116}
            }
        },
        "items": items,
        "payment": {
            "method": random.choice(PAYMENT_METHODS),
            "status": random.choice(PAYMENT_STATUSES),
            "transaction_id": f"tx-{uuid.uuid4().hex[:10]}",
            "gateway_latency_ms": random.randint(30, 400),
            "subtotal": round(subtotal, 2),
            "tax": tax_amount,
            "final_total": final_total,
        },
        "metadata": {
            "channel": random.choice(CHANNELS),
            "user_agent": "Cafeteria-POS-Terminal/2.4",
            "session_id": f"caja-ses-{random.randint(1, 5)}",
            "flags": {
                "para_llevar": random.random() < 0.40,
                "requiere_factura": random.random() < 0.15
            }
        }
    }


# ─────────────────────────────────────────
# Poblar Catálogos de Cafetería
# ─────────────────────────────────────────
def seed_pos_catalogs(mongo_client=None, pg_conn=None):
    print("\n[*] Inicializando catalogos del POS (usuarios, insumos, productos, recetas)...")
    
    # 1. Usuarios con PIN
    usuarios = [
        {"usuario_id": "usr-1", "nombre": "Admin Principal", "rol": "administrador", "pin_autorizacion": "1234"},
        {"usuario_id": "usr-2", "nombre": "Carlos Mesero", "rol": "mesero", "pin_autorizacion": "0000"},
        {"usuario_id": "usr-3", "nombre": "Sofia Barista", "rol": "barra", "pin_autorizacion": "0000"},
        {"usuario_id": "usr-4", "nombre": "Laura Cajera", "rol": "cajero", "pin_autorizacion": "0000"}
    ]

    # 2. Insumos
    insumos = [
        {"insumo_id": "ins-1", "nombre": "Granos Café Chiapas", "stock_kg": 150.0, "costo_kg": 180.0},
        {"insumo_id": "ins-2", "nombre": "Leche Entera", "stock_litros": 80.0, "costo_litro": 26.0},
        {"insumo_id": "ins-3", "nombre": "Leche Avena / Almendra", "stock_litros": 40.0, "costo_litro": 45.0},
        {"insumo_id": "ins-4", "nombre": "Jarabe Vainilla", "stock_litros": 20.0, "costo_litro": 120.0},
        {"insumo_id": "ins-5", "nombre": "Vaso Biodegradable 16oz", "stock_pzas": 1200, "costo_pza": 3.5}
    ]

    # Insertar en Mongo si está conectado
    if mongo_client:
        db = mongo_client[MONGO_DB]
        db["usuarios"].delete_many({})
        db["usuarios"].insert_many(usuarios)
        db["insumos"].delete_many({})
        db["insumos"].insert_many(insumos)
        print("  [+] Catalogos sincronizados en MongoDB.")

    # Insertar en Postgres si está conectado
    if pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (id VARCHAR PRIMARY KEY, data JSONB);
                CREATE TABLE IF NOT EXISTS insumos  (id VARCHAR PRIMARY KEY, data JSONB);
                DELETE FROM usuarios;
                DELETE FROM insumos;
            """)
            for u in usuarios:
                cur.execute("INSERT INTO usuarios VALUES (%s, %s::jsonb)", (u["usuario_id"], json.dumps(u)))
            for i in insumos:
                cur.execute("INSERT INTO insumos VALUES (%s, %s::jsonb)", (i["insumo_id"], json.dumps(i)))
            pg_conn.commit()
            print("  [+] Catalogos sincronizados en PostgreSQL.")


# ─────────────────────────────────────────
# Inserción en MongoDB
# ─────────────────────────────────────────
def insert_mongo(total: int, batch_size: int, seed: int = 42) -> None:
    random.seed(seed)
    Faker.seed(seed)
    fake = Faker()
    client = MongoClient(MONGO_URI)
    col = client[MONGO_DB]["orders"]  # usamos orders para alineación con las queries

    seed_pos_catalogs(mongo_client=client)

    col.drop()
    col.create_index("timestamp")
    col.create_index("order_id", unique=True)

    print(f"\n[MongoDB] Insertando {total:,} ventas de cafetería en lotes de {batch_size:,}...")
    with tqdm(total=total, unit="doc", desc="MongoDB") as pbar:
        for offset in range(0, total, batch_size):
            size = min(batch_size, total - offset)
            ops = [InsertOne(make_order(fake)) for _ in range(size)]
            col.bulk_write(ops, ordered=False)
            pbar.update(size)

    print(f"[MongoDB] [+] {total:,} ventas insertadas exitosamente.")
    client.close()


# ─────────────────────────────────────────
# Inserción en PostgreSQL
# ─────────────────────────────────────────
def insert_postgres(total: int, batch_size: int, seed: int = 42) -> None:
    random.seed(seed)
    Faker.seed(seed)
    fake = Faker()
    conn = psycopg2.connect(PG_DSN)

    seed_pos_catalogs(pg_conn=conn)

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS orders CASCADE;")
        cur.execute("""
            CREATE TABLE orders (
                id   UUID PRIMARY KEY,
                data JSONB NOT NULL
            );
            CREATE INDEX idx_orders_timestamp
            ON orders ((data->>'timestamp'));
        """)
        conn.commit()

    print(f"\n[PostgreSQL] Insertando {total:,} ventas de cafetería en lotes de {batch_size:,}...")
    with tqdm(total=total, unit="doc", desc="PostgreSQL") as pbar:
        for offset in range(0, total, batch_size):
            size = min(batch_size, total - offset)
            docs = [make_order(fake) for _ in range(size)]
            rows = [(doc["order_id"], json.dumps(doc)) for doc in docs]
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO orders (id, data) VALUES %s ON CONFLICT DO NOTHING",
                    rows,
                    template="(%s, %s::jsonb)",
                    page_size=batch_size,
                )
            conn.commit()
            pbar.update(size)

    print(f"[PostgreSQL] [+] {total:,} ventas insertadas exitosamente.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Generador POS Cafeteria -- BDA 2026")
    parser.add_argument("--target", choices=["mongo", "postgres", "both"], default="both")
    parser.add_argument("--total", type=int, default=TOTAL_RECORDS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    args = parser.parse_args()

    print("=" * 65)
    print("  Punto de Venta de Cafeteria -- Generador de Datos del Benchmark")
    print("=" * 65)
    print(f"  Destino : {args.target}")
    print(f"  Total   : {args.total:,} ventas")
    print(f"  Lote    : {args.batch:,} registros/lote")
    print("=" * 65)

    if args.target in ("mongo", "both"):
        insert_mongo(args.total, args.batch)

    if args.target in ("postgres", "both"):
        insert_postgres(args.total, args.batch)

    print("\n[+] Dataset de Cafeteria generado e insertado.")


if __name__ == "__main__":
    main()
