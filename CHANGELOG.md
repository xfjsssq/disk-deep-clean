# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-04

### Added
- Initial release
- Auto clean: temp files, browser caches, package manager caches, recycle bin,
  Windows update cache, thumbnail cache, crash dumps
- Deep scan: 5-phase scan engine with intelligent directory classification
- Selective cleanup: clean by ID, range, or "all-safe" from scan reports
- Cross-platform support (Windows, macOS, Linux)
- Zero external dependencies — pure Python stdlib
- Safety model: trash by default, protected system directories, risk levels
- Claude Code skill integration (SKILL.md)
- Comprehensive test suite
- GitHub Actions CI (3 platforms, Python 3.8–3.12)
- MIT License
