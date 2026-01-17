# Contributing to KnowGraph

Thank you for your interest in contributing to KnowGraph! 🎉

## 🚀 Quick Start

### 1. Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yunusgungor/knowgraph.git
cd knowgraph

# Install in development mode
pip install -e ".[dev]"

# Setup Joern
knowgraph-setup-joern

# Run tests
pytest
```

### 2. Development Workflow

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Run tests**: `pytest`
5. **Check code quality**:
   ```bash
   ruff check .
   mypy .
   ```
6. **Commit** your changes: `git commit -m 'Add amazing feature'`
7. **Push** to your fork: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

## 📋 Code Standards

- **Python 3.10+** required
- **Type hints** for all functions
- **Docstrings** for public APIs
- **Tests** for new features
- **100% test coverage** for critical paths

### Code Quality Tools

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type check
mypy .

# Run all tests
pytest --cov=knowgraph
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_query_engine.py

# Run with coverage
pytest --cov=knowgraph --cov-report=html

# Run integration tests
pytest -m integration
```

## 📝 Commit Messages

Follow conventional commits:

- `feat: Add new feature`
- `fix: Fix bug`
- `docs: Update documentation`
- `test: Add tests`
- `refactor: Refactor code`
- `perf: Performance improvement`
- `chore: Maintenance tasks`

## 🐛 Reporting Bugs

Open an issue with:
- **Description**: What happened?
- **Expected behavior**: What should happen?
- **Steps to reproduce**
- **Environment**: OS, Python version, KnowGraph version
- **Logs**: Error messages or stack traces

## 💡 Feature Requests

Open an issue with:
- **Use case**: Why is this needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other approaches considered?

## 📚 Documentation

- Update `docs/USER_GUIDE.md` for user-facing changes
- Update `docs/ARCHITECTURE.md` for architectural changes
- Add docstrings for new APIs
- Update README.md if needed

## 🔍 Code Review Process

1. All PRs require at least one review
2. CI must pass (tests, linting, type checking)
3. Coverage must not decrease
4. Documentation must be updated

## 📞 Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/yunusgungor/knowgraph/issues)
- **Discussions**: Ask questions in GitHub Discussions
- **Email**: mail@yunusgungor.com

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to KnowGraph!** 🙏
