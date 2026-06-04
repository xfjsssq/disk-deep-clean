"""Tests for Disk Deep Clean core library functions.

Run with: pytest tests/ -v
"""

import os
import sys

from lib import (
    ensure_data_dir,
    find_project_root,
    format_size,
    get_all_users_dir,
    get_dir_size,
    get_fixed_drives,
    get_package_cache_paths,
    is_admin,
    IS_WINDOWS,
    load_auto_clean_result,
    load_scan_results,
    move_to_trash,
    parse_selections,
    path_contains_any,
    safe_normalize_path,
    safe_scandir,
    save_auto_clean_result,
    save_scan_results,
    ScanContext,
)


# ─── format_size tests ─────────────────────────────────────

class TestFormatSize:
    def test_bytes(self):
        assert format_size(0) == "0 B"
        assert format_size(1) == "1 B"
        assert format_size(1023) == "1023 B"

    def test_kb(self):
        assert format_size(1024) == "1.00 KB"
        assert format_size(2048) == "2.00 KB"
        assert format_size(1536) == "1.50 KB"

    def test_mb(self):
        assert format_size(1024 ** 2) == "1.00 MB"
        assert format_size(5 * 1024 ** 2) == "5.00 MB"

    def test_gb(self):
        assert format_size(1024 ** 3) == "1.00 GB"
        assert format_size(10 * 1024 ** 3) == "10.00 GB"

    def test_large(self):
        assert format_size(2 * 1024 ** 4) == "2048.00 GB"


# ─── parse_selections tests ────────────────────────────────

class TestParseSelections:
    def test_single(self):
        assert parse_selections("3", 10) == [3]

    def test_comma_separated(self):
        assert parse_selections("1,3,5", 10) == [1, 3, 5]

    def test_range(self):
        assert parse_selections("1-3", 10) == [1, 2, 3]

    def test_mixed(self):
        assert parse_selections("1,3-5,7", 10) == [1, 3, 4, 5, 7]

    def test_all_safe(self):
        assert parse_selections("all-safe", 10) == []

    def test_out_of_range(self):
        assert parse_selections("1,99", 10) == [1]

    def test_duplicates(self):
        assert parse_selections("1,1,2,2", 10) == [1, 2]

    def test_reversed_range(self):
        assert parse_selections("5-3", 10) == [3, 4, 5]

    def test_empty_string(self):
        assert parse_selections("", 10) == []


# ─── path_contains_any tests ───────────────────────────────

class TestPathContainsAny:
    def test_simple_match(self):
        assert path_contains_any("/usr/local/temp", ["temp"]) is True

    def test_case_insensitive(self):
        assert path_contains_any("/usr/local/TEMP", ["temp"]) is True

    def test_no_match(self):
        assert path_contains_any("/usr/local", ["temp"]) is False

    def test_empty_patterns(self):
        assert path_contains_any("/usr/local", []) is False

    def test_multiple_patterns(self):
        assert path_contains_any("/usr/local/cache", ["temp", "cache"]) is True

    def test_windows_path(self):
        assert path_contains_any("C:\\Users\\test\\Temp", ["temp"]) is True


# ─── ensure_data_dir tests ─────────────────────────────────

class TestEnsureDataDir:
    def test_custom_path(self, tmp_path):
        custom = str(tmp_path / "my-data")
        result = ensure_data_dir(custom)
        assert result == tmp_path / "my-data"
        assert result.exists()

    def test_default_path(self):
        # Default should be under project root /data
        result = ensure_data_dir()
        assert result.name == "data"


# ─── get_fixed_drives tests ────────────────────────────────

class TestGetFixedDrives:
    def test_returns_list(self):
        drives = get_fixed_drives()
        assert isinstance(drives, list)
        assert len(drives) > 0

    def test_drive_format(self):
        drives = get_fixed_drives()
        for d in drives:
            if IS_WINDOWS:
                assert len(d) == 2 and d[1] == ":"
            else:
                assert d == "/"


# ─── safe_normalize_path tests ─────────────────────────────

