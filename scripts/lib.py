"""
Disk Deep Clean — 公共工具函数
纯 Python 标准库，跨平台兼容
"""

import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Optional


# ── 平台检测 ────────────────────────────────────────────

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


# ── 数据目录 ────────────────────────────────────────────

def ensure_data_dir(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        data_dir = Path(custom_path).resolve()
    else:
        script_dir = Path(__file__).resolve().parent
        data_dir = script_dir.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# ── 固定磁盘检测 ─────────────────────────────────────────

def get_fixed_drives() -> list:
    if IS_WINDOWS:
        drives = []
        kernel32 = ctypes.windll.kernel32
        bitmask = kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drive_letter = f"{chr(65 + i)}:\\"
                if kernel32.GetDriveTypeW(drive_letter) == 3:
                    drives.append(f"{chr(65 + i)}:")
        return drives
    else:
        return ["/"]


# ── 文件大小格式化 ───────────────────────────────────────

def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes} B"


# ── 回收站操作 ───────────────────────────────────────────

def move_to_trash(path: str) -> bool:
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False

    if IS_WINDOWS:
        success = _trash_windows(path)
        if not success:
            # 回收站失败(如路径超长) → 回退到直接删除
            try:
                safe = safe_normalize_path(path)
                if os.path.isfile(safe) or os.path.islink(safe):
                    os.remove(safe)
                elif os.path.isdir(safe):
                    shutil.rmtree(safe, ignore_errors=True)
                return not os.path.exists(path)
            except (PermissionError, OSError):
                return False
        return success
    elif IS_MAC:
        return _trash_mac(path)
    else:
        return _trash_linux(path)


def _trash_windows(path: str) -> bool:
    from ctypes import wintypes
    shell32 = ctypes.windll.shell32

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x40
    FOF_NOCONFIRMATION = 0x10
    FOF_NOERRORUI = 0x400
    FOF_SILENT = 0x4

    # SHFileOperationW 不支持 \\?\ 前缀，用原始路径
    file_op = SHFILEOPSTRUCTW()
    file_op.wFunc = FO_DELETE
    file_op.pFrom = path + "\0\0"
    file_op.pTo = None
    file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT

    result = shell32.SHFileOperationW(ctypes.byref(file_op))
    return result == 0 and not file_op.fAnyOperationsAborted


