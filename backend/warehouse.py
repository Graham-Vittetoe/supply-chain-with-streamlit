import pandas as pd
from database.db import get_connection, DB_PATH


def get_warehouse_overview(supplier_id: int) -> pd.DataFrame:
    """
    Returns capacity, stock utilization, low-stock counts, delivery performance,
    and average transit times per warehouse for the active supplier.
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        query = """
            WITH StockStats AS (
                SELECT
                    w.WarehouseID,
                    w.WarehouseName,
                    w.Address,
                    w.Coordinates,
                    COALESCE(w.Capacity, 0) AS Capacity,
                    COALESCE(SUM(i.QuantityOnHand), 0) AS UnitsStored,
                    SUM(CASE WHEN i.QuantityOnHand <= i.ReorderLevel THEN 1 ELSE 0 END) AS LowStockCount
                FROM Warehouses w
                LEFT JOIN Inventory i ON w.WarehouseID = i.WarehouseID
                WHERE w.SupplierID = ?
                GROUP BY w.WarehouseID
            ),
            ShipStats AS (
                SELECT
                    OriginWarehouse,
                    COUNT(ShipmentID) AS TotalShipments,
                    ROUND(AVG(TransitHours), 1) AS AvgTransitHours,
                    SUM(CASE WHEN DeliveryHealth = 'ON TIME' AND ActualArrival IS NOT NULL THEN 1 ELSE 0 END) AS OnTimeCount,
                    SUM(CASE WHEN ActualArrival IS NOT NULL THEN 1 ELSE 0 END) AS DeliveredCount,
                    SUM(CASE WHEN DeliveryHealth IN ('DELAYED', 'DELIVERED LATE') THEN 1 ELSE 0 END) AS DelayedCount
                FROM vw_SupplierOrderTracking
                WHERE SupplierID = ? AND OriginWarehouse IS NOT NULL
                GROUP BY OriginWarehouse
            )
            SELECT
                st.WarehouseID,
                st.WarehouseName,
                st.Address,
                st.Coordinates,
                st.Capacity,
                st.UnitsStored,
                COALESCE(st.LowStockCount, 0) AS LowStockCount,
                COALESCE(sh.TotalShipments, 0) AS TotalShipments,
                COALESCE(sh.AvgTransitHours, 0.0) AS AvgTransitHours,
                CASE
                    WHEN COALESCE(sh.DeliveredCount, 0) = 0 THEN 100.0
                    ELSE ROUND((sh.OnTimeCount * 100.0) / sh.DeliveredCount, 1)
                END AS OnTimeRate,
                COALESCE(sh.DelayedCount, 0) AS DelayedCount
            FROM StockStats st
            LEFT JOIN ShipStats sh ON st.WarehouseName = sh.OriginWarehouse
            ORDER BY st.WarehouseName ASC
        """
        return pd.read_sql_query(query, conn, params=(supplier_id, supplier_id))
    except Exception as e:
        print(f"Error in get_warehouse_overview(): {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def get_supplier_inventory(supplier_id: int) -> pd.DataFrame:
    """
    Returns full per-warehouse stock levels, valuations, reorder thresholds,
    and computed stock health status across all facilities owned by the supplier.
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        query = """
            SELECT
                w.WarehouseID,
                w.WarehouseName AS "Warehouse",
                p.ProductID,
                p.SKU,
                p.ProductName AS "Product",
                p.UnitPrice AS "Unit Price ($)",
                i.QuantityOnHand AS "On Hand",
                i.ReorderLevel AS "Reorder Level",
                ROUND(i.QuantityOnHand * p.UnitPrice, 2) AS "Stock Value ($)",
                CASE
                    WHEN i.QuantityOnHand = 0 THEN 'Out of Stock'
                    WHEN i.QuantityOnHand <= i.ReorderLevel THEN 'Low Stock'
                    ELSE 'Healthy'
                END AS "Stock Status",
                i.UpdatedAt AS "Last Updated"
            FROM Inventory i
            JOIN Warehouses w ON i.WarehouseID = w.WarehouseID
            JOIN Products p ON i.ProductID = p.ProductID
            WHERE w.SupplierID = ?
            ORDER BY
                CASE
                    WHEN i.QuantityOnHand = 0 THEN 1
                    WHEN i.QuantityOnHand <= i.ReorderLevel THEN 2
                    ELSE 3
                END,
                w.WarehouseName ASC,
                p.ProductName ASC
        """
        return pd.read_sql_query(query, conn, params=(supplier_id,))
    except Exception as e:
        print(f"Error in get_supplier_inventory(): {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def restock_inventory(warehouse_id: int, product_id: int, added_qty: int) -> bool:
    """
    Adds incoming units to a specific warehouse and updates UpdatedAt.
    Uses UPSERT so it works even if the SKU wasn't previously stocked in that facility.
    """
    if added_qty <= 0:
        return False

    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO Inventory (WarehouseID, ProductID, QuantityOnHand, UpdatedAt)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(WarehouseID, ProductID) DO UPDATE SET
                QuantityOnHand = Inventory.QuantityOnHand + excluded.QuantityOnHand,
                UpdatedAt = datetime('now')
            """,
            (warehouse_id, product_id, added_qty),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error in restock_inventory(): {e}")
        return False
    finally:
        if conn:
            conn.close()


def update_reorder_level(warehouse_id: int, product_id: int, new_reorder_level: int) -> bool:
    """Updates the reorder threshold for a specific SKU at a warehouse."""
    if new_reorder_level < 0:
        return False

    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE Inventory
            SET ReorderLevel = ?,
                UpdatedAt = datetime('now')
            WHERE WarehouseID = ? AND ProductID = ?
            """,
            (new_reorder_level, warehouse_id, product_id),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error in update_reorder_level(): {e}")
        return False
    finally:
        if conn:
            conn.close()


def transfer_inventory(
    from_warehouse_id: int,
    to_warehouse_id: int,
    product_id: int,
    qty: int,
) -> tuple[bool, str]:

    if from_warehouse_id == to_warehouse_id:
        return False, "Source and destination warehouses must be different."
    if qty <= 0:
        return False, "Transfer quantity must be greater than zero."

    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT QuantityOnHand FROM Inventory
            WHERE WarehouseID = ? AND ProductID = ?
            """,
            (from_warehouse_id, product_id),
        )
        row = cur.fetchone()
        if not row or row["QuantityOnHand"] < qty:
            available = row["QuantityOnHand"] if row else 0
            return False, f"Insufficient stock in source warehouse ({available} available)."

        # Deduct from source
        cur.execute(
            """
            UPDATE Inventory
            SET QuantityOnHand = QuantityOnHand - ?,
                UpdatedAt = datetime('now')
            WHERE WarehouseID = ? AND ProductID = ?
            """,
            (qty, from_warehouse_id, product_id),
        )

        # Add to destination (or create row if new to that warehouse)
        cur.execute(
            """
            INSERT INTO Inventory (WarehouseID, ProductID, QuantityOnHand, UpdatedAt)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(WarehouseID, ProductID) DO UPDATE SET
                QuantityOnHand = Inventory.QuantityOnHand + excluded.QuantityOnHand,
                UpdatedAt = datetime('now')
            """,
            (to_warehouse_id, product_id, qty),
        )

        conn.commit()
        return True, f"Transferred {qty} units successfully."
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error in transfer_inventory(): {e}")
        return False, f"Database error: {e}"
    finally:
        if conn:
            conn.close()


def deduct_inventory_for_order(warehouse_id: int, order_id: int) -> tuple[bool, str]:
    """
    Deducts all Order_Items quantities from a warehouse when dispatching a shipment.
    Rolls back the entire transaction if any item lacks sufficient stock.
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT oi.ProductID, p.SKU, oi.Quantity, COALESCE(i.QuantityOnHand, 0) AS Available
            FROM Order_Items oi
            JOIN Products p ON oi.ProductID = p.ProductID
            LEFT JOIN Inventory i ON i.ProductID = oi.ProductID AND i.WarehouseID = ?
            WHERE oi.OrderID = ?
            """,
            (warehouse_id, order_id),
        )
        items = cur.fetchall()
        if not items:
            return False, f"No line items found for Order #{order_id}."

        # Pre-flight stock check across all line items
        shortages = [
            f"{item['SKU']} (need {item['Quantity']}, have {item['Available']})"
            for item in items
            if item["Available"] < item["Quantity"]
        ]
        if shortages:
            return False, "Insufficient stock for: " + ", ".join(shortages)

        for item in items:
            cur.execute(
                """
                UPDATE Inventory
                SET QuantityOnHand = QuantityOnHand - ?,
                    UpdatedAt = datetime('now')
                WHERE WarehouseID = ? AND ProductID = ?
                """,
                (item["Quantity"], warehouse_id, item["ProductID"]),
            )

        conn.commit()
        return True, f"Inventory deducted for Order #{order_id}."
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error in deduct_inventory_for_order(): {e}")
        return False, f"Database error: {e}"
    finally:
        if conn:
            conn.close()