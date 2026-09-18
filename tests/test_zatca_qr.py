# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for zatca_qr module.
Tests TLV encoding/decoding, validation, and QR generation.
"""
from __future__ import annotations

import pytest
import base64
from decimal import Decimal
from zatca_qr import (
    tlv, parse_tlv, ZATCAError,
    _validate_vat_number, _validate_timestamp, _format_amount,
    canonicalize_invoice_xml, compute_invoice_hash,
    build_phase2_qr
)


class TestTLVEncoding:
    """Tests for TLV encoding and decoding."""

    def test_tlv_single_tag(self):
        """Should encode tag-length-value correctly."""
        result = tlv(1, "test")
        assert result[0] == 1  # Tag
        assert result[1] == 4  # Length
        assert result[2:] == b"test"

    def test_tlv_empty_value(self):
        """Should handle empty value."""
        result = tlv(1, "")
        assert result[0] == 1
        assert result[1] == 0

    def test_tlv_unicode_value(self):
        """Should encode UTF-8 correctly."""
        result = tlv(1, "السعودية")
        assert result[0] == 1
        # Length should be byte length of UTF-8, not character count
        assert result[1] > 0
        # Should decode back
        assert result[2:].decode("utf-8") == "السعودية"

    def test_tlv_max_length_255(self):
        """Should accept value up to 255 bytes."""
        value = "x" * 255
        result = tlv(1, value)
        assert result[1] == 255

    def test_tlv_exceeds_max_length_raises(self):
        """Should raise ZATCAError if value > 255 bytes."""
        value = "x" * 256
        with pytest.raises(ZATCAError) as exc_info:
            tlv(1, value)
        assert "255" in str(exc_info.value)

    def test_tlv_invalid_tag_raises(self):
        """Should raise ZATCAError for tag < 0 or > 255."""
        with pytest.raises(ZATCAError):
            tlv(-1, "test")
        with pytest.raises(ZATCAError):
            tlv(256, "test")

    def test_parse_tlv_single_tag(self):
        """Should decode single TLV."""
        encoded = tlv(1, "test")
        result = parse_tlv(encoded)
        assert result == [(1, "test")]

    def test_parse_tlv_multiple_tags(self):
        """Should decode multiple TLVs in sequence."""
        payload = tlv(1, "first") + tlv(2, "second") + tlv(3, "third")
        result = parse_tlv(payload)
        assert result == [(1, "first"), (2, "second"), (3, "third")]

    def test_parse_tlv_unicode_value(self):
        """Should decode UTF-8 values correctly."""
        payload = tlv(1, "اختبار")
        result = parse_tlv(payload)
        assert result[0] == (1, "اختبار")

    def test_parse_tlv_empty_value(self):
        """Should handle empty values."""
        payload = tlv(1, "")
        result = parse_tlv(payload)
        assert result == [(1, "")]

    def test_parse_tlv_incomplete_header_raises(self):
        """Should raise ZATCAError for incomplete header."""
        with pytest.raises(ZATCAError) as exc_info:
            parse_tlv(b"\x01")  # Tag but no length
        assert "غير مكتملة" in str(exc_info.value)

    def test_parse_tlv_incomplete_value_raises(self):
        """Should raise ZATCAError if value is truncated."""
        with pytest.raises(ZATCAError) as exc_info:
            parse_tlv(b"\x01\x05test")  # Says 5 bytes but only has 4
        assert "يتجاوز" in str(exc_info.value)

    def test_parse_tlv_invalid_utf8_raises(self):
        """Should raise ZATCAError for non-UTF-8 bytes."""
        payload = bytes([1, 2, 0xFF, 0xFE])  # Invalid UTF-8
        with pytest.raises(ZATCAError) as exc_info:
            parse_tlv(payload)
        assert "UTF-8" in str(exc_info.value)

    def test_tlv_roundtrip(self):
        """Encoding then decoding should recover original."""
        values = ["test", "السعودية", "123.45", ""]
        for val in values:
            encoded = tlv(1, val)
            decoded = parse_tlv(encoded)
            assert decoded == [(1, val)]


class TestValidation:
    """Tests for input validation functions."""

    def test_validate_vat_number_valid(self):
        """Should accept valid 15-digit VAT starting with 3."""
        result = _validate_vat_number("311187605900003")
        assert result == "311187605900003"

    def test_validate_vat_number_invalid_short(self):
        """Should reject VAT with < 15 digits."""
        with pytest.raises(ZATCAError) as exc_info:
            _validate_vat_number("31118760590000")  # 14 digits
        assert "صالح" in str(exc_info.value)

    def test_validate_vat_number_invalid_long(self):
        """Should reject VAT with > 15 digits."""
        with pytest.raises(ZATCAError):
            _validate_vat_number("3111876059000031")  # 16 digits

    def test_validate_vat_number_invalid_prefix(self):
        """Should reject VAT not starting with 3."""
        with pytest.raises(ZATCAError):
            _validate_vat_number("211187605900003")

    def test_validate_vat_number_non_numeric(self):
        """Should reject non-numeric VAT."""
        with pytest.raises(ZATCAError):
            _validate_vat_number("31118760590000X")

    def test_validate_vat_number_with_whitespace(self):
        """Should strip whitespace."""
        result = _validate_vat_number("  311187605900003  ")
        assert result == "311187605900003"

    def test_validate_timestamp_valid(self):
        """Should accept valid ISO-8601 UTC timestamp."""
        result = _validate_timestamp("2026-08-12T10:30:00Z")
        assert result == "2026-08-12T10:30:00Z"

    def test_validate_timestamp_with_milliseconds(self):
        """Should accept timestamp with fractional seconds."""
        result = _validate_timestamp("2026-08-12T10:30:00.123Z")
        assert result == "2026-08-12T10:30:00.123Z"

    def test_validate_timestamp_invalid_format(self):
        """Should reject non-ISO-8601 formats."""
        with pytest.raises(ZATCAError) as exc_info:
            _validate_timestamp("12-08-2026 10:30:00")
        assert "ISO-8601" in str(exc_info.value)

    def test_validate_timestamp_no_z_suffix(self):
        """Should require Z (UTC) suffix."""
        with pytest.raises(ZATCAError):
            _validate_timestamp("2026-08-12T10:30:00")

    def test_validate_timestamp_invalid_date(self):
        """Should validate actual date validity."""
        with pytest.raises(ZATCAError):
            _validate_timestamp("2026-02-30T10:30:00Z")  # No Feb 30

    def test_format_amount_valid(self):
        """Should format valid amounts to 2 decimals."""
        result = _format_amount(100.5, "test")
        assert result == "100.50"

    def test_format_amount_rounding(self):
        """Should round to 2 decimals."""
        result = _format_amount(100.555, "test")
        assert result == "100.56"  # ROUND_HALF_UP

    def test_format_amount_zero(self):
        """Should handle zero."""
        result = _format_amount(0, "test")
        assert result == "0.00"

    def test_format_amount_negative_raises(self):
        """Should reject negative amounts."""
        with pytest.raises(ZATCAError) as exc_info:
            _format_amount(-100, "test")
        # The error message contains Arabic text about negative amounts
        assert "سالب" in str(exc_info.value) or "negative" in str(exc_info.value).lower()

    def test_format_amount_non_numeric_raises(self):
        """Should reject non-numeric values."""
        with pytest.raises(ZATCAError):
            _format_amount("not a number", "test")

    def test_format_amount_infinity_raises(self):
        """Should reject non-finite values."""
        with pytest.raises(ZATCAError):
            _format_amount(float('inf'), "test")

    def test_format_amount_none_raises(self):
        """Should require non-None value."""
        with pytest.raises(ZATCAError):
            _format_amount(None, "test")


class TestXMLProcessing:
    """Tests for XML canonicalization and hashing."""

    def test_canonicalize_invoice_xml_basic(self):
        """Should canonicalize valid XML."""
        xml = """<?xml version="1.0"?>
