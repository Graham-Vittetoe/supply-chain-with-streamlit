from database.db import get_connection, DB_PATH

def load_supplier_names() -> list[str]:
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        cur.execute("SELECT SupplierID, CompanyName FROM suppliers")
        suppliers = [str(row["CompanyName"]) for row in cur.fetchall()]
        
        conn.close()
        return suppliers
        
    except Exception:
        return ["Error: Could not load suppliers from database"]

def get_supplier_id(supplier_name: str) -> int | None:
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        cur.execute(
            "SELECT SupplierID FROM suppliers WHERE CompanyName = ?",
            (supplier_name,)
        )
        row = cur.fetchone()
        conn.close()

        return int(row["SupplierID"]) if row else None

    except Exception as e:
        print(f"Error: could not complete get_supplier_id() - {e}")
        return None

