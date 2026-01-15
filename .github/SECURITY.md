# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.7.x   | :white_check_mark: |
| < 0.7   | :x:                |

## Reporting a Vulnerability

RRational is a desktop application for HRV analysis that processes local files. It does not:
- Connect to external servers (except for Streamlit's built-in features)
- Store or transmit user data externally
- Require authentication

### If You Find a Security Issue

1. **Do NOT open a public issue** for security vulnerabilities
2. **Email the maintainers** directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. Allow reasonable time for a fix before public disclosure

### What We Consider Security Issues

- Code execution vulnerabilities
- Data exposure risks
- Dependency vulnerabilities with known exploits

### What We Don't Consider Security Issues

- Vulnerabilities requiring physical access to the machine
- Issues in dependencies without known exploits
- Theoretical attacks without practical impact

## Best Practices for Users

- Keep RRational updated (`git pull && uv sync`)
- Don't run RRational with elevated privileges
- Keep your HRV data in project folders (not system directories)
