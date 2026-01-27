"""
Forge Compliance Framework - Core Enumerations

Comprehensive enums for all compliance jurisdictions, frameworks, 
data classifications, and risk levels.
"""

from enum import Enum


class Jurisdiction(str, Enum):
    """
    Supported regulatory jurisdictions.
    
    Each jurisdiction may have multiple applicable frameworks.
    """
    # European Union & EEA
    EU = "eu"                    # EU-wide (GDPR, EU AI Act, EAA)
    GERMANY = "de"               # BDSG additions
    FRANCE = "fr"                # CNIL specifics
    UK = "uk"                    # UK GDPR post-Brexit
    
    # Americas
    US_FEDERAL = "us_federal"    # Federal (HIPAA, COPPA, GLBA, FTC Act)
    US_CALIFORNIA = "us_ca"      # CCPA/CPRA
    US_COLORADO = "us_co"        # Colorado AI Act
    US_VIRGINIA = "us_va"        # VCDPA
    US_CONNECTICUT = "us_ct"     # CTDPA
    US_UTAH = "us_ut"            # UCPA
    US_NEW_YORK = "us_ny"        # NYC Local Law 144
    US_ILLINOIS = "us_il"        # BIPA, HB 3773
    CANADA_FEDERAL = "ca"        # PIPEDA
    CANADA_QUEBEC = "ca_qc"      # Law 25
    BRAZIL = "br"                # LGPD
    
    # Asia-Pacific
    CHINA = "cn"                 # PIPL, CSL, GenAI regs
    JAPAN = "jp"                 # APPI
    INDIA = "in"                 # DPDP Act 2023
    SINGAPORE = "sg"             # PDPA
    AUSTRALIA = "au"             # Privacy Act, proposed AI rules
    SOUTH_KOREA = "kr"           # PIPA
    VIETNAM = "vn"               # Cybersecurity Law
    INDONESIA = "id"             # PDP Law
    THAILAND = "th"              # PDPA
    PHILIPPINES = "ph"           # DPA
    
    # Other
    RUSSIA = "ru"                # FZ-152 (data localization)
    SOUTH_AFRICA = "za"          # POPIA
    UAE = "ae"                   # DIFC/ADGM
    ISRAEL = "il"                # PPLA
    
    # Global baseline
    GLOBAL = "global"            # Universal controls
    
    @property
    def requires_localization(self) -> bool:
        """Check if jurisdiction requires data localization."""
        return self in {
            Jurisdiction.CHINA,
            Jurisdiction.RUSSIA,
            Jurisdiction.VIETNAM,
            Jurisdiction.INDONESIA,
        }
    
    @property
    def dsar_deadline_days(self) -> int:
        """Get DSAR response deadline in days for jurisdiction."""
        deadlines = {
            Jurisdiction.BRAZIL: 15,        # LGPD: strictest
            Jurisdiction.SINGAPORE: 30,
            Jurisdiction.EU: 30,
            Jurisdiction.UK: 30,
            Jurisdiction.US_CALIFORNIA: 45,
            Jurisdiction.INDIA: 30,
            Jurisdiction.SOUTH_KOREA: 10,
            Jurisdiction.GLOBAL: 30,
        }
        return deadlines.get(self, 30)
    
    @property
    def breach_notification_hours(self) -> int:
        """Get breach notification deadline in hours."""
        deadlines = {
            Jurisdiction.CHINA: 24,         # Immediate for national security
            Jurisdiction.EU: 72,
            Jurisdiction.UK: 72,
            Jurisdiction.SINGAPORE: 72,
            Jurisdiction.THAILAND: 72,
            Jurisdiction.BRAZIL: 72,        # 3 working days
            Jurisdiction.US_CALIFORNIA: 72,
            Jurisdiction.GLOBAL: 72,
        }
        return deadlines.get(self, 72)


