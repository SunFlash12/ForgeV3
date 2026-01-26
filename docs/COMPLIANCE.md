# Data Compliance & Privacy

## Data Classification

### Public Reference Data (No restrictions)
- OMIM disease identifiers (e.g., 219700, 164400)
- HPO terms (e.g., HP:0001250, HP:0000365)
- ClinVar accession numbers (e.g., VCV000007107)
- Gene names and HGVS nomenclature
- Published literature DOIs and citations
- PrimeKG knowledge graph edges

### Sensitive Research Data (Access-controlled)
- Capsule content (knowledge, insights, decisions)
- Analysis results and model outputs
- Variant classification decisions
- Ghost Council deliberation records

### Personal Data (GDPR/HIPAA scope)
- User accounts (email, name, OAuth identifiers)
- Session data and authentication tokens
- Audit logs containing user actions
- Any capsule content containing patient-identifiable information

## GDPR Compliance

### Legal Basis (Article 6)
- **Consent**: User registration constitutes consent for account management
- **Legitimate interest**: System monitoring, security logging

### Special Category Data (Article 9)
Genomics data processed by Forge may fall under Article 9 (genetic data). Processing basis:
- **Explicit consent** for research purposes
- **Scientific research** exemption (Article 9(2)(j)) with appropriate safeguards
- No direct patient data is stored — only anonymized reference identifiers (OMIM, HPO, ClinVar accessions)

### Data Subject Rights

| Right | Implementation |
|-------|---------------|
| **Access** (Art. 15) | User profile API returns all stored personal data |
| **Rectification** (Art. 16) | User profile update endpoints |
| **Erasure** (Art. 17) | Account deletion cascade: user record, sessions, audit logs, authored capsules (configurable: anonymize vs delete) |
| **Portability** (Art. 20) | Export API returns capsules and metadata in JSON format |
| **Restriction** (Art. 18) | Account suspension preserves data without active processing |

### Data Retention

| Data Type | Retention Period | Justification |
|-----------|-----------------|---------------|
| User accounts | Until deletion requested | Service provision |
| Authentication logs | 90 days | Security monitoring |
| Audit trail | 1 year | Compliance, incident response |
| Capsule content | Indefinite (on-chain hash is permanent) | Research integrity |
| Session tokens | Until expiry + 24h cleanup | Authentication |

### Cross-Border Transfers
- Follows GA4GH Framework for Responsible Sharing of Genomic and Health-Related Data (2014)
- On-chain data (Base L2) is publicly accessible by design
- Off-chain data (Neo4j) is stored in the deployment region

## HIPAA Considerations

Forge does **not** store Protected Health Information (PHI) as defined by HIPAA:
- No patient names, addresses, dates of birth, or medical record numbers
- Only anonymized genomic reference identifiers (public databases)
- If a deployment processes actual PHI, a Business Associate Agreement (BAA) is required with the infrastructure provider

## On-Chain Data

Data anchored on-chain (Base L2) via CapsuleRegistry:
- `capsuleId`: SHA-256 hash (not reversible to content)
- `contentHash`: SHA-256 of capsule content (not reversible)
- `merkleRoot`: Lineage chain root (not reversible)
- `capsuleType`: Numeric type indicator (no PII)

**Note**: On-chain data cannot be deleted. The GDPR right to erasure applies to off-chain data only. On-chain hashes are considered pseudonymized (cannot be linked to individuals without the off-chain mapping).

## Genomics Data Standards

- **GA4GH Beacon v2**: Query interface for variant presence/absence
- **FHIR R5**: Health data interoperability standard
- **HGVS Nomenclature**: Standard variant naming (den Dunnen 2016)
- **ACMG/AMP Guidelines**: Variant classification framework (Richards 2015)
