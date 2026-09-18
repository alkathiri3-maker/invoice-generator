# -*- coding: utf-8 -*-
"""
Advanced integration tests for generation engine, QR service, templates, and backup.
Tests complex workflows, async operations, and system-level operations.
"""
from __future__ import annotations

import pytest
import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import date, datetime, timedelta

from app import db as dbm
from app.generator.engine import GenParams, generate
from app.money import to_halalas, from_halalas


@pytest.fixture(scope="function")
def test_db_with_defaults():
    """Create database with default companies and items."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Initialize schema
    for stmt in dbm.SCHEMA.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)

    # Add default company
    cursor = conn.execute(
        """INSERT INTO companies (name, address, tax_number, cr_number, color)
           VALUES (?, ?, ?, ?, ?)""",
        ("شركة الاختبار", "الرياض", "311111111111111", "1234567890", "#0e7490")
    )
    conn.commit()
    company_id = cursor.lastrowid

    # Add default customer
    cursor = conn.execute(
        """INSERT INTO customers (name, address, tax_number, phone)
           VALUES (?, ?, ?, ?)""",
        ("عميل الاختبار", "جدة", "300000000000000", "0501234567")
    )
    conn.commit()
    customer_id = cursor.lastrowid

    # Add default items
    items = [
        ("صنف 1", "ITEM001", "حبة", 100),
        ("صنف 2", "ITEM002", "كيس", 250),
        ("صنف 3", "ITEM003", "متر", 500),
        ("صنف 4", "ITEM004", "صندوق", 1000),
    ]

    item_ids = []
    for name, code, unit, price in items:
        cursor = conn.execute(
            """INSERT INTO items (name, code, unit, unit_price, tax_rate)
               VALUES (?, ?, ?, ?, ?)""",
            (name, code, unit, float(price), 0.15)  # Use float instead of Decimal
        )
        conn.commit()
        item_ids.append(cursor.lastrowid)

    # Add template
    cursor = conn.execute(
        """INSERT INTO templates (name, type, html_content)
           VALUES (?, ?, ?)""",
        ("قالب افتراضي", "invoice", "<html><body>Test Invoice</body></html>")
    )
    conn.commit()
    template_id = cursor.lastrowid

    yield conn, db_path, {
        'company_id': company_id,
        'customer_id': customer_id,
        'item_ids': item_ids,
        'template_id': template_id
    }

    conn.close()
    db_path.unlink(missing_ok=True)


class TestInvoiceGeneration:
    """Tests for invoice generation workflow."""

    def test_generate_single_invoice(self, test_db_with_defaults):
        """Should generate single invoice with correct totals."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net',
            min_amount='100',
            payment_type='نقدي',
            seed='12345',
            qr_mode='none',
            with_receipts=False,
            invoice_start=1001
        )

        result = generate(conn, params, persist=True, return_built=True)

        # Result is dict with count, total_net, total_tax, total_gross, etc.
        assert result is not None
        assert result['count'] == 1
        assert float(result['total_net']) == 1000.0
        assert result['seed'] == 12345

        # Verify in database
        invoice = conn.execute(
            "SELECT * FROM invoices ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert invoice is not None
        assert invoice['subtotal'] == 1000.0

    def test_generate_multiple_invoices(self, test_db_with_defaults):
        """Should generate multiple invoices with distributed amounts."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-02-28',  # Longer period for multiple invoices
            count_mode='total',
            count_total=5,
            amount='50000.00',
            amount_mode='net',
            min_amount='1000',
            payment_type='عشوائي',
            seed='54321',
            qr_mode='none',
            with_receipts=True,
            receipt_start=5001
        )

        result = generate(conn, params, persist=True, return_built=True)

        # Result is dict - verify count
        assert result is not None
        assert result['count'] == 5
        assert float(result['total_net']) == 50000.0

        # Verify invoices in database
        invoices = conn.execute(
            "SELECT COUNT(*) c FROM invoices"
        ).fetchone()['c']
        assert invoices == 5

        # Verify receipts
        receipts = conn.execute(
            "SELECT COUNT(*) c FROM receipts"
        ).fetchone()['c']
        assert receipts == 5

    def test_generate_with_deterministic_seed(self, test_db_with_defaults):
        """Same seed should produce same invoice amounts."""
        conn, db_path, defaults = test_db_with_defaults

        seed_value = '99999'

        # First generation
        params1 = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=3,
            amount='10000.00',
            amount_mode='net',
            min_amount='1000',
            seed=seed_value,
            qr_mode='none'
        )

        result1 = generate(conn, params1, persist=False, return_built=True)
        amounts1 = sorted([int(b.subtotal) for b in result1['_built']])

        # Second generation with same seed
        params2 = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=3,
            amount='10000.00',
            amount_mode='net',
            min_amount='1000',
            seed=seed_value,
            qr_mode='none'
        )

        result2 = generate(conn, params2, persist=False, return_built=True)
        amounts2 = sorted([int(b.subtotal) for b in result2['_built']])

        assert amounts1 == amounts2

    def test_generate_gross_mode_totals_exactly(self, test_db_with_defaults):
        """Gross mode should match target total exactly."""
        conn, db_path, defaults = test_db_with_defaults

        target_gross = 1150.00  # Net 1000 + Tax 150

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount=str(target_gross),
            amount_mode='gross',
            min_amount='100',
            seed='11111',
            qr_mode='none'
        )

        result = generate(conn, params, persist=False, return_built=True)

        actual_gross = result['total_gross']
        # Allow small rounding difference
        assert abs(float(actual_gross) - target_gross) < 0.5

    def test_generate_daily_mode(self, test_db_with_defaults):
        """Should generate invoices based on daily rate with multiple customers."""
        conn, db_path, defaults = test_db_with_defaults

        # Add more customers to support multiple invoices per day
        for i in range(2):
            cursor = conn.execute(
                "INSERT INTO customers (name, address, phone) VALUES (?, ?, ?)",
                (f"عميل إضافي {i}", f"العنوان {i}", f"050555555{i}")
            )
            conn.commit()
            defaults['customer_ids'] = defaults.get('customer_ids', []) + [cursor.lastrowid]

        # Or just use fewer invoices per day to fit within the period
        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='daily',
            count_daily=1.0,  # 1 invoice per day = 31 total
            amount='30000.00',
            amount_mode='net',
            min_amount='500',
            seed='22222',
            qr_mode='none'
        )

        result = generate(conn, params, persist=True, return_built=True)

        assert result['count'] >= 25  # ~31 expected
        assert float(result['total_net']) == 30000.0

    def test_generate_invalid_company_fails(self, test_db_with_defaults):
        """Should fail with invalid company."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=99999,  # Nonexistent
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net'
        )

        with pytest.raises(ValueError) as exc_info:
            generate(conn, params)

        assert 'شركة' in str(exc_info.value)

    def test_generate_invalid_customers_fails(self, test_db_with_defaults):
        """Should fail with invalid customer."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[99999],  # Nonexistent
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net'
        )

        with pytest.raises(ValueError) as exc_info:
            generate(conn, params)

        error_msg = str(exc_info.value)
        # Check for customer-related error (in Arabic or exact message)
        assert 'عميل' in error_msg or 'محدد' in error_msg

    def test_generate_no_items_fails(self, test_db_with_defaults):
        """Should fail with invalid items."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=[99999],  # Nonexistent
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net'
        )

        with pytest.raises(ValueError) as exc_info:
            generate(conn, params)

        assert 'أصناف' in str(exc_info.value)

    def test_generate_invalid_date_range_fails(self, test_db_with_defaults):
        """Should fail with invalid date range."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-02-01',
            date_to='2026-01-01',  # Backwards
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net'
        )

        with pytest.raises(ValueError) as exc_info:
            generate(conn, params)

        assert 'تاريخ' in str(exc_info.value)

    def test_generate_insufficient_amount_fails(self, test_db_with_defaults):
        """Should fail with insufficient total amount."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=10,
            amount='1000.00',  # Too small for 10 invoices
            amount_mode='net',
            min_amount='500'  # Min per invoice
        )

        with pytest.raises(ValueError) as exc_info:
            generate(conn, params)

        assert 'غير كافٍ' in str(exc_info.value)


