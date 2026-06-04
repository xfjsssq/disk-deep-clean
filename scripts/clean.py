"""
按选择执行清理 — 读取扫描报告，按用户选择的序号清理。
用法:
  python scripts/clean.py --selections "all-safe"
  python scripts/clean.py --selections "1,2,3"
  python scripts/clean.py                        # 交互模式
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
import shutil

try:
    from scripts.lib import (
        ensure_data_dir,
        format_size,
        load_scan_results,
        log_action,
        move_to_trash,
        parse_selections,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib import (
        ensure_data_dir,
        format_size,
        load_scan_results,
        log_action,
        move_to_trash,
        parse_selections,
    )


def confirm_action(prompt: str) -> bool:
    while True:
        answer = input(prompt + " (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        print("请输入 y 或 n")


def clean_item(item: dict, data_dir, permanent, dry_run) -> bool:
    path = item["path"]
    size = item["size"]

    if not os.path.exists(path):
        print(f"  ? 路径不存在，已跳过: {path}")
        log_action(data_dir, "SKIP", path, size, "NOT_FOUND")
        return False

    if dry_run:
        print(f"  [DRY RUN] 将删除: {path} ({format_size(size)})")
        log_action(data_dir, "DRY_RUN", path, size)
        return True

    try:
        if permanent:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            print(f"  [永久删除] {path} ({format_size(size)})")
            log_action(data_dir, "PERM_DELETE", path, size)
        else:
            success = move_to_trash(path)
            if success:
                print(f"  [回收站] {path} ({format_size(size)})")
                log_action(data_dir, "DELETE", path, size)
            else:
                print(f"  [失败] 移入回收站失败: {path}")
                log_action(data_dir, "ERROR", path, size, "TRASH_FAILED")
                return False
        return True
    except PermissionError:
        print(f"  [跳过] 权限不足: {path}")
        log_action(data_dir, "SKIP", path, size, "PERMISSION")
        return False
    except OSError as e:
        print(f"  [跳过] ({e}): {path}")
        log_action(data_dir, "SKIP", path, size, str(e))
        return False


def run_cleanup(selections_str, data_dir, permanent, dry_run, yes):
    items = load_scan_results(data_dir)
    if not items:
        print("未找到扫描结果。请先运行 deep_scan.py 生成报告。")
        return

    max_id = max(item["id"] for item in items)

    if selections_str and selections_str.strip().lower() == "all-safe":
        selected_ids = [item["id"] for item in items if item["risk"] == "safe"]
    elif selections_str:
        selected_ids = parse_selections(selections_str, max_id)
    else:
        selected_ids = []

    if not selected_ids:
        print(f"可用序号: 1 - {max_id}")
        while True:
            ui = input(
                "\n请输入要清理的项目序号（逗号分隔，如 1,2,3；范围如 1-5；或输入 all-safe）：\n> "
            ).strip()
            if not ui:
                continue
            if ui.lower() == "all-safe":
                selected_ids = [item["id"] for item in items if item["risk"] == "safe"]
            else:
                selected_ids = parse_selections(ui, max_id)
            if selected_ids:
                break
            print("未识别到有效序号，请重新输入。")

    selected = [it for it in items if it["id"] in selected_ids]
    if not selected:
        print("没有匹配的清理项。")
        return

    print("\n" + "=" * 60)
    print("  以下项目将被清理：")
    print("=" * 60)
    total = 0
    for it in selected:
        icon = {"safe": "[安全]", "confirm": "[确认]", "high": "[高风险]"}.get(it["risk"], "[?]")
        sz = format_size(it['size'])
        print(f"  [{it['id']}] {icon} {it['drive']} - {it['category']} - {it['name']} ({sz})")
        print(f"      路径: {it['path']}")
        total += it["size"]
    print("-" * 60)
    print(f"  共 {len(selected)} 项，合计 {format_size(total)}")
    print("=" * 60)

    if not yes:
        if not confirm_action(f"\n确认清理以上 {len(selected)} 项？"):
            print("已取消。")
            return

    print("\n开始清理...\n")
    success = 0
    fail = 0
    for it in selected:
        if clean_item(it, data_dir, permanent, dry_run):
            success += 1
        else:
            fail += 1

    print("\n" + "=" * 60)
    print(f"  清理完成: 成功 {success} 项, 失败 {fail} 项")
    if dry_run:
        print("  DRY RUN - 未实际删除")
    print(f"  日志: {data_dir / 'disk-clean-log.txt'}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Disk Deep Clean - 按选择执行清理")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--selections", type=str, default=None,
                       help="如 \"1,2,3\" 或 \"1-5,8\" 或 \"all-safe\"")
    parser.add_argument("--permanent", action="store_true", help="永久删除")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认")
    args = parser.parse_args()
    data_dir = ensure_data_dir(args.data_dir)

    if args.permanent and not args.dry_run:
        print("PERMANENT 模式 - 将直接永久删除！")
        if not args.yes and not confirm_action("确认使用永久删除？"):
            print("已取消。")
            return

    run_cleanup(selections_str=args.selections, data_dir=data_dir,
                permanent=args.permanent, dry_run=args.dry_run, yes=args.yes)


if __name__ == "__main__":
    main()
