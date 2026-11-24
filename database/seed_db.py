import sqlite3
from pathlib import Path
from db import init_db, get_connection, DB_PATH


def seed_db(db_path: Path | str = DB_PATH) -> None:
    """Initialize schema and populate realistic sample data for a Supplier Portal."""
    init_db(db_path)
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        # Check if sample data already exists to prevent duplicate seeding
        cursor.execute("SELECT COUNT(*) FROM Suppliers;")
        if cursor.fetchone()[0] > 0:
            print("Database already contains data. Skipping seed.")
            return

        # 1. Suppliers (Login Accounts)
        suppliers = [
            (1, "Bluegrass Logistics & Supply", "demo@bluegrasssupply.com", "hashed_password_123", "36.6103,-88.3148"),
            (2, "Midwest Industrial Goods", "ops@midwestgoods.com", "hashed_password_456", "38.2527,-85.7585"),
        ]
        cursor.executemany(
            """
            INSERT INTO Suppliers (SupplierID, CompanyName, Email, PasswordHash, HQCoordinates)
            VALUES (?, ?, ?, ?, ?);
            """,
            suppliers,
        )

        # 2. Warehouses
        warehouses = [
            (1, 1, "Murray Central Hub", "104 Industrial Pkwy, Murray, KY", "36.6215,-88.3102", 5000),
            (2, 1, "Nashville Distribution Center", "450 Freight Way, Nashville, TN", "36.1627,-86.7816", 12000),
            (3, 2, "Louisville Riverport Depot", "890 River Rd, Louisville, KY", "38.2542,-85.7594", 8000),
        ]
        cursor.executemany(
            """
            INSERT INTO Warehouses (WarehouseID, SupplierID, WarehouseName, Address, Coordinates, Capacity)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            warehouses,
        )

        # 3. Products
        products = [
            (1, 1, "Heavy-Duty Pallet Jack", "Hydraulic 5500 lb capacity pallet truck", "BG-PJ-001", 349.99),
            (2, 1, "Industrial Stretch Wrap (4-Pack)", "18 in x 1500 ft 80-gauge cast film", "BG-SW-002", 89.50),
            (3, 1, "Reinforced Shipping Crates", "Heat-treated wooden transport crate", "BG-SC-003", 64.00),
            (4, 1, "Thermal Barcode Label Rolls", "4x6 direct thermal shipping labels (1000/roll)", "BG-LB-004", 24.99),
            (5, 2, "Steel Shelving Unit", "5-tier boltless industrial storage rack", "MW-SS-101", 179.00),
        ]
        cursor.executemany(
            """
            INSERT INTO Products (ProductID, SupplierID, ProductName, Description, SKU, UnitPrice)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            products,
        )

        # 4. Inventory
        inventory = [
            (1, 1, 45, 10),   # Murray Hub: Pallet Jacks (Healthy)
            (1, 2, 12, 20),   # Murray Hub: Stretch Wrap (Low Stock!)
            (1, 3, 120, 30),  # Murray Hub: Crates (Healthy)
            (2, 1, 80, 15),   # Nashville DC: Pallet Jacks
            (2, 4, 8, 25),    # Nashville DC: Barcode Labels (Low Stock!)
            (3, 5, 60, 15),   # Louisville Depot: Steel Shelving
        ]
        cursor.executemany(
            """
            INSERT INTO Inventory (WarehouseID, ProductID, QuantityOnHand, ReorderLevel)
            VALUES (?, ?, ?, ?);
            """,
            inventory,
        )

        # 5. Customers
        customers = [
            (1, "Acme Manufacturing Co.", "receiving@acmemfg.com", "220 Factory Ln, Paducah, KY", "37.0834,-88.6000"),
            (2, "Cumberland Retail Group", "logistics@cumberlandretail.com", "710 Commerce St, Clarksville, TN", "36.5298,-87.3595"),
            (3, "Heartland Fulfillment Partners", "orders@heartlandfp.com", "1500 Logistics Blvd, Memphis, TN", "35.1495,-90.0490"),
            (4, "Ohio Valley Hardware", "purchasing@ovhardware.com", "330 Main St, Evansville, IN", "37.9716,-87.5711"),
        ]
        cursor.executemany(
            """
            INSERT INTO Customers (CustomerID, CustomerName, Email, ShippingAddress, ShippingCoordinates)
            VALUES (?, ?, ?, ?, ?);
            """,
            customers,
        )

        # 6. Vehicles
        vehicles = [
            (1, 1, "KY-4829-TR", "26ft Box Truck", 10000.0, "In Transit"),
            (2, 1, "KY-9104-VN", "Sprinter Cargo Van", 3500.0, "Available"),
            (3, 1, "TN-7731-Semi", "53ft Dry Van Trailer", 45000.0, "In Transit"),
            (4, 2, "KY-3310-TR", "26ft Box Truck", 10000.0, "Available"),
        ]
        cursor.executemany(
            """
            INSERT INTO Vehicles (VehicleID, SupplierID, LicensePlate, VehicleType, Capacity, Status)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            vehicles,
        )

        # 7. Drivers
        drivers = [
            (1, 1, "Marcus Vance", "CDL-KY-88412", "270-555-0142", "On Duty"),
            (2, 1, "Elena Rostova", "CDL-TN-55209", "615-555-0198", "On Duty"),
            (3, 1, "Devon Brooks", "CDL-KY-30914", "270-555-0177", "Available"),
            (4, 2, "Hannah Abbott", "CDL-KY-77410", "502-555-0111", "Available"),
        ]
        cursor.executemany(
            """
            INSERT INTO Drivers (DriverID, SupplierID, DriverName, LicenseNumber, Phone, Status)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            drivers,
        )

        # 8. Orders (Covers Completed, Delayed, On-Time In Transit, and Unscheduled Pending)
        orders = [
            # Order 1: Completed & Delivered On Time
            (1, 1, 1, "2026-11-18 08:30:00", "Completed"),
            # Order 2: Active & DELAYED (EstimatedArrival is in the past, ActualArrival is NULL)
            (2, 1, 2, "2026-11-20 10:15:00", "Shipped"),
            # Order 3: Active & ON TIME (In Transit, EstimatedArrival is in the future)
            (3, 1, 3, "2026-11-22 14:00:00", "Shipped"),
            # Order 4: Pending / Unscheduled (Not yet assigned a shipment)
            (4, 1, 4, "2026-11-23 09:45:00", "Pending"),
            # Order 5: Belongs to Supplier 2 (Tests multi-tenant isolation)
            (5, 2, 1, "2026-11-21 11:00:00", "Processing"),
        ]
        cursor.executemany(
            """
            INSERT INTO Orders (OrderID, SupplierID, CustomerID, OrderDate, Status)
            VALUES (?, ?, ?, ?, ?);
            """,
            orders,
        )

        # 9. Order_Items
        order_items = [
            (1, 1, 2, 349.99),
            (1, 2, 5, 89.50),
            (2, 3, 20, 64.00),
            (3, 1, 4, 349.99),
            (3, 4, 10, 24.99),
            (4, 2, 15, 89.50),
            (5, 5, 6, 179.00),
        ]
        cursor.executemany(
            """
            INSERT INTO Order_Items (OrderID, ProductID, Quantity, UnitPrice)
            VALUES (?, ?, ?, ?);
            """,
            order_items,
        )

        # 10. Shipments
        shipments = [
            # Shipment 1: Delivered on time (3.5 hours transit)
            (1, 1, 1, "Delivered", "2026-11-18 09:00:00", "2026-11-18 14:00:00", "2026-11-18 12:30:00"),
            # Shipment 2: Delayed in transit (ETA passed yesterday, still not arrived)
            (2, 2, 1, "Delayed", "2026-11-21 07:30:00", "2026-11-22 16:00:00", None),
            # Shipment 3: On-time multi-leg shipment currently in transit
            (3, 3, 2, "In Transit", "2026-11-23 06:00:00", "2026-11-24 18:00:00", None),
        ]
        cursor.executemany(
            """
            INSERT INTO Shipments (ShipmentID, OrderID, WarehouseID, Status, DispatchedAt, EstimatedArrival, ActualArrival)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            shipments,
        )

        # 11. Shipment_Legs
        shipment_legs = [
            # Single-leg completed delivery for Shipment 1
            (1, 1, 1, 2, 1, "36.6215,-88.3102", "37.0834,-88.6000", "2026-11-18 09:00:00", "2026-11-18 12:30:00", "Completed"),
            # Delayed single-leg transit for Shipment 2
            (2, 2, 1, 1, 1, "36.6215,-88.3102", "36.5298,-87.3595", "2026-11-21 07:30:00", None, "Delayed"),
            # Multi-leg transit for Shipment 3 (Leg 1 completed, Leg 2 in transit)
            (3, 3, 2, 3, 1, "36.1627,-86.7816", "35.6145,-88.8139", "2026-11-23 06:00:00", "2026-11-23 10:15:00", "Completed"),
            (4, 3, 2, 3, 2, "35.6145,-88.8139", "35.1495,-90.0490", "2026-11-23 11:00:00", None, "In Transit"),
        ]
        cursor.executemany(
            """
            INSERT INTO Shipment_Legs (
                LegID, ShipmentID, DriverID, VehicleID, LegSequence,
                StartCoordinates, EndCoordinates, DepartedAt, ArrivedAt, Status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            shipment_legs,
        )

        conn.commit()
        print(f"Sample data loaded successfully into: {Path(db_path).resolve()}")

    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to seed database: {e}") from e
    finally:
        conn.close()


if __name__ == "__main__":
    seed_db()

    # Quick verification preview of what Supplier 1 sees on login
    conn = get_connection()
    rows = conn.execute(
        "SELECT OrderID, CustomerName, OrderStatus, ShipmentStatus, DeliveryHealth, TransitHours "
        "FROM vw_SupplierOrderTracking WHERE SupplierID = 1;"
    ).fetchall()
    print("\n--- Supplier 1 Dashboard Preview ---")
    for row in rows:
        print(dict(row))
    conn.close()
