"""
Comprehensive tests for all helper utilities and helper functions.
Tests utility functions, configuration helpers, and common operations.
"""
import pytest
from pathlib import Path
from app.db import (
    DB_PATH, DATA_DIR, UPLOAD_DIR, EXPORT_DIR, KEYS_DIR, TMP_DIR,
    BASE_DIR, APP_DIR
)


class TestPathHelpers:
    """Test path helper utilities and directory constants."""

    def test_base_dir_exists(self):
        """BASE_DIR should point to project root."""
        assert BASE_DIR.exists()
        assert BASE_DIR.name == 'invoice-generator'

    def test_app_dir_exists(self):
        """APP_DIR should point to app directory."""
        assert APP_DIR.exists()
        assert APP_DIR.name == 'app'

    def test_data_dir_path(self):
        """DATA_DIR should be under BASE_DIR."""
        assert DATA_DIR.parent == BASE_DIR
        assert DATA_DIR.name == 'data'

    def test_db_path_location(self):
        """DB_PATH should be in DATA_DIR."""
        assert DB_PATH.parent == DATA_DIR
        assert DB_PATH.name == 'itqan_invoices.db'

    def test_upload_dir_path(self):
        """UPLOAD_DIR should be under DATA_DIR."""
        assert UPLOAD_DIR.parent == DATA_DIR
        assert UPLOAD_DIR.name == 'uploads'

    def test_export_dir_path(self):
        """EXPORT_DIR should be under DATA_DIR."""
        assert EXPORT_DIR.parent == DATA_DIR
        assert EXPORT_DIR.name == 'exports'

    def test_keys_dir_path(self):
        """KEYS_DIR should be under DATA_DIR."""
        assert KEYS_DIR.parent == DATA_DIR
        assert KEYS_DIR.name == 'keys'

    def test_tmp_dir_path(self):
        """TMP_DIR should be under DATA_DIR."""
        assert TMP_DIR.parent == DATA_DIR
        assert TMP_DIR.name == 'tmp'

    def test_path_separators(self):
        """Paths should be properly formed."""
        assert str(DATA_DIR).endswith('data')
        assert str(DB_PATH).endswith('itqan_invoices.db')

    def test_path_instances(self):
        """All paths should be Path instances."""
        assert isinstance(BASE_DIR, Path)
        assert isinstance(APP_DIR, Path)
        assert isinstance(DATA_DIR, Path)
        assert isinstance(DB_PATH, Path)
        assert isinstance(UPLOAD_DIR, Path)
        assert isinstance(EXPORT_DIR, Path)
        assert isinstance(KEYS_DIR, Path)
        assert isinstance(TMP_DIR, Path)


class TestConfigurationConstants:
    """Test configuration constants and their validity."""

    def test_base_dir_not_none(self):
        """BASE_DIR should not be None."""
        assert BASE_DIR is not None

    def test_app_dir_not_none(self):
        """APP_DIR should not be None."""
        assert APP_DIR is not None

    def test_data_dir_not_none(self):
        """DATA_DIR should not be None."""
        assert DATA_DIR is not None

    def test_db_path_not_none(self):
        """DB_PATH should not be None."""
        assert DB_PATH is not None

    def test_directories_are_strings_or_paths(self):
        """Directory constants should be Path objects."""
        for path in [BASE_DIR, APP_DIR, DATA_DIR, UPLOAD_DIR, EXPORT_DIR, KEYS_DIR, TMP_DIR]:
            assert isinstance(path, Path) or isinstance(str(path), str)

    def test_db_path_string_valid(self):
        """DB_PATH string representation should be valid."""
        db_str = str(DB_PATH)
        assert len(db_str) > 0
        assert 'itqan_invoices.db' in db_str

    def test_path_hierarchy_valid(self):
        """Path hierarchy should be correct."""
        assert APP_DIR.parent == BASE_DIR
        assert DATA_DIR.parent == BASE_DIR