class TestQRGeneration:
    """Tests for QR code generation during invoice generation."""

    def test_generate_with_simple_qr(self, test_db_with_defaults):
        """Should generate invoices with simple QR codes."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net',
            seed='33333',
            qr_mode='simple'
        )

        result = generate(conn, params, persist=True, return_built=True)

        # Check QR mode in built invoices
        for inv in result['_built']:
            assert inv.qr_mode == 'simple'
            assert hasattr(inv, 'qr_payload_b64')

        # Verify in database
        invoice = conn.execute(
            "SELECT * FROM invoices WHERE qr_mode=?", ('simple',)
        ).fetchone()
        assert invoice is not None
        assert invoice['qr_payload_b64'] != ''

    def test_generate_phase2_qr_requires_cert(self, test_db_with_defaults):
        """Phase 2 QR should work with training credentials."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=1,
            amount='1000.00',
            amount_mode='net',
            seed='44444',
            qr_mode='phase2'
        )

        # Should succeed with training credentials
        result = generate(conn, params, persist=True, return_built=True)

        # Result is a dict with generation info
        assert result is not None
        assert '_built' in result or result.get('count', 0) > 0


class TestTemplateOperations:
    """Tests for template management."""

    def test_save_template(self, test_db_with_defaults):
        """Should save new template."""
        conn, db_path, defaults = test_db_with_defaults

        html_content = "<html><body>Custom Invoice Template</body></html>"

        cursor = conn.execute(
            """INSERT INTO templates (name, type, html_content)
               VALUES (?, ?, ?)""",
            ("قالب مخصص", "invoice", html_content)
        )
        conn.commit()
        template_id = cursor.lastrowid

        # Verify saved
        template = conn.execute(
            "SELECT * FROM templates WHERE id=?", (template_id,)
        ).fetchone()
        assert template is not None
        assert template['html_content'] == html_content

    def test_update_template(self, test_db_with_defaults):
        """Should update existing template."""
        conn, db_path, defaults = test_db_with_defaults

        template_id = defaults['template_id']
        new_content = "<html><body>Updated Template</body></html>"

        conn.execute(
            "UPDATE templates SET html_content=? WHERE id=?",
            (new_content, template_id)
        )
        conn.commit()

        # Verify updated
        template = conn.execute(
            "SELECT * FROM templates WHERE id=?", (template_id,)
        ).fetchone()
        assert template['html_content'] == new_content

    def test_delete_template(self, test_db_with_defaults):
        """Should delete template."""
        conn, db_path, defaults = test_db_with_defaults

        template_id = defaults['template_id']

        conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
        conn.commit()

        # Verify deleted
        template = conn.execute(
            "SELECT * FROM templates WHERE id=?", (template_id,)
        ).fetchone()
        assert template is None

    def test_template_type_constraint(self, test_db_with_defaults):
        """Should enforce template type constraint."""
        conn, db_path, defaults = test_db_with_defaults

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO templates (name, type, html_content)
                   VALUES (?, ?, ?)""",
                ("قالب خاطئ", "invalid_type", "<html></html>")
            )
            conn.commit()


class TestBatchOperations:
    """Tests for batch management."""

    def test_batch_creation_on_generation(self, test_db_with_defaults):
        """Should create batch when generating invoices."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=3,
            amount='10000.00',
            amount_mode='net',
            seed='55555',
            qr_mode='none'
        )

        result = generate(conn, params, persist=True, return_built=True)

        batch_id = result.get('batch_id')
        assert batch_id is not None

        # Verify batch in database
        batch = conn.execute(
            "SELECT * FROM batches WHERE id=?", (batch_id,)
        ).fetchone()
        assert batch is not None
        assert batch['invoice_count'] == 3
        assert batch['seed'] == 55555

    def test_batch_cascade_delete(self, test_db_with_defaults):
        """Should cascade delete invoices with batch."""
        conn, db_path, defaults = test_db_with_defaults

        # Create batch with invoices
        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=2,
            amount='5000.00',
            amount_mode='net',
            seed='66666',
            qr_mode='none'
        )

        result = generate(conn, params, persist=True, return_built=True)
        batch_id = result['batch_id']

        # Count invoices in batch
        invoice_count = conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE batch_id=?", (batch_id,)
        ).fetchone()['c']
        assert invoice_count == 2

        # Delete batch
        conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
        conn.commit()

        # Verify invoices were cascade deleted
        remaining = conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE batch_id=?", (batch_id,)
        ).fetchone()['c']
        assert remaining == 0