<Invoice><ID>123</ID></Invoice>"""
        result = canonicalize_invoice_xml(xml)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_canonicalize_invoice_xml_invalid_raises(self):
        """Should raise ZATCAError for invalid XML."""
        with pytest.raises(ZATCAError):
            canonicalize_invoice_xml("<not valid xml")

    def test_canonicalize_invoice_xml_empty_raises(self):
        """Should raise ZATCAError for empty XML."""
        with pytest.raises(ZATCAError):
            canonicalize_invoice_xml("")

    def test_compute_invoice_hash_deterministic(self):
        """Same XML should produce same hash."""
        xml = """<?xml version="1.0"?>
<Invoice><ID>123</ID></Invoice>"""
        hash1 = compute_invoice_hash(xml)
        hash2 = compute_invoice_hash(xml)
        assert hash1 == hash2

    def test_compute_invoice_hash_different_xml(self):
        """Different XML should produce different hash."""
        xml1 = """<?xml version="1.0"?>
<Invoice><ID>123</ID></Invoice>"""
        xml2 = """<?xml version="1.0"?>
<Invoice><ID>456</ID></Invoice>"""
        hash1 = compute_invoice_hash(xml1)
        hash2 = compute_invoice_hash(xml2)
        assert hash1 != hash2

    def test_compute_invoice_hash_length(self):
        """SHA-256 hash should be 32 bytes."""
        xml = """<?xml version="1.0"?>
