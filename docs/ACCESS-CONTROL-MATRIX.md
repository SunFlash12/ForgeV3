# Access Control Matrix

## API Endpoint Authorization

Legend: **P** = Public, **A** = Authenticated, **O** = Owner/Self, **M** = Admin, **S** = System

### Authentication Routes (`/api/v1/auth/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/register` | POST | P | | | | Rate limited |
| `/login` | POST | P | | | | Rate limited, lockout after 5 fails |
| `/logout` | POST | | A | | | Blacklists token |
| `/refresh` | POST | | A | | | Refresh token rotation |
| `/google/callback` | POST | P | | | | OAuth callback |
| `/me` | GET | | A | | | Returns own profile |

### User Routes (`/api/v1/users/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/` | GET | | | | M | List all users |
| `/{id}` | GET | | A | | | View user profile |
| `/{id}` | PUT | | | O | M | Update own or admin update |
| `/{id}` | DELETE | | | O | M | Delete own or admin delete |
| `/{id}/capsules` | GET | | A | | | User's public capsules |

### Capsule Routes (`/api/v1/capsules/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/` | GET | | A | | | List capsules (filtered) |
| `/` | POST | | A | | | Create capsule |
| `/{id}` | GET | | A | | | Get capsule |
| `/{id}` | PUT | | | O | M | Update own capsule |
| `/{id}` | DELETE | | | O | M | Delete own capsule |
| `/search` | POST | | A | | | Semantic search |

### Graph Routes (`/api/v1/graph/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/query` | POST | | A | | | Graph query |
| `/neighbors/{id}` | GET | | A | | | Get neighbors |
| `/path` | POST | | A | | | Find path |
| `/stats` | GET | | A | | | Graph statistics |

### Governance Routes (`/api/v1/governance/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/council/deliberate` | POST | | A | | | Ghost Council |
| `/proposals` | GET | | A | | | List proposals |
| `/proposals` | POST | | A | | | Create proposal |
| `/proposals/{id}/vote` | POST | | A | | | Vote on proposal |

### System Routes (`/api/v1/system/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/health` | GET | P | | | | Health check |
| `/metrics` | GET | | | | M | Prometheus metrics |
| `/config` | GET | | | | M | System configuration |
| `/backup` | POST | | | | M | Trigger backup |

### Marketplace Routes (`/api/v1/marketplace/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/listings` | GET | | A | | | Browse listings |
| `/listings` | POST | | A | | | Create listing |
| `/listings/{id}` | PUT | | | O | M | Update listing |
| `/purchase` | POST | | A | | | Purchase capsule |

### Federation Routes (`/api/v1/federation/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/peers` | GET | | | | M | List peers |
| `/peers` | POST | | | | M | Add peer |
| `/sync` | POST | | | | S | Trigger sync |

### Blockchain Routes (`/api/v1/tipping/`, `/api/v1/acp/`)

| Endpoint | Method | P | A | O | M | Notes |
|----------|--------|---|---|---|---|-------|
| `/tip` | POST | | A | | | Send tip |
| `/tips/{user}` | GET | | A | | | Get tip history |
| `/escrow/create` | POST | | A | | | Create ACP escrow |
| `/escrow/{id}/release` | POST | | | O | | Release (buyer only) |
| `/escrow/{id}/refund` | POST | | | O | | Refund (buyer/provider) |

## Middleware Stack

All requests pass through:
1. **CORS** — Origin validation
2. **Rate Limiter** — IP-based, per-endpoint tier
3. **Auth Middleware** — JWT extraction and validation
4. **Request ID** — Unique ID for tracing
5. **Logging** — Structured request/response logging

## Role Hierarchy

```
System (internal) > Admin > Owner (self) > Authenticated > Public
```

Admin can perform all Owner actions. System role is for internal service-to-service calls only.
