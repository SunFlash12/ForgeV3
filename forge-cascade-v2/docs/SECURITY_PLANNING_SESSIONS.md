# Security Planning Sessions

This document outlines the 5 remaining security enhancements identified during Audit 6 that require dedicated planning sessions before implementation.

## Overview

The following security improvements require architectural decisions and careful planning:

| Session | Topic | Priority | Estimated Complexity |
|---------|-------|----------|---------------------|
| 1 | Token Regeneration on Privilege Changes | HIGH | Medium |
| 2 | Session Binding (IP/User-Agent) | MEDIUM | Medium |
| 3 | MFA Integration | MEDIUM | High |
| 4 | Chat Room Access Control | MEDIUM | Medium |
| 5 | Type Safety Audit | LOW | High (volume) |

---

## Session 1: Token Regeneration on Privilege Changes

### Problem
When a user's role or permissions change (promotion, demotion, or permission grant/revoke), their existing JWT tokens still contain the old claims. This creates a window where users may have elevated or reduced privileges that don't match their actual authorization level.

### Security Risk
- **Privilege escalation persistence**: Demoted users retain elevated access until token expiry
- **Delayed privilege grant**: Promoted users must wait for token refresh to gain new access
- **Stale claims**: Token claims don't reflect current authorization state

### Scope
- Hook into `UserRepository.update_role()` and related methods
- Implement token invalidation on privilege changes
- Force re-authentication or automatic token refresh
- Consider WebSocket session handling during privilege changes

### Key Questions
1. Should we invalidate all tokens or just access tokens?
2. How do we handle active WebSocket sessions?
3. Should we notify users of privilege changes?
4. What's the grace period (if any) for token refresh?

### Files Likely Affected
- `forge/security/auth_service.py`
- `forge/repositories/user_repository.py`
- `forge/security/tokens.py`
- `forge/api/dependencies.py`

---

## Session 2: Session Binding (IP/User-Agent)

### Problem
Tokens can be used from any IP address or device. If a token is stolen, an attacker can use it from anywhere without detection.

### Security Risk
- **Token theft**: Stolen tokens work from attacker's environment
- **Session hijacking**: No way to detect suspicious location/device changes
- **Replay attacks**: Tokens can be replayed from different contexts

### Scope
- Store client IP and User-Agent hash with token/session
- Validate IP/User-Agent on each request
- Implement configurable strictness levels (strict, warn, disabled)
- Handle legitimate IP changes (mobile users, VPNs)

### Key Questions
1. How strict should binding be? (exact match vs subnet vs warning only)
2. How do we handle mobile users with changing IPs?
3. Should we bind to User-Agent or just log changes?
4. How do we store binding metadata? (in token vs database)

### Files Likely Affected
- `forge/security/tokens.py`
- `forge/api/middleware.py`
- `forge/api/dependencies.py`
- `forge/config.py`

---

## Session 3: MFA Integration

### Problem
Single-factor authentication (password only) is vulnerable to credential theft, phishing, and brute force attacks.

### Security Risk
- **Credential stuffing**: Reused passwords from breaches
- **Phishing**: Users tricked into revealing passwords
- **Brute force**: Weak passwords can be guessed

### Scope
- TOTP (Time-based One-Time Password) implementation
- Backup codes generation and management
- MFA enrollment flow (QR code generation)
- Recovery flow for lost MFA devices
- Admin override capabilities
- Per-user MFA enforcement policies

### Key Questions
1. Which MFA methods to support? (TOTP, WebAuthn, SMS?)
2. Should MFA be required for all users or configurable?
3. How many backup codes? How are they stored?
4. What's the recovery process for lost devices?
5. Should we support "remember this device" feature?

### Files Likely Affected
- `forge/security/mfa.py` (new file)
- `forge/security/auth_service.py`
- `forge/api/routes/auth.py`
- `forge/models/user.py`
- `forge/repositories/user_repository.py`
- Frontend MFA enrollment components

### Dependencies
- `pyotp` for TOTP generation/verification
- `qrcode` for QR code generation

---

## Session 4: Chat Room Access Control

### Problem
Chat rooms currently have no access control verification. Any authenticated user can join any room by knowing the room ID.

### Security Risk
- **Unauthorized access**: Users can join private conversations
- **Information disclosure**: Sensitive discussions exposed
- **No audit trail**: No record of who accessed which rooms

### Scope
- Room membership model (owner, members, banned)
- Permission levels (read, write, admin)
- Invite system for private rooms
- Public vs private room types
- Room-level rate limiting
- Access logging and audit

### Key Questions
1. What room types do we need? (public, private, invite-only?)
2. What permission levels? (read, write, moderate, admin?)
3. How do we handle room creation and ownership?
4. Should we support temporary/expiring invites?
5. How do we migrate existing rooms?

### Files Likely Affected
- `forge/models/chat.py` (new or extended)
- `forge/repositories/chat_repository.py` (new)
- `forge/api/websocket/handlers.py`
- `forge/api/routes/chat.py` (new)

---

## Session 5: Type Safety Audit

### Problem
The codebase has 47+ locations with type safety issues identified during the audit, including missing type hints, incorrect types, and unsafe type coercion.

### Security Risk
- **Runtime errors**: Type mismatches cause crashes
- **Logic bugs**: Incorrect types lead to unexpected behavior
- **Injection vulnerabilities**: Unvalidated types bypass security checks

### Scope
- Audit all 47+ identified locations
- Add missing type hints
- Fix incorrect type annotations
- Enable stricter mypy/pyright checks
- Add runtime type validation where needed

### Categories of Issues
1. Missing return type annotations
2. `Any` types that should be specific
3. Optional types not properly handled
4. Dict/List without element types
5. Union types that are too broad

### Key Questions
1. Should we enable strict mypy checking?
2. How do we handle third-party libraries without stubs?
3. Should we add runtime validation (pydantic) for critical paths?
4. What's the priority order for fixes?

### Files Likely Affected
- Multiple files across the codebase
- Configuration: `pyproject.toml` or `mypy.ini`

---

## Implementation Order Recommendation

Based on security impact and dependencies:

1. **Session 1: Token Regeneration** - High security impact, foundational
2. **Session 3: MFA Integration** - High security value, user-facing
3. **Session 2: Session Binding** - Defense in depth, complements MFA
4. **Session 4: Chat Room Access Control** - Feature-specific security
5. **Session 5: Type Safety** - Code quality, ongoing maintenance

---

## Notes

- Each session should begin with codebase exploration to understand current implementation
- Plan mode should be used to design the approach before coding
- Security fixes should include comprehensive tests
- Documentation should be updated alongside implementation