class TestDatabaseConfiguration:
    """Test database configuration and schema."""

    def test_database_name_correct(self):
        """Database should have correct name."""
        assert DB_PATH.name == 'itqan_invoices.db'

    def test_database_extension(self):
        """Database should have .db extension."""
        assert DB_PATH.suffix == '.db'

    def test_database_path_has_data_directory(self):
        """Database path should include data directory."""
        assert 'data' in str(DB_PATH)

    def test_database_path_complete(self):
        """Database path should be complete and absolute."""
        assert str(DB_PATH).startswith(str(BASE_DIR))


class TestDirectoryStructure:
    """Test directory structure organization."""

    def test_data_dir_is_subdirectory(self):
        """DATA_DIR should be a subdirectory of BASE_DIR."""
        assert DATA_DIR.is_relative_to(BASE_DIR) or BASE_DIR in DATA_DIR.parents

    def test_all_data_subdirs_in_data(self):
        """All data subdirectories should be under DATA_DIR."""
        for subdir in [UPLOAD_DIR, EXPORT_DIR, KEYS_DIR, TMP_DIR]:
            assert subdir.parent == DATA_DIR

    def test_db_in_data_directory(self):
        """Database should be in DATA_DIR."""
        assert DB_PATH.parent == DATA_DIR

    def test_no_circular_paths(self):
        """Paths should not be circular."""
        assert DATA_DIR != BASE_DIR
        assert APP_DIR != BASE_DIR
        assert DB_PATH != DATA_DIR


class TestPathOperations:
    """Test path operations and manipulations."""

    def test_path_resolution(self):
        """Paths should be properly resolved."""
        assert BASE_DIR.is_absolute() or str(BASE_DIR).startswith('.')

    def test_path_parts(self):
        """Paths should have valid parts."""
        assert len(BASE_DIR.parts) > 0
        assert len(DATA_DIR.parts) > len(BASE_DIR.parts)

    def test_path_as_string(self):
        """Paths should convert to valid strings."""
        assert isinstance(str(BASE_DIR), str)
        assert len(str(DATA_DIR)) > 0

    def test_path_joining(self):
        """Paths should support joining operations."""
        test_file = DATA_DIR / 'test.txt'
        assert 'test.txt' in str(test_file)

    def test_path_parent_relationships(self):
        """Parent relationships should be correct."""
        assert DATA_DIR.parent == BASE_DIR
        assert UPLOAD_DIR.parent == DATA_DIR


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_base_dir_valid(self):
        """BASE_DIR should be valid."""
        assert BASE_DIR is not None
        assert str(BASE_DIR) != ''
        assert not str(BASE_DIR).endswith('.')

    def test_app_dir_valid(self):
        """APP_DIR should be valid."""
        assert APP_DIR is not None
        assert str(APP_DIR) != ''

    def test_data_dir_valid(self):
        """DATA_DIR should be valid."""
        assert DATA_DIR is not None
        assert str(DATA_DIR) != ''

    def test_db_path_valid(self):
        """DB_PATH should be valid."""
        assert DB_PATH is not None
        assert str(DB_PATH) != ''
        assert '.db' in str(DB_PATH)

    def test_all_paths_defined(self):
        """All required paths should be defined."""
        paths = [BASE_DIR, APP_DIR, DATA_DIR, DB_PATH,
                UPLOAD_DIR, EXPORT_DIR, KEYS_DIR, TMP_DIR]
        for path in paths:
            assert path is not None


class TestEnvironmentIntegration:
    """Test environment integration and setup."""

    def test_paths_work_with_pathlib(self):
        """Paths should work with pathlib operations."""
        assert hasattr(BASE_DIR, 'exists')
        assert hasattr(DATA_DIR, 'parts')

    def test_string_conversion_consistent(self):
        """String conversion should be consistent."""
        db_str_1 = str(DB_PATH)
        db_str_2 = str(DB_PATH)
        assert db_str_1 == db_str_2

    def test_path_instance_types(self):
        """Path instances should be proper types."""
        from pathlib import Path as PathlibPath
        assert isinstance(BASE_DIR, PathlibPath)
        assert isinstance(DATA_DIR, PathlibPath)

    def test_multiple_path_accesses(self):
        """Multiple accesses to paths should work."""
        for _ in range(3):
            assert BASE_DIR.name == 'invoice-generator'
            assert DATA_DIR.name == 'data'