<Invoice><ID>123</ID></Invoice>"""
        hash_result = compute_invoice_hash(xml)
        assert len(hash_result) == 32


class TestPhase2QR:
    """Tests for build_phase2_qr function (phase 2 QR generation)."""

    def test_build_phase2_qr_standard_type(self):
        """Should generate standard invoice with tags 1-5 only."""
        result = build_phase2_qr(
            seller_name="شركة تجارية",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=Decimal("1000.00"),
            vat_total=Decimal("130.43"),
            invoice_type="standard",
        )
        assert result["invoice_type"] == "standard"
        tags = [t for t, _ in result["tags"]]
        assert tags == [1, 2, 3, 4, 5]

    def test_build_phase2_qr_missing_seller_name_raises(self):
        """Should raise ZATCAError if seller_name is empty."""
        with pytest.raises(ZATCAError) as exc_info:
            build_phase2_qr(
                seller_name="",
                seller_vat="311187605900003",
                timestamp="2026-08-12T10:30:00Z",
                gross_total=1000,
                vat_total=130.43,
                invoice_type="standard",
            )
        assert "اسم البائع" in str(exc_info.value)

    def test_build_phase2_qr_invalid_vat_raises(self):
        """Should raise ZATCAError for invalid VAT."""
        with pytest.raises(ZATCAError):
            build_phase2_qr(
                seller_name="شركة",
                seller_vat="123",  # Invalid
                timestamp="2026-08-12T10:30:00Z",
                gross_total=1000,
                vat_total=130.43,
                invoice_type="standard",
            )

    def test_build_phase2_qr_vat_exceeds_gross_raises(self):
        """Should raise ZATCAError if VAT > gross."""
        with pytest.raises(ZATCAError) as exc_info:
            build_phase2_qr(
                seller_name="شركة",
                seller_vat="311187605900003",
                timestamp="2026-08-12T10:30:00Z",
                gross_total=100,
                vat_total=200,  # Exceeds gross
                invoice_type="standard",
            )
        assert "يتجاوز" in str(exc_info.value)

    def test_build_phase2_qr_output_structure(self):
        """Should return dict with expected keys."""
        result = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=1000,
            vat_total=130.43,
            invoice_type="standard",
        )
        assert "tlv_b64" in result
        assert "qr_png_b64" in result
        assert "tags" in result
        assert isinstance(result["tlv_b64"], str)

    def test_build_phase2_qr_tlv_base64_valid(self):
        """Should produce valid base64-encoded TLV."""
        result = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=1000,
            vat_total=130.43,
            invoice_type="standard",
        )
        # Should be decodable
        decoded = base64.b64decode(result["tlv_b64"])
        assert isinstance(decoded, bytes)
        # Should parse back as TLV
        tags = parse_tlv(decoded)
        assert len(tags) >= 5

    def test_build_phase2_qr_qr_png_data_uri(self):
        """Should generate valid PNG data URI."""
        result = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=1000,
            vat_total=130.43,
            invoice_type="standard",
        )
        assert result["qr_png_b64"].startswith("data:image/png;base64,")
        # Extract base64 and verify it's valid
        b64_part = result["qr_png_b64"].split(",", 1)[1]
        png_bytes = base64.b64decode(b64_part)
        # PNG magic bytes
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'


class TestZATCAQREdgeCases:
    """Integration and edge case tests."""

    def test_amount_formatting_precision(self):
        """Should format amounts consistently."""
        result1 = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=Decimal("1234.567"),
            vat_total=Decimal("160.99"),
            invoice_type="standard",
        )
        # Should be rounded to 2 decimals
        tags = dict(result1["tags"])
        # Tag 4 is gross
        assert "." in tags[4]
        parts = tags[4].split(".")
        assert len(parts[1]) == 2

    def test_unicode_handling(self):
        """Should handle Arabic text correctly."""
        result = build_phase2_qr(
            seller_name="شركة الهلال للعطور",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=1000,
            vat_total=130.43,
            invoice_type="standard",
        )
        tags = dict(result["tags"])
        assert tags[1] == "شركة الهلال للعطور"

    def test_large_amounts(self):
        """Should handle large amounts."""
        result = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=999999999.99,
            vat_total=999999999.99,
            invoice_type="standard",
        )
        assert result["tlv_b64"]

    def test_zero_vat(self):
        """Should handle zero VAT (exempt goods)."""
        result = build_phase2_qr(
            seller_name="شركة",
            seller_vat="311187605900003",
            timestamp="2026-08-12T10:30:00Z",
            gross_total=1000,
            vat_total=0,
            invoice_type="standard",
        )
        tags = dict(result["tags"])
        assert tags[5] == "0.00"