def _trash_mac(path: str) -> bool:
    try:
        escaped = path.replace('"', '\\"')
        script = f'''
        tell application "Finder"
            delete POSIX file "{escaped}"
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _trash_linux(path: str) -> bool:
    try:
        data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        trash_dir = os.path.join(data_home, "Trash")
        files_dir = os.path.join(trash_dir, "files")
        info_dir = os.path.join(trash_dir, "info")
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(info_dir, exist_ok=True)
        basename = os.path.basename(path)
        dest = os.path.join(files_dir, basename)
        if os.path.exists(dest):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            name, ext = os.path.splitext(basename)
            dest = os.path.join(files_dir, f"{name}_{timestamp}{ext}")
        shutil.move(path, dest)
        info_path = os.path.join(info_dir, os.path.basename(dest) + ".trashinfo")
        with open(info_path, "w", encoding="utf-8") as f:
            f.write("[Trash Info]\n")
            f.write(f"Path={path}\n")
            f.write(f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")
        return True
    except (PermissionError, OSError, shutil.Error):
        return False


# ── 管理员检测 ───────────────────────────────────────────

def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    else:
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False


# ── 日志记录 ────────────────────────────────────────────

def log_action(data_dir: Path, action: str, path: str, size: int,
               status: str = "OK") -> None:
    r"""
    格式: [2026-06-03 14:30:00] DELETE | C:\xxx\file.tmp | 1.23 MB | OK
    """
    log_file = data_dir / "disk-clean-log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    size_str = format_size(size) if size >= 0 else "-"
    line = f"[{timestamp}] {action} | {path} | {size_str} | {status}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except (PermissionError, OSError):
        pass


# ── 路径安全前缀 ─────────────────────────────────────────

def safe_normalize_path(path: str) -> str:
    if IS_WINDOWS and len(path) > 260 and not path.startswith("\\\\?\\"):
        return "\\\\?\\" + path
    return path


# ── 长路径遍历 ───────────────────────────────────────────

def safe_scandir(path: str):
    try:
        safe_path = safe_normalize_path(path)
        yield from os.scandir(safe_path)
    except (PermissionError, OSError):
        return


# ── PE 文件版本信息读取（Windows only）───────────────────

def get_pe_version_info(exe_path: str) -> Optional[dict]:
    if not IS_WINDOWS:
        return None
    try:
        version = ctypes.windll.version
        safe_path = safe_normalize_path(exe_path)
        size = version.GetFileVersionInfoSizeW(safe_path, None)
        if size == 0:
            return None
        buf = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(safe_path, 0, size, buf):
            return None
        trans_ptr = ctypes.c_void_p()
        trans_len = ctypes.c_uint()
        if not version.VerQueryValueW(buf, "\\VarFileInfo\\Translation",
                                       ctypes.byref(trans_ptr),
                                       ctypes.byref(trans_len)):
            return None
        lang_id, charset_id = struct.unpack("<HH", ctypes.string_at(trans_ptr, 4))
        lang_hex = f"{lang_id:04x}{charset_id:04x}"
        info = {}
        fields = {
            "ProductName": f"\\StringFileInfo\\{lang_hex}\\ProductName",
            "CompanyName": f"\\StringFileInfo\\{lang_hex}\\CompanyName",
            "FileDescription": f"\\StringFileInfo\\{lang_hex}\\FileDescription",
        }
        for key, query in fields.items():
            try:
                val_ptr = ctypes.c_void_p()
                val_len = ctypes.c_uint()
                if version.VerQueryValueW(buf, query,
                                           ctypes.byref(val_ptr),
                                           ctypes.byref(val_len)):
                    info[key] = ctypes.wstring_at(val_ptr, val_len - 1)
            except Exception:
                continue
        return info if info else None
    except Exception:
        return None


# ── 扫描结果持久化 ───────────────────────────────────────

def save_scan_results(data_dir: Path, results: list) -> Path:
    scan_file = data_dir / "scan-results.json"
    with open(scan_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    return scan_file


def load_scan_results(data_dir: Path) -> list:
    scan_file = data_dir / "scan-results.json"
    if not scan_file.exists():
        return []
    with open(scan_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 命令行参数解析辅助 ────────────────────────────────────

def parse_selections(selections_str: str, max_id: int) -> list:
    if selections_str.strip().lower() == "all-safe":
        return []
    result = []
    parts = [p.strip() for p in selections_str.split(",") if p.strip()]
    for part in parts:
        if "-" in part and not part.startswith("-"):
            try:
                start, end = part.split("-", 1)
                start, end = int(start.strip()), int(end.strip())
                if start > end:
                    start, end = end, start
                result.extend(range(start, end + 1))
            except ValueError:
                print(f"警告: 无法解析范围 '{part}'，已跳过")
        else:
            try:
                result.append(int(part))
            except ValueError:
                print(f"警告: 无法解析序号 '{part}'，已跳过")
    seen = set()
    unique = []
    for n in result:
        if n not in seen and 1 <= n <= max_id:
            seen.add(n)
            unique.append(n)
    return sorted(unique)


# ── 路径匹配辅助 ─────────────────────────────────────────

def path_contains_any(path: str, patterns: list) -> bool:
    lower = path.lower()
    return any(p.lower() in lower for p in patterns)


def get_all_users_dir() -> list:
    r"""
    Windows: 返回 C:\Users 下所有用户目录
    Linux/Mac: 返回 [os.path.expanduser("~")]
    """
    if IS_WINDOWS:
        users = []
        users_root = "C:\\Users"
        if os.path.exists(users_root):
            for entry in safe_scandir(users_root):
                if entry.is_dir():
                    users.append(entry.path)
        return users
    else:
        return [os.path.expanduser("~")]


# ── 包管理器缓存路径 ──────────────────────────────────────

if IS_WINDOWS:
    PACKAGE_CACHE_DIRS = [
        ("pip", "Local", "pip", "cache"),
        ("npm", "Local", "npm-cache"),
        ("npm", "Roaming", "npm-cache"),
        ("pnpm", "Local", "pnpm-cache"),
        ("yarn", "Local", "Yarn", "cache"),
    ]
else:
    PACKAGE_CACHE_DIRS = [
        ("pip", "~/.cache/pip"),
        ("npm", "~/.npm/_cacache"),
        ("pnpm", "~/.cache/pnpm"),
        ("yarn", "~/.cache/yarn"),
    ]


def get_package_cache_paths() -> list:
    paths = []
    if IS_WINDOWS:
        for name, *parts in PACKAGE_CACHE_DIRS:
            for user_dir in get_all_users_dir():
                cache_path = os.path.join(user_dir, "AppData", *parts)
                if os.path.isdir(cache_path):
                    paths.append((cache_path, name))
                    break
    else:
        for name, template in PACKAGE_CACHE_DIRS:
            expanded = os.path.expanduser(template)
            if os.path.isdir(expanded):
                paths.append((expanded, name))
    return paths


# ── 扫描上下文 ──────────────────────────────────────────

class ScanContext:
    __slots__ = ('dir_sizes', 'pycache_agg', 'node_modules_agg',
                 'cumulative', 'classified_paths')

    def __init__(self):
        self.dir_sizes: dict = {}
        self.pycache_agg: dict = {}
        self.node_modules_agg: dict = {}
        self.cumulative: dict = {}
        self.classified_paths: set = set()


# ── 项目根查找 ───────────────────────────────────────────

def find_project_root(path: str, max_depth: int = 10) -> str:
    current = os.path.dirname(path)
    markers = ['.git', 'pyproject.toml', 'setup.py', 'requirements.txt', 'package.json']
    for _ in range(max_depth):
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.dirname(path))


# ── auto_clean 结果读写 ──────────────────────────────────

def load_auto_clean_result(data_dir: Path) -> Optional[dict]:
    result_file = data_dir / "auto-clean-result.json"
    if not result_file.exists():
        return None
    try:
        with open(result_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ── 目录大小计算 ──────────────────────────────────────────

def get_dir_size(path: str) -> int:
    """递归计算目录总大小（字节），排除权限错误"""
    total = 0
    try:
        for entry in safe_scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total


def save_auto_clean_result(data_dir: Path, result: dict) -> Path:
    result_file = data_dir / "auto-clean-result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    return result_file
