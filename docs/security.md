# Security

This document outlines the security policies, reporting processes, and scanning tools used in the azure-functions-validation library. We take the security of this project seriously and appreciate responsible disclosure.

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it privately. Avoid public disclosure through issues or pull requests until a fix is available and a coordinated release has been prepared.

### Preferred: GitHub Security Advisory

The most secure way to report a vulnerability is through a GitHub Security Advisory. This allows for private collaboration between the reporter and maintainers.

1. Navigate to the [Security Advisories page](https://github.com/yeongseon/azure-functions-validation/security/advisories/new).
2. Click "Report a vulnerability" or "New advisory".
3. Provide the details of the issue in the private advisory form.

### Alternative: Email

If you prefer to use email, you can reach the maintainer at: yeongseon.choe@gmail.com.

### What to Include in Your Report

To help us triage and address the issue efficiently, please include:

- A clear and detailed description of the vulnerability.
- Step-by-step instructions to reproduce the issue.
- An assessment of the potential impact (e.g., data leakage, remote execution).
- Suggested mitigation steps or a potential fix, if available.

### Response Timeline

We aim to respond to all security reports within the following timeframes:

- Initial response: Within 48 hours of receiving the report.
- Status update: Within 7 days of the initial response, detailing progress or required information.

## Supported Versions

Security support is provided for the current active release. Older versions are not actively maintained for security patches.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Older releases | No |

## Security Scanning

We use automated tools to ensure the codebase remains secure and follows best practices.

### Bandit: Static Analysis Security Scanner

Bandit is used for static analysis security scanning of Python code. It is configured to scan the source code while skipping test files to minimize false positives.

You can run a security scan locally using the following commands:

```bash
# Using make
make security

# Using hatch
hatch run security
```

The underlying command executed is `python -m bandit -r src`.

### CI/CD Integration

Security scans are integrated into our continuous integration pipeline. Every push and pull request triggers the `security.yml` workflow via GitHub Actions, ensuring that no known security regressions are introduced into the main branch.

### Pre-commit Hook

To catch issues before they are even committed, Bandit is included as a pre-commit hook (version 1.9.3). This ensures that contributors run basic security checks as part of their local development workflow.

## Security Scope

Understanding the boundaries of this library is essential for building secure Azure Functions.

### Within Scope

- **Input Validation**: This library handles HTTP request validation for body, query parameters, path variables, and headers. Input validation is a primary security boundary against injection and malformed data.
- **Data Integrity**: Pydantic v2 manages data validation, including type coercion and schema constraints, ensuring that incoming data matches expected models.

### Out of Scope

- **Authentication and Authorization**: This library does not handle user identity or permission checks. Use the built-in Azure Functions authentication levels or custom middleware.
- **Rate Limiting**: Protection against denial-of-service (DoS) attacks via rate limiting is managed at the Azure API Management or Azure Functions platform level.
- **Encryption**: Data-at-rest and data-in-transit encryption are handled by the Azure platform and underlying Python runtime.

Azure Functions runtime security and platform-level infrastructure are managed by the Azure platform and are outside the control of this library.

## Security Best Practices for Users

When using this library, follow these practices to enhance your application's security:

1. **Validate All Inputs**: Use the `@validate_http` decorator to check every input source, including body, query, path, and headers.
2. **Use Strict Pydantic Models**: Define field constraints in your Pydantic models (e.g., `min_length`, `max_length`, `ge`, `le`, `pattern`). Avoid using generic `Any` types where possible.
3. **Prevent Data Leakage**: Always use `response_model` in the `@validate_http` decorator. This ensures that only the fields defined in your response model are sent back to the client, preventing accidental exposure of internal data structures.
4. **Keep Dependencies Updated**: Regularly update `pydantic` and `azure-functions` to benefit from the latest security patches.

## Dependency Security

We maintain a minimal dependency surface to reduce the attack vector.

- **Minimal Dependencies**: The library only depends on `azure-functions` and `pydantic`.
- **Dependabot**: Automated dependency updates are enabled via Dependabot to ensure that security vulnerabilities in upstream packages are addressed quickly.
- **Regular Audits**: We perform regular dependency audits to identify and mitigate risks from third-party code.
