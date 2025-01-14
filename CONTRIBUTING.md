# Contributing to SilentScope

First off, thank you for considering contributing to SilentScope! It's people like you that make SilentScope such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by the [SilentScope Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

- Use the GitHub issue tracker
- Include detailed steps to reproduce
- Include system information
- Use the bug report template

### Suggesting Enhancements

- Use the feature request template
- Explain the use case
- Consider the scope and impact

### Pull Requests

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit pull request

### Development Process

```bash
# Setup development environment
git clone https://github.com/kenzycodex/SilentScope.git
cd silentscope
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest

# Check code style
black .
flake8 .
```

### Commit Messages

- Use clear, descriptive messages
- Reference issues and pull requests
- Follow conventional commits format

### Documentation

- Update README.md if needed
- Add docstrings to new code
- Update API documentation
- Include example usage

## Attribution Requirements

When contributing to SilentScope, please ensure:

1. Maintain original author attribution
2. Include license headers in new files
3. Document significant changes
4. Credit original author in documentation

## Questions?

Feel free to create an issue or contact the maintainers.
