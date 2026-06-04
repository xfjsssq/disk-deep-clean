"""
深度扫描 — 单次 os.walk 生成磁盘清理报告。
用法: python scripts/deep_scan.py [--data-dir PATH] [--risky] [--list-all] [--slow-scan]
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
from collections import Counter
from datetime import datetime
import time

try:
    from scripts.lib import (
        IS_MAC,
        IS_WINDOWS,
        ScanContext,
        ensure_data_dir,
        find_project_root,
        format_size,
        get_all_users_dir,
        get_fixed_drives,
        get_package_cache_paths,
        get_pe_version_info,
        load_auto_clean_result,
        safe_scandir,
        save_scan_results,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib import (
        IS_MAC,
        IS_WINDOWS,
        ScanContext,
        ensure_data_dir,
        find_project_root,
        format_size,
        get_all_users_dir,
        get_fixed_drives,
        get_package_cache_paths,
        get_pe_version_info,
        load_auto_clean_result,
        safe_scandir,
        save_scan_results,
    )


# ── 禁止目录 ──

_PROHIBITED_WIN = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"]
_ALLOWED_WIN_SUBS = ["C:\\Windows\\Temp", "C:\\Windows\\Prefetch",
                     "C:\\Windows\\Logs", "C:\\Windows\\SoftwareDistribution"]
_PROHIBITED_MAC = ["/System"]
_PROHIBITED_LINUX = ["/etc", "/boot", "/proc", "/sys", "/dev"]
_IGNORE_DIRS = {'.git', '.svn', '.hg'}


def is_prohibited(path: str) -> bool:
    lower = path.lower().rstrip("\\/")
    if IS_WINDOWS:
        for allowed in _ALLOWED_WIN_SUBS:
            if lower.startswith(allowed.lower()):
                return False
        for p in _PROHIBITED_WIN:
            if lower.startswith(p.lower() + "\\") or lower == p.lower():
                return True
        return False
    elif IS_MAC:
        for p in _PROHIBITED_MAC:
            if lower == p.lower() or lower.startswith(p.lower() + "/"):
                return True
        return False
    else:
        for p in _PROHIBITED_LINUX:
            if lower == p.lower() or lower.startswith(p.lower() + "/"):
                return True
        return False


def _should_skip_dir(dirname: str) -> bool:
    return dirname.lower() in _IGNORE_DIRS


class ScanItem:
    __slots__ = ('id', 'drive', 'category', 'name', 'path', 'size',
                 'risk', 'description', 'suggestion', 'is_classified')

    def __init__(self, id_num, drive, category, name, path, size, risk,
                 description="", suggestion="", is_classified=True):
        self.id = id_num
        self.drive = drive
        self.category = category
        self.name = name
        self.path = path
        self.size = size
        self.risk = risk
        self.description = description
        self.suggestion = suggestion
        self.is_classified = is_classified


# ── 智能探针 ──

def _classify_by_filetypes(path: str, max_samples: int = 100) -> str:
    ext_counter = Counter()
    try:
        for i, entry in enumerate(safe_scandir(path)):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                ext_counter[ext] += 1
            if i >= max_samples:
                break
    except Exception:
        pass
    if not ext_counter:
        return "空目录或无文件"
    total = sum(ext_counter.values())
    top = ext_counter.most_common(5)
    media = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.ts'}
    img = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.psd', '.raw', '.cr2',
           '.nef', '.tiff', '.webp', '.svg', '.ico', '.heic'}
    game = {'.pak', '.unity3d', '.unity', '.asset', '.assets', '.uasset',
            '.bsa', '.wad', '.pk3', '.vpk', '.dat', '.bin'}
    code = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.rs', '.go', '.rb', '.php', '.cs', '.swift', '.kt', '.vue'}
    doc = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'}
    arch = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'}
    db = {'.sqlite', '.sqlite3', '.db', '.mdb', '.accdb', '.sql', '.dump'}
    def cnt(s): return sum(c for e, c in top if e in s)
    if cnt(media) > total * 0.3:
        return "影视/视频素材"
    if cnt(img) > total * 0.3:
        return "图片素材/照片库"
    if cnt(game | {'.exe'}) > total * 0.3:
        return "游戏资源/可执行文件"
    if cnt(code) > total * 0.3:
        return "代码项目"
    if cnt(doc) > total * 0.3:
        return "文档资料"
    if cnt(arch) > total * 0.3:
        return "压缩包/镜像文件"
    if cnt(db) > total * 0.3:
        return "数据库文件"
    return "文件类型混合 — " + ", ".join(f"{e}({c})" for e, c in top[:3])


def _probe_directory(path: str) -> dict:
    exe_files = []
    try:
        for entry in safe_scandir(path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ('.exe', '.dll'):
                    exe_files.append(entry.path)
            if len(exe_files) >= 5:
                break
    except Exception:
        pass
    for pe in exe_files[:3]:
        info = get_pe_version_info(pe)
        if info:
            product = info.get("ProductName", "")
            company = info.get("CompanyName", "")
            if product or company:
                soft = product or company
                ev = f"读取 {os.path.basename(pe)} -> ProductName=\"{soft}\""
                return {"software": soft, "confidence": "high", "evidence": ev}
    dir_name = os.path.basename(path).lower()
    known = {
        "baidunetdiskdownload": "百度云盘", "baidunetdisk": "百度云盘",
        "wechat files": "微信", "tencent files": "QQ",
        "steamapps": "Steam", "steam": "Steam",
        "epic games": "Epic Games", "origin games": "Origin",
        "docker": "Docker", "node_modules": "Node.js",
        "venv": "Python 虚拟环境", ".venv": "Python 虚拟环境",
        "miniconda": "Miniconda", "anaconda": "Anaconda",
        "androidstudio": "Android Studio", "visual studio": "Visual Studio",
        "pycharm": "PyCharm",
        "cache": "缓存目录", "temp": "临时文件",
        "downloads": "下载", "desktop": "桌面",
        "documents": "文档", "pictures": "图片", "videos": "视频", "music": "音乐",
        ".git": "Git 仓库",
    }
    for kw, name in known.items():
        if kw in dir_name:
            return {"software": name, "confidence": "medium", "evidence": "目录名匹配"}
    return {"software": "未知", "confidence": "low",
            "evidence": _classify_by_filetypes(path)}


# ── Phase 1: 快速路径检查 ──

def _get_local_appdata():
    if not IS_WINDOWS:
        return []
    r = []
    for entry in safe_scandir("C:\\Users"):
        if entry.is_dir():
            local = os.path.join(entry.path, "AppData", "Local")
            if os.path.isdir(local):
                r.append((entry.name, local))
    return r


def phase1_check_paths():
    items = []
    paths = set()

    def _add(drive, cat, name, p, risk, desc="", sug=""):
        if os.path.isdir(p):
            paths.add(p)
            items.append(ScanItem(0, drive, cat, name, p, 0, risk, desc, sug))
            return True
        return False

    if IS_WINDOWS:
        for e in safe_scandir("C:\\Users"):
            if not e.is_dir():
                continue
            wb = os.path.join(e.path, "Documents", "WeChat Files")
            if os.path.isdir(wb):
                for w in safe_scandir(wb):
                    if not w.is_dir():
                        continue
                    fs = os.path.join(w.path, "FileStorage")
                    if os.path.isdir(fs):
                        for sub in ["File", "Image", "Video"]:
                            _add("C:", "微信", f"群聊{sub}",
                                 os.path.join(fs, sub), "safe",
                                 f"微信自动下载的群聊{sub}文件", "安全，删除后聊天记录不受影响")
            qq = os.path.join(e.path, "Documents", "Tencent Files")
            if os.path.isdir(qq):
                for q in safe_scandir(qq):
                    if not q.is_dir():
                        continue
                    for sub in ["Image", "Video", "FileRecv"]:
                        _add("C:", "QQ", f"接收{sub}", os.path.join(q.path, sub),
                             "safe", f"QQ 接收的{sub}文件", "安全，删除后聊天记录不受影响")
        for u, la in _get_local_appdata():
            for wp in [os.path.join(la, "Kingsoft", "WPS Cloud Files", "cache"),
                       os.path.join(la, "Kingsoft", "wpscloud", "cache")]:
                _add("C:", "WPS", "云盘缓存", wp, "safe", "WPS 云盘本地缓存", "安全")
        for d in get_fixed_drives():
            _add(d, "NVIDIA", "驱动解包残留", os.path.join(d + "\\", "NVIDIA", "DisplayDriver"),
                 "safe", "NVIDIA 驱动安装解包残余", "驱动安装完成后不再需要")
        _add("C:", "系统", "Prefetch 预读文件", "C:\\Windows\\Prefetch", "safe",
             "Windows 应用启动加速缓存", "安全")
        _add("C:", "Windows 更新", "更新下载缓存",
             "C:\\Windows\\SoftwareDistribution\\Download", "confirm",
             "Windows Update 下载包", "建议确认后再清理")
        for d in get_fixed_drives():
            for sp in [os.path.join(d + "\\", "Program Files (x86)", "Steam", "steamapps"),
                       os.path.join(d + "\\", "SteamLibrary", "steamapps"),
                       os.path.join(d + "\\", "Steam", "steamapps")]:
                _add(d, "Steam", "着色器缓存", os.path.join(sp, "shadercache"),
                     "confirm", "Steam 着色器预编译缓存", "清理后游戏首次启动会重新编译")
        for ud in get_all_users_dir():
            for bn, br in [("Chrome", "AppData\\Local\\Google\\Chrome\\User Data"),
                           ("Edge", "AppData\\Local\\Microsoft\\Edge\\User Data")]:
                bp = os.path.join(ud, br)
                if os.path.isdir(bp):
                    for e in safe_scandir(bp):
                        if e.is_dir():
                            for cs in ["Cache", "Code Cache"]:
                                _add("C:", "浏览器缓存", f"{bn} - {cs}", os.path.join(e.path, cs),
                                     "safe", f"{bn} 浏览器缓存", "安全，浏览器会自动重建")
            ff = os.path.join(ud, "AppData", "Local", "Mozilla", "Firefox", "Profiles")
            if os.path.isdir(ff):
                for p in safe_scandir(ff):
                    if p.is_dir():
                        for cs in ["cache2", "startupCache"]:
                            _add("C:", "浏览器缓存", f"Firefox - {cs}",
                                 os.path.join(p.path, cs), "safe", "Firefox 缓存", "安全")

    # Docker
    if IS_WINDOWS:
        for u, la in _get_local_appdata():
            for dp in [os.path.join(la, "Docker"), os.path.join(la, "Docker", "wsl", "data")]:
                _add("C:", "Docker", "Docker 数据", dp, "confirm", "Docker 数据")
    else:
        for dp in ["/var/lib/docker", os.path.expanduser("~/.docker")]:
            _add("/", "Docker", "Docker 数据", dp, "confirm")

    # High risk
    if IS_WINDOWS:
        for fp, name, desc, sug in [
            ("C:\\hiberfil.sys", "休眠文件 hiberfil.sys", "休眠模式使用的文件",
             "通过 powercfg -h off 安全关闭"),
            ("C:\\pagefile.sys", "虚拟内存页面文件 pagefile.sys", "虚拟内存文件",
             "不建议手动删除"),
        ]:
            if os.path.isfile(fp):
                try:
                    sz = os.path.getsize(fp)
                except (PermissionError, OSError):
                    sz = 0
                paths.add(fp)
                items.append(ScanItem(0, "C:", "系统文件", name, fp, sz, "high", desc, sug))
        if os.path.isdir("C:\\Windows.old"):
            paths.add("C:\\Windows.old")
            items.append(ScanItem(0, "C:", "系统", "Windows.old", "C:\\Windows.old",
                                 0, "high", "Windows 大版本更新残留",
                                 "通过 设置->系统->存储->临时文件 清理"))

    for cache_path, cache_name in get_package_cache_paths():
        _add("C:" if IS_WINDOWS else "/", "包管理器",
             f"{cache_name} 缓存残留", cache_path, "safe",
             f"{cache_name} 缓存", "安全")

    return items, paths


# ── Phase 2: 单次 os.walk ──

def phase2_single_walk(ctx: ScanContext):
    for drive in get_fixed_drives():
        scan_root = drive + "\\" if IS_WINDOWS else drive
        if not os.path.exists(scan_root):
            continue
        dir_count = 0
        last_report = 0
        print(f"\n正在扫描 {drive}...")
        for root, dirs, files in os.walk(scan_root):
            dir_count += 1
            dirs[:] = [d for d in dirs
                       if not is_prohibited(os.path.join(root, d))
                       and not _should_skip_dir(d)]
            ds = 0
            for f in files:
                try:
                    ds += os.path.getsize(os.path.join(root, f))
                except (PermissionError, OSError):
                    continue
            ctx.dir_sizes[root] = ds
            if os.path.basename(root) == "__pycache__":
                proot = find_project_root(root)
                ctx.pycache_agg[proot] = ctx.pycache_agg.get(proot, 0) + ds
            bn = os.path.basename(root)
            if bn in ("node_modules", "pnpm-store", ".yarn"):
                proot = find_project_root(root)
                if proot not in ctx.node_modules_agg:
                    ctx.node_modules_agg[proot] = []
                try:
                    st = os.stat(root)
                    lm = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
                except Exception:
                    lm = "unknown"
                ctx.node_modules_agg[proot].append((root, ds, lm))
            if dir_count - last_report >= 1000:
                print(f"  {dir_count} 个目录...")
                last_report = dir_count
        print(f"  {drive} 完成 - {dir_count} 个目录")


# ── Phase 3: 后处理 ──

def phase3_post_process(ctx, classified_items, classified_paths, show_all):
    print("\n正在汇总目录大小...")
    ctx.cumulative = dict(ctx.dir_sizes)
    sorted_paths = sorted(ctx.dir_sizes.keys(),
                          key=lambda p: p.count(os.sep) if IS_WINDOWS else p.count("/"),
                          reverse=True)
    for path in sorted_paths:
        parent = os.path.dirname(path)
        if parent != path and parent in ctx.cumulative:
            ctx.cumulative[parent] += ctx.cumulative[path]

    for item in classified_items:
        if item.size == 0 and item.path in ctx.cumulative:
            item.size = ctx.cumulative[item.path]

    large = []
    for path, sz in ctx.cumulative.items():
        if sz <= 1024 ** 3:
            continue
        lower = path.lower().rstrip("\\/")
        dup = False
        for cp in classified_paths:
            if lower == cp.lower().rstrip("\\/"):
                dup = True
                break
        if dup:
            continue
        large.append((path, sz))
    large.sort(key=lambda x: x[1], reverse=True)
    total_large = len(large)
    limit = None if show_all else 30
    if limit:
        large = large[:limit]

    print(f"正在探查 {len(large)} 个大目录...")
    large_items = []
    for i, (path, sz) in enumerate(large):
        probe = _probe_directory(path)
        conf = probe["confidence"]
        if conf == "high":
            name = f"{probe['software']} - {os.path.basename(path)}"
            sug = "确认后可清理"
        elif conf == "medium":
            name = f"{probe['software']}（推测） - {os.path.basename(path)}"
            sug = "确认后可清理"
        else:
            name = f"未知 - {os.path.basename(path)}"
            sug = "建议打开查看后决定"
        drive = path[:2] if IS_WINDOWS else "/"
        large_items.append(ScanItem(0, drive, "大目录", name, path, sz,
                                   "confirm", f"识别：{probe['evidence']}", sug, False))
        if (i + 1) % 5 == 0:
            print(f"  {i + 1}/{len(large)}...")
    if total_large > 30 and not show_all:
        print(f"\n 共 {total_large} 个 >1GB 大目录，展示前 30 个。使用 --list-all 查看全部。")
    return large_items, total_large


# ── Phase 4: 轻量扫描 ──

def phase4_lightweight_scans():
    items = []
    installer_exts = {'.exe', '.msi', '.zip', '.rar', '.7z', '.dmg', '.pkg', '.deb', '.rpm'}

    # 安装包
    download_dirs = []
    if IS_WINDOWS:
        for e in safe_scandir("C:\\Users"):
            if e.is_dir():
                d = os.path.join(e.path, "Downloads")
                if os.path.isdir(d):
                    download_dirs.append(d)
    else:
        d = os.path.expanduser("~/Downloads")
        if os.path.isdir(d):
            download_dirs.append(d)
    for dw in download_dirs:
        total = 0
        cnt = 0
        for e in safe_scandir(dw):
            if e.is_file():
                ext = os.path.splitext(e.name)[1].lower()
                if ext in installer_exts:
                    try:
                        total += e.stat().st_size
                        cnt += 1
                    except Exception:
                        pass
        if total > 0:
            items.append(ScanItem(0, "C:" if IS_WINDOWS else "/",
                         "下载目录", "安装包文件", dw, total, "safe",
                         f"共 {cnt} 个安装包", "已安装的软件安装包可安全删除"))
    # 下载碎片
    fragment_paths = []
    if IS_WINDOWS:
        for d in get_fixed_drives():
            for dn in ["TDDOWNLOAD", "ThunderDownload"]:
                p = os.path.join(d + "\\", dn)
                if os.path.isdir(p):
                    fragment_paths.append(p)
    frag_exts = {'.td', '.td.cfg', '.xltd', '.tmp.download'}
    for fp in fragment_paths:
        total = 0
        cnt = 0
        for root, dirs, files in os.walk(fp):
            dirs[:] = [d for d in dirs if not is_prohibited(os.path.join(root, d))]
            for f in files:
                if os.path.splitext(f)[1].lower() in frag_exts:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                        cnt += 1
                    except Exception:
                        pass
        if total > 0:
            items.append(ScanItem(0, "C:" if IS_WINDOWS else "/",
                         "下载碎片", "迅雷/IDM 残留", fp, total, "safe",
                         f"{cnt} 个下载碎片", "安全"))

    # 过期系统日志
    if IS_WINDOWS:
        logd = "C:\\Windows\\Logs"
        if os.path.isdir(logd):
            cutoff = time.time() - (90 * 24 * 3600)
            total = 0
            cnt = 0
            for root, dirs, files in os.walk(logd):
                for f in files:
                    if f.lower().endswith(".log"):
                        try:
                            st = os.stat(os.path.join(root, f))
                            if st.st_mtime < cutoff:
                                total += st.st_size
                                cnt += 1
                        except Exception:
                            continue
            if total > 0:
                items.append(ScanItem(0, "C:", "系统日志", "过期系统日志",
                             logd, total, "confirm",
                             f"{cnt} 个 .log 超 90 天", "旧日志"))
    return items


# ── Phase 5: 报告 ──

def phase5_report(all_items, data_dir, extra_info):
    ac = load_auto_clean_result(data_dir)
    if ac:
        print("\n" + "=" * 70)
        print("  ==== 上次自动清理结果 ====")
        print(f"  运行时间：{ac.get('timestamp', '')}")
        for it in ac.get("items", []):
            print(f"  {it['category']}：{format_size(it['freed'])}")
        print(f"  累计释放：{format_size(ac.get('total_freed', 0))}")
        print("=" * 70)

    print("\n" + "=" * 70)
    print("  Disk 深度清理报告")
    print("=" * 70)

    safe_items = [i for i in all_items if i.risk == "safe"]
    confirm_items = [i for i in all_items if i.risk == "confirm"]
    high_items = [i for i in all_items if i.risk == "high"]

    print("\n[安全] (不影响任何软件运行)")
    print("-" * 50)
    if safe_items:
        for it in safe_items:
            print(f"\n[{it.id}] {it.drive} - {it.category} - {it.name} ({format_size(it.size)})")
            print(f"路径：{it.path}")
            if it.description:
                print(f"说明：{it.description}")
            if it.suggestion:
                print(f"建议：{it.suggestion}")
    else:
        print("\n  (无)")
    total_safe = sum(i.size for i in safe_items)
    print(f"\n[安全] 小计：{format_size(total_safe)}")

    print("\n\n[建议确认]")
    print("-" * 50)
    if confirm_items:
        for it in confirm_items:
            print(f"\n[{it.id}] {it.drive} - {it.category} - {it.name} ({format_size(it.size)})")
            print(f"路径：{it.path}")
            if it.description:
                print(f"说明：{it.description}")
            if it.suggestion:
                print(f"建议：{it.suggestion}")
    else:
        print("\n  (无)")
    total_confirm = sum(i.size for i in confirm_items)
    print(f"\n[建议确认] 小计：{format_size(total_confirm)}")

    print("\n\n[高风险]")
    print("-" * 50)
    if high_items and extra_info.get("show_risky"):
        for it in high_items:
            print(f"\n[{it.id}] {it.drive} - {it.category} - {it.name} ({format_size(it.size)})")
            print(f"路径：{it.path}")
            if it.description:
                print(f"说明：{it.description}")
            if it.suggestion:
                print(f"建议：{it.suggestion}")
    else:
        print("\n  (未显示，用 --risky 查看)")

    tl = extra_info.get("total_large_dirs", 0)
    if tl > 30 and not extra_info.get("show_all"):
        print(f"\n 共 {tl} 个 >1GB 大目录，展示前 30 个。使用 --list-all 查看全部。")

    total_all = total_safe + total_confirm + sum(i.size for i in high_items)
    print("\n" + "=" * 70)
    print(f"  可清理总计：{format_size(total_all)}")
    print(f"  报告保存至：{data_dir / 'scan-results.json'}")
    print("=" * 70)
    safe_str = format_size(total_safe)
    confirm_str = format_size(total_confirm)
    print(f"\n扫描完成。安全项 {safe_str} 可一键清理；确认项 {confirm_str} 请询问用户。")


def run_scan(data_dir, show_risky=False, show_all=False, slow_scan=False):
    all_items = []
    extra_info = {"show_risky": show_risky, "show_all": show_all}

    ac = load_auto_clean_result(data_dir)
    if ac:
        freed_str = format_size(ac.get('total_freed', 0))
        print(f"检测到上次自动清理结果 ({ac.get('timestamp', '')}) - 释放 {freed_str}")

    print("\n[Phase 1/5] 快速路径检查...")
    classified_items, classified_paths = phase1_check_paths()
    print(f"  发现 {len(classified_items)} 个已知路径")

    print("\n[Phase 2/5] 全盘目录扫描...")
    ctx = ScanContext()
    ctx.classified_paths = classified_paths
    phase2_single_walk(ctx)

    print("\n[Phase 3/5] 后处理...")
    large_items, total_large = phase3_post_process(
        ctx, classified_items, classified_paths, show_all
    )
    extra_info["total_large_dirs"] = total_large

    print("\n[Phase 4/5] 轻量扫描...")
    lightweight_items = phase4_lightweight_scans()

    print("\n[Phase 5/5] 生成报告...")

    safe_cls = [i for i in classified_items if i.risk == "safe"]
    confirm_cls = [i for i in classified_items if i.risk == "confirm"]

    all_items.extend(safe_cls)
    all_items.extend(lightweight_items)
    all_items.extend(large_items)
    all_items.extend(confirm_cls)

    high_items = [i for i in classified_items if i.risk == "high"]
    if show_risky:
        all_items.extend(high_items)

    # pycache 聚合
    for proot, total_size in sorted(ctx.pycache_agg.items(), key=lambda x: x[1], reverse=True):
        if total_size > 0:
            dr = proot[:2] if IS_WINDOWS and len(proot) >= 2 else ("C:" if IS_WINDOWS else "/")
            all_items.append(ScanItem(0, dr, "Python",
                f"__pycache__ ({os.path.basename(proot)})", proot, total_size, "safe",
                f"项目 {os.path.basename(proot)} 下所有 __pycache__", "安全，Python 自动重建"))

    # node_modules 聚合
    for proot, entries in ctx.node_modules_agg.items():
        total_size = sum(e[1] for e in entries)
        if total_size > 100 * 1024 ** 2:
            dr = proot[:2] if IS_WINDOWS and len(proot) >= 2 else ("C:" if IS_WINDOWS else "/")
            all_items.append(ScanItem(0, dr, "Node.js",
                f"node_modules ({os.path.basename(proot)})", proot, total_size, "confirm",
                f"共 {len(entries)} 个 node_modules 目录", "npm install 重新安装"))

    for i, item in enumerate(all_items, 1):
        item.id = i

    results_json = []
    for item in all_items:
        results_json.append({
            "id": item.id, "drive": item.drive, "category": item.category,
            "name": item.name, "path": item.path, "size": item.size,
            "risk": item.risk, "description": item.description, "suggestion": item.suggestion,
        })
    save_scan_results(data_dir, results_json)
    phase5_report(all_items, data_dir, extra_info)
    return all_items, extra_info


def main():
    parser = argparse.ArgumentParser(description="Disk Deep Clean - 深度扫描")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--risky", action="store_true", help="显示高风险项")
    parser.add_argument("--list-all", action="store_true", help="显示全部大目录")
    parser.add_argument("--slow-scan", action="store_true")
    args = parser.parse_args()
    data_dir = ensure_data_dir(args.data_dir)
    run_scan(data_dir, show_risky=args.risky, show_all=args.list_all, slow_scan=args.slow_scan)


if __name__ == "__main__":
    main()
