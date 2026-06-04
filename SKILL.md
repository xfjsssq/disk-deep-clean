# Disk Deep Clean — AI 助手技能指南

## 这是什么

零外部依赖的跨平台磁盘深度清理工具，纯 Python 标准库。

## 仓库结构

```
disk-deep-clean/
├── scripts/
│   ├── lib.py          # 公共工具函数
│   ├── auto_clean.py   # 自动清理（无需确认）
│   ├── deep_scan.py    # 深度扫描（单次 walk）
│   └── clean.py        # 按选择清理
├── SKILL.md            # 本文件
└── README.md           # 人类用户手册
```

## 运行方式

```bash
python scripts/auto_clean.py          # 一键自动清理
python scripts/deep_scan.py           # 全盘扫描报告
python scripts/clean.py --selections "all-safe"  # 安全项清理
```

## 标准工作流

当用户说"帮我清理磁盘"时：
1. 先 auto_clean (自动垃圾)
2. 再 deep_scan (生成报告)
3. 根据报告用 clean.py 清理

## 主动询问规则

扫描完成后主动汇报：
- 安全可清理 XX GB
- 需确认项 YY GB
- 询问用户"是否现在清理安全项？"

## 安全规则

- 禁止碰 C:\Program Files, C:\Windows（除 Temp/Prefetch/Logs/SoftwareDistribution）
- 禁止碰 /System (Mac), /etc (Linux)
- 所有删除默认走回收站
- 高风险项默认隐藏 (--risky)
- WinSxS 只建议 DISM

## 参数参考

```
auto_clean.py: --dry-run, --permanent, --data-dir PATH
deep_scan.py:  --risky, --list-all, --slow-scan, --data-dir PATH
clean.py:      --selections "1,3,5-7", --selections "all-safe", --yes
               --permanent, --dry-run, --data-dir PATH
```