class TestSafeNormalizePath:
    def test_short_path_unchanged(self):
        path = "C:\\test\\file.txt"
        result = safe_normalize_path(path)
        assert result == path

    def test_long_path_gets_prefix(self):
        if IS_WINDOWS:
            long_path = "C:\\" + "a" * 260 + "\\file.txt"
            result = safe_normalize_path(long_path)
            assert result.startswith("\\\\?\\")


# ─── get_dir_size tests ────────────────────────────────────

class TestGetDirSize:
    def test_empty_directory(self, tmp_path):
        assert get_dir_size(str(tmp_path)) == 0

    def test_single_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert get_dir_size(str(tmp_path)) == 5

    def test_nested_directories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        f1 = tmp_path / "a.txt"
        f1.write_text("12345")
        f2 = sub / "b.txt"
        f2.write_text("1234567890")
        assert get_dir_size(str(tmp_path)) == 15

    def test_nonexistent_path(self):
        assert get_dir_size("/nonexistent/path") == 0


# ─── is_admin tests ────────────────────────────────────────

class TestIsAdmin:
    def test_returns_bool(self):
        result = is_admin()
        assert isinstance(result, bool)


# ─── get_all_users_dir tests ───────────────────────────────

class TestGetAllUsersDir:
    def test_returns_list(self):
        users = get_all_users_dir()
        assert isinstance(users, list)
        assert len(users) > 0

    def test_paths_exist(self):
        for p in get_all_users_dir():
            assert os.path.isdir(p)


# ─── get_package_cache_paths tests ─────────────────────────

class TestGetPackageCachePaths:
    def test_returns_list(self):
        caches = get_package_cache_paths()
        assert isinstance(caches, list)
        # May be empty on CI but should be a list


# ─── ScanContext tests ─────────────────────────────────────

class TestScanContext:
    def test_initialization(self):
        ctx = ScanContext()
        assert ctx.dir_sizes == {}
        assert ctx.pycache_agg == {}
        assert ctx.node_modules_agg == {}
        assert ctx.cumulative == {}
        assert ctx.classified_paths == set()

    def test_slots(self):
        ctx = ScanContext()
        ctx.dir_sizes["/test"] = 100
        assert ctx.dir_sizes["/test"] == 100


# ─── find_project_root tests ───────────────────────────────

class TestFindProjectRoot:
    def test_current_directory(self, tmp_path):
        # Create markers
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        result = find_project_root(str(sub / "file.py"))
        assert result == str(tmp_path)

    def test_max_depth(self):
        result = find_project_root("/", max_depth=1)
        assert result is not None


# ─── JSON persistence tests ────────────────────────────────

class TestJSONPersistence:
    def test_save_and_load_scan_results(self, tmp_path):
        data = [{"id": 1, "name": "test", "size": 100}]
        saved = save_scan_results(tmp_path, data)
        assert saved.exists()
        loaded = load_scan_results(tmp_path)
        assert loaded == data

    def test_load_missing(self, tmp_path):
        assert load_scan_results(tmp_path) == []

    def test_save_and_load_auto_clean(self, tmp_path):
        data = {"total_freed": 100, "items": []}
        saved = save_auto_clean_result(tmp_path, data)
        assert saved.exists()
        loaded = load_auto_clean_result(tmp_path)
        assert loaded == data

    def test_load_auto_clean_missing(self, tmp_path):
        assert load_auto_clean_result(tmp_path) is None


# ─── move_to_trash tests ───────────────────────────────────

class TestMoveToTrash:
    def test_nonexistent_path(self):
        assert move_to_trash("/nonexistent/path/xyz123") is False

    def test_trash_temporary_file(self, tmp_path):
        f = tmp_path / "to-delete.txt"
        f.write_text("test")
        result = move_to_trash(str(f))
        # Should succeed on all platforms
        assert result is True
        # Original file should no longer exist
        assert not f.exists()


# ─── safe_scandir tests ────────────────────────────────────

class TestSafeScandir:
    def test_existing_directory(self, tmp_path):
        entries = list(safe_scandir(str(tmp_path)))
        assert isinstance(entries, list)

    def test_nonexistent_path(self):
        entries = list(safe_scandir("/nonexistent_path_xyz"))
        assert entries == []
