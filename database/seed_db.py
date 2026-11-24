import hashlib
import random
from datetime import datetime, timedelta
from db import DB_PATH, get_connection, init_db

SUPPLIERS = [
    ("Apex Industrial Supply", "ops@apexindustrial.com", "36.6103,-88.3148"),
    ("BlueRidge Logistics & Parts", "dispatch@blueridgeparts.com", "35.2271,-80.8431"),
    ("Pacific Rim Components", "orders@pacrimcomponents.com", "47.6062,-122.3321"),
    ("Heartland Packaging Co.", "support@heartlandpack.com", "38.2527,-85.7585"),
    ("Summit Precision Hardware", "sales@summitprecision.com", "39.7392,-104.9903"),
    ("Atlantic Fasteners Ltd.", "portal@atlanticfasteners.com", "42.3601,-71.0589"),
]

WAREHOUSE_HUBS = [
    ("Midwest Distribution Center", "1420 Industrial Pkwy, Paducah, KY", "37.0834,-88.6000"),
    ("Southeast Fulfillment Hub", "890 Freight Way, Atlanta, GA", "33.7490,-84.3880"),
    ("Great Lakes Regional Depot", "410 Harbor Blvd, Chicago, IL", "41.8781,-87.6298"),
    ("Texas Gulf Logistics Hub", "2200 Port Rd, Houston, TX", "29.7604,-95.3698"),
    ("West Coast Terminal", "750 Dockside Ave, Oakland, CA", "37.8044,-122.2712"),
    ("Northeast Cross-Dock", "315 Turnpike Dr, Newark, NJ", "40.7357,-74.1724"),
]

CUSTOMERS = [
    ("Vanguard Manufacturing", "purchasing@vanguardmfg.com", "500 Assembly Dr, Nashville, TN", "36.1627,-86.7816"),
    ("Kestrel Aerospace Group", "supply@kestrelaero.com", "1200 Hangar Rd, Wichita, KS", "37.6872,-97.3301"),
    ("Ironwood Construction Corp", "materials@ironwoodbuild.com", "88 Builder Way, Columbus, OH", "39.9612,-82.9988"),
    ("Meridian Automotive Systems", "procurement@meridianauto.com", "4400 Motor City Blvd, Detroit, MI", "42.3314,-83.0458"),
    ("Cascade Medical Devices", "sourcing@cascademed.com", "910 BioTech Pkwy, Portland, OR", "45.5152,-122.6784"),
    ("Sunbelt Energy Solutions", "orders@sunbeltenergy.com", "330 Solar Ave, Phoenix, AZ", "33.4484,-112.0740"),
    ("Metro Rail & Transit Authority", "parts@metrotransit.org", "75 Depot St, St. Louis, MO", "38.6270,-90.1994"),
    ("Aegis Defense Contractors", "logistics@aegisdefense.com", "610 Arsenal Rd, Huntsville, AL", "34.7304,-86.5861"),
    ("harborView Marine Works", "buyers@harborviewmarine.com", "204 Shipyard Ln, Norfolk, VA", "36.8508,-76.2859"),
    ("Prairie Wind Turbines", "supplychain@prairiewind.com", "1500 Turbine Rd, Omaha, NE", "41.2565,-95.9345"),
    ("Canyon Robotics Inc.", "ops@canyonrobotics.com", "402 Automation Way, Salt Lake City, UT", "40.7608,-111.8910"),
    ("Bayou Petrochemical Services", "procurement@bayoupetro.com", "980 Refinery Rd, Baton Rouge, LA", "30.4515,-91.1871"),
]

