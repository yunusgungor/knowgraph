# Test Fixtures for Taint Analysis

This directory contains **intentionally vulnerable code** for testing KnowGraph's security analysis features.

⚠️ **WARNING:** These files contain real security vulnerabilities. **DO NOT** deploy to production or expose to the internet.

## Files

### `vulnerable_app.py`
Flask application with 4 types of vulnerabilities:
- **SQL Injection** (2 examples) - CWE-89
- **Cross-Site Scripting** (2 examples) - CWE-79
- **Command Injection** (2 examples) - CWE-78
- **Path Traversal** (1 example) - CWE-22

### `vulnerable_django.py`
Django-specific vulnerability patterns:
- SQL injection via raw queries
- XSS via `mark_safe()`
- Command injection in file operations

## Usage

These fixtures are used by `tests/test_taint_analysis.py` to verify:
1. ✅ Vulnerable code is correctly flagged
2. ✅ Safe code is not flagged (no false positives)
3. ✅ Taint paths are accurately traced
4. ✅ Multi-hop data flows are detected

## Expected Taint Flows

### SQL Injection (vulnerable_login)
```
Source: request.form['username']
  ↓
Variable: username
  ↓
String interpolation: f"... WHERE username='{username}' ..."
  ↓
Sink: cursor.execute(query)
```

### XSS (vulnerable_xss)
```
Source: request.args.get('name')
  ↓
Variable: name
  ↓
Template string: f"<h1>Hello, {name}!</h1>"
  ↓
Sink: render_template_string(template)
```

### Command Injection (vulnerable_ping)
```
Source: request.args.get('host')
  ↓
Variable: host
  ↓
Command string: f"ping -c 4 {host}"
  ↓
Sink: subprocess.call(command, shell=True)
```

## Testing Strategy

1. **Index with Joern:** Generate CPG with `data_flow` edges
2. **Run TaintAnalyzer:** Find source-to-sink paths
3. **Verify Results:** Check vulnerability type, severity, and path accuracy
4. **Test Safe Code:** Ensure no false positives

## Future Additions

- [ ] JavaScript/Node.js vulnerabilities
- [ ] Java/Spring Boot examples
- [ ] Go web application examples
- [ ] Multi-language polyglot scenarios
