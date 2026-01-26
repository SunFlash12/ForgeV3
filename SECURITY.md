# Security Policy

## Supported Versions

| Component | Version | Supported |
|-----------|---------|-----------|
| Forge Cascade API | 3.x | Yes |
| Smart Contracts (Base) | 0.8.20 | Yes |
| Smart Contracts (testnet) | 0.8.20 | Best-effort |

## Scope

This policy covers:

- **Smart Contracts**: CapsuleRegistry, SimpleEscrow, CapsuleMarketplace (Solidity)
- **Backend API**: Forge Cascade FastAPI application
- **Authentication**: JWT, OAuth, session management
- **Data Layer**: Neo4j graph database, Redis cache
- **Blockchain Integration**: EVM (Base) and Solana chain clients
- **Genomics Data Handling**: Capsule content, HPO terms, OMIM references

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

### Contact

Report vulnerabilities via email to: **security@forgeproject.dev**

Include:
1. Description of the vulnerability
2. Steps to reproduce
3. Affected component(s) and version(s)
4. Potential impact assessment
5. Any suggested fix (optional)

### Response Timeline

| Action | Target |
|--------|--------|
| Acknowledgement | 48 hours |
| Initial assessment | 5 business days |
| Fix development | Severity-dependent |
| Public disclosure | After fix is deployed |

### Severity Levels

| Level | Description | Examples |
|-------|-------------|---------|
| **Critical** | Funds at risk, data breach, RCE | Smart contract drain, auth bypass, SQL/Cypher injection |
| **High** | Significant impact, no direct fund loss | Privilege escalation, PII exposure, DoS on critical path |
| **Medium** | Limited impact | Information disclosure, non-critical DoS, logic errors |
| **Low** | Minimal impact | UI issues, non-sensitive info leaks, best-practice deviations |

## Safe Harbor

We consider security research conducted in good faith to be authorized if you:

- Make a good faith effort to avoid privacy violations, data destruction, and service disruption
- Only interact with accounts you own or with explicit permission
- Do not exploit the vulnerability beyond what is necessary to demonstrate it
- Report the vulnerability promptly and do not disclose it publicly before a fix is available
- Do not use the vulnerability for financial gain beyond any bug bounty offered

## Security Measures

### Smart Contracts
- OpenZeppelin Ownable, ReentrancyGuard, Pausable
- Gas-optimized struct packing
- Configurable safety caps (maxEscrowAmount)
- All contracts verified on BaseScan

### API
- JWT authentication with refresh token rotation and blacklisting
- bcrypt password hashing with constant-time comparison
- Google OAuth with state parameter and audience validation
- Account lockout after 5 failed attempts (30-minute window)
- IP-based rate limiting on all endpoints
- Parameterized Cypher queries (injection prevention)
- CORS, CSP, and security headers via middleware

### Infrastructure
- Non-root Docker containers with no-new-privileges
- Pinned base image versions
- CI pipeline: Ruff, MyPy (strict), Bandit, Safety, Trivy
- Private keys and API keys stored only in gitignored .env files

## Dependencies

We monitor dependencies for known vulnerabilities using:
- `npm audit` for Node.js / Solidity toolchain
- `pip-audit` / Safety for Python
- Trivy for container image scanning
- Dependabot for automated updates

## Acknowledgements

We thank all security researchers who responsibly disclose vulnerabilities. Contributors will be credited (with permission) in release notes.