class ComplianceFramework(str, Enum):
    """
    Regulatory and certification frameworks.
    
    Organized by category:
    - Privacy regulations
    - Security frameworks
    - Industry-specific regulations
    - AI governance
    - Accessibility standards
    """
    # Privacy Regulations
    GDPR = "gdpr"                       # EU General Data Protection Regulation
    CCPA = "ccpa"                       # California Consumer Privacy Act
    CPRA = "cpra"                       # California Privacy Rights Act (amends CCPA)
    LGPD = "lgpd"                       # Brazil Lei Geral de Proteção de Dados
    PIPL = "pipl"                       # China Personal Information Protection Law
    PDPA_SG = "pdpa_sg"                 # Singapore Personal Data Protection Act
    PDPA_TH = "pdpa_th"                 # Thailand Personal Data Protection Act
    POPIA = "popia"                     # South Africa Protection of Personal Information
    APPI = "appi"                       # Japan Act on Protection of Personal Information
    DPDP = "dpdp"                       # India Digital Personal Data Protection
    LAW25 = "law25"                     # Quebec Law 25
    PIPEDA = "pipeda"                   # Canada Federal Privacy
    VCDPA = "vcdpa"                     # Virginia Consumer Data Protection Act
    CTDPA = "ctdpa"                     # Connecticut Data Privacy Act
    UCPA = "ucpa"                       # Utah Consumer Privacy Act
    
    # Security Frameworks
    SOC2 = "soc2"                       # SOC 2 Type I/II
    ISO27001 = "iso27001"               # ISO/IEC 27001:2022
    NIST_CSF = "nist_csf"               # NIST Cybersecurity Framework 2.0
    NIST_800_53 = "nist_800_53"         # NIST SP 800-53 Rev 5
    CIS_CONTROLS = "cis_controls"       # CIS Controls v8
    FEDRAMP = "fedramp"                 # FedRAMP (Moderate/High)
    CSA_CCM = "csa_ccm"                 # Cloud Security Alliance CCM
    
    # Industry-Specific
    HIPAA = "hipaa"                     # Health Insurance Portability & Accountability
    HITECH = "hitech"                   # Health Information Technology for Economic
    PCI_DSS = "pci_dss"                 # Payment Card Industry Data Security Standard
    COPPA = "coppa"                     # Children's Online Privacy Protection Act
    FERPA = "ferpa"                     # Family Educational Rights and Privacy Act
    GLBA = "glba"                       # Gramm-Leach-Bliley Act
    SOX = "sox"                         # Sarbanes-Oxley Act
    FINRA = "finra"                     # Financial Industry Regulatory Authority
    
    # AI Governance
    EU_AI_ACT = "eu_ai_act"             # EU Artificial Intelligence Act
    COLORADO_AI = "colorado_ai"         # Colorado AI Act (SB 21-169)
    NYC_LL144 = "nyc_ll144"             # NYC Local Law 144 (AEDT)
    NIST_AI_RMF = "nist_ai_rmf"         # NIST AI Risk Management Framework
    ISO_42001 = "iso_42001"             # ISO/IEC 42001 AI Management System
    CA_AB2013 = "ca_ab2013"             # California AB 2013 Training Data Disclosure
    IL_HB3773 = "il_hb3773"             # Illinois HB 3773 AI in Employment
    
    # Accessibility
    WCAG_22 = "wcag_22"                 # Web Content Accessibility Guidelines 2.2
    EAA = "eaa"                         # European Accessibility Act
    EN_301_549 = "en_301_549"           # EU Accessibility Standard
    ADA_DIGITAL = "ada_digital"         # ADA Digital Accessibility
    SECTION_508 = "section_508"         # US Section 508
    
    @property
    def category(self) -> str:
        """Get framework category."""
        privacy = {self.GDPR, self.CCPA, self.CPRA, self.LGPD, self.PIPL, 
                   self.PDPA_SG, self.PDPA_TH, self.POPIA, self.APPI,
                   self.DPDP, self.LAW25, self.PIPEDA, self.VCDPA, 
                   self.CTDPA, self.UCPA}
        security = {self.SOC2, self.ISO27001, self.NIST_CSF, self.NIST_800_53,
                    self.CIS_CONTROLS, self.FEDRAMP, self.CSA_CCM}
        industry = {self.HIPAA, self.HITECH, self.PCI_DSS, self.COPPA, 
                    self.FERPA, self.GLBA, self.SOX, self.FINRA}
        ai = {self.EU_AI_ACT, self.COLORADO_AI, self.NYC_LL144, 
              self.NIST_AI_RMF, self.ISO_42001, self.CA_AB2013, self.IL_HB3773}
        accessibility = {self.WCAG_22, self.EAA, self.EN_301_549, 
                         self.ADA_DIGITAL, self.SECTION_508}
        
        if self in privacy:
            return "privacy"
        elif self in security:
            return "security"
        elif self in industry:
            return "industry"
        elif self in ai:
            return "ai_governance"
        elif self in accessibility:
            return "accessibility"
        return "other"


