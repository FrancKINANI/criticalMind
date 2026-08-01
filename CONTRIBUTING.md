# Contributing to CriticalMind

Thank you for your interest in contributing to CriticalMind! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to [support@criticalmind.ai](mailto:support@criticalmind.ai).

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and pnpm
- PostgreSQL 15+ (or use Docker)
- Git

### Development Setup

1. **Fork the repository**
   ```bash
   # Click the "Fork" button on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/criticalMind.git
   cd criticalMind
   ```

2. **Set up the backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp ../.env.example .env
   # Configure your .env file
   ```

3. **Set up the frontend**
   ```bash
   cd frontend
   pnpm install
   cp ../.env.example .env
   # Configure your .env file
   ```

4. **Start the development servers**
   ```bash
   # Terminal 1 - Backend
   cd backend
   python src/main.py

   # Terminal 2 - Frontend
   cd frontend
   pnpm dev
   ```

## Contributing Guidelines

### What to Contribute

We welcome contributions in the following areas:

- **Bug fixes** - Help us squash bugs!
- **New features** - Propose new features via issues first
- **Documentation** - Improve docs, fix typos, add examples
- **Tests** - Improve test coverage
- **Performance** - Optimize code for better performance
- **Accessibility** - Improve accessibility features

### Reporting Issues

Before creating an issue, please:

1. Search existing issues to avoid duplicates
2. Check if the issue is resolved in the latest version
3. Use the issue template and provide:
   - Clear description of the problem
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, browser, versions)
   - Screenshots if applicable

### Feature Requests

For feature requests:

1. Open an issue describing the feature
2. Explain the use case and why it's valuable
3. Discuss implementation approaches
4. Wait for maintainer approval before starting work

## Pull Request Process

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Follow the coding standards
   - Add tests for new functionality
   - Update documentation
   - Commit frequently with clear messages

3. **Test your changes**
   ```bash
   # Backend tests
   cd backend
   pytest

   # Frontend tests
   cd frontend
   pnpm test
   ```

4. **Submit your PR**
   - Fill out the PR template
   - Link related issues
   - Describe your changes clearly
   - Ensure CI checks pass

## Coding Standards

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

```python
# Good
def calculate_user_score(user_id: int) -> float:
    """Calculate the user's critical thinking score based on their progress."""
    pass

# Bad
def calc(uid):
    pass
```

### TypeScript/React (Frontend)

- Follow ESLint configuration
- Use functional components with hooks
- Keep components small and focused
- Use TypeScript strictly (no `any`)
- Follow React best practices

```typescript
// Good
interface UserProps {
  id: string;
  name: string;
}

export const UserCard: React.FC<UserProps> = ({ id, name }) => {
  return <div>{name}</div>;
};

// Bad
export const UserCard = (props: any) => {
  return <div>{props.name}</div>;
};
```

### Git Commit Messages

Follow conventional commits format:

```
type(scope): subject

body

footer
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(auth): add OAuth2 support`
- `fix(learning): resolve timeout in exercise submission`
- `docs(readme): update installation instructions`

## Testing

### Backend Tests

```bash
cd backend
pytest                          # Run all tests
pytest --cov=src                # With coverage
pytest tests/test_auth.py       # Specific test file
```

### Frontend Tests

```bash
cd frontend
pnpm test                       # Run all tests
pnpm test:coverage              # With coverage
pnpm test:watch                 # Watch mode
```

### Test Requirements

- New features must include tests
- Bug fixes should include regression tests
- Maintain test coverage above 80%
- All tests must pass before PR submission

## Documentation

### Code Documentation

- Add docstrings to Python functions and classes
- Add JSDoc comments to complex TypeScript functions
- Comment complex logic
- Keep documentation up to date with code changes

### Project Documentation

- Update README.md for user-facing changes
- Update ARCHITECTURE.md for structural changes
- Add inline code comments for complex algorithms
- Update API documentation for endpoint changes

## Questions?

- Join our community discussions
- Open an issue for questions
- Contact: [support@criticalmind.ai](mailto:support@criticalmind.ai)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to CriticalMind! 🎉
