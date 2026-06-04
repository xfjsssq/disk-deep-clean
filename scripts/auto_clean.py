"""
自动安全清理 — 无需用户确认，清理明确的垃圾文件。
用法: python scripts/auto_clean.py [--data-dir PATH] [--dry-run] [--permanent]
"""

import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import argparse
import glob
from pathlib import Path
import shutil

try:
    from scripts.lib import (
        IS_LINUX,
        IS_MAC,
        IS_WINDOWS,
        ensure_data_dir,
        format_size,
        get_all_users_dir,
        get_dir_size,
        get_fixed_drives,
        get_package_cache_paths,
        is_admin,
        log_action,
        move_to_trash,
        safe_scandir,
        save_auto_clean_result,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib import (
        IS_LINUX,
        IS_MAC,
        IS_WINDOWS,
        ensure_data_dir,
        format_size,
        get_all_users_dir,
        get_dir_size,
        get_fixed_drives,
        get_package_cache_paths,
        is_admin,
        log_action,
        move_to_trash,
        safe_scandir,
        save_auto_clean_result,
    )


def clean_temp_files(data_dir: Path, dry_run: bool, permanent: bool) -> tuple:
    r"""清理 %TEMP% 和 C:\Windows\Temp"""
    freed = 0
    temp_dirs = []
    if IS_WINDOWS:
        temp_dirs.append(os.environ.get("TEMP", ""))
        temp_dirs.append(os.environ.get("TMP", ""))
        temp_dirs.append("C:\\Windows\\Temp")
    else:
        temp_dirs.append("/tmp")
        temp_dirs.append("/var/tmp")
    for temp_root in temp_dirs:
        if not temp_root or not os.path.isdir(temp_root):
            continue
        for entry in safe_scandir(temp_root):
            try:
                size = get_dir_size(entry.path) if entry.is_dir() else entry.stat().st_size
                if not dry_run:
                    if permanent:
                        if entry.is_dir():
                            shutil.rmtree(entry.path, ignore_errors=True)
                        else:
                            os.remove(entry.path)
                    else:
                        move_to_trash(entry.path)
                freed += size
                log_action(data_dir, "DELETE" if not permanent else "PERM_DELETE",
                          entry.path, size)
            except (PermissionError, OSError):
                log_action(data_dir, "SKIP", entry.path,
                           size if 'size' in dir() else -1, "PERMISSION")
                continue
    return freed, len(temp_dirs)


def clean_browser_cache(data_dir: Path, dry_run: bool, permanent: bool) -> tuple:
    if not IS_WINDOWS:
        return 0, 0
    freed = 0
    browser_count = 0
    users = get_all_users_dir()
    browsers = {
        "Chrome": os.path.join("AppData", "Local", "Google", "Chrome", "User Data"),
        "Edge": os.path.join("AppData", "Local", "Microsoft", "Edge", "User Data"),
        "Firefox": os.path.join("AppData", "Local", "Mozilla", "Firefox", "Profiles"),
    }
    for user_dir in users:
        for browser_name, browser_rel_path in browsers.items():
            browser_path = os.path.join(user_dir, browser_rel_path)
            if not os.path.isdir(browser_path):
                continue
            if browser_name in ("Chrome", "Edge"):
                for entry in safe_scandir(browser_path):
                    if not entry.is_dir():
                        continue
                    for cache_sub in ["Cache", "Code Cache", "Service Worker",
                                      "GPUCache", "DawnCache"]:
                        cache_path = os.path.join(entry.path, cache_sub)
                        if os.path.isdir(cache_path):
                            size = get_dir_size(cache_path)
                            if not dry_run:
                                try:
                                    if permanent:
                                        shutil.rmtree(cache_path, ignore_errors=True)
                                    else:
                                        move_to_trash(cache_path)
                                except (PermissionError, OSError):
                                    log_action(data_dir, "SKIP", cache_path, size, "PERMISSION")
                                    continue
                            freed += size
                            log_action(data_dir, "DELETE", cache_path, size)
                            browser_count += 1
            elif browser_name == "Firefox":
                for profile_dir in safe_scandir(browser_path):
                    if not profile_dir.is_dir():
                        continue
                    for cache_sub in ["cache2", "startupCache", "thumbnails"]:
                        cache_path = os.path.join(profile_dir.path, cache_sub)
                        if os.path.isdir(cache_path):
                            size = get_dir_size(cache_path)
                            if not dry_run:
                                try:
                                    if permanent:
                                        shutil.rmtree(cache_path, ignore_errors=True)
                                    else:
                                        move_to_trash(cache_path)
                                except (PermissionError, OSError):
                                    continue
                            freed += size
                            log_action(data_dir, "DELETE", cache_path, size)
                            browser_count += 1
    return freed, browser_count


def clean_package_caches(data_dir: Path, dry_run: bool, permanent: bool) -> tuple:
    freed = 0
    cache_count = 0
    for cache_path, cache_name in get_package_cache_paths():
        if not os.path.isdir(cache_path):
            continue
        try:
            size = get_dir_size(cache_path)
            if not dry_run:
                if permanent:
                    shutil.rmtree(cache_path, ignore_errors=True)
                else:
                    move_to_trash(cache_path)
            freed += size
            cache_count += 1
            log_action(data_dir, "DELETE" if not permanent else "PERM_DELETE",
                       cache_path, size)
        except (PermissionError, OSError):
            log_action(data_dir, "SKIP", cache_path, -1, "PERMISSION")
            continue
    return freed, cache_count


def empty_recycle_bin(data_dir: Path, dry_run: bool) -> int:
    if not IS_WINDOWS:
        trash_paths = []
        if IS_LINUX:
            dh = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
            trash_paths.append(os.path.join(dh, "Trash", "files"))
        if IS_MAC:
            trash_paths.append(os.path.expanduser("~/.Trash"))
        freed = 0
        for tp in trash_paths:
            if os.path.isdir(tp):
                size = get_dir_size(tp)
                if not dry_run:
                    shutil.rmtree(tp, ignore_errors=True)
                    os.makedirs(tp, exist_ok=True)
                freed += size
        return freed
    import ctypes
    try:
        shell32 = ctypes.windll.shell32
        freed = 0
        for drive in get_fixed_drives():
            recycle_path = os.path.join(drive + "\\", "$Recycle.Bin")
            if os.path.isdir(recycle_path):
                freed += get_dir_size(recycle_path)
        if not dry_run:
            SHERB_NOCONFIRMATION = 0x1
            SHERB_NOPROGRESSUI = 0x2
            SHERB_NOSOUND = 0x4
            shell32.SHEmptyRecycleBinW(None, None,
                          SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
        return freed
    except Exception as e:
        log_action(data_dir, "ERROR", "RecycleBin", -1, str(e))
        return 0


def clean_windows_update_cache(data_dir: Path, dry_run: bool, permanent: bool) -> int:
    r"""清理 C:\Windows\SoftwareDistribution\Download（需管理员）"""
    if not IS_WINDOWS:
        return 0
    path = "C:\\Windows\\SoftwareDistribution\\Download"
    if not os.path.isdir(path):
        return 0
    if not is_admin():
        log_action(data_dir, "SKIP", path, -1, "NEED_ADMIN")
        return 0
    size = get_dir_size(path)
    if not dry_run:
        try:
            for entry in safe_scandir(path):
                try:
                    if permanent:
                        os.remove(entry.path)
                    else:
                        shutil.rmtree(entry.path, ignore_errors=True)
                except (PermissionError, OSError):
                    pass
            log_action(data_dir, "DELETE", path, size)
        except Exception as e:
            log_action(data_dir, "ERROR", path, size, str(e))
            return 0
    return size


def clean_thumbnail_cache(data_dir: Path, dry_run: bool, permanent: bool) -> int:
    if not IS_WINDOWS:
        return 0
    freed = 0
    users = get_all_users_dir()
    for user_dir in users:
        thumbcache_dir = os.path.join(user_dir, "AppData", "Local",
                                      "Microsoft", "Windows", "Explorer")
        if not os.path.isdir(thumbcache_dir):
            continue
        for pattern in ["thumbcache_*.db", "ThumbCache_*.db"]:
            for f in glob.glob(os.path.join(thumbcache_dir, pattern)):
                try:
                    size = os.path.getsize(f)
                    if not dry_run:
                        if permanent:
                            os.remove(f)
                        else:
                            move_to_trash(f)
                    freed += size
                    log_action(data_dir, "DELETE", f, size)
                except (PermissionError, OSError):
                    continue
    return freed


def clean_crash_dumps(data_dir: Path, dry_run: bool, permanent: bool) -> tuple:
    freed = 0
    count = 0
    for drive in get_fixed_drives():
        scan_root = drive + "\\" if IS_WINDOWS else drive
        for root, dirs, files in os.walk(scan_root):
            dirs[:] = [d for d in dirs if not _is_prohibited_dir(os.path.join(root, d))]
            for f in files:
                if f.lower().endswith(('.dmp', '.hdmp')):
                    filepath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(filepath)
                        if not dry_run:
                            if permanent:
                                os.remove(filepath)
                            else:
                                move_to_trash(filepath)
                        freed += size
                        count += 1
                        log_action(data_dir, "DELETE", filepath, size)
                    except (PermissionError, OSError) as e:
                        log_action(data_dir, "SKIP", filepath, -1, str(e))
                        continue
    return freed, count


def _is_prohibited_dir(path: str) -> bool:
    lower = path.lower()
    if IS_WINDOWS:
        prohibited = ["c:\\windows\\", "c:\\program files\\", "c:\\program files (x86)\\"]
        allowed_windows_subs = ["c:\\windows\\temp", "c:\\windows\\prefetch",
                                "c:\\windows\\logs", "c:\\windows\\softwaredistribution"]
        for allowed in allowed_windows_subs:
            if lower.startswith(allowed):
                return False
        for p in prohibited:
            if lower.startswith(p):
                return True
    if IS_MAC:
        if lower.startswith("/system") and not lower.startswith("/system/volumes/data"):
            return True
    if IS_LINUX:
        if lower in ("/etc", "/etc/") or lower.startswith("/etc/"):
            return True
        if lower in ("/boot", "/boot/") or lower.startswith("/boot/"):
            return True
    return False


# ── 命令行入口 ────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Disk Deep Clean — 自动安全清理（无需确认）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data-dir", type=str, default=None,
                       help="数据/日志目录（默认 scripts/../data/）")
    parser.add_argument("--dry-run", action="store_true",
                       help="预览模式，不实际删除")
    parser.add_argument("--permanent", action="store_true",
                       help="直接永久删除，不走回收站")
    args = parser.parse_args()
    data_dir = ensure_data_dir(args.data_dir)

    print("=" * 60)
    print("  Disk Deep Clean - 自动安全清理")
    if args.dry_run:
        print("  DRY RUN - 不会实际删除")
    if args.permanent:
        print("  PERMANENT - 直接删除，不走回收站")
    print("=" * 60)
    print()

    total_freed = 0
    result_items = []

    def _rec(cat, val):
        result_items.append({"category": cat, "freed": val})
        return val

    print("[1/7] 清理系统临时文件...")
    freed, count = clean_temp_files(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("系统临时文件", freed)
    print(f"  系统临时文件: {format_size(freed)} ({count} 个目录)\n")

    print("[2/7] 清理浏览器缓存...")
    freed, count = clean_browser_cache(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("浏览器缓存", freed)
    print(f"  浏览器缓存: {format_size(freed)} ({count} 个缓存目录)\n")

    print("[3/7] 清理包管理器缓存 (npm/pip/yarn/pnpm)...")
    freed, count = clean_package_caches(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("包管理器缓存", freed)
    print(f"  包管理器缓存: {format_size(freed)} ({count} 个)\n")

    print("[4/7] 清空回收站...")
    freed = empty_recycle_bin(data_dir, args.dry_run)
    total_freed += _rec("回收站", freed)
    print(f"  回收站: {format_size(freed)}\n")

    print("[5/7] 清理 Windows 更新下载缓存...")
    freed = clean_windows_update_cache(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("Windows 更新缓存", freed)
    print(f"  更新缓存: {format_size(freed)}\n")

    print("[6/7] 清理缩略图缓存...")
    freed = clean_thumbnail_cache(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("缩略图缓存", freed)
    print(f"  缩略图缓存: {format_size(freed)}\n")

    print("[7/7] 清理崩溃转储文件...")
    freed, count = clean_crash_dumps(data_dir, args.dry_run, args.permanent)
    total_freed += _rec("崩溃转储", freed)
    print(f"  崩溃转储: {format_size(freed)} ({count} 个文件)\n")

    print("=" * 60)
    if args.dry_run:
        print(f"  预计可释放: {format_size(total_freed)}")
    else:
        print(f"  累计释放: {format_size(total_freed)}")
    print(f"  详细日志: {data_dir / 'disk-clean-log.txt'}")
    print("=" * 60)

    from datetime import datetime
    result = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "total_freed": total_freed, "items": result_items}
    save_auto_clean_result(data_dir, result)


if __name__ == "__main__":
    main()