class DataClassification(str, Enum):
    """
    Data classification levels based on sensitivity.
    
    Determines encryption, access control, and retention requirements.
    """
    # Standard Classifications
    PUBLIC = "public"                   # Publicly available
    INTERNAL = "internal"               # Internal use only
    CONFIDENTIAL = "confidential"       # Business confidential
    RESTRICTED = "restricted"           # Highly sensitive
    
    # Special Categories (GDPR Article 9 / CCPA Sensitive)
    PERSONAL_DATA = "personal_data"     # Standard PII
    SENSITIVE_PERSONAL = "sensitive_personal"  # Special category data
    
    # Industry-Specific
    PHI = "phi"                         # Protected Health Information (HIPAA)
    PCI = "pci"                         # Payment Card Industry data
    FINANCIAL = "financial"             # Financial records (GLBA)
    EDUCATIONAL = "educational"         # Student records (FERPA)
    CHILDREN = "children"               # Children's data (COPPA)
    BIOMETRIC = "biometric"             # Biometric identifiers (BIPA)
    GENETIC = "genetic"                 # Genetic data
    
    # Cross-Border
    CRITICAL_INFRA = "critical_infrastructure"  # CIIO data (China PIPL)
    GOVERNMENT = "government"           # Government/defense
    
    @property
    def requires_encryption_at_rest(self) -> bool:
        """All sensitive data requires encryption at rest."""
        return self not in {self.PUBLIC}
    
    @property
    def requires_explicit_consent(self) -> bool:
        """Check if explicit consent is required."""
        return self in {
            self.SENSITIVE_PERSONAL, self.PHI, self.BIOMETRIC,
            self.GENETIC, self.CHILDREN, self.FINANCIAL,
        }
    
    @property
    def minimum_retention_years(self) -> int:
        """Get minimum retention period in years."""
        retention = {
            self.PHI: 6,            # HIPAA
            self.PCI: 1,            # PCI-DSS (after relationship ends)
            self.FINANCIAL: 7,      # SOX
            self.EDUCATIONAL: 5,    # FERPA varies
            self.GOVERNMENT: 10,
        }
        return retention.get(self, 3)
    
    @property
    def maximum_retention_years(self) -> int | None:
        """Get maximum retention period (None = no maximum)."""
        # GDPR principle: don't keep longer than necessary
        if self in {self.PERSONAL_DATA, self.SENSITIVE_PERSONAL}:
            return 7  # Default maximum for personal data
        return None


class RiskLevel(str, Enum):
    """Risk assessment levels for controls and operations."""
    CRITICAL = "critical"   # Immediate action required
    HIGH = "high"           # Urgent attention needed
    MEDIUM = "medium"       # Should be addressed
    LOW = "low"             # Monitor and track
    INFO = "info"           # Informational only


class ConsentType(str, Enum):
    """
    Types of consent for data processing.
    
    Granular consent types for different processing purposes.
    """
    # Core Consent Types
    ESSENTIAL = "essential"             # Required for service (no consent needed)
    ANALYTICS = "analytics"             # Usage analytics
    MARKETING = "marketing"             # Marketing communications
    PROFILING = "profiling"             # User profiling
    THIRD_PARTY = "third_party"         # Third-party sharing
    CROSS_BORDER = "cross_border"       # Cross-border transfers
    
    # AI-Specific
    AI_PROCESSING = "ai_processing"     # AI/ML processing
    AI_TRAINING = "ai_training"         # Use for AI training
    AI_DECISION = "ai_decision"         # Automated decision-making
    
    # Industry-Specific
    RESEARCH = "research"               # Research purposes
    HEALTH = "health"                   # Health data processing
    FINANCIAL = "financial"             # Financial data processing
    CHILDREN = "children"               # Child data (requires VPC)
    
    @property
    def requires_explicit_opt_in(self) -> bool:
        """Check if explicit opt-in is required."""
        return self not in {self.ESSENTIAL}
    
    @property
    def parent_consent_required(self) -> bool:
        """Check if verifiable parental consent required."""
        return self == self.CHILDREN


class DSARType(str, Enum):
    """
    Data Subject Access Request types.
    
    Per GDPR Articles 15-22 and equivalent regulations.
    """
    ACCESS = "access"                   # Right to access (Art. 15)
    RECTIFICATION = "rectification"     # Right to rectification (Art. 16)
    ERASURE = "erasure"                 # Right to erasure/deletion (Art. 17)
    RESTRICTION = "restriction"         # Right to restrict processing (Art. 18)
    PORTABILITY = "portability"         # Right to data portability (Art. 20)
    OBJECTION = "objection"             # Right to object (Art. 21)
    AUTOMATED = "automated"             # Rights re: automated decisions (Art. 22)
    
    # CCPA-Specific
    OPT_OUT_SALE = "opt_out_sale"       # Opt-out of sale/sharing
    LIMIT_SENSITIVE = "limit_sensitive" # Limit sensitive data use
    CORRECT = "correct"                 # Correction (CCPA 2023)
    
    @property
    def baseline_deadline_days(self) -> int:
        """Get baseline response deadline."""
        deadlines = {
            self.ACCESS: 30,
            self.ERASURE: 30,
            self.PORTABILITY: 30,
            self.OPT_OUT_SALE: 15,      # Must be honored immediately
            self.LIMIT_SENSITIVE: 15,
        }
        return deadlines.get(self, 30)


