from database.db import get_connection, DB_PATH
import pandas as pd


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

#returns total, active, completed, revenue metrics
def get_dashboard_metrics(supplierID: int) -> list[str]:
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        metrics = []

        #total orders
        cur.execute("""
            SELECT COUNT(SupplierID) FROM Orders WHERE SupplierID = ?
        """, (supplierID,))
        metrics.append(cur.fetchone()[0])

        #active orders
        cur.execute("""
            SELECT COUNT(SupplierID) FROM Orders WHERE Status != "Completed" AND SupplierID = ?
        """, (supplierID,))
        metrics.append(cur.fetchone()[0])

        #completed
        cur.execute("""
            SELECT COUNT(SupplierID) FROM Orders WHERE Status = "Completed" AND SupplierID = ?
        """, (supplierID,))
        metrics.append(cur.fetchone()[0])

        #products sold
        cur.execute("""
            SELECT 
            COALESCE(SUM(i.quantity),0)
            FROM order_items as i
            RIGHT JOIN Orders as o on o.orderID = i.orderID
            WHERE o.supplierID = ?
        """, (supplierID,))
        metrics.append(cur.fetchone()[0])


        #revenue
        cur.execute("""
            SELECT 
            COALESCE(SUM(i.quantity * i.unitPrice),0)
            FROM order_items as i
            RIGHT JOIN Orders as o on o.orderID = i.orderID
            WHERE o.supplierID = ?
        """, (supplierID,))
        metrics.append(cur.fetchone()[0])

        conn.close()
        return metrics

    except Exception as e:
        print(f"Error: could not complete get_dashboard_metrics() - {e}")
        return [0,0,0,0,0]

def get_active_orders(supplier_id: int) -> pd.DataFrame:
    try:
        conn = get_connection(DB_PATH)
        query = """
            SELECT 
                o.orderID AS "Order ID",
                o.OrderDate AS "Order Date",
                o.Status AS "Status",
                COUNT(i.orderID) AS "Line Items",
                ROUND(COALESCE(SUM(i.quantity * i.unitPrice), 0), 2) AS "Order Total ($)"
            FROM Orders AS o
            LEFT JOIN order_items AS i ON o.orderID = i.orderID
            WHERE o.SupplierID = ? AND o.Status != 'Completed'
            GROUP BY o.orderID
            ORDER BY o.OrderDate ASC
        """
        df = pd.read_sql_query(query, conn, params=(supplier_id,))
        conn.close()
        return df
    except Exception as e:
        print(f"Error loading active orders: {e}")
        return pd.DataFrame()

def update_order_status(order_id: int, new_status: str) -> bool:
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE Orders SET Status = ? WHERE orderID = ?",
            (new_status, order_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating order status: {e}")
        return False

def get_supplier_alerts(supplier_id: int) -> dict[str, pd.DataFrame]:
    conn = None
    try:
        conn = get_connection(DB_PATH)

        # 1. Shipment exceptions from your view
        shipments_df = pd.read_sql_query(
            """
            SELECT
                OrderID,
                CustomerName,
                OriginWarehouse,
                DeliveryHealth,
                EstimatedArrival
            FROM vw_SupplierOrderTracking
            WHERE SupplierID = ?
              AND OrderStatus NOT IN ('Completed', 'Cancelled')
              AND DeliveryHealth IN ('DELAYED', 'UNSCHEDULED')
            ORDER BY
                CASE DeliveryHealth WHEN 'DELAYED' THEN 1 ELSE 2 END,
                EstimatedArrival ASC
            """,
            conn,
            params=(supplier_id,),
        )

        # 2. Low-stock items across warehouses
        stock_df = pd.read_sql_query(
            """
            SELECT
                p.SKU,
                p.ProductName,
                w.WarehouseName,
                i.QuantityOnHand,
                i.ReorderLevel
            FROM Inventory i
            JOIN Products p ON i.ProductID = p.ProductID
            JOIN Warehouses w ON i.WarehouseID = w.WarehouseID
            WHERE p.SupplierID = ?
              AND i.QuantityOnHand <= i.ReorderLevel
            ORDER BY (i.QuantityOnHand - i.ReorderLevel) ASC
            """,
            conn,
            params=(supplier_id,),
        )

        # 3. Fleet vehicles offline for maintenance
        fleet_df = pd.read_sql_query(
            """
            SELECT
                LicensePlate,
                VehicleType,
                Status
            FROM Vehicles
            WHERE SupplierID = ?
              AND Status = 'Maintenance'
            """,
            conn,
            params=(supplier_id,),
        )

        return {
            "shipments": shipments_df,
            "stock": stock_df,
            "fleet": fleet_df,
        }

    except Exception as e:
        print(f"Error loading alerts: {e}")
        return {
            "shipments": pd.DataFrame(),
            "stock": pd.DataFrame(),
            "fleet": pd.DataFrame(),
        }
    finally:
        if conn:
            conn.close()