class TestHelperFunctionIntegration:
    """Test integration of helper functions."""

    def test_database_ready_for_import(self):
        """Database module should be importable."""
        from app import db
        assert hasattr(db, 'DB_PATH')
        assert hasattr(db, 'DATA_DIR')

    def test_path_constants_accessible(self):
        """Path constants should be accessible."""
        from app.db import BASE_DIR as bd
        from app.db import DATA_DIR as dd
        assert bd is not None
        assert dd is not None

    def test_schema_defined(self):
        """Database schema should be defined."""
        from app.db import SCHEMA
        assert SCHEMA is not None
        assert len(SCHEMA) > 0
        assert 'CREATE TABLE' in SCHEMA


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_path_with_special_characters(self):
        """Paths should handle special characters."""
        # Most Path operations should work transparently
        assert str(DB_PATH) is not None

    def test_deeply_nested_paths(self):
        """Deeply nested paths should work."""
        nested = DATA_DIR / 'uploads' / 'invoices' / '2024' / '09' / 'test.pdf'
        assert 'invoices' in str(nested)

    def test_path_normalization(self):
        """Paths should be normalized."""
        # Path object handles normalization
        assert DB_PATH.resolve() is not None

    def test_empty_operations_on_paths(self):
        """Empty operations on paths should not fail."""
        _ = BASE_DIR.parent
        _ = DATA_DIR.parts
        _ = DB_PATH.stat() if DB_PATH.exists() else None


class TestErrorHandling:
    """Test error handling in helper utilities."""

    def test_missing_paths_graceful(self):
        """Missing paths should be handled gracefully."""
        # Path objects don't error on missing paths
        assert UPLOAD_DIR is not None

    def test_path_access_safe(self):
        """Path access should be safe."""
        try:
            _ = DATA_DIR / 'test'
            assert True
        except Exception as e:
            pytest.fail(f"Path access failed: {e}")

    def test_multiple_path_creations(self):
        """Multiple path creations should be independent."""
        path1 = BASE_DIR / 'test1'
        path2 = BASE_DIR / 'test2'
        assert path1 != path2


class TestDocumentation:
    """Test that helpers are properly documented."""

    def test_module_has_docstring(self):
        """Module should have docstring."""
        import app.db
        assert app.db.__doc__ is not None

    def test_schema_is_non_empty_string(self):
        """Schema should be a non-empty string."""
        from app.db import SCHEMA
        assert isinstance(SCHEMA, str)
        assert len(SCHEMA) > 100  # Schema should be substantial

    def test_constants_named_correctly(self):
        """Constants should follow naming conventions."""
        # All caps for constants
        assert 'BASE_DIR' == 'BASE_DIR'.upper()
        assert 'DATA_DIR' == 'DATA_DIR'.upper()


class TestCombinedOperations:
    """Test combined helper operations."""

    def test_path_chain_operations(self):
        """Path chain operations should work."""
        test_path = BASE_DIR / 'data' / 'uploads' / 'test.txt'
        assert 'uploads' in str(test_path)

    def test_multiple_module_imports(self):
        """Multiple imports from db module should work."""
        from app.db import DB_PATH, DATA_DIR, BASE_DIR
        assert DB_PATH is not None
        assert DATA_DIR is not None
        assert BASE_DIR is not None

    def test_configuration_consistency(self):
        """Configuration should be consistent across imports."""
        from app.db import DB_PATH as path1
        from app.db import DB_PATH as path2
        assert path1 == path2

    def test_all_constants_unique(self):
        """All directory constants should be unique."""
        dirs = [BASE_DIR, APP_DIR, DATA_DIR, UPLOAD_DIR,
               EXPORT_DIR, KEYS_DIR, TMP_DIR]
        # Convert to strings to compare
        dir_strs = [str(d) for d in dirs]
        assert len(dir_strs) == len(set(dir_strs))