PRODUCT_CATALOG = [
    ("Heavy-Duty Steel Brackets (50pk)", "Cold-rolled galvanized mounting brackets", "BRK-500", 42.50),
    ("Industrial Hydraulic Hose 10ft", "High-pressure braided rubber hose, 4000 PSI", "HYD-104", 68.00),
    ("Corrugated Shipping Boxes (25pk)", "Double-wall 18x18x12 kraft boxes", "PKG-218", 31.25),
    ("Stainless Steel Hex Bolts M8 (100pk)", "316 marine-grade corrosion-resistant bolts", "FST-808", 19.75),
    ("High-Temp Silicone Gasket Sealant", "RTV sealant rated up to 650°F", "SLN-302", 14.90),
    ("Pallet Stretch Wrap Roll 18-inch", "80-gauge cast film, 1500ft per roll", "PKG-418", 24.00),
    ("Digital Pressure Gauge 0-300 PSI", "Backlit LCD industrial manifold gauge", "GGE-300", 89.50),
    ("Pneumatic Quick-Connect Coupler", "Brass 1/4-inch NPT industrial interchange", "PNE-112", 12.40),
    ("Thermal Barcode Labels (1000/Roll)", "4x6 direct thermal shipping labels", "LBL-406", 16.80),
    ("Anti-Vibration Rubber Mounts (4pk)", "Heavy machinery shock-absorbing isolators", "MNT-044", 22.10),
    ("Reinforced Kraft Packing Tape (6pk)", "Water-activated fiberglass reinforced tape", "PKG-601", 18.50),
    ("Brushless DC Cooling Fan 120mm", "24V high-airflow enclosure cooling fan", "ELC-120", 34.00),
    ("Aluminum Extrusion Rail 2000mm", "40x40mm T-slot anodized framing profile", "ALU-204", 55.00),
    ("Heavy-Duty Caster Wheels (Set of 4)", "Polyurethane swivel casters, 1200lb rating", "WHL-412", 64.25),
    ("Safety Lockout/Tagout Kit", "OSHA-compliant electrical/valve LOTO kit", "SAF-901", 47.00),
    ("Precision Ball Bearings 6204-2RS (10pk)", "Double-sealed chrome steel bearings", "BRG-620", 29.80),
]

VEHICLE_TYPES = [
    ("Box Truck (26ft)", 10000.0),
    ("Semi-Trailer (53ft)", 45000.0),
    ("Sprinter Cargo Van", 3500.0),
    ("Flatbed Hauler", 38000.0),
    ("Refrigerated Reefer", 40000.0),
]

DRIVER_FIRST = ["Marcus", "Elena", "Darius", "Hannah", "Carlos", "Tanya", "Trevor", "Nadia", "Kenji", " Brianna", "Devon", "claire"]
DRIVER_LAST = ["Vance", "Rostova", "Brooks", "Kowalski", "Mendez", "Okafor", "Lindqvist", "Patel", "Sato", "Mercer", "Galloway", "Bauer"]


