import pandas as pd
from datetime import datetime, timedelta
from database.db import get_connection, DB_PATH


def get_supplier_shipments(supplier_id: int) -> pd.DataFrame:
    """
    Returns all orders and their associated shipment tracking, transit hours,
    and delivery health status from vw_SupplierOrderTracking.
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        query = """
            SELECT
                OrderID,
                ShipmentID,
                OrderDate,
                OrderStatus,
                CustomerName,
                DestinationCoordinates,
                COALESCE(OriginWarehouse, 'Unassigned') AS OriginWarehouse,
                COALESCE(ShipmentStatus, 'Unscheduled') AS ShipmentStatus,
                DispatchedAt,
                EstimatedArrival,
                ActualArrival,
                TransitHours,
                DeliveryHealth
            FROM vw_SupplierOrderTracking
            WHERE SupplierID = ?
            ORDER BY
                CASE DeliveryHealth
                    WHEN 'DELAYED' THEN 1
                    WHEN 'UNSCHEDULED' THEN 2
                    WHEN 'ON TIME' THEN 3
                    WHEN 'DELIVERED LATE' THEN 4
                    ELSE 5
                END,
                OrderDate DESC
        """
        return pd.read_sql_query(query, conn, params=(supplier_id,))
    except Exception as e:
        print(f"Error in get_supplier_shipments(): {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def get_order_trace(supplier_id: int, order_id: int) -> dict[str, pd.DataFrame]:
    """
    Retrieves the complete end-to-end trace for an order:
    1. Order + Shipment summary (origin warehouse -> customer destination)
    2. Line items (Order_Items + Products)
    3. Multi-leg transit segments (Shipment_Legs + Drivers + Vehicles)
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)

        summary = pd.read_sql_query(
            """
            SELECT
                v.OrderID,
                v.OrderDate,
                v.OrderStatus,
                v.CustomerName,
                c.ShippingAddress,
                v.DestinationCoordinates,
                v.ShipmentID,
                v.OriginWarehouse,
                w.Address AS WarehouseAddress,
                w.Coordinates AS OriginCoordinates,
                v.ShipmentStatus,
                v.DispatchedAt,
                v.EstimatedArrival,
                v.ActualArrival,
                v.TransitHours,
                v.DeliveryHealth
            FROM vw_SupplierOrderTracking v
            JOIN Customers c ON v.CustomerID = c.CustomerID
            LEFT JOIN Shipments s ON v.ShipmentID = s.ShipmentID
            LEFT JOIN Warehouses w ON s.WarehouseID = w.WarehouseID
            WHERE v.SupplierID = ? AND v.OrderID = ?
            """,
            conn,
            params=(supplier_id, order_id),
        )

        items = pd.read_sql_query(
            """
            SELECT
                p.SKU,
                p.ProductName AS "Product",
                oi.Quantity,
                oi.UnitPrice AS "Unit Price ($)",
                ROUND(oi.Quantity * oi.UnitPrice, 2) AS "Line Total ($)"
            FROM Order_Items oi
            JOIN Products p ON oi.ProductID = p.ProductID
            JOIN Orders o ON oi.OrderID = o.OrderID
            WHERE o.SupplierID = ? AND oi.OrderID = ?
            """,
            conn,
            params=(supplier_id, order_id),
        )

        legs = pd.read_sql_query(
            """
            SELECT
                sl.LegSequence AS "Leg",
                sl.Status AS "Leg Status",
                COALESCE(d.DriverName, 'Unassigned') AS "Driver",
                COALESCE(v.LicensePlate || ' (' || v.VehicleType || ')', 'Unassigned') AS "Vehicle",
                sl.StartCoordinates AS "From Coordinates",
                sl.EndCoordinates AS "To Coordinates",
                sl.DepartedAt AS "Departed",
                sl.ArrivedAt AS "Arrived"
            FROM Shipment_Legs sl
            JOIN Shipments s ON sl.ShipmentID = s.ShipmentID
            JOIN Orders o ON s.OrderID = o.OrderID
            LEFT JOIN Drivers d ON sl.DriverID = d.DriverID
            LEFT JOIN Vehicles v ON sl.VehicleID = v.VehicleID
            WHERE o.SupplierID = ? AND s.OrderID = ?
            ORDER BY sl.LegSequence ASC
            """,
            conn,
            params=(supplier_id, order_id),
        )

        return {"summary": summary, "items": items, "legs": legs}
    except Exception as e:
        print(f"Error in get_order_trace(): {e}")
        return {"summary": pd.DataFrame(), "items": pd.DataFrame(), "legs": pd.DataFrame()}
    finally:
        if conn:
            conn.close()