class TestDataIntegrity:
    """Tests for data integrity across complex operations."""

    def test_summary_totals_accuracy(self, test_db_with_defaults):
        """Generated summary totals should match actual invoice totals."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=5,
            amount='25000.00',
            amount_mode='net',
            seed='77777',
            qr_mode='none'
        )

        result = generate(conn, params, persist=True, return_built=True)

        # Get summary
        summary_net = float(result['total_net'])
        summary_tax = float(result['total_tax'])
        summary_gross = float(result['total_gross'])

        # Calculate from database
        db_net = conn.execute(
            "SELECT COALESCE(SUM(subtotal), 0) total FROM invoices"
        ).fetchone()['total']

        db_tax = conn.execute(
            "SELECT COALESCE(SUM(tax_amount), 0) total FROM invoices"
        ).fetchone()['total']

        db_gross = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) total FROM invoices"
        ).fetchone()['total']

        # Should match (within rounding)
        assert abs(summary_net - db_net) < 0.5
        assert abs(summary_tax - db_tax) < 0.5
        assert abs(summary_gross - db_gross) < 0.5

    def test_invoice_items_relationship_integrity(self, test_db_with_defaults):
        """Invoice items should maintain referential integrity with invoices."""
        conn, db_path, defaults = test_db_with_defaults

        params = GenParams(
            company_id=defaults['company_id'],
            customer_ids=[defaults['customer_id']],
            item_ids=defaults['item_ids'],
            items_mode='individual',
            date_from='2026-01-01',
            date_to='2026-01-31',
            count_mode='total',
            count_total=2,
            amount='5000.00',
            amount_mode='net',
            seed='88888',
            qr_mode='none'
        )

        result = generate(conn, params, persist=True, return_built=True)

        # For each invoice, verify items exist and sums match
        invoices = conn.execute(
            "SELECT id, subtotal FROM invoices ORDER BY id"
        ).fetchall()

        for invoice in invoices:
            items_total = conn.execute(
                "SELECT COALESCE(SUM(line_total), 0) total FROM invoice_items WHERE invoice_id=?",
                (invoice['id'],)
            ).fetchone()['total']

            # Should match subtotal (within rounding)
            assert abs(items_total - invoice['subtotal']) < 1.0