def _hash_pw(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _midpoint_coords(coord_a: str, coord_b: str) -> str:
    lat1, lon1 = map(float, coord_a.split(","))
    lat2, lon2 = map(float, coord_b.split(","))
    mid_lat = round((lat1 + lat2) / 2 + random.uniform(-0.35, 0.35), 4)
    mid_lon = round((lon1 + lon2) / 2 + random.uniform(-0.35, 0.35), 4)
    return f"{mid_lat},{mid_lon}"


def seed_database(orders_per_supplier: int = 45, reset: bool = True) -> None:
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    if reset:
        # Delete in child-to-parent order to respect ON DELETE RESTRICT constraints
        cur.executescript("""
            DELETE FROM Shipment_Legs;
            DELETE FROM Shipments;
            DELETE FROM Order_Items;
            DELETE FROM Orders;
            DELETE FROM Inventory;
            DELETE FROM Products;
            DELETE FROM Warehouses;
            DELETE FROM Vehicles;
            DELETE FROM Drivers;
            DELETE FROM Customers;
            DELETE FROM Suppliers;
            DELETE FROM sqlite_sequence;
        """)

    # 1. Seed Customers
    cur.executemany(
        """
        INSERT INTO Customers (CustomerName, Email, ShippingAddress, ShippingCoordinates)
        VALUES (?, ?, ?, ?)
        """,
        CUSTOMERS,
    )
    cur.execute("SELECT CustomerID, ShippingCoordinates FROM Customers")
    customers = [(row["CustomerID"], row["ShippingCoordinates"]) for row in cur.fetchall()]

    # 2. Seed Suppliers
    supplier_rows = [(name, email, _hash_pw("password123"), coords) for name, email, coords in SUPPLIERS]
    cur.executemany(
        """
        INSERT INTO Suppliers (CompanyName, Email, PasswordHash, HQCoordinates)
        VALUES (?, ?, ?, ?)
        """,
        supplier_rows,
    )
    cur.execute("SELECT SupplierID, CompanyName FROM Suppliers")
    suppliers = [(row["SupplierID"], row["CompanyName"]) for row in cur.fetchall()]

    now = datetime.now()

    for supplier_id, company_name in suppliers:
        # 3. Seed 2–3 Warehouses per Supplier
        chosen_hubs = random.sample(WAREHOUSE_HUBS, k=random.randint(2, 3))
        warehouses = []
        for idx, (hub_name, addr, coords) in enumerate(chosen_hubs, start=1):
            w_name = f"{company_name.split()[0]} — {hub_name}"
            cur.execute(
                """
                INSERT INTO Warehouses (SupplierID, WarehouseName, Address, Coordinates, Capacity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (supplier_id, w_name, addr, coords, random.randint(5000, 25000)),
            )
            warehouses.append((cur.lastrowid, coords))

        # 4. Seed 8–12 Products per Supplier
        chosen_products = random.sample(PRODUCT_CATALOG, k=random.randint(8, 12))
        products = []
        for prod_name, desc, sku_base, base_price in chosen_products:
            sku = f"S{supplier_id}-{sku_base}"
            price = round(base_price * random.uniform(0.92, 1.12), 2)
            cur.execute(
                """
                INSERT INTO Products (SupplierID, ProductName, Description, SKU, UnitPrice)
                VALUES (?, ?, ?, ?, ?)
                """,
                (supplier_id, prod_name, desc, sku, price),
            )
            products.append((cur.lastrowid, price))

        # 5. Seed Inventory across each Supplier's Warehouses (some intentionally low-stock)
        for warehouse_id, _ in warehouses:
            for product_id, _ in products:
                reorder_lvl = random.choice([10, 15, 20, 25])
                qty_on_hand = random.randint(2, 140)
                cur.execute(
                    """
                    INSERT INTO Inventory (WarehouseID, ProductID, QuantityOnHand, ReorderLevel)
                    VALUES (?, ?, ?, ?)
                    """,
                    (warehouse_id, product_id, qty_on_hand, reorder_lvl),
                )

        # 6. Seed 4–6 Vehicles per Supplier
        vehicle_ids = []
        for v_idx in range(1, random.randint(5, 7)):
            v_type, v_cap = random.choice(VEHICLE_TYPES)
            plate = f"SUP{supplier_id}-{100 + v_idx}{random.choice('ABCDEFGH')}"
            v_status = random.choices(
                ["Available", "In Transit", "Maintenance", "Inactive"],
                weights=[0.50, 0.35, 0.10, 0.05],
            )[0]
            cur.execute(
                """
                INSERT INTO Vehicles (SupplierID, LicensePlate, VehicleType, Capacity, Status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (supplier_id, plate, v_type, v_cap, v_status),
            )
            vehicle_ids.append(cur.lastrowid)

        # 7. Seed 4–6 Drivers per Supplier
        driver_ids = []
        for d_idx in range(random.randint(5, 7)):
            d_name = f"{random.choice(DRIVER_FIRST).strip().title()} {random.choice(DRIVER_LAST)}"
            lic = f"CDL-{supplier_id}{random.randint(100000, 999999)}"
            phone = f"555-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
            d_status = random.choices(
                ["Available", "On Duty", "Off Duty", "Inactive"],
                weights=[0.45, 0.35, 0.15, 0.05],
            )[0]
            cur.execute(
                """
                INSERT INTO Drivers (SupplierID, DriverName, LicenseNumber, Phone, Status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (supplier_id, d_name, lic, phone, d_status),
            )
            driver_ids.append(cur.lastrowid)

        # 8. Seed Orders, Order_Items, Shipments, and Shipment_Legs
        for _ in range(orders_per_supplier):
            cust_id, cust_coords = random.choice(customers)
            days_ago = random.randint(0, 180)
            order_dt = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            order_date_str = order_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Realistic status distribution based on order age
            if days_ago > 14:
                order_status = random.choices(
                    ["Completed", "Cancelled"],
                    weights=[0.93, 0.07],
                )[0]
            else:
                order_status = random.choices(
                    ["Pending", "Processing", "Shipped", "Completed", "Cancelled"],
                    weights=[0.25, 0.30, 0.25, 0.15, 0.05],
                )[0]

            cur.execute(
                """
                INSERT INTO Orders (SupplierID, CustomerID, OrderDate, Status)
                VALUES (?, ?, ?, ?)
                """,
                (supplier_id, cust_id, order_date_str, order_status),
            )
            order_id = cur.lastrowid

            # 1 to 5 distinct products per order (respects PRIMARY KEY (OrderID, ProductID))
            line_products = random.sample(products, k=min(random.randint(1, 5), len(products)))
            for prod_id, unit_price in line_products:
                qty = random.randint(2, 35)
                cur.execute(
                    """
                    INSERT INTO Order_Items (OrderID, ProductID, Quantity, UnitPrice)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order_id, prod_id, qty, unit_price),
                )

            # Create a Shipment for non-cancelled orders (leave ~30% of Pending unscheduled)
            if order_status == "Cancelled":
                continue
            if order_status == "Pending" and random.random() < 0.35:
                continue

            warehouse_id, origin_coords = random.choice(warehouses)
            transit_duration = timedelta(hours=random.randint(24, 96))
            est_arrival_dt = order_dt + timedelta(hours=12) + transit_duration
            est_arrival_str = est_arrival_dt.strftime("%Y-%m-%d %H:%M:%S")

            if order_status == "Completed":
                ship_status = "Delivered"
                dispatched_dt = order_dt + timedelta(hours=random.randint(4, 18))
                # ~15% delivered late to populate 'DELIVERED LATE' in vw_SupplierOrderTracking
                variance_hours = random.randint(-12, 18)
                actual_dt = est_arrival_dt + timedelta(hours=variance_hours)
                dispatched_str = dispatched_dt.strftime("%Y-%m-%d %H:%M:%S")
                actual_str = actual_dt.strftime("%Y-%m-%d %H:%M:%S")

            elif order_status == "Shipped":
                dispatched_dt = order_dt + timedelta(hours=random.randint(2, 12))
                dispatched_str = dispatched_dt.strftime("%Y-%m-%d %H:%M:%S")
                actual_str = None
                # Force some active shipments past EstimatedArrival so 'DELAYED' appears
                if now > est_arrival_dt or random.random() < 0.25:
                    ship_status = "Delayed"
                    est_arrival_str = (now - timedelta(hours=random.randint(2, 36))).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    ship_status = "In Transit"

            else:  # Pending or Processing with a scheduled shipment
                ship_status = "Preparing"
                dispatched_str = None
                actual_str = None

            cur.execute(
                """
                INSERT INTO Shipments (
                    OrderID, WarehouseID, Status, DispatchedAt, EstimatedArrival, ActualArrival
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, warehouse_id, ship_status, dispatched_str, est_arrival_str, actual_str),
            )
            shipment_id = cur.lastrowid

            # Create 1 or 2 Shipment_Legs per Shipment
            num_legs = random.choice([1, 1, 2])
            mid_coords = _midpoint_coords(origin_coords, cust_coords) if num_legs == 2 else cust_coords

            for leg_seq in range(1, num_legs + 1):
                start_c = origin_coords if leg_seq == 1 else mid_coords
                end_c = mid_coords if (num_legs == 2 and leg_seq == 1) else cust_coords

                if ship_status == "Delivered":
                    leg_status = "Completed"
                    leg_dep = dispatched_str
                    leg_arr = actual_str
                elif ship_status in ("In Transit", "Delayed"):
                    if num_legs == 2 and leg_seq == 1:
                        leg_status = "Completed"
                        leg_dep = dispatched_str
                        leg_arr = (datetime.strptime(dispatched_str, "%Y-%m-%d %H:%M:%S") + timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        leg_status = "Delayed" if ship_status == "Delayed" else "In Transit"
                        leg_dep = dispatched_str
                        leg_arr = None
                else:
                    leg_status = "Scheduled"
                    leg_dep = None
                    leg_arr = None

                cur.execute(
                    """
                    INSERT INTO Shipment_Legs (
                        ShipmentID, DriverID, VehicleID, LegSequence,
                        StartCoordinates, EndCoordinates, DepartedAt, ArrivedAt, Status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        shipment_id,
                        random.choice(driver_ids),
                        random.choice(vehicle_ids),
                        leg_seq,
                        start_c,
                        end_c,
                        leg_dep,
                        leg_arr,
                        leg_status,
                    ),
                )

    conn.commit()
    conn.close()
    total_orders = len(suppliers) * orders_per_supplier
    print(f"Seeded {len(suppliers)} suppliers, {len(customers)} customers, and {total_orders} orders into {DB_PATH.name}.")


if __name__ == "__main__":
    seed_database(orders_per_supplier=50, reset=True)