"""Tests for deep_scan utility functions."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deep_scan import IS_WINDOWS, is_prohibited, _should_skip_dir, _classify_by_filetypes

IS_NOT_WINDOWS = pytest.mark.skipif(
    not IS_WINDOWS,
    reason="Windows-specific paths only apply on Windows",
)


class TestIsProhibited:
    @IS_NOT_WINDOWS
    def test_windows_system_dir(self):
        assert is_prohibited("C:\\Windows")

    @IS_NOT_WINDOWS
    def test_windows_program_files(self):
        assert is_prohibited("C:\\Program Files")

    def test_windows_temp_allowed(self):
        assert is_prohibited("C:\\Windows\\Temp") is False

    def test_windows_prefetch_allowed(self):
        assert is_prohibited("C:\\Windows\\Prefetch") is False

    def test_windows_logs_allowed(self):
        assert is_prohibited("C:\\Windows\\Logs") is False

    def test_windows_softwaredistribution_allowed(self):
        assert is_prohibited("C:\\Windows\\SoftwareDistribution") is False

    def test_normal_user_dir(self):
        assert is_prohibited("C:\\Users\\test") is False

    def test_empty_string(self):
        assert is_prohibited("") is False


class TestShouldSkipDir:
    def test_git(self):
        assert _should_skip_dir(".git")

    def test_svn(self):
        assert _should_skip_dir(".svn")

    def test_normal_dir(self):
        assert not _should_skip_dir("src")

    def test_case_insensitive(self):
        assert _should_skip_dir(".GIT")


class TestClassifyByFiletypes:
    def test_empty_directory(self, tmp_path):
        result = _classify_by_filetypes(str(tmp_path))
        assert "空目录" in result or "无文件" in result

    def test_media_directory(self, tmp_path):
        (tmp_path / "video.mp4").write_text("data")
        (tmp_path / "movie.mkv").write_text("data")
        result = _classify_by_filetypes(str(tmp_path))
        assert "影视" in result or "视频" in result

    def test_code_directory(self, tmp_path):
        (tmp_path / "main.py").write_text("data")
        (tmp_path / "utils.js").write_text("data")
        result = _classify_by_filetypes(str(tmp_path))
        assert "代码" in result
