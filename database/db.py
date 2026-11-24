import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "supply_chain.db"

SCHEMA_STATEMENTS = [
    # 1. Suppliers (Root Tenant / Authenticated User Account)
    """
    CREATE TABLE IF NOT EXISTS Suppliers (
        SupplierID      INTEGER PRIMARY KEY AUTOINCREMENT,
        CompanyName     TEXT NOT NULL,
        Email           TEXT NOT NULL UNIQUE,
        PasswordHash    TEXT NOT NULL,
        HQCoordinates   TEXT,
        CreatedAt       TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    # 2. Warehouses (Owned/Operated by a Supplier)
    """
    CREATE TABLE IF NOT EXISTS Warehouses (
        WarehouseID     INTEGER PRIMARY KEY AUTOINCREMENT,
        SupplierID      INTEGER NOT NULL,
        WarehouseName   TEXT NOT NULL,
        Address         TEXT,
        Coordinates     TEXT NOT NULL,
        Capacity        INTEGER CHECK (Capacity IS NULL OR Capacity >= 0),
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID) ON DELETE CASCADE
    );
    """,
    # 3. Products (Catalog Items Offered by a Supplier)
    """
    CREATE TABLE IF NOT EXISTS Products (
        ProductID       INTEGER PRIMARY KEY AUTOINCREMENT,
        SupplierID      INTEGER NOT NULL,
        ProductName     TEXT NOT NULL,
        Description     TEXT,
        SKU             TEXT NOT NULL,
        UnitPrice       REAL NOT NULL DEFAULT 0.0 CHECK (UnitPrice >= 0),
        UNIQUE (SupplierID, SKU),
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID) ON DELETE CASCADE
    );
    """,
    # 4. Inventory (Stock Levels per Product per Warehouse)
    """
    CREATE TABLE IF NOT EXISTS Inventory (
        WarehouseID     INTEGER NOT NULL,
        ProductID       INTEGER NOT NULL,
        QuantityOnHand  INTEGER NOT NULL DEFAULT 0 CHECK (QuantityOnHand >= 0),
        ReorderLevel    INTEGER NOT NULL DEFAULT 10 CHECK (ReorderLevel >= 0),
        UpdatedAt       TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (WarehouseID, ProductID),
        FOREIGN KEY (WarehouseID) REFERENCES Warehouses(WarehouseID) ON DELETE CASCADE,
        FOREIGN KEY (ProductID) REFERENCES Products(ProductID) ON DELETE CASCADE
    );
    """,
    # 5. Customers (Buyers Placing Orders with Suppliers)
    """
    CREATE TABLE IF NOT EXISTS Customers (
        CustomerID          INTEGER PRIMARY KEY AUTOINCREMENT,
        CustomerName        TEXT NOT NULL,
        Email               TEXT,
        ShippingAddress     TEXT,
        ShippingCoordinates TEXT NOT NULL
    );
    """,
    # 6. Orders (Customer Orders Fulfilled by a Supplier)
    """
    CREATE TABLE IF NOT EXISTS Orders (
        OrderID         INTEGER PRIMARY KEY AUTOINCREMENT,
        SupplierID      INTEGER NOT NULL,
        CustomerID      INTEGER NOT NULL,
        OrderDate       TEXT NOT NULL DEFAULT (datetime('now')),
        Status          TEXT NOT NULL DEFAULT 'Pending'
                        CHECK (Status IN ('Pending', 'Processing', 'Shipped', 'Completed', 'Cancelled')),
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID) ON DELETE CASCADE,
        FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID) ON DELETE RESTRICT
    );
    """,
    # 7. Order_Items (Line Items per Order)
    """
    CREATE TABLE IF NOT EXISTS Order_Items (
        OrderID         INTEGER NOT NULL,
        ProductID       INTEGER NOT NULL,
        Quantity        INTEGER NOT NULL CHECK (Quantity > 0),
        UnitPrice       REAL NOT NULL CHECK (UnitPrice >= 0),
        PRIMARY KEY (OrderID, ProductID),
        FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
        FOREIGN KEY (ProductID) REFERENCES Products(ProductID) ON DELETE RESTRICT
    );
    """,
    # 8. Vehicles (Fleet Owned or Contracted by a Supplier)
    """
    CREATE TABLE IF NOT EXISTS Vehicles (
        VehicleID       INTEGER PRIMARY KEY AUTOINCREMENT,
        SupplierID      INTEGER NOT NULL,
        LicensePlate    TEXT NOT NULL,
        VehicleType     TEXT,
        Capacity        REAL CHECK (Capacity IS NULL OR Capacity > 0),
        Status          TEXT NOT NULL DEFAULT 'Available'
                        CHECK (Status IN ('Available', 'In Transit', 'Maintenance', 'Inactive')),
        UNIQUE (SupplierID, LicensePlate),
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID) ON DELETE CASCADE
    );
    """,
    # 9. Drivers (Drivers Employed or Contracted by a Supplier)
    """
    CREATE TABLE IF NOT EXISTS Drivers (
        DriverID        INTEGER PRIMARY KEY AUTOINCREMENT,
        SupplierID      INTEGER NOT NULL,
        DriverName      TEXT NOT NULL,
        LicenseNumber   TEXT,
        Phone           TEXT,
        Status          TEXT NOT NULL DEFAULT 'Available'
                        CHECK (Status IN ('Available', 'On Duty', 'Off Duty', 'Inactive')),
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID) ON DELETE CASCADE
    );
    """,
    # 10. Shipments (Dispatches Fulfilling an Order from a Warehouse)
    """
    CREATE TABLE IF NOT EXISTS Shipments (
        ShipmentID          INTEGER PRIMARY KEY AUTOINCREMENT,
        OrderID             INTEGER NOT NULL,
        WarehouseID         INTEGER NOT NULL,
        Status              TEXT NOT NULL DEFAULT 'Preparing'
                            CHECK (Status IN ('Preparing', 'In Transit', 'Delivered', 'Delayed', 'Cancelled')),
        DispatchedAt        TEXT,
        EstimatedArrival    TEXT NOT NULL,
        ActualArrival       TEXT,
        FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
        FOREIGN KEY (WarehouseID) REFERENCES Warehouses(WarehouseID) ON DELETE RESTRICT
    );
    """,
    # 11. Shipment_Legs (Multi-Stop Transit Segments per Shipment)
    """
    CREATE TABLE IF NOT EXISTS Shipment_Legs (
        LegID               INTEGER PRIMARY KEY AUTOINCREMENT,
        ShipmentID          INTEGER NOT NULL,
        DriverID            INTEGER,
        VehicleID           INTEGER,
        LegSequence         INTEGER NOT NULL CHECK (LegSequence > 0),
        StartCoordinates    TEXT NOT NULL,
        EndCoordinates      TEXT NOT NULL,
        DepartedAt          TEXT,
        ArrivedAt           TEXT,
        Status              TEXT NOT NULL DEFAULT 'Scheduled'
                            CHECK (Status IN ('Scheduled', 'In Transit', 'Completed', 'Delayed')),
        UNIQUE (ShipmentID, LegSequence),
        FOREIGN KEY (ShipmentID) REFERENCES Shipments(ShipmentID) ON DELETE CASCADE,
        FOREIGN KEY (DriverID) REFERENCES Drivers(DriverID) ON DELETE SET NULL,
        FOREIGN KEY (VehicleID) REFERENCES Vehicles(VehicleID) ON DELETE SET NULL
    );
    """,
    # Performance Indexes
    "CREATE INDEX IF NOT EXISTS idx_warehouses_supplier ON Warehouses(SupplierID);",
    "CREATE INDEX IF NOT EXISTS idx_products_supplier ON Products(SupplierID);",
    "CREATE INDEX IF NOT EXISTS idx_orders_supplier_status ON Orders(SupplierID, Status);",
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON Orders(CustomerID);",
    "CREATE INDEX IF NOT EXISTS idx_shipments_order ON Shipments(OrderID);",
    "CREATE INDEX IF NOT EXISTS idx_shipments_status_eta ON Shipments(Status, EstimatedArrival);",
    "CREATE INDEX IF NOT EXISTS idx_legs_shipment ON Shipment_Legs(ShipmentID);",
    "CREATE INDEX IF NOT EXISTS idx_vehicles_supplier ON Vehicles(SupplierID);",
    "CREATE INDEX IF NOT EXISTS idx_drivers_supplier ON Drivers(SupplierID);",
    # Dashboard View
    """
    CREATE VIEW IF NOT EXISTS vw_SupplierOrderTracking AS
    SELECT
        o.SupplierID,
        o.OrderID,
        o.OrderDate,
        o.Status AS OrderStatus,
        c.CustomerID,
        c.CustomerName,
        c.ShippingCoordinates AS DestinationCoordinates,
        s.ShipmentID,
        w.WarehouseName AS OriginWarehouse,
        s.Status AS ShipmentStatus,
        s.DispatchedAt,
        s.EstimatedArrival,
        s.ActualArrival,
        CASE
            WHEN s.ActualArrival IS NOT NULL THEN
                ROUND((julianday(s.ActualArrival) - julianday(s.DispatchedAt)) * 24, 2)
            ELSE NULL
        END AS TransitHours,
        CASE
            WHEN s.ShipmentID IS NULL THEN 'UNSCHEDULED'
            WHEN s.ActualArrival IS NULL AND datetime('now') > datetime(s.EstimatedArrival) THEN 'DELAYED'
            WHEN s.ActualArrival IS NOT NULL AND datetime(s.ActualArrival) > datetime(s.EstimatedArrival) THEN 'DELIVERED LATE'
            ELSE 'ON TIME'
        END AS DeliveryHealth
    FROM Orders o
    JOIN Customers c ON o.CustomerID = c.CustomerID
    LEFT JOIN Shipments s ON o.OrderID = s.OrderID
    LEFT JOIN Warehouses w ON s.WarehouseID = w.WarehouseID;
    """
]


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with foreign key enforcement enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Create all tables, indexes, and views using a cursor."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at: {DB_PATH.resolve()}")