def get_fleet_and_drivers(supplier_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns the supplier's vehicles and drivers."""
    conn = None
    try:
        conn = get_connection(DB_PATH)
        vehicles = pd.read_sql_query(
            """
            SELECT VehicleID, LicensePlate, VehicleType, Capacity, Status
            FROM Vehicles
            WHERE SupplierID = ?
            ORDER BY Status ASC, LicensePlate ASC
            """,
            conn,
            params=(supplier_id,),
        )
        drivers = pd.read_sql_query(
            """
            SELECT DriverID, DriverName, LicenseNumber, Phone, Status
            FROM Drivers
            WHERE SupplierID = ?
            ORDER BY Status ASC, DriverName ASC
            """,
            conn,
            params=(supplier_id,),
        )
        return vehicles, drivers
    except Exception as e:
        print(f"Error in get_fleet_and_drivers(): {e}")
        return pd.DataFrame(), pd.DataFrame()
    finally:
        if conn:
            conn.close()


def dispatch_order(
    supplier_id: int,
    order_id: int,
    warehouse_id: int,
    driver_id: int,
    vehicle_id: int,
    est_transit_hours: int = 48,
) -> tuple[bool, str]:
    """
    Atomically dispatches an order:
    1. Validates sufficient warehouse inventory for all Order_Items
    2. Deducts Inventory.QuantityOnHand
    3. Creates (or updates) the Shipments record as 'In Transit'
    4. Creates an active Shipment_Legs record linking driver, vehicle, and coordinates
    5. Updates Orders.Status to 'Shipped' and marks Driver/Vehicle active
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        # Verify order belongs to supplier and get customer destination coordinates
        cur.execute(
            """
            SELECT o.OrderID, o.Status, c.ShippingCoordinates
            FROM Orders o
            JOIN Customers c ON o.CustomerID = c.CustomerID
            WHERE o.OrderID = ? AND o.SupplierID = ?
            """,
            (order_id, supplier_id),
        )
        order_row = cur.fetchone()
        if not order_row:
            return False, f"Order #{order_id} not found."
        if order_row["Status"] in ("Shipped", "Completed", "Cancelled"):
            return False, f"Order #{order_id} cannot be dispatched (status: {order_row['Status']})."

        # Get origin warehouse coordinates
        cur.execute(
            "SELECT Coordinates FROM Warehouses WHERE WarehouseID = ? AND SupplierID = ?",
            (warehouse_id, supplier_id),
        )
        wh_row = cur.fetchone()
        if not wh_row:
            return False, "Selected warehouse not found."

        # Pre-flight stock check
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
        shortages = [
            f"{r['SKU']} (need {r['Quantity']}, have {r['Available']})"
            for r in items
            if r["Available"] < r["Quantity"]
        ]
        if shortages:
            return False, "Insufficient warehouse stock: " + ", ".join(shortages)

        # Deduct stock
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

        now_dt = datetime.now()
        dispatched_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        est_arrival_str = (now_dt + timedelta(hours=est_transit_hours)).strftime("%Y-%m-%d %H:%M:%S")

        # Check if a 'Preparing' shipment already exists for this order
        cur.execute("SELECT ShipmentID FROM Shipments WHERE OrderID = ?", (order_id,))
        existing_ship = cur.fetchone()

        if existing_ship:
            shipment_id = existing_ship["ShipmentID"]
            cur.execute(
                """
                UPDATE Shipments
                SET WarehouseID = ?,
                    Status = 'In Transit',
                    DispatchedAt = ?,
                    EstimatedArrival = ?
                WHERE ShipmentID = ?
                """,
                (warehouse_id, dispatched_str, est_arrival_str, shipment_id),
            )
            cur.execute("DELETE FROM Shipment_Legs WHERE ShipmentID = ?", (shipment_id,))
        else:
            cur.execute(
                """
                INSERT INTO Shipments (
                    OrderID, WarehouseID, Status, DispatchedAt, EstimatedArrival
                )
                VALUES (?, ?, 'In Transit', ?, ?)
                """,
                (order_id, warehouse_id, dispatched_str, est_arrival_str),
            )
            shipment_id = cur.lastrowid

        # Insert primary transit leg
        cur.execute(
            """
            INSERT INTO Shipment_Legs (
                ShipmentID, DriverID, VehicleID, LegSequence,
                StartCoordinates, EndCoordinates, DepartedAt, Status
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, 'In Transit')
            """,
            (
                shipment_id,
                driver_id,
                vehicle_id,
                wh_row["Coordinates"],
                order_row["ShippingCoordinates"],
                dispatched_str,
            ),
        )

        # Update Order, Driver, and Vehicle statuses
        cur.execute("UPDATE Orders SET Status = 'Shipped' WHERE OrderID = ?", (order_id,))
        cur.execute("UPDATE Drivers SET Status = 'On Duty' WHERE DriverID = ?", (driver_id,))
        cur.execute("UPDATE Vehicles SET Status = 'In Transit' WHERE VehicleID = ?", (vehicle_id,))

        conn.commit()
        return True, f"Order #{order_id} dispatched (Shipment #{shipment_id})."
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error in dispatch_order(): {e}")
        return False, f"Dispatch failed: {e}"
    finally:
        if conn:
            conn.close()


def complete_shipment_delivery(supplier_id: int, shipment_id: int) -> tuple[bool, str]:
    """
    Marks a shipment and all its legs as Delivered/Completed, records ActualArrival
    (enabling TransitHours calculation), marks the Order 'Completed', and releases
    assigned Drivers and Vehicles back to 'Available'.
    """
    conn = None
    try:
        conn = get_connection(DB_PATH)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT s.ShipmentID, s.OrderID, s.Status
            FROM Shipments s
            JOIN Orders o ON s.OrderID = o.OrderID
            WHERE s.ShipmentID = ? AND o.SupplierID = ?
            """,
            (shipment_id, supplier_id),
        )
        ship_row = cur.fetchone()
        if not ship_row:
            return False, f"Shipment #{shipment_id} not found."
        if ship_row["Status"] == "Delivered":
            return False, f"Shipment #{shipment_id} is already delivered."

        arrived_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update Shipment
        cur.execute(
            """
            UPDATE Shipments
            SET Status = 'Delivered',
                ActualArrival = ?
            WHERE ShipmentID = ?
            """,
            (arrived_str, shipment_id),
        )

        # Update Shipment_Legs
        cur.execute(
            """
            UPDATE Shipment_Legs
            SET Status = 'Completed',
                ArrivedAt = COALESCE(ArrivedAt, ?)
            WHERE ShipmentID = ?
            """,
            (arrived_str, shipment_id),
        )

        # Update Order
        cur.execute(
            "UPDATE Orders SET Status = 'Completed' WHERE OrderID = ?",
            (ship_row["OrderID"],),
        )

        # Release assigned Driver(s) and Vehicle(s)
        cur.execute(
            """
            UPDATE Drivers
            SET Status = 'Available'
            WHERE DriverID IN (
                SELECT DISTINCT DriverID FROM Shipment_Legs
                WHERE ShipmentID = ? AND DriverID IS NOT NULL
            )
            """,
            (shipment_id,),
        )
        cur.execute(
            """
            UPDATE Vehicles
            SET Status = 'Available'
            WHERE VehicleID IN (
                SELECT DISTINCT VehicleID FROM Shipment_Legs
                WHERE ShipmentID = ? AND VehicleID IS NOT NULL
            )
            """,
            (shipment_id,),
        )

        conn.commit()
        return True, f"Shipment #{shipment_id} marked Delivered and Order #{ship_row['OrderID']} completed."
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error in complete_shipment_delivery(): {e}")
        return False, f"Completion failed: {e}"
    finally:
        if conn:
            conn.close()