class BreachSeverity(str, Enum):
    """Breach severity classification."""
    CRITICAL = "critical"       # Mass data exposure, sensitive data
    HIGH = "high"               # Significant exposure
    MEDIUM = "medium"           # Limited exposure
    LOW = "low"                 # Minimal exposure
    
    @property
    def requires_authority_notification(self) -> bool:
        """Check if regulatory authority must be notified."""
        return self in {self.CRITICAL, self.HIGH, self.MEDIUM}
    
    @property
    def requires_individual_notification(self) -> bool:
        """Check if affected individuals must be notified."""
        return self in {self.CRITICAL, self.HIGH}


class AIRiskClassification(str, Enum):
    """
    EU AI Act risk classification.
    
    Per Article 6 and Annex III of the EU AI Act.
    """
    UNACCEPTABLE = "unacceptable"       # Prohibited (Art. 5)
    HIGH_RISK = "high_risk"             # Annex III, requires conformity
    LIMITED_RISK = "limited_risk"       # Transparency obligations only
    MINIMAL_RISK = "minimal_risk"       # No specific obligations
    GPAI = "gpai"                       # General Purpose AI (Chapter V)
    GPAI_SYSTEMIC = "gpai_systemic"     # GPAI with systemic risk
    
    @property
    def requires_conformity_assessment(self) -> bool:
        """Check if conformity assessment required."""
        return self in {self.HIGH_RISK, self.GPAI_SYSTEMIC}
    
    @property
    def requires_registration(self) -> bool:
        """Check if EU database registration required."""
        return self in {self.HIGH_RISK, self.GPAI, self.GPAI_SYSTEMIC}
    
    @property
    def max_penalty_percent_revenue(self) -> float:
        """Maximum penalty as percentage of global revenue."""
        penalties = {
            self.UNACCEPTABLE: 7.0,     # 7% or €35M
            self.HIGH_RISK: 3.0,        # 3% or €15M
            self.GPAI_SYSTEMIC: 3.0,
            self.LIMITED_RISK: 1.5,     # 1.5% or €7.5M
        }
        return penalties.get(self, 1.0)


class EncryptionStandard(str, Enum):
    """Encryption standards for data protection."""
    AES_256_GCM = "aes_256_gcm"         # Data at rest standard
    AES_256_CBC = "aes_256_cbc"         # Legacy compatibility
    CHACHA20_POLY1305 = "chacha20"      # Alternative to AES
    RSA_4096 = "rsa_4096"               # Asymmetric encryption
    ECDSA_P384 = "ecdsa_p384"           # Key signing
    
    # Transport
    TLS_1_3 = "tls_1_3"                 # Transport encryption
    TLS_1_2 = "tls_1_2"                 # Minimum acceptable


class KeyRotationPolicy(str, Enum):
    """Key rotation frequencies per NIST SP 800-57."""
    DAYS_30 = "30d"                     # High-risk environments
    DAYS_90 = "90d"                     # Standard production
    DAYS_180 = "180d"                   # Lower risk
    YEARS_1 = "1y"                      # Archive keys
    YEARS_2 = "2y"                      # Maximum for data encryption


class AccessControlModel(str, Enum):
    """Access control models."""
    RBAC = "rbac"                       # Role-Based Access Control
    ABAC = "abac"                       # Attribute-Based Access Control
    PBAC = "pbac"                       # Policy-Based Access Control
    DAC = "dac"                         # Discretionary Access Control
    MAC = "mac"                         # Mandatory Access Control
    ZERO_TRUST = "zero_trust"           # Zero Trust Architecture


class AuditEventCategory(str, Enum):
    """Categories for audit logging."""
    AUTHENTICATION = "authentication"   # Login, logout, MFA events
    AUTHORIZATION = "authorization"     # Access attempts, role changes
    DATA_ACCESS = "data_access"         # Read operations on sensitive data
    DATA_MODIFICATION = "data_modification"  # Create, update, delete
    SYSTEM = "system"                   # Config changes, service events
    SECURITY = "security"               # Threats, anomalies, incidents
    PRIVACY = "privacy"                 # DSAR, consent, breach events
    AI_DECISION = "ai_decision"         # AI/ML decision logging
    COMPLIANCE = "compliance"           # Compliance-related events
