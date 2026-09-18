#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Initialize demo data to database
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "itqan_invoices.db"

def init_demo_data():
    """Add demo data"""

    if not DB_PATH.exists():
        print("Database not found")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Demo customers
    customers = [
        ("Al-Amal Trading Company", "Riyadh", "1234567890", ""),
        ("Al-Noor Distribution", "Jeddah", "9876543210", ""),
        ("Al-Saada Store", "Dammam", "5555555555", ""),
        ("Al-Bina Construction", "Khobar", "6666666666", ""),
        ("Integrated Services Center", "Riyadh", "7777777777", ""),
    ]

    print("Adding customers...")
    for name, address, tax_num, cr_num in customers:
        try:
            cursor.execute(
                "INSERT INTO customers (name, address, tax_number, cr_number) VALUES (?, ?, ?, ?)",
                (name, address, tax_num, cr_num)
            )
        except sqlite3.IntegrityError:
            pass

    # Demo item groups
    groups = [
        ("Services", "Professional Services"),
        ("Products", "Physical Products"),
    ]

    print("Adding item groups...")
    cursor.execute("DELETE FROM items")
    cursor.execute("DELETE FROM item_groups")
    for name, desc in groups:
        cursor.execute(
            "INSERT INTO item_groups (name, description) VALUES (?, ?)",
            (name, desc)
        )

    # Get first group
    cursor.execute("SELECT id FROM item_groups LIMIT 1")
    result = cursor.fetchone()
    group_id = result[0] if result else 1

    # Demo items
    items = [
        ("Consulting Services", "001", "Hour", 500.00, 15.0),
        ("Training Courses", "002", "Course", 2000.00, 15.0),
        ("Software Development", "003", "Hour", 800.00, 15.0),
        ("Graphic Design", "004", "Hour", 600.00, 15.0),
        ("Translation", "005", "Page", 50.00, 15.0),
        ("Accounting & Audit", "006", "Hour", 400.00, 15.0),
        ("Project Management", "007", "Hour", 700.00, 15.0),
        ("Digital Marketing", "008", "Month", 3000.00, 15.0),
        ("Technical Support", "009", "Hour", 300.00, 15.0),
        ("Sales & Distribution", "010", "Unit", 100.00, 15.0),
    ]

    print("Adding items...")
    for name, code, unit, price, tax in items:
        try:
            cursor.execute(
                "INSERT INTO items (group_id, name, code, unit, unit_price, tax_rate) VALUES (?, ?, ?, ?, ?, ?)",
                (group_id, name, code, unit, price, tax)
            )
        except sqlite3.IntegrityError:
            pass

    # Demo company
    try:
        cursor.execute(
            "INSERT INTO companies (name, address, tax_number, cr_number) VALUES (?, ?, ?, ?)",
            ("Our Company", "Riyadh", "3333333333", "1111111111")
        )
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()

    print("Demo data added successfully!")
    print("  - 5 customers")
    print("  - 2 item groups")
    print("  - 10 items")
    print("  - 1 company")

if __name__ == "__main__":
    init_demo_data()
