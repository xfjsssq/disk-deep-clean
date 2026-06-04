# Contributing to Disk Deep Clean

Thank you for considering contributing! This project aims to be a safe, cross-platform disk cleanup tool with zero external dependencies.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/disk-deep-clean.git
cd disk-deep-clean

# Install in editable mode
pip install -e .

# Run tests
pytest tests/ -v
```

## Guidelines

### Code Style
- Target Python 3.8+ compatibility
- Keep **zero external dependencies** — stdlib only
- Use type hints for all function signatures
- Follow existing naming conventions (snake_case for functions, PascalCase for classes)
- Keep lines under 100 characters

### Testing
- Add tests for any new functionality
- Use `tmp_path` fixture for file system tests
- Mock platform-specific behavior where needed
- Run `pytest tests/ -v` before submitting

### Safety First
- All destructive operations MUST default to recycle bin/trash
- Protected system directories must never be modified
- Add appropriate risk classifications for new scan items
- Use `--dry-run` support for all destructive operations

### Pull Request Process
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Run tests
5. Push to your fork
6. Open a Pull Request

## Reporting Issues

When reporting bugs, include:
- Your operating system and version
- Python version
- Command used and full output
- Expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
