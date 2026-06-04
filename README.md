<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/python-3.8+-blue?style=flat-square&logo=python&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/python-3.8+-blue?style=flat-square&logo=python&logoColor=white">
</picture>
<img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat-square">
<img alt="Platform" src="https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey?style=flat-square">
<img alt="Dependencies" src="https://img.shields.io/badge/dependencies-0-success?style=flat-square">
<img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square">

# Disk Deep Clean 🧹

> **跨平台磁盘深度清理工具 — 零依赖，纯 Python 标准库**
>
> **Cross-platform disk deep clean tool — zero dependencies, pure Python stdlib.**

Disk Deep Clean scans your drives for junk files, cache bloat, and large unused directories, then helps you clean them safely. Every deletion goes through the **recycle bin/trash** by default — nothing is permanently lost without your explicit say-so.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **Auto Clean** | One-click safe cleanup: temp files, browser cache, package manager cache, recycle bin, crash dumps, Windows update cache |
| 🔍 **Deep Scan** | 5-phase scan engine: known paths → full `os.walk` → post-processing → lightweight scans → formatted report |
| 🎯 **Selective Cleanup** | Clean exactly what you want from the scan report, by ID or category |
| 🛡️ **Safety First** | All deletions go to trash by default; protected system directories are off-limits (C:\Windows, /System, /etc) |
| 🌍 **Cross-Platform** | Works on Windows, macOS, and Linux with zero external dependencies |
| 💡 **AI-Ready** | Ships with `SKILL.md` — designed for Claude Code guided operation |

---

## 📦 Quick Start

```bash
# Auto clean junk files (safe, no confirmation needed)
python scripts/auto_clean.py

# Deep scan your entire disk
python scripts/deep_scan.py

# Clean safe items from the scan report
python scripts/clean.py --selections "all-safe"
```

Or install as a package:

```bash
pip install -e .
disk-deep-clean --dry-run
```

---

## 🔧 Usage

### Auto Clean — `auto_clean.py`

One-click cleanup of clearly safe junk files:

```
python scripts/auto_clean.py [--dry-run] [--permanent] [--data-dir PATH]
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview mode — show what would be deleted without deleting |
| `--permanent` | Permanently delete instead of moving to trash |
| `--data-dir PATH` | Custom directory for logs and data |

**What it cleans:** system temp files, browser caches (Chrome/Edge/Firefox), pip/npm/pnpm/yarn caches, recycle bin, Windows update cache (needs admin), thumbnail cache, crash dumps (.dmp/.hdmp).

### Deep Scan — `deep_scan.py`

Full disk scan to identify cleanup opportunities:

```
python scripts/deep_scan.py [--risky] [--list-all] [--slow-scan] [--data-dir PATH]
```

| Option | Description |
|--------|-------------|
| `--risky` | Show high-risk items (hiberfil.sys, Windows.old, etc.) |
| `--list-all` | Show all large directories (>1GB), not just top 30 |
| `--slow-scan` | Enable slower but more thorough scanning modes |
| `--data-dir PATH` | Custom directory for scan results |

### Selective Cleanup — `clean.py`

Clean specific items from the scan report:

```
python scripts/clean.py --selections "1,3,5-7" [--dry-run] [--permanent] [--yes]
```

| Option | Description |
|--------|-------------|
| `--selections "1,3,5-7"` | Clean items by ID (comma/range syntax) |
| `--selections "all-safe"` | Clean all items marked as "safe" |
| `--yes` / `-y` | Skip confirmation prompts |
| `--dry-run` | Preview mode |
| `--permanent` | Permanent deletion (use with caution) |

---

## 🛡️ Safety Model

| Risk Level | Description | Default Behavior |
|------------|-------------|------------------|
| ✅ **Safe** | Temp files, cache, logs | Shown by default, can auto-clean |
| ⚠️ **Confirm** | Large directories, app data, Steam shader cache | Requires user confirmation |
| 🔴 **High Risk** | System files (hiberfil.sys, pagefile.sys, Windows.old) | Hidden by default, use `--risky` to show |

Protected directories that can NEVER be deleted:
- **Windows:** `C:\Windows` (except Temp/Prefetch/Logs/SoftwareDistribution), `C:\Program Files`, `C:\Program Files (x86)`
- **macOS:** `/System`
- **Linux:** `/etc`, `/boot`, `/proc`, `/sys`, `/dev`

All deletions go to the **recycle bin/trash** by default. Use `--permanent` only when you're sure.

---

## 📁 Project Structure

```
disk-deep-clean/
├── scripts/
│   ├── lib.py              # Core utilities (cross-platform)
│   ├── auto_clean.py       # One-click auto cleanup
│   ├── deep_scan.py        # 5-phase deep scan engine
│   ├── clean.py            # Selective cleanup executor
│   ├── __init__.py         # Package marker
│   └── __main__.py         # `python -m scripts` entry point
├── tests/
│   ├── test_lib.py         # Tests for core functions
│   ├── test_deep_scan.py   # Tests for scan utilities
│   ├── conftest.py         # Pytest configuration
│   └── __init__.py
├── .claude/
│   └── settings.local.json # Claude Code permissions
├── .github/workflows/
│   └── test.yml            # CI configuration
├── SKILL.md                # Claude Code skill guide
├── README.md               # This file
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Contribution guide
├── CODE_OF_CONDUCT.md      # Code of conduct
├── pyproject.toml          # Python package metadata
├── .gitignore
└── LICENSE                 # MIT License
```

---

## 🧪 Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/ -v

# Run linting (if ruff is installed)
ruff check .
```

**Requirements:** Python 3.8+ (no external packages needed).

---

## 🤖 AI Assistant Integration

This project is designed as a [Claude Code](https://claude.ai/code) skill. See [`SKILL.md`](SKILL.md) for the AI operation guide, including:

- Standard workflow: auto_clean → deep_scan → clean
- Safety rules and prohibited paths
- Parameter reference

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

## 🌟 快速开始（中文）

```bash
# 一键自动清理
python scripts/auto_clean.py

# 深度扫描生成报告
python scripts/deep_scan.py

# 按报告清理安全项
python scripts/clean.py --selections "all-safe"
```

每个脚本支持 `--help` 查看参数详情。

---

*Made with ❤️ using pure Python.*
