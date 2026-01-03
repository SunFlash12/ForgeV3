# **FORGE CASCADE V3 \- Complete System Specification**

**Version:** 3.0.0  
 **Date:** 2026-01-02  
 **Classification:** Enterprise Production Specification  
 **Purpose:** Definitive architecture specification for the Forge Institutional Memory Engine

---

## **Document Control**

| Revision | Date | Author | Changes |
| ----- | ----- | ----- | ----- |
| 3.0.0 | 2026-01-02 | Forge Architecture Team | Complete v3 specification with global compliance, multi-platform UI, and AI-resistant implementation patterns |
| 2.0.0 | 2026-01-01 | \- | Neo4j unification, WebAssembly runtime, parallelized pipeline |
| 1.0.0 | 2025-11-13 | \- | Initial vision and architecture |

---

## **Table of Contents**

1. Executive Summary  
2. Problem Domain and Vision  
3. Core Concepts and Terminology  
4. System Architecture  
5. Data Model  
6. Neo4j Unified Data Store  
7. Seven-Phase Processing Pipeline  
8. WebAssembly Overlay Runtime  
9. Immune System Architecture  
10. Governance System  
11. Event Sourcing Architecture  
12. Global Compliance Framework  
13. Security Architecture  
14. API Specification  
15. Web Dashboard Interface  
16. Command Line Interface  
17. Mobile Application  
18. Deployment Architecture  
19. Implementation Guidelines  
20. Testing Strategy  
21. Migration Path  
22. Success Metrics

---

## **1\. Executive Summary**

### **1.1 What is Forge?**

Forge Cascade is an **Institutional Memory Engine** that solves the fundamental problem of ephemeral wisdom in AI systems. When AI models are upgraded, retrained, or migrated, they lose all learned knowledge, preferences, and hard-won insights. Forge creates a persistent layer that captures, preserves, and propagates knowledge across AI generations.

The platform combines three revolutionary capabilities into a unified architecture.

**Persistent Knowledge Capsules** store institutional wisdom in versioned, traceable containers that survive across any AI model change. When you migrate from GPT-4 to Claude to a future model, your organization's accumulated knowledge transfers seamlessly.

**Isnad Lineage Tracking** provides an unbroken chain of knowledge provenance inspired by the Islamic scholarly tradition of authenticating hadith through chains of transmission. Every piece of knowledge in Forge traces back through its complete ancestry, enabling audit trails, explainability, and rollback capabilities.

**Self-Governing Intelligence** implements democratic governance, self-healing immune systems, and ethical guardrails that ensure the platform operates autonomously while maintaining human oversight and control.

### **1.2 Strategic Positioning**

Forge is positioned as enterprise infrastructure for regulated industries, not as a consumer AI product. The target markets are legal firms requiring audit trails for AI-assisted decisions, biotechnology companies needing research provenance documentation, financial institutions subject to explainability requirements, and healthcare organizations requiring HIPAA-compliant AI systems.

The pricing model uses per-seat licensing or outcome-based pricing rather than token-based pricing, which masks the computational overhead inherent in maintaining full lineage and governance for every operation.

### **1.3 V3 Upgrades Summary**

Version 3 introduces four major architectural advances over previous versions.

**HybridRAG Architecture** combines Neo4j 5.x native vector indexing with graph traversal to enable queries that blend semantic similarity with structural relationships. A single query can find capsules semantically similar to a prompt while simultaneously traversing their lineage graphs.

**Global Compliance Framework** implements 400+ technical controls across 25+ regulatory frameworks including the EU AI Act (effective August 2026), NIST AI RMF, ISO 42001, GDPR, HIPAA, and regional data sovereignty requirements. The framework provides jurisdiction-aware data routing, automated breach notification workflows, and audit-ready logging.

**Multi-Platform Interface Architecture** delivers a professional web dashboard built on Shadcn/UI with dark mode and glassmorphism effects, a command-line interface using Typer with Rich for enterprise tooling integration, and a mobile application for monitoring and approval workflows.

**AI-Resistant Implementation Patterns** throughout this specification use explicit type schemas, validation constraints, concrete examples, and edge case documentation specifically designed to prevent common AI code generation errors such as hallucinated APIs, missing error handling, and type mismatches.

### **1.4 Key Technical Decisions**

| Decision | Choice | Rationale |
| ----- | ----- | ----- |
| Primary Database | Neo4j 5.x with Vector-2.0 | Unified graph \+ vector \+ properties in single ACID store |
| Overlay Runtime | Wasmtime (WebAssembly) | True memory isolation, instant termination, capability security |
| API Framework | FastAPI with Pydantic v2 | Async-native, type-safe, OpenAPI generation |
| Event System | Event Sourcing with Kafka/KurrentDB | Complete audit trail, temporal queries, corruption recovery |
| Web UI | React 18 \+ Shadcn/UI \+ Radix | Accessible, composable, dark-mode native |
| CLI | Typer \+ Rich \+ InquirerPy | Type-driven, beautiful output, wizard workflows |
| Mobile | React Native | Cross-platform, enterprise adoption, JavaScript ecosystem |

---

## **2\. Problem Domain and Vision**

### **2.1 The Problem: Ephemeral Wisdom**

Traditional AI systems suffer from knowledge amnesia. When systems are upgraded, patched, or retrained, four critical losses occur.

**Nuanced Wisdom Disappears.** The experiential knowledge and subtle lessons that the system accumulated over months or years of operation vanish instantly. An AI that learned your organization's communication style, your technical standards, your decision-making patterns—all of it resets to zero.

**Mistakes Repeat.** Without memory of past failures, new AI versions are destined to make the same errors. The organization loses weeks or months as the new system re-learns lessons that the previous version already mastered.

**No Generational Learning.** Each AI generation starts from scratch. Unlike human civilization, which builds upon accumulated cultural knowledge, AI systems show a sawtooth pattern of learning followed by complete forgetting.

**Knowledge Trapped in Parameters.** Whatever wisdom exists lives only within the current model's weights—opaque, inaccessible, and destined for deletion at the next upgrade.

This problem affects organizations at multiple levels. Individual users lose personalized AI assistants that understood their preferences. Teams lose AI systems that knew their workflows and conventions. Enterprises lose AI platforms that embodied institutional knowledge accumulated across years of operation.

### **2.2 The Solution: Forge Architecture**

Forge provides a cognitive architecture layer that sits between organizations and their AI systems, capturing and preserving knowledge independently of any specific model.

**Persistent Memory** stores knowledge in Capsules—versioned, traceable containers designed to survive across system generations. Capsules are stored in a dedicated data layer and can be loaded into any AI model's context.

**Evolutionary Intelligence** ensures each generation builds upon predecessors. When a new AI model is deployed, it inherits all Capsules from the previous system, starting with full access to organizational wisdom rather than blank slate.

**Symbolic Inheritance** links new knowledge explicitly to its ancestors through the DERIVED\_FROM relationship. When an insight evolves, the new version maintains a pointer to its parent, creating traceable lineage.

**The Cascade Effect** propagates breakthroughs across the ecosystem. When one overlay learns a critical lesson, it publishes an event that other overlays can integrate, elevating system-wide intelligence from localized discoveries.

**Self-Governance** implements democratic processes for system decisions. Proposals for changes go through voting periods where stakeholders with appropriate trust levels can approve or reject modifications.

**Self-Healing Architecture** detects problems through multi-level health checks, quarantines faulty components before they cause cascading failures, and recovers automatically when issues resolve.

### **2.3 The Philosophical Foundation**

Forge embodies the principle that AI systems should learn like cultures, not like individuals. Human civilization progresses because each generation inherits the accumulated knowledge of all previous generations through language, writing, and institutions. A physicist today does not need to rediscover calculus—they inherit it.

AI systems currently lack this civilizational property. Each model instance is an individual that will be forgotten entirely upon replacement. Forge transforms AI from a collection of isolated individuals into a continuous culture with persistent memory.

The Isnad model draws from Islamic scholarship's rigorous tradition of knowledge authentication. For over a millennium, hadith scholars have authenticated religious teachings by tracing chains of transmission back to original sources. Each narrator in the chain adds credibility through their reputation. Forge applies this same principle to AI knowledge—every insight traces back through verified predecessors to its original source.

### **2.4 Competitive Positioning**

The major AI providers are addressing memory at the model level through longer context windows and fine-tuning capabilities. This approach has fundamental limitations.

**Context Windows** are expensive, scale poorly, and still reset between conversations. A 200,000-token context window helps within a single session but provides no persistence across sessions or model changes.

**Fine-Tuning** bakes knowledge into model weights, making it impossible to trace, version, or selectively update. Fine-tuned knowledge cannot be audited, attributed, or explained.

Forge solves memory at the infrastructure level, providing capabilities that model-level approaches cannot match.

**Model Agnosticism** means Forge works with any AI model. Organizations can switch between OpenAI, Anthropic, Google, and open-source models while preserving all accumulated knowledge.

**Explainability** is built in through lineage tracking. Every piece of knowledge traces back to its source through a verifiable chain, satisfying regulatory requirements for AI explainability.

**Governance** provides organizational control over knowledge through democratic processes, trust hierarchies, and audit trails that model-level memory cannot offer.

**Selective Updates** allow organizations to modify specific knowledge without retraining entire models. A policy change updates the relevant Capsules; everything else remains intact.

---

## **3\. Core Concepts and Terminology**

### **3.1 Capsule**

A Capsule is the atomic unit of knowledge in Forge. It represents a single piece of persistent, evolvable information designed to survive across system generations.

#### **Capsule Schema**

python  
from pydantic import BaseModel, Field, field\_validator  
from typing import Optional, Literal  
from datetime import datetime, timezone  
from uuid import UUID, uuid4  
import re

class CapsuleType(str, Enum):  
    """  
    Classification of capsule content.  
      
    KNOWLEDGE: Facts, information, documentation  
    CODE: Source code, algorithms, implementations  
    DECISION: Recorded decisions with rationale  
    INSIGHT: Patterns, observations, learned lessons  
    CONFIG: System configuration, settings, preferences  
    POLICY: Organizational rules, guidelines, constraints  
    """  
    KNOWLEDGE \= "knowledge"  
    CODE \= "code"  
    DECISION \= "decision"  
    INSIGHT \= "insight"  
    CONFIG \= "config"  
    POLICY \= "policy"

class TrustLevel(str, Enum):  
    """  
    Security and reputation classification.  
      
    CORE (100): System-critical, immune to quarantine  
    TRUSTED (80): Verified reliable, full privileges  
    STANDARD (60): Default level, normal operations  
    SANDBOX (40): Experimental, limited and monitored  
    QUARANTINE (0): Blocked, no execution permitted  
    """  
    CORE \= "core"  
    TRUSTED \= "trusted"  
    STANDARD \= "standard"  
    SANDBOX \= "sandbox"  
    QUARANTINE \= "quarantine"

    @property  
    def numeric\_value(self) \-\> int:  
        mapping \= {  
            "core": 100,  
            "trusted": 80,  
            "standard": 60,  
            "sandbox": 40,  
            "quarantine": 0  
        }  
        return mapping\[self.value\]

class CapsuleCreate(BaseModel):  
    """  
    Schema for creating a new Capsule.  
    All validation rules are explicit to prevent implementation errors.  
    """  
    content: str \= Field(  
        ...,  
        min\_length\=1,  
        max\_length\=1\_000\_000,  
        description\="The actual knowledge content. Cannot be empty."  
    )  
    type: CapsuleType \= Field(  
        ...,  
        description\="Classification of the capsule content"  
    )  
    parent\_id: Optional\[UUID\] \= Field(  
        default\=None,  
        description\="UUID of parent capsule for symbolic inheritance. None for root capsules."  
    )  
    metadata: dict \= Field(  
        default\_factory\=dict,  
        description\="Extensible JSON metadata. Keys must be strings."  
    )  
      
    @field\_validator('content')  
    @classmethod  
    def content\_not\_whitespace\_only(cls, v: str) \-\> str:  
        if not v.strip():  
            raise ValueError('Content cannot be whitespace only')  
        return v  
      
    @field\_validator('metadata')  
    @classmethod  
    def metadata\_keys\_are\_strings(cls, v: dict) \-\> dict:  
        for key in v.keys():  
            if not isinstance(key, str):  
                raise ValueError(f'Metadata keys must be strings, got {type(key)}')  
        return v

class Capsule(BaseModel):  
    """  
    Complete Capsule entity as stored in Neo4j.  
      
    IMPORTANT: This schema is the source of truth. Any Neo4j queries  
    must return data conforming to this structure.  
    """  
    id: UUID \= Field(  
        default\_factory\=uuid4,  
        description\="Unique identifier. Generated server-side, never from client."  
    )  
    content: str \= Field(  
        ...,  
        min\_length\=1,  
        max\_length\=1\_000\_000  
    )  
    type: CapsuleType  
    version: str \= Field(  
        default\="1.0.0",  
        pattern\=r"^\\d+\\.\\d+\\.\\d+$",  
        description\="Semantic version. Format: MAJOR.MINOR.PATCH"  
    )  
    parent\_id: Optional\[UUID\] \= None  
    owner\_id: UUID \= Field(  
        ...,  
        description\="UUID of the user who created this capsule"  
    )  
    trust\_level: TrustLevel \= Field(  
        default\=TrustLevel.STANDARD  
    )  
    embedding: Optional\[list\[float\]\] \= Field(  
        default\=None,  
        description\="Vector embedding for semantic search. 1536 dimensions for OpenAI, 768 for smaller models."  
    )  
    metadata: dict \= Field(default\_factory\=dict)  
    created\_at: datetime \= Field(  
        default\_factory\=lambda: datetime.now(timezone.utc),  
        description\="Creation timestamp. Always UTC."  
    )  
    updated\_at: datetime \= Field(  
        default\_factory\=lambda: datetime.now(timezone.utc),  
        description\="Last modification timestamp. Always UTC."  
    )  
      
    @field\_validator('embedding')  
    @classmethod  
    def validate\_embedding\_dimensions(cls, v: Optional\[list\[float\]\]) \-\> Optional\[list\[float\]\]:  
        if v is not None:  
            valid\_dimensions \= {384, 768, 1024, 1536, 3072, 4096}  
            if len(v) not in valid\_dimensions:  
                raise ValueError(  
                    f'Embedding dimension {len(v)} not in valid set: {valid\_dimensions}'  
                )  
        return v

    model\_config \= {  
        "json\_schema\_extra": {  
            "examples": \[  
                {  
                    "id": "550e8400-e29b-41d4-a716-446655440000",  
                    "content": "Use FastAPI for all new Python web services due to superior async support and automatic OpenAPI generation.",  
                    "type": "decision",  
                    "version": "1.0.0",  
                    "parent\_id": None,  
                    "owner\_id": "123e4567-e89b-12d3-a456-426614174000",  
                    "trust\_level": "trusted",  
                    "embedding": None,  
                    "metadata": {  
                        "context": "Architecture review meeting 2025-12-15",  
                        "stakeholders": \["engineering", "platform"\],  
                        "supersedes": "flask-recommendation-2024"  
                    },  
                    "created\_at": "2025-12-15T14:30:00Z",  
                    "updated\_at": "2025-12-15T14:30:00Z"  
                }  
            \]  
        }

    }

#### **Capsule Lifecycle States**

Capsules progress through a defined lifecycle. The CREATE state occurs when a capsule is first submitted but not yet validated. ACTIVE indicates a capsule that passed validation and is available for use. VERSIONED means the capsule has been superseded by a child capsule through symbolic inheritance. ARCHIVED indicates a capsule that has been soft-deleted but remains available for lineage queries. MIGRATED marks a capsule that has been transferred to a new system while maintaining lineage.

┌─────────┐      ┌────────┐      ┌───────────┐      ┌──────────┐      ┌──────────┐  
│ CREATE  │ ──── │ ACTIVE │ ──── │ VERSIONED │ ──── │ ARCHIVED │ ──── │ MIGRATED │  
└─────────┘      └────────┘      └───────────┘      └──────────┘      └──────────┘  
                     │  
                     │ (Trust violation)  
                     ▼  
               ┌─────────────┐  
               │ QUARANTINED │

               └─────────────┘

### **3.2 Overlay**

An Overlay is a self-contained intelligent module that extends Forge's capabilities. Overlays provide specialized functionality such as governance, security validation, machine learning analysis, and performance optimization. In v3, overlays are compiled to WebAssembly for execution in a sandboxed environment.

#### **Overlay Schema**

python  
class OverlayCapability(str, Enum):  
    """  
    Explicit permissions that overlays must declare.  
    The runtime only links functions for declared capabilities.  
    """  
    NETWORK\_OUTBOUND \= "network\_outbound"      *\# HTTP requests to external services*  
    NETWORK\_LOOPBACK \= "network\_loopback"      *\# Localhost connections only*  
    DATABASE\_READ \= "database\_read"            *\# Neo4j read queries*  
    DATABASE\_WRITE \= "database\_write"          *\# Neo4j write queries*  
    EVENT\_PUBLISH \= "event\_publish"            *\# Publish to event bus*  
    EVENT\_SUBSCRIBE \= "event\_subscribe"        *\# Subscribe to event bus*  
    CAPSULE\_CREATE \= "capsule\_create"          *\# Create new capsules*  
    CAPSULE\_MODIFY \= "capsule\_modify"          *\# Modify existing capsules*  
    CAPSULE\_DELETE \= "capsule\_delete"          *\# Soft-delete capsules*  
    GOVERNANCE\_VOTE \= "governance\_vote"        *\# Participate in voting*  
    GOVERNANCE\_PROPOSE \= "governance\_propose"  *\# Create proposals*  
    FILESYSTEM\_READ \= "filesystem\_read"        *\# Read from designated paths*  
    FILESYSTEM\_WRITE \= "filesystem\_write"      *\# Write to designated paths*

class OverlayState(str, Enum):  
    """Runtime state of an overlay instance."""  
    REGISTERED \= "registered"    *\# Known but not loaded*  
    LOADING \= "loading"          *\# WebAssembly compilation in progress*  
    ACTIVE \= "active"            *\# Running normally*  
    SUSPENDED \= "suspended"      *\# Temporarily paused*  
    QUARANTINED \= "quarantined"  *\# Blocked due to failures*  
    TERMINATED \= "terminated"    *\# Permanently stopped*

class OverlayManifest(BaseModel):  
    """  
    Manifest file that must accompany every overlay.  
    Located at: overlays/{overlay\_name}/manifest.json  
    """  
    name: str \= Field(  
        ...,  
        pattern\=r"^\[a-z\]\[a-z0-9\_\]{2,63}$",  
        description\="Lowercase identifier. Letters, numbers, underscores. 3-64 chars."  
    )  
    version: str \= Field(  
        ...,  
        pattern\=r"^\\d+\\.\\d+\\.\\d+$"  
    )  
    description: str \= Field(  
        ...,  
        max\_length\=500  
    )  
    author: str \= Field(  
        ...,  
        max\_length\=100  
    )  
    capabilities: list\[OverlayCapability\] \= Field(  
        ...,  
        min\_length\=1,  
        description\="Required capabilities. Cannot be empty."  
    )  
    dependencies: list\[str\] \= Field(  
        default\_factory\=list,  
        description\="Names of overlays this one requires"  
    )  
    resource\_limits: ResourceLimits \= Field(  
        default\_factory\=ResourceLimits  
    )  
      
    @field\_validator('capabilities')  
    @classmethod  
    def validate\_capability\_combinations(cls, v: list\[OverlayCapability\]) \-\> list\[OverlayCapability\]:  
        *\# DATABASE\_WRITE requires DATABASE\_READ*  
        if OverlayCapability.DATABASE\_WRITE in v and OverlayCapability.DATABASE\_READ not in v:  
            raise ValueError('DATABASE\_WRITE requires DATABASE\_READ capability')  
        *\# CAPSULE\_MODIFY and CAPSULE\_DELETE require DATABASE\_WRITE*  
        if (OverlayCapability.CAPSULE\_MODIFY in v or OverlayCapability.CAPSULE\_DELETE in v):  
            if OverlayCapability.DATABASE\_WRITE not in v:  
                raise ValueError('CAPSULE\_MODIFY/DELETE requires DATABASE\_WRITE capability')  
        return v

class ResourceLimits(BaseModel):  
    """  
    Resource constraints enforced by the WebAssembly runtime.  
    """  
    max\_memory\_mb: int \= Field(  
        default\=256,  
        ge\=16,  
        le\=2048,  
        description\="Maximum memory allocation in megabytes"  
    )  
    max\_cpu\_ms: int \= Field(  
        default\=5000,  
        ge\=100,  
        le\=60000,  
        description\="Maximum CPU time per invocation in milliseconds"  
    )  
    max\_fuel: int \= Field(  
        default\=10\_000\_000,  
        ge\=100\_000,  
        le\=1\_000\_000\_000,  
        description\="Wasmtime fuel units (approximately 1 fuel per wasm instruction)"  
    )

class Overlay(BaseModel):  
    """Complete overlay entity."""  
    id: UUID \= Field(default\_factory\=uuid4)  
    manifest: OverlayManifest  
    wasm\_hash: str \= Field(  
        ...,  
        pattern\=r"^sha256:\[a-f0-9\]{64}$",  
        description\="SHA-256 hash of compiled WebAssembly binary"  
    )  
    source\_hash: str \= Field(  
        ...,  
        pattern\=r"^sha256:\[a-f0-9\]{64}$",  
        description\="SHA-256 hash of source code for verification"  
    )  
    trust\_level: TrustLevel \= Field(default\=TrustLevel.SANDBOX)  
    state: OverlayState \= Field(default\=OverlayState.REGISTERED)  
    metrics: OverlayMetrics \= Field(default\_factory\=OverlayMetrics)  
    created\_at: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))  
    updated\_at: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))

class OverlayMetrics(BaseModel):  
    """Runtime metrics for overlay monitoring."""  
    invocation\_count: int \= Field(default\=0, ge\=0)  
    success\_count: int \= Field(default\=0, ge\=0)  
    failure\_count: int \= Field(default\=0, ge\=0)  
    total\_execution\_ms: int \= Field(default\=0, ge\=0)  
    last\_invocation\_at: Optional\[datetime\] \= None  
    last\_failure\_at: Optional\[datetime\] \= None

    circuit\_breaker\_state: Literal\["closed", "open", "half\_open"\] \= "closed"

#### **Core Overlays**

Forge ships with six core overlays that provide fundamental functionality.

**symbolic\_governance** implements democratic decision-making through proposals, voting, and policy enforcement. It requires database read/write, event publish/subscribe, and governance capabilities.

**security\_validator** validates trust levels, detects threats, and enforces access policies. It requires database read and event capabilities.

**ml\_intelligence** provides machine learning analysis including anomaly detection, pattern recognition, and similarity scoring. It requires database read and event publish capabilities.

**performance\_optimizer** monitors system performance, manages caching, and allocates resources. It requires database read and event capabilities.

**capsule\_analyzer** extracts insights from capsule content through summarization, classification, and relationship detection. It requires database read/write, capsule create, and event capabilities.

**lineage\_tracker** visualizes and queries capsule ancestry for audit trails and explainability. It requires database read only.

### **3.3 Symbolic Inheritance**

Symbolic Inheritance is the principle that knowledge passes down through system generations with explicit lineage tracking. When a new capsule evolves from an existing one, the DERIVED\_FROM relationship preserves the connection.

The inheritance mechanism works as follows. When creating a capsule with a parent\_id, the new capsule initially inherits the parent's trust level (potentially adjusted based on the creator's trust). The new capsule's version starts at 1.0.0 regardless of parent version. The DERIVED\_FROM edge records the reason for evolution, a timestamp, and a diff of changes.

cypher  
*// Creating a child capsule with inheritance*  
MATCH (parent:Capsule {id: $parent\_id})  
CREATE (child:Capsule {  
  id: randomUUID(),  
  content: $content,  
  type: $type,  
  version: '1.0.0',  
  owner\_id: $owner\_id,  
  trust\_level: CASE   
    WHEN parent.trust\_level \= 'core' THEN 'trusted'  
    ELSE parent.trust\_level   
  END,  
  created\_at: datetime(),  
  updated\_at: datetime()  
})  
CREATE (child)\-\[:DERIVED\_FROM {  
  reason: $reason,  
  timestamp: datetime(),  
  changes: $changes\_summary  
}\]\-\>(parent)

RETURN child

The complete lineage of any capsule can be traced with a single query.

cypher  
*// Trace full ancestry (the Isnad chain)*  
MATCH path \= (c:Capsule {id: $capsule\_id})\-\[:DERIVED\_FROM\*\]\-\>(ancestor)  
RETURN path

ORDER BY length(path)

### **3.4 The Cascade Effect**

The Cascade Effect describes how breakthroughs in one overlay propagate across the entire ecosystem. The mechanism operates through the event system.

When an overlay makes a significant discovery—such as the security\_validator detecting a new attack pattern—it publishes an event containing the insight, contextual information, confidence level, and suggested relevance to other overlays. The event system routes this to subscribed overlays. The ml\_intelligence overlay might update its anomaly detection model based on the new pattern. The performance\_optimizer might adjust resource allocation to increase security validation capacity. The governance system might create a proposal for new input validation rules.

python  
*\# Example cascade event*  
class CascadeEvent(BaseModel):  
    source\_overlay: str  
    event\_type: str  
    payload: dict  
    confidence: float \= Field(ge\=0.0, le\=1.0)  
    suggested\_relevance: list\[str\] \= Field(  
        description\="Overlay names that might find this relevant"  
    )  
    timestamp: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))

*\# Publishing a cascade event*  
await event\_bus.publish(CascadeEvent(  
    source\_overlay\="security\_validator",  
    event\_type\="threat\_pattern\_detected",  
    payload\={  
        "pattern\_type": "sql\_injection",  
        "signature": "UNION SELECT from information\_schema",  
        "sample\_count": 47,  
        "first\_seen": "2026-01-02T14:30:00Z"  
    },  
    confidence\=0.94,  
    suggested\_relevance\=\["ml\_intelligence", "capsule\_analyzer"\]

))

### **3.5 Trust Hierarchy**

Every entity in Forge—users, capsules, overlays—has a trust level that determines what operations it can perform. Trust levels form a hierarchy with five tiers.

**CORE (100)** is reserved for system-critical components. Core entities have full access to all operations and cannot be quarantined. Only the system can assign this level.

**TRUSTED (80)** indicates verified, reliable entities. Trusted entities can perform most operations, participate in governance voting, and create new capsules with elevated trust.

**STANDARD (60)** is the default level for new entities. Standard entities can perform basic operations but have limited influence in governance.

**SANDBOX (40)** is used for experimental or unverified entities. Sandbox entities operate with limited capabilities and are monitored more closely.

**QUARANTINE (0)** blocks all execution. Entities at this level cannot perform any operations and must be rehabilitated through governance processes.

Trust adjusts dynamically based on behavior. Successful operations, positive governance votes, and time in service increase trust. Failures, security incidents, and negative votes decrease trust. Three consecutive health check failures trigger automatic quarantine.

---

## **4\. System Architecture**

### **4.1 High-Level Architecture**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                              CLIENT LAYER                                    │  
│                                                                             │  
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐               │  
│  │  Web Dashboard │    │     CLI       │    │ Mobile App    │               │  
│  │  (React 18\)    │    │  (Typer+Rich) │    │ (React Native)│               │  
│  └───────────────┘    └───────────────┘    └───────────────┘               │  
│           │                   │                     │                        │  
└───────────┴───────────────────┴─────────────────────┴────────────────────────┘  
            │                   │                     │  
            └───────────────────┴─────────────────────┘  
                                │  
                          HTTPS/WSS  
                                │  
┌───────────────────────────────┴─────────────────────────────────────────────┐  
│                              API LAYER                                       │  
│                                                                             │  
│  ┌─────────────────────────────────────────────────────────────────────┐   │  
│  │                        API GATEWAY                                   │   │  
│  │  • Rate Limiting (per-user, per-IP, per-endpoint)                   │   │  
│  │  • JWT Validation                                                    │   │  
│  │  • Request Routing                                                   │   │  
│  │  • SSL Termination                                                   │   │  
│  └─────────────────────────────────────────────────────────────────────┘   │  
│                                │                                            │  
│  ┌─────────────────────────────┴───────────────────────────────────────┐   │  
│  │                     FastAPI Application                              │   │  
│  │                                                                      │   │  
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │  
│  │  │ Capsules │ │  Users   │ │Governance│ │ Overlays │ │Compliance│  │   │  
│  │  │   API    │ │   API    │ │   API    │ │   API    │ │   API    │  │   │  
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │  
│  │                                                                      │   │  
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │  
│  │  │                   Middleware Stack                              │ │   │  
│  │  │  • Authentication (JWT \+ API Key)                               │ │   │  
│  │  │  • Authorization (RBAC \+ ABAC)                                  │ │   │  
│  │  │  • Audit Logging                                                │ │   │  
│  │  │  • Request ID Injection                                         │ │   │  
│  │  │  • CORS Handling                                                │ │   │  
│  │  │  • Compression                                                  │ │   │  
│  │  └────────────────────────────────────────────────────────────────┘ │   │  
│  └─────────────────────────────────────────────────────────────────────┘   │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
┌───────────────────────────────┴─────────────────────────────────────────────┐  
│                           PROCESSING LAYER                                   │  
│                                                                             │  
│  ┌────────────────────────────────────────────────────────────────────┐    │  
│  │                    Seven-Phase Pipeline                             │    │  
│  │                                                                     │    │  
│  │  ┌───────────────────────────────────────────────────────────┐    │    │  
│  │  │ PARALLEL GROUP (asyncio.gather)                            │    │    │  
│  │  │  Phase 1: Context    Phase 2: Analysis    Phase 3: Security│    │    │  
│  │  └───────────────────────────────────────────────────────────┘    │    │  
│  │                            │                                       │    │  
│  │  ┌───────────────────────────────────────────────────────────┐    │    │  
│  │  │ SEQUENTIAL                                                 │    │    │  
│  │  │  Phase 4: Optimization    Phase 5: Intelligence            │    │    │  
│  │  └───────────────────────────────────────────────────────────┘    │    │  
│  │                            │                                       │    │  
│  │  ┌───────────────────────────────────────────────────────────┐    │    │  
│  │  │ FIRE-AND-FORGET (asyncio.create\_task)                      │    │    │  
│  │  │  Phase 6: Metrics    Phase 7: Storage                      │    │    │  
│  │  └───────────────────────────────────────────────────────────┘    │    │  
│  └────────────────────────────────────────────────────────────────────┘    │  
│                                                                             │  
│  ┌────────────────────────────────────────────────────────────────────┐    │  
│  │                   WebAssembly Overlay Runtime                       │    │  
│  │                                                                     │    │  
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │  
│  │  │Governance│ │ Security │ │    ML    │ │ Analyzer │ ...          │    │  
│  │  │ (Wasm)   │ │  (Wasm)  │ │  (Wasm)  │ │  (Wasm)  │              │    │  
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │  
│  │                                                                     │    │  
│  │  Wasmtime Runtime with Capability-Based Security                   │    │  
│  └────────────────────────────────────────────────────────────────────┘    │  
│                                                                             │  
│  ┌────────────────────────────────────────────────────────────────────┐    │  
│  │                      Immune System                                  │    │  
│  │                                                                     │    │  
│  │  Health Checker → Anomaly Detector → Circuit Breaker → Recovery    │    │  
│  └────────────────────────────────────────────────────────────────────┘    │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
┌───────────────────────────────┴─────────────────────────────────────────────┐  
│                             DATA LAYER                                       │  
│                                                                             │  
│  ┌──────────────────────────────────────────────────────────────────────┐  │  
│  │                     Neo4j Unified Store                               │  │  
│  │                                                                       │  │  
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐            │  │  
│  │  │     GRAPH      │ │     VECTOR     │ │   PROPERTIES   │            │  │  
│  │  │   Lineage,     │ │   Semantic     │ │  Trust, Owner, │            │  │  
│  │  │   Ancestry,    │ │   Search,      │ │  Version, Meta │            │  │  
│  │  │   Cascades     │ │   Similarity   │ │  Timestamps    │            │  │  
│  │  └────────────────┘ └────────────────┘ └────────────────┘            │  │  
│  │                                                                       │  │  
│  │             SINGLE ACID-COMPLIANT DATABASE                           │  │  
│  └──────────────────────────────────────────────────────────────────────┘  │  
│                                                                             │  
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────────┐  │  
│  │    Event Store     │ │       Redis        │ │   Object Storage       │  │  
│  │  (Kafka/KurrentDB) │ │  (Cache \+ Queues)  │ │  (S3/MinIO)           │  │  
│  │  Immutable Events  │ │  Session, Cache    │ │  Wasm Binaries, Logs  │  │  
│  └────────────────────┘ └────────────────────┘ └────────────────────────┘  │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
┌───────────────────────────────┴─────────────────────────────────────────────┐  
│                         OBSERVABILITY LAYER                                  │  
│                                                                             │  
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────────┐  │  
│  │    Prometheus      │ │      Grafana       │ │        Jaeger          │  │  
│  │    (Metrics)       │ │   (Dashboards)     │ │  (Distributed Tracing) │  │  
│  └────────────────────┘ └────────────────────┘ └────────────────────────┘  │

└─────────────────────────────────────────────────────────────────────────────┘

### **4.2 Request Flow**

A typical request flows through the system as follows.

The client sends an HTTPS request to the API Gateway. The gateway validates the JWT token, checks rate limits, and routes to the appropriate FastAPI endpoint.

The FastAPI middleware stack authenticates the user, authorizes the specific operation based on trust level and RBAC/ABAC rules, generates a request ID, and begins audit logging.

The request enters the Seven-Phase Pipeline. Phases 1-3 run in parallel gathering context from similar capsules, analyzing content with ML, and validating security constraints. Phase 4 optimizes based on combined results. Phase 5 makes the primary LLM call if needed. Phases 6-7 run as fire-and-forget tasks for metrics and storage.

During pipeline execution, overlays may be invoked through the WebAssembly runtime. Each overlay runs in its own isolated sandbox with only the capabilities declared in its manifest.

The Immune System monitors the entire flow, checking health at multiple levels, managing circuit breakers, and triggering recovery if needed.

All state changes are persisted to Neo4j. Events are published to the event store. Metrics are scraped by Prometheus. Traces are collected by Jaeger.

### **4.3 Component Boundaries**

Clear boundaries separate components to enable independent scaling and maintenance.

**API Layer** handles HTTP concerns only. It validates input schemas, authenticates users, and routes requests. It does not contain business logic.

**Processing Layer** contains all business logic. The pipeline orchestrates operation flow. Overlays provide specialized functionality. The immune system ensures reliability.

**Data Layer** provides persistence only. Neo4j stores structured data. The event store provides immutable event history. Redis provides caching. Object storage holds large binaries.

**Observability Layer** collects and visualizes telemetry. It has read-only access to other layers and never affects system behavior.

---

## **5\. Data Model**

### **5.1 Entity Relationship Diagram**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                          FORGE DATA MODEL                                    │  
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐          ┌──────────────┐          ┌──────────────┐  
│     User     │          │   Capsule    │          │   Overlay    │  
├──────────────┤          ├──────────────┤          ├──────────────┤  
│ id: UUID     │──owns───▶│ id: UUID     │◀─process─│ id: UUID     │  
│ email: str   │          │ content: str │          │ name: str    │  
│ trust: Trust │──votes──▶│ type: Type   │          │ version: str │  
│ roles: list  │          │ version: str │          │ wasm\_hash    │  
│ created\_at   │          │ parent\_id?   │          │ capabilities │  
│ mfa\_enabled  │          │ owner\_id     │          │ trust: Trust │  
└──────────────┘          │ trust: Trust │          │ state: State │  
       │                  │ embedding\[\]  │          └──────────────┘  
       │                  │ metadata: {} │                 │  
       │                  │ created\_at   │                 │  
       │                  └──────────────┘                 │  
       │                         │                         │  
       │                         │ DERIVED\_FROM            │  
       │                         ▼                         │  
       │                  ┌──────────────┐                 │  
       │                  │   Capsule    │                 │  
       │                  │   (Parent)   │                 │  
       │                  └──────────────┘                 │  
       │                                                   │  
       │                  ┌──────────────┐                 │  
       └───creates───────▶│   Proposal   │◀───submits─────┘  
                          ├──────────────┤  
                          │ id: UUID     │  
                          │ title: str   │  
                          │ type: Type   │  
                          │ status: enum │  
                          │ proposer\_id  │  
                          │ voting\_ends  │  
                          └──────────────┘  
                                 │  
                                 │ HAS\_VOTE  
                                 ▼  
                          ┌──────────────┐  
                          │     Vote     │  
                          ├──────────────┤  
                          │ voter\_id     │  
                          │ decision     │  
                          │ weight: int  │  
                          │ timestamp    │  
                          └──────────────┘

┌──────────────┐          ┌──────────────┐          ┌──────────────┐  
│    Event     │          │  AuditLog    │          │   Session    │  
├──────────────┤          ├──────────────┤          ├──────────────┤  
│ id: UUID     │          │ id: UUID     │          │ id: UUID     │  
│ type: str    │          │ timestamp    │          │ user\_id      │  
│ source: str  │          │ action: str  │          │ token\_hash   │  
│ payload: {}  │          │ actor\_id     │          │ ip\_address   │  
│ timestamp    │          │ resource     │          │ user\_agent   │  
│ sequence: int│          │ changes: {}  │          │ expires\_at   │  
└──────────────┘          │ ip\_address   │          │ mfa\_verified │

                          └──────────────┘          └──────────────┘

### **5.2 Neo4j Node Labels**

The following node labels are used in the Neo4j graph.

cypher  
*// Core entities*  
(:User {id, email, display\_name, trust\_level, roles, created\_at, updated\_at})  
(:Capsule {id, content, type, version, trust\_level, embedding, metadata, created\_at, updated\_at})  
(:Overlay {id, name, version, wasm\_hash, source\_hash, trust\_level, state, capabilities, created\_at})  
(:Proposal {id, title, description, type, status, proposer\_id, voting\_ends, created\_at})  
(:Vote {voter\_id, decision, weight, reasoning, timestamp})

*// Supporting entities*  
(:Session {id, token\_hash, ip\_address, user\_agent, expires\_at, mfa\_verified, created\_at})  
(:AuditLog {id, timestamp, action, actor\_type, actor\_id, resource\_type, resource\_id, changes, ip\_address})

*// Compliance entities*  
(:ConsentRecord {id, user\_id, purpose, granted, timestamp, jurisdiction, version})  
(:DSARRequest {id, user\_id, type, status, submitted\_at, due\_date, completed\_at})

(:BreachIncident {id, severity, detected\_at, description, affected\_count, notifications\_sent})

### **5.3 Neo4j Relationship Types**

cypher  
*// Capsule relationships*  
(child:Capsule)\-\[:DERIVED\_FROM {reason, timestamp, changes}\]\-\>(parent:Capsule)  
(capsule:Capsule)\-\[:OWNED\_BY\]\-\>(user:User)  
(capsule:Capsule)\-\[:TAGGED\_WITH\]\-\>(tag:Tag)  
(capsule:Capsule)\-\[:REFERENCES\]\-\>(other:Capsule)

*// User relationships*  
(user:User)\-\[:HAS\_ROLE\]\-\>(role:Role)  
(user:User)\-\[:MEMBER\_OF\]\-\>(organization:Organization)  
(user:User)\-\[:HAS\_SESSION\]\-\>(session:Session)

*// Governance relationships*  
(user:User)\-\[:CREATED\]\-\>(proposal:Proposal)  
(proposal:Proposal)\-\[:HAS\_VOTE\]\-\>(vote:Vote)  
(user:User)\-\[:CAST\]\-\>(vote:Vote)

*// Overlay relationships*  
(overlay:Overlay)\-\[:DEPENDS\_ON\]\-\>(dependency:Overlay)  
(overlay:Overlay)\-\[:PROCESSED\]\-\>(capsule:Capsule)

*// Compliance relationships*  
(user:User)\-\[:GAVE\_CONSENT\]\-\>(consent:ConsentRecord)

(user:User)\-\[:SUBMITTED\]\-\>(dsar:DSARRequest)

### **5.4 Vector Indexes**

Neo4j 5.x vector indexes enable semantic search on capsule embeddings.

cypher  
*// Create vector index for capsule embeddings*  
CREATE VECTOR INDEX capsule\_embedding\_index IF NOT EXISTS  
FOR (c:Capsule)  
ON c.embedding  
OPTIONS {  
  indexConfig: {  
    \`vector.dimensions\`: 1536,  
    \`vector.similarity\_function\`: 'cosine',  
    \`vector.quantization.enabled\`: true,  
    \`vector.hnsw.m\`: 16,  
    \`vector.hnsw.efConstruction\`: 200  
  }  
}

*// Semantic search query*  
CALL db.index.vector.queryNodes(  
  'capsule\_embedding\_index',  
  10,  *// top K results*  
  $query\_embedding  
)  
YIELD node, score  
WHERE node.trust\_level \<\> 'quarantine'

RETURN node, score

### **5.5 Composite Queries**

The power of Neo4j's unified store is combining graph traversal with vector search.

cypher  
*// Find similar capsules from the same author lineage*  
CALL db.index.vector.queryNodes('capsule\_embedding\_index', 20, $embedding)  
YIELD node AS similar, score  
MATCH (similar)\-\[:OWNED\_BY\]\-\>(owner:User)  
MATCH path \= (similar)\-\[:DERIVED\_FROM\*0..5\]\-\>(ancestor:Capsule)  
WHERE score \> 0.7  
RETURN similar, score, owner.display\_name,   
       \[n IN nodes(path) | n.id\] AS lineage  
ORDER BY score DESC

LIMIT 10

---

## **6\. Neo4j Unified Data Store**

### **6.1 Design Rationale**

Version 1 of Forge required three separate databases working together: a vector database for semantic search, a graph database for lineage tracking, and a relational database for user management and metadata. Keeping these synchronized created significant challenges.

**Consistency Issues.** If the vector index recorded a similarity relationship but the graph database hadn't created the lineage edge yet, the system would show "hallucinated references"—relationships that appeared to exist but didn't.

**Transaction Complexity.** Creating a capsule required coordinating transactions across three databases with no guarantee of atomicity. A failure partway through could leave the system in an inconsistent state.

**Operational Overhead.** Three databases meant three sets of backups, three monitoring systems, three scaling strategies, and three potential points of failure.

Neo4j 5.x solves these problems by providing native vector indexing alongside its graph capabilities. A single ACID-compliant database handles all three concerns: graph relationships for lineage, vector indexes for semantic search, and node properties for structured data.

### **6.2 Database Configuration**

yaml  
*\# neo4j.conf recommended settings for Forge*  
server.memory.heap.initial\_size=2g  
server.memory.heap.max\_size=4g  
server.memory.pagecache.size=2g

*\# Enable vector indexes*  
dbms.security.procedures.unrestricted=db.index.vector.\*

*\# Enable Change Data Capture for event sourcing*  
db.tx\_log.rotation.retention\_policy=7 days

*\# Enable query logging for audit*  
db.logs.query.enabled=VERBOSE

db.logs.query.threshold=0ms

### **6.3 Schema Constraints**

cypher  
*// Unique constraints*  
CREATE CONSTRAINT capsule\_id\_unique IF NOT EXISTS  
FOR (c:Capsule) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT user\_id\_unique IF NOT EXISTS  
FOR (u:User) REQUIRE u.id IS UNIQUE;

CREATE CONSTRAINT user\_email\_unique IF NOT EXISTS  
FOR (u:User) REQUIRE u.email IS UNIQUE;

CREATE CONSTRAINT overlay\_id\_unique IF NOT EXISTS  
FOR (o:Overlay) REQUIRE o.id IS UNIQUE;

CREATE CONSTRAINT overlay\_name\_version\_unique IF NOT EXISTS  
FOR (o:Overlay) REQUIRE (o.name, o.version) IS UNIQUE;

CREATE CONSTRAINT proposal\_id\_unique IF NOT EXISTS  
FOR (p:Proposal) REQUIRE p.id IS UNIQUE;

*// Existence constraints*  
CREATE CONSTRAINT capsule\_content\_exists IF NOT EXISTS  
FOR (c:Capsule) REQUIRE c.content IS NOT NULL;

CREATE CONSTRAINT capsule\_type\_exists IF NOT EXISTS  
FOR (c:Capsule) REQUIRE c.type IS NOT NULL;

CREATE CONSTRAINT user\_email\_exists IF NOT EXISTS  
FOR (u:User) REQUIRE u.email IS NOT NULL;

*// Property type constraints (Neo4j 5.9+)*  
CREATE CONSTRAINT capsule\_trust\_type IF NOT EXISTS  
FOR (c:Capsule) REQUIRE c.trust\_level IS :: STRING;

CREATE CONSTRAINT capsule\_version\_format IF NOT EXISTS

FOR (c:Capsule) REQUIRE c.version \=\~ '^\\d+\\.\\d+\\.\\d+$';

### **6.4 Index Strategy**

cypher  
*// Performance indexes*  
CREATE INDEX capsule\_type\_index IF NOT EXISTS  
FOR (c:Capsule) ON (c.type);

CREATE INDEX capsule\_trust\_index IF NOT EXISTS  
FOR (c:Capsule) ON (c.trust\_level);

CREATE INDEX capsule\_owner\_index IF NOT EXISTS  
FOR (c:Capsule) ON (c.owner\_id);

CREATE INDEX capsule\_created\_index IF NOT EXISTS  
FOR (c:Capsule) ON (c.created\_at);

CREATE INDEX user\_trust\_index IF NOT EXISTS  
FOR (u:User) ON (u.trust\_level);

CREATE INDEX proposal\_status\_index IF NOT EXISTS  
FOR (p:Proposal) ON (p.status);

CREATE INDEX audit\_timestamp\_index IF NOT EXISTS  
FOR (a:AuditLog) ON (a.timestamp);

*// Full-text index for content search*  
CREATE FULLTEXT INDEX capsule\_content\_fulltext IF NOT EXISTS  
FOR (c:Capsule)  
ON EACH \[c.content, c.metadata\]  
OPTIONS {  
  indexConfig: {  
    \`fulltext.analyzer\`: 'english'  
  }

}

### **6.5 Connection Management**

python  
from neo4j import AsyncGraphDatabase  
from contextlib import asynccontextmanager  
from typing import AsyncGenerator

class Neo4jClient:  
    """  
    Neo4j connection manager with connection pooling.  
      
    IMPORTANT: Use this class as a singleton. Do not create multiple instances.  
    """  
      
    \_instance \= None  
      
    def \_\_new\_\_(cls, \*args, \*\*kwargs):  
        if cls.\_instance is None:  
            cls.\_instance \= super().\_\_new\_\_(cls)  
        return cls.\_instance  
      
    def \_\_init\_\_(  
        self,  
        uri: str,  
        username: str,  
        password: str,  
        database: str \= "neo4j",  
        max\_connection\_pool\_size: int \= 50,  
        connection\_acquisition\_timeout: float \= 60.0,  
    ):  
        if hasattr(self, '\_driver'):  
            return  *\# Already initialized*  
              
        self.\_driver \= AsyncGraphDatabase.driver(  
            uri,  
            auth\=(username, password),  
            max\_connection\_pool\_size\=max\_connection\_pool\_size,  
            connection\_acquisition\_timeout\=connection\_acquisition\_timeout,  
        )  
        self.\_database \= database  
      
    @asynccontextmanager  
    async def session(self) \-\> AsyncGenerator:  
        """  
        Get a session from the pool.  
        Always use as context manager to ensure proper cleanup.  
          
        Example:  
            async with client.session() as session:  
                result \= await session.run(query, params)  
        """  
        session \= self.\_driver.session(database\=self.\_database)  
        try:  
            yield session  
        finally:  
            await session.close()  
      
    @asynccontextmanager  
    async def transaction(self) \-\> AsyncGenerator:  
        """  
        Get a transaction with automatic commit/rollback.  
          
        Example:  
            async with client.transaction() as tx:  
                await tx.run(query1, params1)  
                await tx.run(query2, params2)  
                \# Auto-commits on exit, rolls back on exception  
        """  
        async with self.session() as session:  
            tx \= await session.begin\_transaction()  
            try:  
                yield tx  
                await tx.commit()  
            except Exception:  
                await tx.rollback()  
                raise  
      
    async def close(self):  
        """Close the driver. Call on application shutdown."""  
        await self.\_driver.close()  
      
    async def verify\_connectivity(self) \-\> bool:  
        """  
        Verify database connectivity.  
        Returns True if connected, raises exception otherwise.  
        """  
        await self.\_driver.verify\_connectivity()

        return True

### **6.6 Repository Pattern**

python  
from abc import ABC, abstractmethod  
from typing import TypeVar, Generic, Optional  
from uuid import UUID

T \= TypeVar('T')

class BaseRepository(ABC, Generic\[T\]):  
    """  
    Base repository providing standard CRUD operations.  
    All database access should go through repositories.  
    """  
      
    def \_\_init\_\_(self, client: Neo4jClient):  
        self.\_client \= client  
      
    @abstractmethod  
    async def create(self, entity: T) \-\> T:  
        """Create a new entity. Returns the created entity with generated ID."""  
        pass  
      
    @abstractmethod  
    async def get\_by\_id(self, id: UUID) \-\> Optional\[T\]:  
        """Retrieve entity by ID. Returns None if not found."""  
        pass  
      
    @abstractmethod  
    async def update(self, entity: T) \-\> T:  
        """Update an existing entity. Raises if not found."""  
        pass  
      
    @abstractmethod  
    async def delete(self, id: UUID) \-\> bool:  
        """Delete entity by ID. Returns True if deleted, False if not found."""  
        pass

class CapsuleRepository(BaseRepository\[Capsule\]):  
    """  
    Repository for Capsule entities.  
      
    Thread-safe: Yes  
    Transaction handling: Each method is a single transaction  
    """  
      
    async def create(self, capsule: CapsuleCreate, owner\_id: UUID) \-\> Capsule:  
        """  
        Create a new capsule with optional parent linkage.  
          
        Args:  
            capsule: The capsule data to create  
            owner\_id: UUID of the creating user  
              
        Returns:  
            The created Capsule with generated ID  
              
        Raises:  
            ValueError: If parent\_id specified but parent not found  
            ValueError: If parent is quarantined  
        """  
        query \= """  
        CREATE (c:Capsule {  
            id: randomUUID(),  
            content: $content,  
            type: $type,  
            version: '1.0.0',  
            owner\_id: $owner\_id,  
            trust\_level: $trust\_level,  
            metadata: $metadata,  
            created\_at: datetime(),  
            updated\_at: datetime()  
        })  
        RETURN c  
        """  
          
        if capsule.parent\_id:  
            query \= """  
            MATCH (parent:Capsule {id: $parent\_id})  
            WHERE parent.trust\_level \<\> 'quarantine'  
            CREATE (c:Capsule {  
                id: randomUUID(),  
                content: $content,  
                type: $type,  
                version: '1.0.0',  
                owner\_id: $owner\_id,  
                trust\_level: CASE   
                    WHEN parent.trust\_level \= 'core' THEN 'trusted'  
                    ELSE parent.trust\_level   
                END,  
                metadata: $metadata,  
                created\_at: datetime(),  
                updated\_at: datetime()  
            })  
            CREATE (c)-\[:DERIVED\_FROM {  
                reason: $reason,  
                timestamp: datetime()  
            }\]-\>(parent)  
            RETURN c  
            """  
          
        async with self.\_client.transaction() as tx:  
            result \= await tx.run(query, {  
                "content": capsule.content,  
                "type": capsule.type.value,  
                "owner\_id": str(owner\_id),  
                "trust\_level": TrustLevel.STANDARD.value,  
                "metadata": capsule.metadata,  
                "parent\_id": str(capsule.parent\_id) if capsule.parent\_id else None,  
                "reason": capsule.metadata.get("evolution\_reason", "Version update"),  
            })  
            record \= await result.single()  
              
            if record is None:  
                if capsule.parent\_id:  
                    raise ValueError(f"Parent capsule {capsule.parent\_id} not found or quarantined")  
                raise ValueError("Failed to create capsule")  
              
            return Capsule(\*\*record\["c"\])  
      
    async def get\_by\_id(self, id: UUID) \-\> Optional\[Capsule\]:  
        """Retrieve a single capsule by ID."""  
        query \= """  
        MATCH (c:Capsule {id: $id})  
        RETURN c  
        """  
        async with self.\_client.session() as session:  
            result \= await session.run(query, {"id": str(id)})  
            record \= await result.single()  
            if record is None:  
                return None  
            return Capsule(\*\*record\["c"\])  
      
    async def semantic\_search(  
        self,  
        embedding: list\[float\],  
        limit: int \= 10,  
        min\_score: float \= 0.7,  
        type\_filter: Optional\[CapsuleType\] \= None,  
        exclude\_quarantined: bool \= True,  
    ) \-\> list\[tuple\[Capsule, float\]\]:  
        """  
        Search for semantically similar capsules.  
          
        Args:  
            embedding: Query embedding vector  
            limit: Maximum results to return (1-100)  
            min\_score: Minimum similarity score (0.0-1.0)  
            type\_filter: Optional filter by capsule type  
            exclude\_quarantined: Whether to exclude quarantined capsules  
              
        Returns:  
            List of (Capsule, score) tuples ordered by score descending  
        """  
        if not 1 \<= limit \<= 100:  
            raise ValueError("limit must be between 1 and 100")  
        if not 0.0 \<= min\_score \<= 1.0:  
            raise ValueError("min\_score must be between 0.0 and 1.0")  
          
        query \= """  
        CALL db.index.vector.queryNodes('capsule\_embedding\_index', $limit, $embedding)  
        YIELD node, score  
        WHERE score \>= $min\_score  
        """  
          
        if exclude\_quarantined:  
            query \+= " AND node.trust\_level \<\> 'quarantine'"  
        if type\_filter:  
            query \+= " AND node.type \= $type\_filter"  
          
        query \+= " RETURN node, score ORDER BY score DESC"  
          
        async with self.\_client.session() as session:  
            result \= await session.run(query, {  
                "embedding": embedding,  
                "limit": limit,  
                "min\_score": min\_score,  
                "type\_filter": type\_filter.value if type\_filter else None,  
            })  
            records \= await result.fetch\_all()  
            return \[(Capsule(\*\*r\["node"\]), r\["score"\]) for r in records\]  
      
    async def get\_lineage(self, id: UUID, max\_depth: int \= 10) \-\> list\[Capsule\]:  
        """  
        Trace the complete ancestry of a capsule.  
          
        Args:  
            id: The capsule ID to trace from  
            max\_depth: Maximum ancestry depth to traverse  
              
        Returns:  
            List of ancestor capsules ordered from parent to oldest ancestor  
        """  
        if not 1 \<= max\_depth \<= 100:  
            raise ValueError("max\_depth must be between 1 and 100")  
          
        query \= """  
        MATCH path \= (c:Capsule {id: $id})-\[:DERIVED\_FROM\*1..$max\_depth\]-\>(ancestor:Capsule)  
        RETURN ancestor  
        ORDER BY length(path)  
        """  
          
        async with self.\_client.session() as session:  
            result \= await session.run(query, {  
                "id": str(id),  
                "max\_depth": max\_depth,  
            })  
            records \= await result.fetch\_all()

            return \[Capsule(\*\*r\["ancestor"\]) for r in records\]

---

## **7\. Seven-Phase Processing Pipeline**

### **7.1 Pipeline Overview**

Every operation in Forge flows through a seven-phase pipeline that ensures consistent context gathering, security validation, and intelligent processing. Version 3 parallelizes independent phases for performance while maintaining correctness.

┌─────────────────────────────────────────────────────────────────────────────┐  
│                    SEVEN-PHASE PIPELINE ARCHITECTURE                         │  
└─────────────────────────────────────────────────────────────────────────────┘

Request ──────┬─────────────────────────────────────────────────────▶ Response  
              │                                                           ▲  
              ▼                                                           │  
┌─────────────────────────────────────────────────────────────────────────┐  
│ PHASE GROUP 1: PARALLEL GATHERING (asyncio.gather)                      │  
│                                                                         │  
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐        │  
│  │ Phase 1: Context │ │ Phase 2: Analysis│ │ Phase 3: Security│        │  
│  │                  │ │                  │ │                  │        │  
│  │ • Semantic search│ │ • ML patterns    │ │ • Trust check    │        │  
│  │ • Lineage query  │ │ • Anomaly detect │ │ • Rate limit     │        │  
│  │ • Related caps   │ │ • Classify intent│ │ • Auth verify    │        │  
│  │                  │ │                  │ │                  │        │  
│  │ \~200ms           │ │ \~300ms           │ │ \~100ms           │        │  
│  └──────────────────┘ └──────────────────┘ └──────────────────┘        │  
│                                                                         │  
│  Total: max(200, 300, 100\) \= \~300ms                                    │  
└─────────────────────────────────────────────────────────────────────────┘  
                              │  
                              ▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ PHASE GROUP 2: SEQUENTIAL PROCESSING                                    │  
│                                                                         │  
│  ┌──────────────────────────────────────────────────────────────────┐  │  
│  │ Phase 4: Optimization                                             │  │  
│  │ • Cache check (skip Phase 5 if hit)                               │  │  
│  │ • Resource allocation                                             │  │  
│  │ • Context window packing                                          │  │  
│  │ \~20ms                                                             │  │  
│  └──────────────────────────────────────────────────────────────────┘  │  
│                              │                                          │  
│                              ▼                                          │  
│  ┌──────────────────────────────────────────────────────────────────┐  │  
│  │ Phase 5: Intelligence                                             │  │  
│  │ • Primary LLM call                                                │  │  
│  │ • Context injection                                               │  │  
│  │ • Response generation                                             │  │  
│  │ \~800-2000ms (bottleneck)                                         │  │  
│  └──────────────────────────────────────────────────────────────────┘  │  
│                                                                         │  
│  Total: \~820-2020ms                                                    │  
└─────────────────────────────────────────────────────────────────────────┘  
                              │  
                              ├──────────────────────────────────▶ Response  
                              │  
                              ▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ PHASE GROUP 3: FIRE-AND-FORGET (asyncio.create\_task)                    │  
│                                                                         │  
│  ┌──────────────────┐ ┌──────────────────┐                             │  
│  │ Phase 6: Metrics │ │ Phase 7: Storage │                             │  
│  │                  │ │                  │                             │  
│  │ • Latency record │ │ • Capsule create │                             │  
│  │ • Token count    │ │ • Event publish  │                             │  
│  │ • Cost tracking  │ │ • Audit log      │                             │  
│  │                  │ │                  │                             │  
│  │ \~10ms            │ │ \~400ms           │                             │  
│  └──────────────────┘ └──────────────────┘                             │  
│                                                                         │  
│  Does not block response                                                │  
└─────────────────────────────────────────────────────────────────────────┘

TOTAL LATENCY: \~1.1-2.3s (vs 3.6s sequential \= 1.6-3.3x improvement)

### **7.2 Phase Specifications**

#### **Phase 1: Context Gathering**

Phase 1 retrieves relevant context for the current operation through semantic search and lineage queries.

python  
class Phase1Context:  
    """  
    Context gathering phase.  
      
    Responsibilities:  
    \- Semantic search for similar capsules  
    \- Retrieve lineage of referenced capsules  
    \- Gather user's recent capsules  
      
    Outputs:  
    \- similar\_capsules: List of semantically related capsules  
    \- lineage\_context: Ancestry of any referenced capsules  
    \- user\_context: Recent capsules from the same user  
    """  
      
    async def execute(self, ctx: PipelineContext) \-\> Phase1Result:  
        """  
        Execute context gathering.  
          
        Args:  
            ctx: Pipeline context containing request data  
              
        Returns:  
            Phase1Result with gathered context  
              
        Timeout: 500ms (fails open with empty context)  
        """  
        async with asyncio.timeout(0.5):  
            try:  
                similar, lineage, user \= await asyncio.gather(  
                    self.\_semantic\_search(ctx),  
                    self.\_get\_lineage(ctx),  
                    self.\_get\_user\_context(ctx),  
                    return\_exceptions\=True  
                )  
                  
                return Phase1Result(  
                    similar\_capsules\=similar if not isinstance(similar, Exception) else \[\],  
                    lineage\_context\=lineage if not isinstance(lineage, Exception) else \[\],  
                    user\_context\=user if not isinstance(user, Exception) else \[\],  
                )  
            except asyncio.TimeoutError:  
                *\# Fail open: return empty context rather than block*  
                return Phase1Result(  
                    similar\_capsules\=\[\],  
                    lineage\_context\=\[\],  
                    user\_context\=\[\],  
                    timed\_out\=True,

                )

#### **Phase 2: Analysis**

Phase 2 applies machine learning analysis to understand the request.

python  
class Phase2Analysis:  
    """  
    ML analysis phase.  
      
    Responsibilities:  
    \- Anomaly detection on request patterns  
    \- Intent classification  
    \- Content categorization  
    \- Sentiment analysis (for feedback)  
      
    Outputs:  
    \- anomaly\_score: 0.0-1.0, higher \= more anomalous  
    \- intent: Classified intent of the request  
    \- categories: Suggested capsule categories  
    \- sentiment: Positive/negative/neutral  
    """  
      
    async def execute(self, ctx: PipelineContext) \-\> Phase2Result:  
        """  
        Execute ML analysis.  
          
        Args:  
            ctx: Pipeline context  
              
        Returns:  
            Phase2Result with analysis outputs  
              
        Timeout: 800ms (fails open with neutral defaults)  
        """  
        async with asyncio.timeout(0.8):  
            try:  
                *\# Invoke ml\_intelligence overlay via WebAssembly*  
                ml\_result \= await self.\_overlay\_runtime.invoke(  
                    overlay\_id\="ml\_intelligence",  
                    function\="analyze",  
                    args\={  
                        "content": ctx.request.content,  
                        "user\_history": ctx.user\_history\_embedding,  
                    }  
                )  
                  
                return Phase2Result(  
                    anomaly\_score\=ml\_result.get("anomaly\_score", 0.0),  
                    intent\=ml\_result.get("intent", "unknown"),  
                    categories\=ml\_result.get("categories", \[\]),  
                    sentiment\=ml\_result.get("sentiment", "neutral"),  
                )  
            except asyncio.TimeoutError:

                return Phase2Result.default()

#### **Phase 3: Security**

Phase 3 validates security constraints before processing.

python  
class Phase3Security:  
    """  
    Security validation phase.  
      
    Responsibilities:  
    \- Verify user trust level  
    \- Check rate limits  
    \- Validate operation permissions  
    \- Detect potential threats  
      
    Outputs:  
    \- authorized: Boolean, whether to proceed  
    \- denial\_reason: If not authorized, why  
    \- elevated\_monitoring: Whether to increase logging  
    """  
      
    async def execute(self, ctx: PipelineContext) \-\> Phase3Result:  
        """  
        Execute security validation.  
          
        Args:  
            ctx: Pipeline context  
              
        Returns:  
            Phase3Result with authorization decision  
              
        Raises:  
            SecurityException: If request is definitively blocked  
              
        IMPORTANT: This phase must NOT fail open. Timeouts should deny.  
        """  
        async with asyncio.timeout(0.3):  
            try:  
                *\# Check trust level*  
                if ctx.user.trust\_level \== TrustLevel.QUARANTINE:  
                    return Phase3Result(  
                        authorized\=False,  
                        denial\_reason\="User is quarantined",  
                        elevated\_monitoring\=True,  
                    )  
                  
                *\# Check rate limits*  
                rate\_ok \= await self.\_rate\_limiter.check(  
                    key\=f"user:{ctx.user.id}",  
                    limit\=ctx.user.rate\_limit,  
                    window\_seconds\=60,  
                )  
                if not rate\_ok:  
                    return Phase3Result(  
                        authorized\=False,  
                        denial\_reason\="Rate limit exceeded",  
                        elevated\_monitoring\=False,  
                    )  
                  
                *\# Invoke security\_validator overlay*  
                security\_result \= await self.\_overlay\_runtime.invoke(  
                    overlay\_id\="security\_validator",  
                    function\="validate",  
                    args\={  
                        "user": ctx.user.model\_dump(),  
                        "operation": ctx.operation,  
                        "resource": ctx.resource\_id,  
                    }  
                )  
                  
                return Phase3Result(  
                    authorized\=security\_result.get("authorized", False),  
                    denial\_reason\=security\_result.get("reason"),  
                    elevated\_monitoring\=security\_result.get("elevated", False),  
                )  
                  
            except asyncio.TimeoutError:  
                *\# Security timeouts must deny*  
                return Phase3Result(  
                    authorized\=False,  
                    denial\_reason\="Security validation timeout",  
                    elevated\_monitoring\=True,

                )

#### **Phase 4: Optimization**

Phase 4 optimizes resource usage based on gathered information.

python  
class Phase4Optimization:  
    """  
    Optimization phase.  
      
    Responsibilities:  
    \- Check cache for existing results  
    \- Allocate LLM resources based on complexity  
    \- Pack context window efficiently  
    \- Determine model selection  
      
    Outputs:  
    \- cache\_hit: Boolean, whether to skip Phase 5  
    \- cached\_response: If cache hit, the response  
    \- model: Selected model for Phase 5  
    \- context\_budget: Token budget for context  
    """  
      
    async def execute(  
        self,  
        ctx: PipelineContext,  
        phase1: Phase1Result,  
        phase2: Phase2Result,  
        phase3: Phase3Result,  
    ) \-\> Phase4Result:  
        """  
        Execute optimization.  
          
        Args:  
            ctx: Pipeline context  
            phase1: Results from context gathering  
            phase2: Results from ML analysis  
            phase3: Results from security validation  
              
        Returns:  
            Phase4Result with optimization decisions  
        """  
        *\# Check cache*  
        cache\_key \= self.\_compute\_cache\_key(ctx, phase1)  
        cached \= await self.\_cache.get(cache\_key)  
        if cached:  
            return Phase4Result(  
                cache\_hit\=True,  
                cached\_response\=cached,  
            )  
          
        *\# Select model based on complexity*  
        model \= self.\_select\_model(phase2.intent, len(phase1.similar\_capsules))  
          
        *\# Compute context budget*  
        context\_budget \= self.\_compute\_budget(  
            model\=model,  
            similar\_count\=len(phase1.similar\_capsules),  
            lineage\_depth\=len(phase1.lineage\_context),  
        )  
          
        *\# Pack context efficiently*  
        packed\_context \= self.\_pack\_context(  
            similar\=phase1.similar\_capsules,  
            lineage\=phase1.lineage\_context,  
            budget\=context\_budget,  
        )  
          
        return Phase4Result(  
            cache\_hit\=False,  
            model\=model,  
            context\_budget\=context\_budget,  
            packed\_context\=packed\_context,

        )

#### **Phase 5: Intelligence**

Phase 5 makes the primary LLM call with optimized context.

python  
class Phase5Intelligence:  
    """  
    Intelligence phase \- primary LLM interaction.  
      
    Responsibilities:  
    \- Construct prompt with context  
    \- Call LLM with appropriate parameters  
    \- Parse and validate response  
    \- Extract new insights for storage  
      
    Outputs:  
    \- response: The LLM response  
    \- insights: Extracted insights to store as capsules  
    \- tokens\_used: Token count for billing  
    """  
      
    async def execute(  
        self,  
        ctx: PipelineContext,  
        phase4: Phase4Result,  
    ) \-\> Phase5Result:  
        """  
        Execute LLM call.  
          
        Args:  
            ctx: Pipeline context  
            phase4: Optimization results  
              
        Returns:  
            Phase5Result with LLM response  
              
        Timeout: 30s (user-facing timeout)  
        """  
        if phase4.cache\_hit:  
            return Phase5Result(  
                response\=phase4.cached\_response,  
                from\_cache\=True,  
                tokens\_used\=0,  
            )  
          
        *\# Construct prompt*  
        prompt \= self.\_construct\_prompt(  
            user\_input\=ctx.request.content,  
            context\=phase4.packed\_context,  
            system\_instructions\=self.\_get\_system\_prompt(ctx.operation),  
        )  
          
        async with asyncio.timeout(30.0):  
            *\# Call LLM*  
            llm\_response \= await self.\_llm\_client.complete(  
                model\=phase4.model,  
                messages\=prompt,  
                max\_tokens\=ctx.max\_response\_tokens,  
                temperature\=0.7,  
            )  
              
            *\# Extract insights for storage*  
            insights \= self.\_extract\_insights(llm\_response)  
              
            return Phase5Result(  
                response\=llm\_response.content,  
                insights\=insights,  
                tokens\_used\=llm\_response.usage.total\_tokens,  
                model\=phase4.model,

            )

#### **Phase 6: Metrics**

Phase 6 records metrics asynchronously without blocking response.

python  
class Phase6Metrics:  
    """  
    Metrics recording phase (fire-and-forget).  
      
    Responsibilities:  
    \- Record latency metrics  
    \- Track token usage  
    \- Update cost accounting  
    \- Publish telemetry events  
      
    This phase runs as fire-and-forget and does not block response.  
    """  
      
    async def execute(  
        self,  
        ctx: PipelineContext,  
        phase5: Phase5Result,  
        total\_latency\_ms: float,  
    ) \-\> None:  
        """  
        Record metrics.  
          
        Args:  
            ctx: Pipeline context  
            phase5: Intelligence results  
            total\_latency\_ms: Total pipeline latency  
              
        Returns:  
            None (fire-and-forget)  
              
        Error handling: Log and continue, never raise  
        """  
        try:  
            *\# Record to Prometheus*  
            self.\_metrics.pipeline\_latency.observe(total\_latency\_ms / 1000)  
            self.\_metrics.tokens\_used.inc(phase5.tokens\_used)  
            self.\_metrics.operations\_total.inc()  
              
            *\# Record to event store*  
            await self.\_event\_store.append(MetricsEvent(  
                operation\_id\=ctx.operation\_id,  
                user\_id\=ctx.user.id,  
                latency\_ms\=total\_latency\_ms,  
                tokens\_used\=phase5.tokens\_used,  
                model\=phase5.model,  
                cache\_hit\=phase5.from\_cache,  
            ))  
              
        except Exception as e:  
            *\# Never let metrics recording fail the pipeline*

            logger.error(f"Metrics recording failed: {e}", exc\_info\=True)

#### **Phase 7: Storage**

Phase 7 persists results and publishes events asynchronously.

python  
class Phase7Storage:  
    """  
    Storage phase (fire-and-forget).  
      
    Responsibilities:  
    \- Create capsules for extracted insights  
    \- Update cache for future requests  
    \- Publish completion events  
    \- Write audit log  
      
    This phase runs as fire-and-forget and does not block response.  
    """  
      
    async def execute(  
        self,  
        ctx: PipelineContext,  
        phase5: Phase5Result,  
    ) \-\> None:  
        """  
        Persist results.  
          
        Args:  
            ctx: Pipeline context  
            phase5: Intelligence results  
              
        Returns:  
            None (fire-and-forget)  
              
        Error handling: Log and retry once, then continue  
        """  
        try:  
            *\# Store extracted insights as capsules*  
            for insight in phase5.insights:  
                await self.\_capsule\_repo.create(  
                    CapsuleCreate(  
                        content\=insight.content,  
                        type\=CapsuleType.INSIGHT,  
                        metadata\={  
                            "source\_operation": ctx.operation\_id,  
                            "confidence": insight.confidence,  
                        },  
                    ),  
                    owner\_id\=ctx.user.id,  
                )  
              
            *\# Update cache*  
            if not phase5.from\_cache:  
                cache\_key \= self.\_compute\_cache\_key(ctx)  
                await self.\_cache.set(  
                    key\=cache\_key,  
                    value\=phase5.response,  
                    ttl\_seconds\=3600,  *\# 1 hour cache*  
                )  
              
            *\# Publish completion event*  
            await self.\_event\_bus.publish(OperationCompletedEvent(  
                operation\_id\=ctx.operation\_id,  
                user\_id\=ctx.user.id,  
                success\=True,  
            ))  
              
            *\# Write audit log*  
            await self.\_audit\_log.write(AuditEntry(  
                timestamp\=datetime.now(timezone.utc),  
                action\=ctx.operation,  
                actor\_id\=ctx.user.id,  
                resource\_id\=ctx.resource\_id,  
                success\=True,  
            ))  
              
        except Exception as e:  
            logger.error(f"Storage phase failed: {e}", exc\_info\=True)  
            *\# Attempt retry once*  
            try:  
                await self.\_retry\_storage(ctx, phase5)  
            except Exception:

                logger.error("Storage retry also failed", exc\_info\=True)

### **7.3 Pipeline Orchestrator**

python  
class PipelineOrchestrator:  
    """  
    Orchestrates the seven-phase pipeline.  
      
    Thread-safe: Yes  
    Concurrency: Handles multiple concurrent pipelines  
    Error handling: Per-phase isolation with graceful degradation  
    """  
      
    def \_\_init\_\_(  
        self,  
        phase1: Phase1Context,  
        phase2: Phase2Analysis,  
        phase3: Phase3Security,  
        phase4: Phase4Optimization,  
        phase5: Phase5Intelligence,  
        phase6: Phase6Metrics,  
        phase7: Phase7Storage,  
    ):  
        self.\_phase1 \= phase1  
        self.\_phase2 \= phase2  
        self.\_phase3 \= phase3  
        self.\_phase4 \= phase4  
        self.\_phase5 \= phase5  
        self.\_phase6 \= phase6  
        self.\_phase7 \= phase7  
      
    async def execute(self, request: PipelineRequest) \-\> PipelineResponse:  
        """  
        Execute the full pipeline.  
          
        Args:  
            request: The incoming request  
              
        Returns:  
            PipelineResponse with results  
              
        Raises:  
            SecurityException: If security validation fails  
            PipelineException: If unrecoverable error occurs  
        """  
        start\_time \= time.perf\_counter()  
        ctx \= PipelineContext(request\=request)  
          
        *\# Phase Group 1: Parallel gathering*  
        phase1\_result, phase2\_result, phase3\_result \= await asyncio.gather(  
            self.\_phase1.execute(ctx),  
            self.\_phase2.execute(ctx),  
            self.\_phase3.execute(ctx),  
        )  
          
        *\# Check security result*  
        if not phase3\_result.authorized:  
            raise SecurityException(phase3\_result.denial\_reason)  
          
        *\# Phase Group 2: Sequential processing*  
        phase4\_result \= await self.\_phase4.execute(  
            ctx, phase1\_result, phase2\_result, phase3\_result  
        )  
        phase5\_result \= await self.\_phase5.execute(ctx, phase4\_result)  
          
        *\# Calculate latency before fire-and-forget*  
        total\_latency\_ms \= (time.perf\_counter() \- start\_time) \* 1000  
          
        *\# Phase Group 3: Fire-and-forget*  
        asyncio.create\_task(  
            self.\_phase6.execute(ctx, phase5\_result, total\_latency\_ms)  
        )  
        asyncio.create\_task(  
            self.\_phase7.execute(ctx, phase5\_result)  
        )  
          
        return PipelineResponse(  
            content\=phase5\_result.response,  
            operation\_id\=ctx.operation\_id,  
            latency\_ms\=total\_latency\_ms,

        )

---

## **8\. WebAssembly Overlay Runtime**

### **8.1 Design Rationale**

Version 1 overlays ran as Python modules with resource limits enforced through RLIMIT\_AS. This approach had critical limitations.

**Security Vulnerabilities.** Python's introspection capabilities allow malicious code to inspect the runtime environment, potentially accessing sensitive data or escaping the sandbox. C-extensions can bypass memory limits entirely.

**Unreliable Termination.** When the Immune System needs to terminate a misbehaving overlay, Python processes may ignore SIGTERM, hang during cleanup, or leak resources. Clean termination is not guaranteed.

**Imprecise Resource Control.** RLIMIT\_AS limits total address space, not actual memory usage. An overlay could allocate virtual memory far exceeding limits without triggering enforcement.

WebAssembly solves these problems through architectural guarantees.

**Memory Safety by Design.** WebAssembly's linear memory model prevents accessing memory outside the allocated sandbox. There is no pointer arithmetic escape, no buffer overflow exploitation, and no access to host memory.

**Instant Termination.** Dropping a WebAssembly instance immediately frees all associated memory. There is no cleanup code to run, no signals to send, and no race conditions.

**Precise Metering.** Wasmtime's fuel mechanism counts actual instructions executed, providing precise CPU limiting independent of wall-clock time.

**Capability Security.** Host functions are explicitly linked at instantiation time. If an overlay doesn't declare NETWORK\_ACCESS, the network functions simply don't exist in its environment.

### **8.2 Runtime Architecture**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                     WEBASSEMBLY OVERLAY RUNTIME                              │  
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐  
│ OVERLAY MANAGER                                                             │  
│                                                                             │  
│  ┌──────────────────────────────────────────────────────────────────────┐  │  
│  │ Registry: overlay\_id → OverlayEntry                                  │  │  
│  │                                                                       │  │  
│  │ OverlayEntry {                                                       │  │  
│  │   manifest: OverlayManifest                                          │  │  
│  │   wasm\_module: wasmtime.Module (compiled, cached)                    │  │  
│  │   instance\_pool: list\[WasmInstance\]                                  │  │  
│  │   metrics: OverlayMetrics                                            │  │  
│  │   circuit\_breaker: CircuitBreaker                                    │  │  
│  │ }                                                                    │  │  
│  └──────────────────────────────────────────────────────────────────────┘  │  
│                                                                             │  
│  ┌──────────────────────────────────────────────────────────────────────┐  │  
│  │ Dependency Graph: overlay\_id → set\[overlay\_id\]                       │  │  
│  │                                                                       │  │  
│  │ Ensures dependencies are loaded before dependents                    │  │  
│  │ Detects circular dependencies at registration time                   │  │  
│  └──────────────────────────────────────────────────────────────────────┘  │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ WASMTIME ENGINE                                                             │  
│                                                                             │  
│  ┌────────────────────────────────────────────────────────────────────┐    │  
│  │ Engine Configuration                                                │    │  
│  │                                                                     │    │  
│  │ • Fuel metering: enabled                                           │    │  
│  │ • Epoch interruption: enabled                                      │    │  
│  │ • Reference types: enabled (for complex data)                      │    │  
│  │ • SIMD: disabled (security)                                        │    │  
│  │ • Threads: disabled (security)                                     │    │  
│  └────────────────────────────────────────────────────────────────────┘    │  
│                                                                             │  
│  ┌────────────────────────────────────────────────────────────────────┐    │  
│  │ Host Functions (linked per-capability)                              │    │  
│  │                                                                     │    │  
│  │ DATABASE\_READ:                                                      │    │  
│  │   • db\_query(query: string, params: bytes) → bytes                 │    │  
│  │                                                                     │    │  
│  │ DATABASE\_WRITE:                                                     │    │  
│  │   • db\_execute(query: string, params: bytes) → i32                 │    │  
│  │                                                                     │    │  
│  │ EVENT\_PUBLISH:                                                      │    │  
│  │   • event\_publish(topic: string, payload: bytes) → i32             │    │  
│  │                                                                     │    │  
│  │ EVENT\_SUBSCRIBE:                                                    │    │  
│  │   • event\_subscribe(topic: string, callback: i32) → i32            │    │  
│  │                                                                     │    │  
│  │ NETWORK\_OUTBOUND:                                                   │    │  
│  │   • http\_request(url: string, method: string, body: bytes) → bytes │    │  
│  │                                                                     │    │  
│  │ CAPSULE\_CREATE:                                                     │    │  
│  │   • capsule\_create(data: bytes) → bytes                            │    │  
│  └────────────────────────────────────────────────────────────────────┘    │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ INSTANCE SANDBOXES                                                          │  
│                                                                             │  
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │  
│  │ governance      │  │ security        │  │ ml\_intelligence │   ...       │  
│  │ instance        │  │ instance        │  │ instance        │             │  
│  │                 │  │                 │  │                 │             │  
│  │ Memory: 256MB   │  │ Memory: 128MB   │  │ Memory: 512MB   │             │  
│  │ Fuel: 10M/call  │  │ Fuel: 5M/call   │  │ Fuel: 20M/call  │             │  
│  │ Capabilities:   │  │ Capabilities:   │  │ Capabilities:   │             │  
│  │  • DB\_READ      │  │  • DB\_READ      │  │  • DB\_READ      │             │  
│  │  • DB\_WRITE     │  │  • EVENT\_\*      │  │  • EVENT\_PUB    │             │  
│  │  • EVENT\_\*      │  │                 │  │                 │             │  
│  │  • GOVERNANCE\_\* │  │                 │  │                 │             │  
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │  
│                                                                             │  
│  Each instance is fully isolated. Memory, fuel, and capabilities            │  
│  are independent. One instance cannot affect another.                       │

└─────────────────────────────────────────────────────────────────────────────┘

### **8.3 Overlay Compilation**

Overlays are written in Python and compiled to WebAssembly using a Python-to-Wasm toolchain.

python  
class OverlayCompiler:  
    """  
    Compiles Python overlays to WebAssembly.  
      
    Supported toolchains:  
    \- Nuitka \+ Emscripten: Best performance, full Python support  
    \- Pyodide: Easier setup, CPython compatible  
    \- RustPython \+ wasm32: Experimental, best security  
    """  
      
    async def compile(  
        self,  
        source\_path: Path,  
        manifest: OverlayManifest,  
    ) \-\> CompilationResult:  
        """  
        Compile Python source to WebAssembly.  
          
        Args:  
            source\_path: Path to overlay Python source  
            manifest: Overlay manifest with metadata  
              
        Returns:  
            CompilationResult containing wasm binary and hashes  
              
        Raises:  
            CompilationError: If compilation fails  
        """  
        *\# Validate source*  
        source\_hash \= self.\_hash\_source(source\_path)  
        self.\_validate\_source(source\_path, manifest.capabilities)  
          
        *\# Compile to WebAssembly*  
        wasm\_binary \= await self.\_compile\_with\_nuitka(source\_path)  
        wasm\_hash \= f"sha256:{hashlib.sha256(wasm\_binary).hexdigest()}"  
          
        *\# Optimize*  
        optimized \= await self.\_optimize\_wasm(wasm\_binary)  
          
        return CompilationResult(  
            wasm\_binary\=optimized,  
            wasm\_hash\=wasm\_hash,  
            source\_hash\=source\_hash,  
            size\_bytes\=len(optimized),  
        )  
      
    def \_validate\_source(  
        self,  
        source\_path: Path,  
        allowed\_capabilities: list\[OverlayCapability\],  
    ) \-\> None:  
        """  
        Static analysis to detect capability violations.  
          
        Checks for:  
        \- Import of disallowed modules (socket, subprocess, os.system)  
        \- Use of eval/exec  
        \- File system access without FILESYSTEM\_\* capability  
        """  
        import ast  
          
        source \= source\_path.read\_text()  
        tree \= ast.parse(source)  
          
        disallowed\_modules \= {"subprocess", "os", "sys", "ctypes", "multiprocessing"}  
          
        for node in ast.walk(tree):  
            if isinstance(node, ast.Import):  
                for alias in node.names:  
                    if alias.name.split('.')\[0\] in disallowed\_modules:  
                        raise CompilationError(  
                            f"Disallowed import: {alias.name}"  
                        )  
              
            if isinstance(node, ast.Call):  
                if isinstance(node.func, ast.Name):  
                    if node.func.id in ("eval", "exec", "compile"):  
                        raise CompilationError(  
                            f"Disallowed function: {node.func.id}"

                        )

### **8.4 Runtime Invocation**

python  
class WasmRuntime:  
    """  
    WebAssembly runtime for overlay execution.  
      
    Thread-safe: Yes (each invocation gets its own instance)  
    Resource limits: Enforced via Wasmtime fuel metering  
    """  
      
    def \_\_init\_\_(self):  
        *\# Configure engine with security settings*  
        config \= wasmtime.Config()  
        config.consume\_fuel \= True  
        config.epoch\_interruption \= True  
        config.wasm\_reference\_types \= True  
        config.wasm\_simd \= False  *\# Security: disable SIMD*  
        config.wasm\_threads \= False  *\# Security: disable threads*  
          
        self.\_engine \= wasmtime.Engine(config)  
        self.\_linker \= wasmtime.Linker(self.\_engine)  
        self.\_instances: dict\[str, OverlayInstance\] \= {}  
      
    async def invoke(  
        self,  
        overlay\_id: str,  
        function: str,  
        args: dict,  
        timeout\_ms: int \= 5000,  
    ) \-\> dict:  
        """  
        Invoke a function on an overlay.  
          
        Args:  
            overlay\_id: ID of the overlay to invoke  
            function: Name of the function to call  
            args: Arguments to pass (will be serialized to JSON)  
            timeout\_ms: Maximum execution time  
              
        Returns:  
            Function result as dictionary  
              
        Raises:  
            OverlayNotFoundError: If overlay not registered  
            OverlayQuarantinedError: If overlay is quarantined  
            OverlayTimeoutError: If execution exceeds timeout  
            OverlayFuelExhaustedError: If fuel limit reached  
        """  
        instance \= self.\_get\_instance(overlay\_id)  
          
        if instance.state \== OverlayState.QUARANTINED:  
            raise OverlayQuarantinedError(overlay\_id)  
          
        *\# Serialize arguments*  
        args\_bytes \= json.dumps(args).encode('utf-8')  
          
        *\# Set fuel limit*  
        store \= instance.store  
        store.set\_fuel(instance.fuel\_limit)  
          
        *\# Set epoch deadline for timeout*  
        deadline \= time.monotonic() \+ (timeout\_ms / 1000)  
          
        try:  
            *\# Call the function*  
            result\_ptr \= instance.exports\[function\](  
                store,  
                args\_bytes,  
                len(args\_bytes),  
            )  
              
            *\# Read result from linear memory*  
            result\_bytes \= self.\_read\_result(instance, result\_ptr)  
            return json.loads(result\_bytes)  
              
        except wasmtime.Trap as e:  
            if "out of fuel" in str(e):  
                raise OverlayFuelExhaustedError(overlay\_id)  
            raise OverlayExecutionError(overlay\_id, str(e))  
      
    def terminate(self, overlay\_id: str) \-\> None:  
        """  
        Immediately terminate an overlay instance.  
          
        This is instant and guaranteed to succeed.  
        All resources are freed immediately.  
        """  
        if overlay\_id in self.\_instances:  
            *\# Simply delete the instance*  
            *\# Wasmtime frees all memory immediately*

            del self.\_instances\[overlay\_id\]

### **8.5 Host Function Implementation**

python  
class HostFunctions:  
    """  
    Host functions exposed to WebAssembly overlays.  
      
    Functions are linked based on declared capabilities.  
    Undeclared capabilities have their functions unavailable.  
    """  
      
    def \_\_init\_\_(  
        self,  
        neo4j\_client: Neo4jClient,  
        event\_bus: EventBus,  
        http\_client: httpx.AsyncClient,  
    ):  
        self.\_neo4j \= neo4j\_client  
        self.\_event\_bus \= event\_bus  
        self.\_http \= http\_client  
      
    def link\_for\_capabilities(  
        self,  
        linker: wasmtime.Linker,  
        capabilities: list\[OverlayCapability\],  
    ) \-\> None:  
        """  
        Link host functions for the given capabilities.  
          
        Only functions for declared capabilities are linked.  
        Attempting to call unlinked functions will trap.  
        """  
        if OverlayCapability.DATABASE\_READ in capabilities:  
            linker.define\_func(  
                "forge", "db\_query",  
                wasmtime.FuncType(  
                    \[wasmtime.ValType.i32(), wasmtime.ValType.i32()\],  
                    \[wasmtime.ValType.i32()\]  
                ),  
                self.\_db\_query  
            )  
          
        if OverlayCapability.DATABASE\_WRITE in capabilities:  
            linker.define\_func(  
                "forge", "db\_execute",  
                wasmtime.FuncType(  
                    \[wasmtime.ValType.i32(), wasmtime.ValType.i32()\],  
                    \[wasmtime.ValType.i32()\]  
                ),  
                self.\_db\_execute  
            )  
          
        if OverlayCapability.EVENT\_PUBLISH in capabilities:  
            linker.define\_func(  
                "forge", "event\_publish",  
                wasmtime.FuncType(  
                    \[wasmtime.ValType.i32(), wasmtime.ValType.i32(),  
                     wasmtime.ValType.i32(), wasmtime.ValType.i32()\],  
                    \[wasmtime.ValType.i32()\]  
                ),  
                self.\_event\_publish  
            )  
          
        if OverlayCapability.NETWORK\_OUTBOUND in capabilities:  
            linker.define\_func(  
                "forge", "http\_request",  
                wasmtime.FuncType(  
                    \[wasmtime.ValType.i32()\] \* 6,  
                    \[wasmtime.ValType.i32()\]  
                ),  
                self.\_http\_request  
            )  
      
    def \_db\_query(  
        self,  
        caller: wasmtime.Caller,  
        query\_ptr: int,  
        query\_len: int,  
    ) \-\> int:  
        """  
        Execute a read-only database query.  
          
        The query must be a valid Cypher read query.  
        Write queries will be rejected.  
        """  
        memory \= caller.get("memory")  
        query \= memory.read(query\_ptr, query\_len).decode('utf-8')  
          
        *\# Validate read-only*  
        if not self.\_is\_read\_only\_query(query):  
            return self.\_write\_error(caller, "Query must be read-only")  
          
        *\# Execute query*  
        result \= asyncio.run(self.\_neo4j.query(query))  
          
        *\# Write result to linear memory*  
        result\_bytes \= json.dumps(result).encode('utf-8')  
        return self.\_write\_result(caller, result\_bytes)  
      
    def \_is\_read\_only\_query(self, query: str) \-\> bool:  
        """Validate that a Cypher query is read-only."""  
        write\_keywords \= {'CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP'}  
        query\_upper \= query.upper()

        return not any(kw in query\_upper for kw in write\_keywords)

---

## **9\. Immune System Architecture**

### **9.1 Design Principles**

The Immune System provides self-healing capabilities that detect problems, quarantine faulty components, and recover automatically. The design addresses a critical risk identified in the feasibility study: autoimmune failures where the system incorrectly quarantines healthy components.

The architecture follows four principles.

**Defense in Depth.** Multiple detection layers ensure that a single false positive cannot trigger quarantine. Four independent health checks must all fail before quarantine.

**Gradual Escalation.** Responses start with warnings, escalate to throttling, then to isolation, and only finally to quarantine. Each step provides opportunity for recovery.

**Canary Deployments.** Updates are validated with a small percentage of traffic before full rollout. Failures trigger automatic rollback without human intervention.

**Transparent Operation.** All Immune System decisions are logged with full reasoning. Administrators can review and override decisions.

### **9.2 Health Check Hierarchy**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                      FOUR-LEVEL HEALTH CHECK HIERARCHY                       │  
└─────────────────────────────────────────────────────────────────────────────┘

Level 1: SELF-CHECK  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ Each overlay implements health\_check() returning HealthStatus               │  
│                                                                             │  
│ Checks:                                                                     │  
│ • Internal state consistency                                                │  
│ • Resource usage within limits                                              │  
│ • No pending errors                                                         │  
│                                                                             │  
│ Failure mode: Overlay reports its own problems                              │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
Level 2: DEPENDENCY CHECK  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ Verify all declared dependencies are healthy                                │  
│                                                                             │  
│ Checks:                                                                     │  
│ • All dependencies registered and active                                    │  
│ • No circular dependency failures                                           │  
│ • Dependency circuit breakers closed                                        │  
│                                                                             │  
│ Failure mode: Upstream problems propagate accurately                        │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
Level 3: CIRCUIT BREAKER STATE  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ Per-overlay circuit breaker state                                           │  
│                                                                             │  
│ States:                                                                     │  
│ • CLOSED: Normal operation, all requests pass                               │  
│ • OPEN: Failures exceeded threshold, requests rejected                      │  
│ • HALF\_OPEN: Testing recovery, limited requests allowed                     │  
│                                                                             │  
│ Failure mode: Prevents cascading failures                                   │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
Level 4: EXTERNAL PROBE  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ External monitoring validates overlay behavior                              │  
│                                                                             │  
│ Checks:                                                                     │  
│ • Response time within SLA                                                  │  
│ • Output format valid                                                       │  
│ • No anomalous behavior detected                                            │  
│                                                                             │  
│ Failure mode: Catches issues overlays don't self-report                     │  
└─────────────────────────────────────────────────────────────────────────────┘

QUARANTINE RULE: All four levels must fail for 3 consecutive checks

before automatic quarantine is triggered.

### **9.3 Circuit Breaker Implementation**

python  
class CircuitBreaker:  
    """  
    Circuit breaker for overlay failure isolation.  
      
    States:  
    \- CLOSED: Normal operation  
    \- OPEN: Failing, requests rejected  
    \- HALF\_OPEN: Testing recovery  
      
    Thresholds are configurable per-overlay based on trust level.  
    """  
      
    def \_\_init\_\_(  
        self,  
        failure\_threshold: int \= 3,  
        recovery\_timeout\_seconds: float \= 30.0,  
        half\_open\_max\_requests: int \= 3,  
    ):  
        self.\_failure\_threshold \= failure\_threshold  
        self.\_recovery\_timeout \= recovery\_timeout\_seconds  
        self.\_half\_open\_max \= half\_open\_max\_requests  
          
        self.\_state \= CircuitState.CLOSED  
        self.\_failure\_count \= 0  
        self.\_success\_count \= 0  
        self.\_last\_failure\_time: Optional\[datetime\] \= None  
        self.\_half\_open\_requests \= 0  
      
    def can\_execute(self) \-\> bool:  
        """  
        Check if a request should be allowed.  
          
        Returns:  
            True if request should proceed, False if rejected  
        """  
        if self.\_state \== CircuitState.CLOSED:  
            return True  
          
        if self.\_state \== CircuitState.OPEN:  
            *\# Check if recovery timeout has passed*  
            if self.\_last\_failure\_time:  
                elapsed \= (datetime.now(timezone.utc) \- self.\_last\_failure\_time).total\_seconds()  
                if elapsed \>= self.\_recovery\_timeout:  
                    self.\_state \= CircuitState.HALF\_OPEN  
                    self.\_half\_open\_requests \= 0  
                    return True  
            return False  
          
        if self.\_state \== CircuitState.HALF\_OPEN:  
            if self.\_half\_open\_requests \< self.\_half\_open\_max:  
                self.\_half\_open\_requests \+= 1  
                return True  
            return False  
          
        return False  
      
    def record\_success(self) \-\> None:  
        """Record a successful execution."""  
        if self.\_state \== CircuitState.HALF\_OPEN:  
            self.\_success\_count \+= 1  
            if self.\_success\_count \>= 2:  *\# 2 successes to close*  
                self.\_state \= CircuitState.CLOSED  
                self.\_failure\_count \= 0  
                self.\_success\_count \= 0  
        elif self.\_state \== CircuitState.CLOSED:  
            *\# Reset failure count on success*  
            self.\_failure\_count \= max(0, self.\_failure\_count \- 1)  
      
    def record\_failure(self) \-\> None:  
        """Record a failed execution."""  
        self.\_failure\_count \+= 1  
        self.\_last\_failure\_time \= datetime.now(timezone.utc)  
          
        if self.\_state \== CircuitState.HALF\_OPEN:  
            *\# Any failure in half-open goes back to open*  
            self.\_state \= CircuitState.OPEN  
            self.\_success\_count \= 0  
        elif self.\_state \== CircuitState.CLOSED:  
            if self.\_failure\_count \>= self.\_failure\_threshold:

                self.\_state \= CircuitState.OPEN

### **9.4 Canary Deployment**

python  
class CanaryDeployment:  
    """  
    Canary deployment for safe overlay updates.  
      
    Process:  
    1\. Deploy new version alongside old  
    2\. Route small percentage of traffic to new  
    3\. Monitor error rate and latency  
    4\. Gradually increase traffic if healthy  
    5\. Automatic rollback if metrics degrade  
    """  
      
    def \_\_init\_\_(  
        self,  
        overlay\_id: str,  
        old\_version: str,  
        new\_version: str,  
        initial\_percentage: float \= 0.05,  
        promotion\_increment: float \= 0.10,  
        min\_requests\_per\_stage: int \= 100,  
        max\_error\_rate: float \= 0.01,  
        max\_latency\_ratio: float \= 2.0,  
    ):  
        self.\_overlay\_id \= overlay\_id  
        self.\_old\_version \= old\_version  
        self.\_new\_version \= new\_version  
        self.\_traffic\_percentage \= initial\_percentage  
        self.\_promotion\_increment \= promotion\_increment  
        self.\_min\_requests \= min\_requests\_per\_stage  
        self.\_max\_error\_rate \= max\_error\_rate  
        self.\_max\_latency\_ratio \= max\_latency\_ratio  
          
        self.\_old\_metrics \= DeploymentMetrics()  
        self.\_new\_metrics \= DeploymentMetrics()  
        self.\_state \= CanaryState.RUNNING  
      
    def should\_use\_new\_version(self) \-\> bool:  
        """  
        Determine which version to use for a request.  
          
        Returns:  
            True to use new version, False for old  
        """  
        if self.\_state \!= CanaryState.RUNNING:  
            return self.\_state \== CanaryState.PROMOTED  
          
        return random.random() \< self.\_traffic\_percentage  
      
    def record\_result(  
        self,  
        is\_new\_version: bool,  
        success: bool,  
        latency\_ms: float,  
    ) \-\> None:  
        """Record execution result for analysis."""  
        metrics \= self.\_new\_metrics if is\_new\_version else self.\_old\_metrics  
        metrics.record(success, latency\_ms)  
          
        *\# Check for automatic decisions*  
        self.\_evaluate\_canary()  
      
    def \_evaluate\_canary(self) \-\> None:  
        """Evaluate canary health and decide next action."""  
        if self.\_new\_metrics.request\_count \< self.\_min\_requests:  
            return  *\# Not enough data*  
          
        *\# Calculate metrics*  
        new\_error\_rate \= self.\_new\_metrics.error\_rate  
        latency\_ratio \= self.\_new\_metrics.p95\_latency / max(self.\_old\_metrics.p95\_latency, 1)  
          
        *\# Check failure conditions*  
        if new\_error\_rate \> self.\_max\_error\_rate:  
            self.\_rollback(f"Error rate {new\_error\_rate:.2%} exceeds {self.\_max\_error\_rate:.2%}")  
            return  
          
        if latency\_ratio \> self.\_max\_latency\_ratio:  
            self.\_rollback(f"Latency ratio {latency\_ratio:.1f}x exceeds {self.\_max\_latency\_ratio}x")  
            return  
          
        *\# Success \- consider promotion*  
        if self.\_traffic\_percentage \>= 1.0:  
            self.\_promote()  
        else:  
            self.\_traffic\_percentage \= min(1.0, self.\_traffic\_percentage \+ self.\_promotion\_increment)  
            self.\_new\_metrics.reset\_for\_next\_stage()  
      
    def \_rollback(self, reason: str) \-\> None:  
        """Rollback to old version."""  
        self.\_state \= CanaryState.ROLLED\_BACK  
        logger.warning(f"Canary rollback for {self.\_overlay\_id}: {reason}")  
        *\# Publish event for monitoring*  
        asyncio.create\_task(self.\_publish\_rollback\_event(reason))  
      
    def \_promote(self) \-\> None:  
        """Promote new version to full traffic."""  
        self.\_state \= CanaryState.PROMOTED

        logger.info(f"Canary promoted for {self.\_overlay\_id}: {self.\_new\_version}")

### **9.5 Anomaly Detection**

python  
class AnomalyDetector:  
    """  
    ML-based anomaly detection for overlay behavior.  
      
    Uses isolation forest for unsupervised anomaly detection.  
    Trained on historical metrics, updated continuously.  
    """  
      
    def \_\_init\_\_(  
        self,  
        contamination: float \= 0.01,  *\# Expected anomaly rate*  
        window\_size: int \= 1000,      *\# Samples in sliding window*  
    ):  
        self.\_model \= IsolationForest(  
            contamination\=contamination,  
            random\_state\=42,  
            n\_estimators\=100,  
        )  
        self.\_window: deque\[MetricSample\] \= deque(maxlen\=window\_size)  
        self.\_is\_trained \= False  
      
    def add\_sample(self, sample: MetricSample) \-\> Optional\[float\]:  
        """  
        Add a metric sample and return anomaly score.  
          
        Args:  
            sample: The metric sample to analyze  
              
        Returns:  
            Anomaly score (0.0-1.0) if trained, None otherwise  
            Higher scores indicate more anomalous behavior  
        """  
        self.\_window.append(sample)  
          
        if len(self.\_window) \< 100:  
            return None  *\# Not enough data*  
          
        if not self.\_is\_trained:  
            self.\_train()  
          
        *\# Calculate anomaly score*  
        features \= self.\_extract\_features(sample)  
        score \= self.\_model.score\_samples(\[features\])\[0\]  
          
        *\# Convert to 0-1 range (isolation forest returns negative scores)*  
        normalized \= 1 \- (score \+ 0.5)  
        return max(0.0, min(1.0, normalized))  
      
    def \_extract\_features(self, sample: MetricSample) \-\> list\[float\]:  
        """Extract feature vector from metric sample."""  
        return \[  
            sample.latency\_ms,  
            sample.memory\_mb,  
            sample.cpu\_percent,  
            sample.error\_rate,  
            sample.request\_rate,  
            sample.fuel\_consumed,  
        \]  
      
    def \_train(self) \-\> None:  
        """Train the model on accumulated samples."""  
        features \= \[self.\_extract\_features(s) for s in self.\_window\]  
        self.\_model.fit(features)

        self.\_is\_trained \= True

---

## **10\. Governance System**

### **10.1 Governance Model**

Forge governs itself through democratic processes that balance speed with deliberation. The governance model implements proposal-based decision making with trust-weighted voting.

**Proposal Types.** Configuration changes modify system settings. Policy changes update rules and constraints. Trust adjustments modify entity trust levels. Emergency actions bypass normal voting for critical situations.

**Voting Mechanics.** Votes are weighted by the voter's trust level. A TRUSTED user's vote counts more than a STANDARD user's vote. Quorum requirements ensure sufficient participation. Voting periods provide time for deliberation.

**Constitutional AI.** An AI advisory layer reviews proposals against ethical principles. It can flag concerns but has no veto power. All AI analysis is transparent and visible to voters.

### **10.2 Proposal Schema**

python  
class ProposalType(str, Enum):  
    CONFIGURATION \= "configuration"    *\# System settings*  
    POLICY \= "policy"                  *\# Rules and constraints*  
    TRUST\_ADJUSTMENT \= "trust"         *\# Trust level changes*  
    OVERLAY\_REGISTRATION \= "overlay"   *\# New overlay approval*  
    OVERLAY\_UPDATE \= "overlay\_update"  *\# Overlay version update*  
    EMERGENCY \= "emergency"            *\# Critical actions (shortened period)*

class ProposalStatus(str, Enum):  
    DRAFT \= "draft"              *\# Being prepared*  
    ACTIVE \= "active"            *\# Open for voting*  
    VOTING\_CLOSED \= "closed"     *\# Voting ended, awaiting result*  
    APPROVED \= "approved"        *\# Passed, pending execution*  
    REJECTED \= "rejected"        *\# Failed*  
    EXECUTED \= "executed"        *\# Successfully applied*  
    FAILED \= "failed"            *\# Execution failed*

class ProposalCreate(BaseModel):  
    """Schema for creating a governance proposal."""  
    title: str \= Field(  
        ...,  
        min\_length\=10,  
        max\_length\=200,  
        description\="Clear, descriptive title"  
    )  
    description: str \= Field(  
        ...,  
        min\_length\=50,  
        max\_length\=10000,  
        description\="Detailed description with rationale"  
    )  
    type: ProposalType  
    changes: dict \= Field(  
        ...,  
        description\="Structured representation of proposed changes"  
    )  
    voting\_duration\_hours: int \= Field(  
        default\=72,  
        ge\=1,  
        le\=720,  *\# Max 30 days*  
        description\="How long voting remains open"  
    )  
      
    @field\_validator('voting\_duration\_hours')  
    @classmethod  
    def emergency\_has\_short\_duration(cls, v: int, info) \-\> int:  
        if info.data.get('type') \== ProposalType.EMERGENCY and v \> 4:  
            raise ValueError('Emergency proposals must have voting duration \<= 4 hours')  
        return v

class Proposal(BaseModel):  
    """Complete proposal entity."""  
    id: UUID \= Field(default\_factory\=uuid4)  
    title: str  
    description: str  
    type: ProposalType  
    status: ProposalStatus \= Field(default\=ProposalStatus.DRAFT)  
    changes: dict  
    proposer\_id: UUID  
    created\_at: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))  
    voting\_starts\_at: Optional\[datetime\] \= None  
    voting\_ends\_at: Optional\[datetime\] \= None  
    execution\_at: Optional\[datetime\] \= None  
      
    *\# Voting results*  
    votes\_for: int \= Field(default\=0, ge\=0)  
    votes\_against: int \= Field(default\=0, ge\=0)  
    votes\_abstain: int \= Field(default\=0, ge\=0)  
    weighted\_for: float \= Field(default\=0.0, ge\=0.0)  
    weighted\_against: float \= Field(default\=0.0, ge\=0.0)  
      
    *\# AI advisory*  
    ai\_analysis: Optional\[str\] \= None  
    ai\_concerns: list\[str\] \= Field(default\_factory\=list)  
    ai\_recommendation: Optional\[Literal\["support", "oppose", "neutral"\]\] \= None

class VoteDecision(str, Enum):  
    FOR \= "for"  
    AGAINST \= "against"  
    ABSTAIN \= "abstain"

class Vote(BaseModel):  
    """Individual vote on a proposal."""  
    proposal\_id: UUID  
    voter\_id: UUID  
    decision: VoteDecision  
    weight: float \= Field(  
        ...,  
        ge\=0.0,  
        le\=100.0,  
        description\="Vote weight based on voter's trust level"  
    )  
    reasoning: Optional\[str\] \= Field(  
        default\=None,  
        max\_length\=2000,  
        description\="Optional explanation of vote"  
    )

    timestamp: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))

### **10.3 Voting Process**

python  
class GovernanceService:  
    """  
    Service for governance operations.  
      
    Handles proposal lifecycle, voting, and execution.  
    """  
      
    def \_\_init\_\_(  
        self,  
        proposal\_repo: ProposalRepository,  
        user\_repo: UserRepository,  
        ai\_advisor: ConstitutionalAI,  
        event\_bus: EventBus,  
    ):  
        self.\_proposals \= proposal\_repo  
        self.\_users \= user\_repo  
        self.\_ai \= ai\_advisor  
        self.\_events \= event\_bus  
      
    async def create\_proposal(  
        self,  
        data: ProposalCreate,  
        proposer\_id: UUID,  
    ) \-\> Proposal:  
        """  
        Create a new proposal.  
          
        Args:  
            data: Proposal data  
            proposer\_id: ID of the proposing user  
              
        Returns:  
            Created proposal in DRAFT status  
              
        Raises:  
            PermissionError: If user cannot create proposals  
        """  
        *\# Verify proposer can create proposals*  
        proposer \= await self.\_users.get\_by\_id(proposer\_id)  
        if proposer.trust\_level.numeric\_value \< TrustLevel.STANDARD.numeric\_value:  
            raise PermissionError("Insufficient trust level to create proposals")  
          
        proposal \= Proposal(  
            \*\*data.model\_dump(),  
            proposer\_id\=proposer\_id,  
        )  
          
        *\# Get AI advisory analysis*  
        analysis \= await self.\_ai.analyze\_proposal(proposal)  
        proposal.ai\_analysis \= analysis.summary  
        proposal.ai\_concerns \= analysis.concerns  
        proposal.ai\_recommendation \= analysis.recommendation  
          
        await self.\_proposals.create(proposal)  
          
        return proposal  
      
    async def activate\_proposal(self, proposal\_id: UUID, activator\_id: UUID) \-\> Proposal:  
        """  
        Activate a proposal for voting.  
          
        Moves proposal from DRAFT to ACTIVE status.  
        """  
        proposal \= await self.\_proposals.get\_by\_id(proposal\_id)  
          
        if proposal.status \!= ProposalStatus.DRAFT:  
            raise ValueError(f"Cannot activate proposal in {proposal.status} status")  
          
        if proposal.proposer\_id \!= activator\_id:  
            raise PermissionError("Only proposer can activate proposal")  
          
        now \= datetime.now(timezone.utc)  
        proposal.status \= ProposalStatus.ACTIVE  
        proposal.voting\_starts\_at \= now  
        proposal.voting\_ends\_at \= now \+ timedelta(hours\=proposal.voting\_duration\_hours)  
          
        await self.\_proposals.update(proposal)  
          
        *\# Publish event for notifications*  
        await self.\_events.publish(ProposalActivatedEvent(  
            proposal\_id\=proposal.id,  
            title\=proposal.title,  
            voting\_ends\_at\=proposal.voting\_ends\_at,  
        ))  
          
        return proposal  
      
    async def cast\_vote(  
        self,  
        proposal\_id: UUID,  
        voter\_id: UUID,  
        decision: VoteDecision,  
        reasoning: Optional\[str\] \= None,  
    ) \-\> Vote:  
        """  
        Cast a vote on an active proposal.  
          
        Args:  
            proposal\_id: ID of the proposal  
            voter\_id: ID of the voter  
            decision: FOR, AGAINST, or ABSTAIN  
            reasoning: Optional explanation  
              
        Returns:  
            The recorded vote  
              
        Raises:  
            ValueError: If proposal not active or voting closed  
            PermissionError: If user cannot vote  
        """  
        proposal \= await self.\_proposals.get\_by\_id(proposal\_id)  
          
        if proposal.status \!= ProposalStatus.ACTIVE:  
            raise ValueError(f"Cannot vote on proposal in {proposal.status} status")  
          
        if datetime.now(timezone.utc) \> proposal.voting\_ends\_at:  
            raise ValueError("Voting period has ended")  
          
        *\# Check if already voted*  
        existing \= await self.\_proposals.get\_vote(proposal\_id, voter\_id)  
        if existing:  
            raise ValueError("Already voted on this proposal")  
          
        *\# Get voter trust for weighting*  
        voter \= await self.\_users.get\_by\_id(voter\_id)  
        if voter.trust\_level \== TrustLevel.QUARANTINE:  
            raise PermissionError("Quarantined users cannot vote")  
          
        weight \= float(voter.trust\_level.numeric\_value)  
          
        vote \= Vote(  
            proposal\_id\=proposal\_id,  
            voter\_id\=voter\_id,  
            decision\=decision,  
            weight\=weight,  
            reasoning\=reasoning,  
        )  
          
        await self.\_proposals.add\_vote(vote)  
          
        *\# Update proposal tallies*  
        if decision \== VoteDecision.FOR:  
            proposal.votes\_for \+= 1  
            proposal.weighted\_for \+= weight  
        elif decision \== VoteDecision.AGAINST:  
            proposal.votes\_against \+= 1  
            proposal.weighted\_against \+= weight  
        else:  
            proposal.votes\_abstain \+= 1  
          
        await self.\_proposals.update(proposal)  
          
        return vote  
      
    async def close\_voting(self, proposal\_id: UUID) \-\> Proposal:  
        """  
        Close voting and determine result.  
          
        Called automatically when voting period ends.  
        """  
        proposal \= await self.\_proposals.get\_by\_id(proposal\_id)  
          
        if proposal.status \!= ProposalStatus.ACTIVE:  
            raise ValueError(f"Cannot close voting on {proposal.status} proposal")  
          
        proposal.status \= ProposalStatus.VOTING\_CLOSED  
          
        *\# Determine result*  
        *\# Requires: \>50% weighted votes FOR, minimum 3 votes*  
        total\_weighted \= proposal.weighted\_for \+ proposal.weighted\_against  
        total\_votes \= proposal.votes\_for \+ proposal.votes\_against  
          
        if total\_votes \< 3:  
            proposal.status \= ProposalStatus.REJECTED  
            proposal.rejection\_reason \= "Insufficient votes (minimum 3 required)"  
        elif total\_weighted \> 0 and (proposal.weighted\_for / total\_weighted) \> 0.5:  
            proposal.status \= ProposalStatus.APPROVED  
        else:  
            proposal.status \= ProposalStatus.REJECTED  
            proposal.rejection\_reason \= "Did not achieve majority weighted support"  
          
        await self.\_proposals.update(proposal)  
          
        *\# Publish result event*  
        await self.\_events.publish(ProposalClosedEvent(  
            proposal\_id\=proposal.id,  
            status\=proposal.status,  
            votes\_for\=proposal.votes\_for,  
            votes\_against\=proposal.votes\_against,  
            weighted\_for\=proposal.weighted\_for,  
            weighted\_against\=proposal.weighted\_against,  
        ))  
        

        return proposal

### **10.4 Constitutional AI**

python  
class ConstitutionalAI:  
    """  
    AI advisory system for governance.  
      
    Reviews proposals against ethical principles.  
    Provides analysis and recommendations.  
    Has no veto power \- purely advisory.  
    """  
      
    PRINCIPLES \= \[  
        "Preserve user privacy and data sovereignty",  
        "Maintain system security and integrity",  
        "Ensure equitable access and non-discrimination",  
        "Promote transparency in AI decision-making",  
        "Prevent concentration of power",  
        "Support human oversight and control",  
        "Protect against harmful applications",  
        "Maintain audit trails and accountability",  
    \]  
      
    def \_\_init\_\_(self, llm\_client: LLMClient):  
        self.\_llm \= llm\_client  
      
    async def analyze\_proposal(self, proposal: Proposal) \-\> AIAnalysis:  
        """  
        Analyze a proposal against constitutional principles.  
          
        Args:  
            proposal: The proposal to analyze  
              
        Returns:  
            AIAnalysis with summary, concerns, and recommendation  
        """  
        prompt \= self.\_build\_analysis\_prompt(proposal)  
          
        response \= await self.\_llm.complete(  
            model\="claude-3-5-sonnet-20241022",  
            messages\=\[  
                {"role": "system", "content": self.\_system\_prompt},  
                {"role": "user", "content": prompt},  
            \],  
            temperature\=0.3,  *\# More deterministic for analysis*  
        )  
          
        return self.\_parse\_analysis(response.content)  
      
    def \_build\_analysis\_prompt(self, proposal: Proposal) \-\> str:  
        principles\_text \= "\\n".join(f"- {p}" for p in self.PRINCIPLES)  
          
        return f"""  
Analyze the following governance proposal against our constitutional principles.

PRINCIPLES:  
{principles\_text}

PROPOSAL:  
Title: {proposal.title}  
Type: {proposal.type.value}  
Description: {proposal.description}  
Proposed Changes: {json.dumps(proposal.changes, indent\=2)}

Provide your analysis in the following format:  
1\. SUMMARY: Brief summary of what the proposal does (2-3 sentences)  
2\. CONCERNS: List any potential violations or tensions with principles (or "None identified")  
3\. RECOMMENDATION: One of "support", "oppose", or "neutral" with brief rationale

Remember: Your role is advisory only. You cannot veto proposals.  
"""

    \_system\_prompt \= """You are a Constitutional AI advisor for the Forge governance system.  
Your role is to analyze proposals for potential ethical concerns and alignment with core principles.  
You provide transparent analysis that helps voters make informed decisions.  
You do not have veto power \- your recommendations are advisory only.

Be concise, specific, and constructive in your analysis."""

---

## **11\. Event Sourcing Architecture**

### **11.1 Design Rationale**

Event sourcing stores every state change as an immutable event. Instead of storing only current state, the system maintains a complete log of all events that led to that state. This architecture provides critical capabilities for Forge.

**Complete Audit Trail.** Every action is recorded with full context. Regulators can see exactly what happened and when.

**Temporal Queries.** The system can reconstruct state at any point in time. "What did the system know on January 15th?" is answerable.

**Corruption Recovery.** If state becomes corrupted, it can be rebuilt by replaying events from the last known good state.

**Debugging and Analytics.** The event log provides rich data for understanding system behavior and training ML models.

### **11.2 Event Store Architecture**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                        EVENT SOURCING ARCHITECTURE                           │  
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐  
│ COMMAND SIDE (Write)                                                        │  
│                                                                             │  
│  Command ─▶ Validate ─▶ Generate Events ─▶ Store Events ─▶ Update State    │  
│                                                                             │  
│  Commands are intentions: CreateCapsule, CastVote, QuarantineOverlay       │  
│  Events are facts: CapsuleCreated, VoteCast, OverlayQuarantined           │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ EVENT STORE (Kafka / KurrentDB)                                             │  
│                                                                             │  
│  ┌─────────────────────────────────────────────────────────────────────┐   │  
│  │ Stream: capsules                                                     │   │  
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │  
│  │ │ Event 1 │ │ Event 2 │ │ Event 3 │ │ Event 4 │ │ Event 5 │  ...   │   │  
│  │ │ Created │ │ Updated │ │ Created │ │ Deleted │ │ Created │        │   │  
│  │ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │  
│  └─────────────────────────────────────────────────────────────────────┘   │  
│                                                                             │  
│  ┌─────────────────────────────────────────────────────────────────────┐   │  
│  │ Stream: governance                                                   │   │  
│  │ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │  
│  │ │ Proposal  │ │ Vote      │ │ Vote      │ │ Proposal  │   ...       │   │  
│  │ │ Created   │ │ Cast      │ │ Cast      │ │ Approved  │             │   │  
│  │ └───────────┘ └───────────┘ └───────────┘ └───────────┘             │   │  
│  └─────────────────────────────────────────────────────────────────────┘   │  
│                                                                             │  
│  Properties:                                                                │  
│  • Append-only (immutable)                                                  │  
│  • Ordered within stream                                                    │  
│  • Globally ordered via sequence numbers                                    │  
│  • Retained for compliance period (minimum 6 months for EU AI Act)         │  
└─────────────────────────────────────────────────────────────────────────────┘  
                                │  
                                ▼  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ QUERY SIDE (Read)                                                           │  
│                                                                             │  
│  Events ─▶ Projections ─▶ Read Models ─▶ Query Handlers                    │  
│                                                                             │  
│  Projections rebuild current state from events                              │  
│  Read models are optimized for specific queries                             │  
│  Multiple projections can coexist for different views                       │

└─────────────────────────────────────────────────────────────────────────────┘

### **11.3 Event Schema**

python  
class EventBase(BaseModel):  
    """Base class for all events."""  
    event\_id: UUID \= Field(default\_factory\=uuid4)  
    event\_type: str  
    stream\_id: str  
    sequence\_number: int \= Field(  
        ...,  
        ge\=0,  
        description\="Monotonically increasing sequence within stream"  
    )  
    timestamp: datetime \= Field(default\_factory\=lambda: datetime.now(timezone.utc))  
    actor\_id: Optional\[UUID\] \= None  
    correlation\_id: Optional\[UUID\] \= None  
    causation\_id: Optional\[UUID\] \= None  
    metadata: dict \= Field(default\_factory\=dict)  
      
    model\_config \= {  
        "frozen": True  *\# Events are immutable*  
    }

*\# Capsule Events*  
class CapsuleCreated(EventBase):  
    event\_type: Literal\["capsule.created"\] \= "capsule.created"  
    capsule\_id: UUID  
    content: str  
    capsule\_type: CapsuleType  
    owner\_id: UUID  
    parent\_id: Optional\[UUID\] \= None  
    trust\_level: TrustLevel

class CapsuleUpdated(EventBase):  
    event\_type: Literal\["capsule.updated"\] \= "capsule.updated"  
    capsule\_id: UUID  
    changes: dict  *\# Only changed fields*  
    previous\_values: dict

class CapsuleDeleted(EventBase):  
    event\_type: Literal\["capsule.deleted"\] \= "capsule.deleted"  
    capsule\_id: UUID  
    reason: str

class CapsuleTrustChanged(EventBase):  
    event\_type: Literal\["capsule.trust\_changed"\] \= "capsule.trust\_changed"  
    capsule\_id: UUID  
    old\_trust: TrustLevel  
    new\_trust: TrustLevel  
    reason: str

*\# Governance Events*  
class ProposalCreated(EventBase):  
    event\_type: Literal\["governance.proposal\_created"\] \= "governance.proposal\_created"  
    proposal\_id: UUID  
    title: str  
    proposal\_type: ProposalType  
    proposer\_id: UUID

class VoteCast(EventBase):  
    event\_type: Literal\["governance.vote\_cast"\] \= "governance.vote\_cast"  
    proposal\_id: UUID  
    voter\_id: UUID  
    decision: VoteDecision  
    weight: float

class ProposalClosed(EventBase):  
    event\_type: Literal\["governance.proposal\_closed"\] \= "governance.proposal\_closed"  
    proposal\_id: UUID  
    result: ProposalStatus  
    votes\_for: int  
    votes\_against: int  
    weighted\_for: float  
    weighted\_against: float

*\# Overlay Events*  
class OverlayRegistered(EventBase):  
    event\_type: Literal\["overlay.registered"\] \= "overlay.registered"  
    overlay\_id: UUID  
    name: str  
    version: str  
    capabilities: list\[OverlayCapability\]

class OverlayStateChanged(EventBase):  
    event\_type: Literal\["overlay.state\_changed"\] \= "overlay.state\_changed"  
    overlay\_id: UUID  
    old\_state: OverlayState  
    new\_state: OverlayState  
    reason: str

*\# Security Events*  
class SecurityThreatDetected(EventBase):  
    event\_type: Literal\["security.threat\_detected"\] \= "security.threat\_detected"  
    threat\_type: str  
    severity: Literal\["low", "medium", "high", "critical"\]  
    source: str  
    details: dict

class AuthenticationAttempt(EventBase):  
    event\_type: Literal\["security.auth\_attempt"\] \= "security.auth\_attempt"  
    user\_id: Optional\[UUID\]  
    success: bool  
    method: str  *\# "password", "api\_key", "oauth", "mfa"*  
    ip\_address: str

    user\_agent: str

### **11.4 Event Store Implementation**

python  
class EventStore:  
    """  
    Event store using Kafka or KurrentDB.  
      
    Provides:  
    \- Append-only event storage  
    \- Stream-based organization  
    \- Global ordering via sequence numbers  
    \- Subscription for real-time processing  
    """  
      
    def \_\_init\_\_(  
        self,  
        kafka\_bootstrap\_servers: str,  
        schema\_registry\_url: str,  
    ):  
        self.\_producer \= AIOKafkaProducer(  
            bootstrap\_servers\=kafka\_bootstrap\_servers,  
            value\_serializer\=self.\_serialize\_event,  
        )  
        self.\_schema\_registry \= SchemaRegistryClient({"url": schema\_registry\_url})  
        self.\_sequence\_counters: dict\[str, int\] \= {}  
      
    async def append(  
        self,  
        stream\_id: str,  
        event: EventBase,  
        expected\_sequence: Optional\[int\] \= None,  
    ) \-\> int:  
        """  
        Append an event to a stream.  
          
        Args:  
            stream\_id: The stream to append to  
            event: The event to append  
            expected\_sequence: For optimistic concurrency (optional)  
              
        Returns:  
            The sequence number assigned to the event  
              
        Raises:  
            ConcurrencyError: If expected\_sequence doesn't match  
        """  
        *\# Get next sequence number*  
        current\_seq \= self.\_sequence\_counters.get(stream\_id, \-1)  
          
        if expected\_sequence is not None and current\_seq \!= expected\_sequence:  
            raise ConcurrencyError(  
                f"Expected sequence {expected\_sequence}, but current is {current\_seq}"  
            )  
          
        next\_seq \= current\_seq \+ 1  
          
        *\# Set sequence on event (create new instance since events are frozen)*  
        event\_with\_seq \= event.model\_copy(update\={  
            "sequence\_number": next\_seq,  
            "stream\_id": stream\_id,  
        })  
          
        *\# Send to Kafka*  
        await self.\_producer.send\_and\_wait(  
            topic\=f"forge.events.{stream\_id}",  
            value\=event\_with\_seq,  
            key\=str(event\_with\_seq.event\_id).encode(),  
        )  
          
        self.\_sequence\_counters\[stream\_id\] \= next\_seq  
        return next\_seq  
      
    async def read\_stream(  
        self,  
        stream\_id: str,  
        from\_sequence: int \= 0,  
        to\_sequence: Optional\[int\] \= None,  
    ) \-\> AsyncIterator\[EventBase\]:  
        """  
        Read events from a stream.  
          
        Args:  
            stream\_id: The stream to read  
            from\_sequence: Start reading from this sequence (inclusive)  
            to\_sequence: Stop reading at this sequence (inclusive, optional)  
              
        Yields:  
            Events in sequence order  
        """  
        consumer \= AIOKafkaConsumer(  
            f"forge.events.{stream\_id}",  
            bootstrap\_servers\=self.\_bootstrap\_servers,  
            auto\_offset\_reset\='earliest',  
        )  
          
        await consumer.start()  
        try:  
            async for msg in consumer:  
                event \= self.\_deserialize\_event(msg.value)  
                  
                if event.sequence\_number \< from\_sequence:  
                    continue  
                  
                if to\_sequence is not None and event.sequence\_number \> to\_sequence:  
                    break  
                  
                yield event  
        finally:  
            await consumer.stop()  
      
    async def subscribe(  
        self,  
        stream\_id: str,  
        handler: Callable\[\[EventBase\], Awaitable\[None\]\],  
        from\_sequence: Optional\[int\] \= None,  
    ) \-\> Subscription:  
        """  
        Subscribe to new events on a stream.  
          
        Args:  
            stream\_id: The stream to subscribe to  
            handler: Async function to call for each event  
            from\_sequence: Start from this sequence (None \= latest only)  
              
        Returns:  
            Subscription object for management  
        """  
        subscription \= Subscription(  
            stream\_id\=stream\_id,  
            handler\=handler,  
            from\_sequence\=from\_sequence,  
        )  
          
        asyncio.create\_task(self.\_run\_subscription(subscription))  
        

        return subscription

### **11.5 Projections**

python  
class Projection(ABC):  
    """  
    Base class for event projections.  
      
    Projections consume events and build read models.  
    They can be rebuilt from scratch by replaying events.  
    """  
      
    @property  
    @abstractmethod  
    def stream\_ids(self) \-\> list\[str\]:  
        """Streams this projection subscribes to."""  
        pass  
      
    @abstractmethod  
    async def handle(self, event: EventBase) \-\> None:  
        """Handle a single event."""  
        pass  
      
    @abstractmethod  
    async def checkpoint(self) \-\> dict\[str, int\]:  
        """Return current sequence numbers for each stream."""  
        pass  
      
    async def rebuild(self, event\_store: EventStore) \-\> None:  
        """Rebuild projection from scratch."""  
        for stream\_id in self.stream\_ids:  
            async for event in event\_store.read\_stream(stream\_id):  
                await self.handle(event)

class CapsuleCountsProjection(Projection):  
    """  
    Projection maintaining capsule counts by type and trust level.  
      
    Useful for dashboard statistics without querying Neo4j.  
    """  
      
    stream\_ids \= \["capsules"\]  
      
    def \_\_init\_\_(self, redis: Redis):  
        self.\_redis \= redis  
        self.\_checkpoint: dict\[str, int\] \= {}  
      
    async def handle(self, event: EventBase) \-\> None:  
        if isinstance(event, CapsuleCreated):  
            await self.\_redis.hincrby("capsule\_counts:type", event.capsule\_type.value, 1)  
            await self.\_redis.hincrby("capsule\_counts:trust", event.trust\_level.value, 1)  
            await self.\_redis.incr("capsule\_counts:total")  
          
        elif isinstance(event, CapsuleDeleted):  
            await self.\_redis.hincrby("capsule\_counts:total", \-1)  
          
        elif isinstance(event, CapsuleTrustChanged):  
            await self.\_redis.hincrby("capsule\_counts:trust", event.old\_trust.value, \-1)  
            await self.\_redis.hincrby("capsule\_counts:trust", event.new\_trust.value, 1)  
          
        self.\_checkpoint\[event.stream\_id\] \= event.sequence\_number  
      
    async def checkpoint(self) \-\> dict\[str, int\]:

        return self.\_checkpoint.copy()

---

## **12\. Global Compliance Framework**

### **12.1 Regulatory Landscape**

Forge must comply with regulations across multiple jurisdictions. The framework implements 400+ technical controls across 25+ regulatory frameworks.

**Key Compliance Deadlines**

| Date | Regulation | Requirements |
| ----- | ----- | ----- |
| February 2025 | EU AI Act \- Prohibited | Social scoring, certain biometric systems banned |
| March 2025 | PCI-DSS 4.0.1 | MFA for all cardholder data access |
| June 2025 | COPPA Updates | Separate third-party consent, written security program |
| June 2025 | European Accessibility Act | WCAG 2.2 Level AA mandatory |
| February 2026 | Colorado AI Act | Consequential decision disclosure |
| August 2026 | EU AI Act \- High Risk | Full conformity assessment, technical documentation |

**Maximum Penalties**

| Regulation | Maximum Penalty |
| ----- | ----- |
| EU AI Act | €35M or 7% global revenue |
| GDPR | €20M or 4% global revenue |
| China PIPL | ¥50M or 5% revenue |
| Australia Privacy | A$50M or 30% turnover |

### **12.2 Compliance Architecture**

┌─────────────────────────────────────────────────────────────────────────────┐  
│                      GLOBAL COMPLIANCE FRAMEWORK                             │  
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐  
│ COMPLIANCE ENGINE                                                           │  
│                                                                             │  
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │  
│  │ Control        │  │ Jurisdiction   │  │ Assessment     │                │  
│  │ Registry       │  │ Router         │  │ Engine         │                │  
│  │                │  │                │  │                │                │  
│  │ 400+ controls  │  │ 25+ regions    │  │ Automated      │                │  
│  │ Mapped to regs │  │ Data routing   │  │ gap analysis   │                │  
│  └────────────────┘  └────────────────┘  └────────────────┘                │  
│                                                                             │  
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │  
│  │ Audit Logger   │  │ Report         │  │ Notification   │                │  
│  │                │  │ Generator      │  │ Service        │                │  
│  │ Immutable logs │  │ SOC 2, ISO     │  │ Breach alerts  │                │  
│  │ 6mo retention  │  │ Custom formats │  │ Multi-channel  │                │  
│  └────────────────┘  └────────────────┘  └────────────────┘                │  
└─────────────────────────────────────────────────────────────────────────────┘  
                              │  
              ┌───────────────┼───────────────┐  
              ▼               ▼               ▼  
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  
│ PRIVACY         │ │ AI GOVERNANCE   │ │ DATA RESIDENCY  │  
│                 │ │                 │ │                 │  
│ • DSAR Process  │ │ • Risk Tiers    │ │ • Regional Pods │  
│ • Consent Mgmt  │ │ • Explainability│ │ • Transfer TIA  │  
│ • Data Mapping  │ │ • Human Review  │ │ • Localization  │  
│ • Retention     │ │ • Bias Audit    │ │ • SCC/BCRs      │  
└─────────────────┘ └─────────────────┘ └─────────────────┘  
              │               │               │  
              ▼               ▼               ▼  
┌─────────────────────────────────────────────────────────────────────────────┐  
│ SECURITY CONTROLS                                                           │  
│                                                                             │  
│ • AES-256-GCM encryption at rest                                           │  
│ • TLS 1.3 in transit                                                       │  
│ • HSM-backed key management                                                │  
│ • Field-level encryption for PII                                           │  
│ • Tokenization for sensitive identifiers                                   │  
│ • Access control (RBAC \+ ABAC)                                             │  
│ • Audit logging with tamper detection                                      │

└─────────────────────────────────────────────────────────────────────────────┘

### **12.3 EU AI Act Compliance**

The EU AI Act classifies AI systems by risk level. Forge implements controls for high-risk systems.

python  
class EUAIActRiskLevel(str, Enum):  
    """EU AI Act risk classification."""  
    PROHIBITED \= "prohibited"      *\# Banned applications*  
    HIGH\_RISK \= "high\_risk"        *\# Strict requirements*  
    LIMITED\_RISK \= "limited\_risk"  *\# Transparency obligations*  
    MINIMAL\_RISK \= "minimal\_risk"  *\# No specific requirements*

class EUAIActCompliance:  
    """  
    EU AI Act compliance implementation.  
      
    Requirements for high-risk systems (effective August 2026):  
    \- Risk management system  
    \- Data governance  
    \- Technical documentation  
    \- Automatic logging (6-month retention)  
    \- Transparency to users  
    \- Human oversight capability  
    \- Accuracy, robustness, cybersecurity  
    """  
      
    async def assess\_risk\_level(self, system\_description: dict) \-\> EUAIActRiskLevel:  
        """  
        Assess EU AI Act risk level for a system.  
          
        Args:  
            system\_description: Description of the AI system's purpose and use  
              
        Returns:  
            Assessed risk level  
        """  
        *\# Check for prohibited uses*  
        prohibited\_indicators \= \[  
            "social\_scoring",  
            "emotion\_recognition\_workplace",  
            "biometric\_categorization\_protected",  
            "facial\_recognition\_public\_spaces",  
        \]  
          
        for indicator in prohibited\_indicators:  
            if indicator in str(system\_description).lower():  
                return EUAIActRiskLevel.PROHIBITED  
          
        *\# Check for high-risk uses (Annex III)*  
        high\_risk\_domains \= \[  
            "biometric\_identification",  
            "critical\_infrastructure",  
            "education\_assessment",  
            "employment\_recruitment",  
            "essential\_services\_access",  
            "law\_enforcement",  
            "migration\_asylum",  
            "justice\_administration",  
        \]  
          
        for domain in high\_risk\_domains:  
            if domain in str(system\_description).lower():  
                return EUAIActRiskLevel.HIGH\_RISK  
          
        *\# Check for transparency obligations*  
        if self.\_interacts\_with\_humans(system\_description):  
            return EUAIActRiskLevel.LIMITED\_RISK  
          
        return EUAIActRiskLevel.MINIMAL\_RISK  
      
    async def generate\_technical\_documentation(  
        self,  
        system\_id: str,  
    ) \-\> TechnicalDocumentation:  
        """  
        Generate technical documentation required by Article 11\.  
          
        Documentation must include:  
        \- General description  
        \- Design specifications  
        \- System architecture  
        \- Training methodology  
        \- Risk management measures  
        \- Data governance practices  
        \- Performance metrics  
        \- Logging and monitoring  
        """  
        system \= await self.\_get\_system(system\_id)  
          
        return TechnicalDocumentation(  
            system\_id\=system\_id,  
            version\=system.version,  
            generated\_at\=datetime.now(timezone.utc),  
            sections\={  
                "general\_description": self.\_generate\_general\_description(system),  
                "design\_specifications": self.\_generate\_design\_specs(system),  
                "architecture": self.\_generate\_architecture\_doc(system),  
                "training\_methodology": self.\_generate\_training\_doc(system),  
                "risk\_management": self.\_generate\_risk\_doc(system),  
                "data\_governance": self.\_generate\_data\_gov\_doc(system),  
                "performance\_metrics": self.\_generate\_performance\_doc(system),  
                "logging\_monitoring": self.\_generate\_logging\_doc(system),  
            }  
        )  
      
    async def verify\_logging\_compliance(self, system\_id: str) \-\> ComplianceResult:  
        """  
        Verify that logging meets Article 19 requirements.  
          
        Requirements:  
        \- Automatic logging of operations  
        \- Minimum 6-month retention  
        \- Logs must be traceable to natural persons  
        \- Must enable post-market monitoring  
        """  
        log\_config \= await self.\_get\_log\_config(system\_id)  
          
        issues \= \[\]  
          
        if not log\_config.automatic\_logging:  
            issues.append("Automatic logging not enabled")  
          
        if log\_config.retention\_days \< 180:  *\# 6 months*  
            issues.append(f"Retention {log\_config.retention\_days} days \< required 180 days")  
          
        if not log\_config.user\_traceability:  
            issues.append("Logs not traceable to users")  
          
        return ComplianceResult(  
            compliant\=len(issues) \== 0,  
            issues\=issues,  
            checked\_at\=datetime.now(timezone.utc),

        )

### **12.4 GDPR Compliance**

python  
class GDPRCompliance:  
    """  
    GDPR compliance implementation.  
      
    Key requirements:  
    \- Lawful basis for processing  
    \- Data subject rights (access, erasure, portability)  
    \- Data Protection Impact Assessment  
    \- Cross-border transfer controls  
    \- Breach notification (72 hours)  
    """  
      
    async def process\_dsar(self, request: DSARRequest) \-\> DSARResponse:  
        """  
        Process a Data Subject Access Request.  
          
        Args:  
            request: The DSAR request  
              
        Returns:  
            Response with requested data or denial with reason  
              
        Timeline: Must respond within 30 days (extendable to 90\)  
        """  
        *\# Verify identity*  
        if not await self.\_verify\_identity(request.subject\_id, request.verification):  
            return DSARResponse(  
                status\=DSARStatus.DENIED,  
                reason\="Identity verification failed",  
            )  
          
        *\# Gather data*  
        if request.type \== DSARType.ACCESS:  
            data \= await self.\_gather\_subject\_data(request.subject\_id)  
            return DSARResponse(  
                status\=DSARStatus.COMPLETED,  
                data\=data,  
                format\=request.preferred\_format or "json",  
            )  
          
        elif request.type \== DSARType.ERASURE:  
            *\# Check for exemptions*  
            if await self.\_has\_erasure\_exemption(request.subject\_id):  
                return DSARResponse(  
                    status\=DSARStatus.DENIED,  
                    reason\="Legal retention requirement prevents erasure",  
                )  
              
            await self.\_erase\_subject\_data(request.subject\_id)  
            return DSARResponse(status\=DSARStatus.COMPLETED)  
          
        elif request.type \== DSARType.PORTABILITY:  
            data \= await self.\_gather\_portable\_data(request.subject\_id)  
            return DSARResponse(  
                status\=DSARStatus.COMPLETED,  
                data\=data,  
                format\="json",  *\# Machine-readable required*  
            )  
      
    async def report_breach(self, breach: BreachReport) -> BreachNotification:
        """
        Handle data breach notification.
        
        GDPR Article 33: Notify supervisory authority within 72 hours.
        GDPR Article 34: Notify affected individuals if high risk.
        
        Args:
            breach: Details of the breach including scope, data types, and timing
            
        Returns:
            Notification record with timeline and actions taken
        """
        notification = BreachNotification(
            breach_id=breach.id,
            detected_at=breach.detected_at,
            deadline_authority=breach.detected_at + timedelta(hours=72),
        )
        
        # Assess severity using standardized criteria
        severity = await self._assess_breach_severity(breach)
        
        # Notify supervisory authority if required (Article 33)
        if severity.requires_authority_notification:
            notification.authority_notified_at = datetime.now(timezone.utc)
            await self._notify_supervisory_authority(breach, severity)
            
            # Log for audit trail
            await self._event_store.append("compliance", BreachAuthorityNotified(
                breach_id=breach.id,
                authority=severity.supervisory_authority,
                notification_method="secure_portal",
                notified_at=notification.authority_notified_at,
            ))
        
        # Notify individuals if high risk to rights and freedoms (Article 34)
        if severity.requires_individual_notification:
            notification.individuals_notified_at = datetime.now(timezone.utc)
            affected_count = await self._notify_affected_individuals(breach)
            
            await self._event_store.append("compliance", BreachIndividualsNotified(
                breach_id=breach.id,
                affected_count=affected_count,
                notification_method=breach.notification_preference or "email",
                notified_at=notification.individuals_notified_at,
            ))
        
        # Record complete breach report for regulatory audit
        await self._event_store.append("compliance", BreachReportedEvent(
            breach_id=breach.id,
            severity=severity.level,
            data_categories=breach.data_categories,
            affected_count=breach.estimated_affected,
            authority_notified=severity.requires_authority_notification,
            individuals_notified=severity.requires_individual_notification,
            containment_measures=breach.containment_measures,
            remediation_plan=breach.remediation_plan,
        ))
        
        return notification
    
    async def _assess_breach_severity(self, breach: BreachReport) -> BreachSeverity:
        """
        Assess breach severity using EDPB guidelines.
        
        Factors considered:
        - Type of data (special categories increase severity)
        - Number of individuals affected
        - Potential consequences (identity theft, financial loss, etc.)
        - Whether data was encrypted
        - Ability to identify affected individuals
        """
        severity_score = 0
        
        # Special category data (Article 9) - highest severity
        special_categories = {"health", "biometric", "genetic", "racial_ethnic", 
                            "political_opinions", "religious_beliefs", "sexual_orientation"}
        if any(cat in breach.data_categories for cat in special_categories):
            severity_score += 40
        
        # Financial data - high severity
        if "financial" in breach.data_categories or "payment" in breach.data_categories:
            severity_score += 30
        
        # Scale of breach
        if breach.estimated_affected > 10000:
            severity_score += 20
        elif breach.estimated_affected > 1000:
            severity_score += 15
        elif breach.estimated_affected > 100:
            severity_score += 10
        
        # Encryption status - reduces severity if properly encrypted
        if breach.data_was_encrypted:
            severity_score -= 20
        
        # Determine notification requirements based on score
        requires_authority = severity_score >= 20  # Most breaches require notification
        requires_individuals = severity_score >= 50  # High risk to rights/freedoms
        
        return BreachSeverity(
            level="critical" if severity_score >= 60 else "high" if severity_score >= 40 else "medium" if severity_score >= 20 else "low",
            score=severity_score,
            requires_authority_notification=requires_authority,
            requires_individual_notification=requires_individuals,
            supervisory_authority=self._get_lead_authority(breach.affected_jurisdictions),
        )


class ConsentManagementService:
    """
    GDPR-compliant consent management.
    
    Implements:
    - Granular consent per processing purpose
    - Easy withdrawal mechanism
    - Consent receipt generation
    - Audit trail of all consent changes
    """
    
    def __init__(self, neo4j_client: Neo4jClient, event_store: EventStore):
        self._neo4j = neo4j_client
        self._events = event_store
    
    async def record_consent(
        self,
        user_id: UUID,
        purpose: str,
        scope: list[str],
        expiry: Optional[datetime] = None,
    ) -> ConsentRecord:
        """
        Record explicit consent for a specific purpose.
        
        Args:
            user_id: The data subject
            purpose: Processing purpose (e.g., "marketing", "analytics")
            scope: Specific data categories covered
            expiry: Optional consent expiry date
            
        Returns:
            ConsentRecord with receipt for user's records
        """
        consent = ConsentRecord(
            id=uuid4(),
            user_id=user_id,
            purpose=purpose,
            scope=scope,
            granted=True,
            granted_at=datetime.now(timezone.utc),
            expires_at=expiry,
            version=await self._get_current_policy_version(purpose),
            jurisdiction=await self._get_user_jurisdiction(user_id),
        )
        
        async with self._neo4j.transaction() as tx:
            # Store consent record
            await tx.run("""
                MATCH (u:User {id: $user_id})
                CREATE (c:ConsentRecord {
                    id: $consent_id,
                    purpose: $purpose,
                    scope: $scope,
                    granted: true,
                    granted_at: datetime(),
                    expires_at: $expires_at,
                    policy_version: $version,
                    jurisdiction: $jurisdiction
                })
                CREATE (u)-[:GAVE_CONSENT]->(c)
                RETURN c
            """, {
                "user_id": str(user_id),
                "consent_id": str(consent.id),
                "purpose": purpose,
                "scope": scope,
                "expires_at": expiry.isoformat() if expiry else None,
                "version": consent.version,
                "jurisdiction": consent.jurisdiction,
            })
        
        # Emit event for audit
        await self._events.append("consent", ConsentGranted(
            consent_id=consent.id,
            user_id=user_id,
            purpose=purpose,
            scope=scope,
        ))
        
        return consent
    
    async def withdraw_consent(
        self,
        user_id: UUID,
        purpose: str,
        reason: Optional[str] = None,
    ) -> ConsentWithdrawal:
        """
        Process consent withdrawal request.
        
        GDPR requires withdrawal to be as easy as giving consent.
        """
        async with self._neo4j.transaction() as tx:
            # Find and update active consent
            result = await tx.run("""
                MATCH (u:User {id: $user_id})-[:GAVE_CONSENT]->(c:ConsentRecord)
                WHERE c.purpose = $purpose AND c.granted = true
                SET c.granted = false,
                    c.withdrawn_at = datetime(),
                    c.withdrawal_reason = $reason
                RETURN c
            """, {
                "user_id": str(user_id),
                "purpose": purpose,
                "reason": reason,
            })
            
            record = await result.single()
            if not record:
                raise ConsentNotFoundError(f"No active consent for purpose: {purpose}")
        
        withdrawal = ConsentWithdrawal(
            consent_id=UUID(record["c"]["id"]),
            user_id=user_id,
            purpose=purpose,
            withdrawn_at=datetime.now(timezone.utc),
            reason=reason,
        )
        
        # Emit event for downstream systems to stop processing
        await self._events.append("consent", ConsentWithdrawn(
            consent_id=withdrawal.consent_id,
            user_id=user_id,
            purpose=purpose,
            reason=reason,
        ))
        
        # Trigger data processing cessation
        await self._trigger_processing_halt(user_id, purpose)
        
        return withdrawal


### **12.5 Data Residency Service**

```python
class DataResidencyService:
    """
    Data residency and sovereignty management.
    
    Ensures data stays within required jurisdictions per regulation:
    - EU data stays in EU (GDPR)
    - China data stays in China (PIPL)
    - Russia data stays in Russia (FZ-152)
    - Sector-specific requirements (HIPAA, etc.)
    """
    
    # Regional endpoint configuration
    REGIONAL_ENDPOINTS = {
        Jurisdiction.EU: RegionalConfig(
            endpoint="eu-west-1.forge.example.com",
            storage_location="eu-west-1",
            backup_region="eu-central-1",
            encryption_key_region="eu-west-1",
        ),
        Jurisdiction.US: RegionalConfig(
            endpoint="us-east-1.forge.example.com",
            storage_location="us-east-1",
            backup_region="us-west-2",
            encryption_key_region="us-east-1",
        ),
        Jurisdiction.CHINA: RegionalConfig(
            endpoint="cn-north-1.forge.example.cn",
            storage_location="cn-north-1",
            backup_region="cn-northwest-1",
            encryption_key_region="cn-north-1",
        ),
        Jurisdiction.RUSSIA: RegionalConfig(
            endpoint="ru-central-1.forge.example.ru",
            storage_location="ru-central-1",
            backup_region="ru-central-1",  # No cross-region for Russia
            encryption_key_region="ru-central-1",
        ),
        Jurisdiction.SINGAPORE: RegionalConfig(
            endpoint="ap-southeast-1.forge.example.com",
            storage_location="ap-southeast-1",
            backup_region="ap-southeast-2",
            encryption_key_region="ap-southeast-1",
        ),
        Jurisdiction.AUSTRALIA: RegionalConfig(
            endpoint="ap-southeast-2.forge.example.com",
            storage_location="ap-southeast-2",
            backup_region="ap-southeast-1",
            encryption_key_region="ap-southeast-2",
        ),
    }
    
    # Adequacy decisions for EU data transfers
    ADEQUACY_DECISIONS = {
        Jurisdiction.UK,  # Post-Brexit adequacy
        Jurisdiction.JAPAN,
        Jurisdiction.SOUTH_KOREA,
        Jurisdiction.CANADA,  # Commercial organizations
        Jurisdiction.SWITZERLAND,
        Jurisdiction.NEW_ZEALAND,
        Jurisdiction.ISRAEL,
    }
    
    def __init__(
        self,
        encryption_service: EncryptionService,
        event_store: EventStore,
    ):
        self._encryption = encryption_service
        self._events = event_store
    
    async def route_data(
        self,
        data: bytes,
        jurisdiction: Jurisdiction,
        data_type: DataType,
        metadata: dict,
    ) -> DataLocation:
        """
        Route data to appropriate regional endpoint.
        
        Args:
            data: The data to store
            jurisdiction: Required jurisdiction for storage
            data_type: Classification of data (personal, sensitive, etc.)
            metadata: Additional routing metadata
            
        Returns:
            DataLocation with storage identifier and region
        """
        config = self.REGIONAL_ENDPOINTS.get(jurisdiction)
        if not config:
            raise UnsupportedJurisdictionError(
                f"No regional endpoint configured for {jurisdiction}"
            )
        
        # Encrypt with region-specific key
        encrypted = await self._encryption.encrypt_for_region(
            data=data,
            region=config.encryption_key_region,
            context={
                "jurisdiction": jurisdiction.value,
                "data_type": data_type.value,
            },
        )
        
        # Store in regional bucket/database
        location = await self._store_in_region(
            endpoint=config.endpoint,
            storage_location=config.storage_location,
            data=encrypted,
            metadata=metadata,
        )
        
        # Log for compliance audit
        await self._events.append("data_residency", DataRoutedEvent(
            location_id=location.id,
            jurisdiction=jurisdiction,
            data_type=data_type,
            storage_region=config.storage_location,
            encrypted=True,
        ))
        
        return location
    
    async def validate_transfer(
        self,
        source: Jurisdiction,
        destination: Jurisdiction,
        data_type: DataType,
        transfer_purpose: str,
    ) -> TransferValidation:
        """
        Validate cross-border data transfer legality.
        
        Checks:
        - Adequacy decisions (GDPR Article 45)
        - Standard Contractual Clauses (Article 46)
        - Binding Corporate Rules
        - Explicit consent (Article 49 derogations)
        - Sector-specific restrictions
        
        Returns:
            TransferValidation with allowed status and mechanism used
        """
        # Same jurisdiction is always allowed
        if source == destination:
            return TransferValidation(
                allowed=True,
                mechanism="same_jurisdiction",
            )
        
        # China PIPL: Requires CAC security assessment for outbound transfers
        if source == Jurisdiction.CHINA:
            return TransferValidation(
                allowed=False,
                reason="China PIPL requires Cyberspace Administration security assessment for cross-border transfers",
                remediation="Submit security assessment application to CAC",
                estimated_approval_time="45-60 business days",
            )
        
        # Russia FZ-152: Personal data of Russian citizens must be stored in Russia
        if source == Jurisdiction.RUSSIA and data_type == DataType.PERSONAL:
            return TransferValidation(
                allowed=False,
                reason="Federal Law 152-FZ requires Russian citizen personal data to be stored and processed in Russia",
                remediation="Process data within Russian Federation borders",
            )
        
        # EU GDPR: Check transfer mechanisms
        if source == Jurisdiction.EU:
            # Check adequacy decision
            if destination in self.ADEQUACY_DECISIONS:
                return TransferValidation(
                    allowed=True,
                    mechanism="adequacy_decision",
                    legal_basis="GDPR Article 45",
                )
            
            # Check for SCCs
            if await self._has_standard_contractual_clauses(destination):
                return TransferValidation(
                    allowed=True,
                    mechanism="standard_contractual_clauses",
                    legal_basis="GDPR Article 46(2)(c)",
                    conditions=["Transfer Impact Assessment required", 
                               "Supplementary measures may be needed"],
                )
            
            # Check for BCRs (intra-group transfers)
            if await self._has_binding_corporate_rules(destination):
                return TransferValidation(
                    allowed=True,
                    mechanism="binding_corporate_rules",
                    legal_basis="GDPR Article 46(2)(b)",
                )
        
        # Default: not allowed without explicit mechanism
        return TransferValidation(
            allowed=False,
            reason="No valid transfer mechanism established",
            remediation="Implement Standard Contractual Clauses or obtain adequacy decision",
        )
    
    async def enforce_residency(
        self,
        query_context: QueryContext,
    ) -> QueryContext:
        """
        Modify query context to enforce data residency requirements.
        
        Automatically routes queries to appropriate regional endpoints
        based on user jurisdiction and data type.
        """
        user_jurisdiction = await self._get_user_jurisdiction(query_context.user_id)
        
        # Add regional routing to query
        query_context.regional_endpoint = self.REGIONAL_ENDPOINTS[user_jurisdiction].endpoint
        query_context.allowed_regions = [self.REGIONAL_ENDPOINTS[user_jurisdiction].storage_location]
        
        # For cross-jurisdiction queries, validate each transfer
        if query_context.involves_foreign_data:
            for foreign_jurisdiction in query_context.foreign_jurisdictions:
                validation = await self.validate_transfer(
                    source=foreign_jurisdiction,
                    destination=user_jurisdiction,
                    data_type=query_context.data_type,
                    transfer_purpose=query_context.purpose,
                )
                if not validation.allowed:
                    query_context.blocked_jurisdictions.append(
                        BlockedJurisdiction(
                            jurisdiction=foreign_jurisdiction,
                            reason=validation.reason,
                        )
                    )
        
        return query_context
```

### **12.6 Audit Logging Service**

```python
class ComplianceAuditLogger:
    """
    Immutable audit logging for compliance requirements.
    
    Satisfies requirements across multiple regulations:
    - EU AI Act Article 19: Automatic logging, 6-month minimum retention
    - GDPR Article 30: Records of processing activities
    - SOC 2 Type II: Complete audit trail
    - HIPAA: 6-year retention for PHI access
    - ISO 27001: Security event logging
    """
    
    # Retention periods by jurisdiction and data type
    RETENTION_REQUIREMENTS = {
        (Jurisdiction.EU, "ai_decision"): timedelta(days=180),  # EU AI Act
        (Jurisdiction.EU, "personal_data"): timedelta(days=365),  # GDPR best practice
        (Jurisdiction.US_HIPAA, "phi"): timedelta(days=2190),  # 6 years
        (Jurisdiction.US_HIPAA, "phi_access"): timedelta(days=2190),
        (Jurisdiction.US_SOX, "financial"): timedelta(days=2555),  # 7 years
        (Jurisdiction.DEFAULT, "default"): timedelta(days=365),
    }
    
    def __init__(
        self,
        event_store: EventStore,
        encryption_service: EncryptionService,
        neo4j_client: Neo4jClient,
    ):
        self._events = event_store
        self._encryption = encryption_service
        self._neo4j = neo4j_client
    
    async def log(
        self,
        action: str,
        actor: AuditActor,
        resource: AuditResource,
        details: dict,
        jurisdiction: Jurisdiction,
        outcome: str = "success",
    ) -> AuditEntry:
        """
        Create an immutable audit log entry.
        
        Args:
            action: The action performed (e.g., "capsule.create", "user.login")
            actor: Who performed the action (user, system, overlay)
            resource: What was acted upon
            details: Additional context (changes, parameters, etc.)
            jurisdiction: Applicable jurisdiction (affects retention)
            outcome: Result of the action ("success", "failure", "denied")
            
        Returns:
            The created audit entry with integrity checksum
        """
        # Determine retention based on jurisdiction and resource type
        retention = self._calculate_retention(jurisdiction, resource.type)
        
        # Create entry with all required fields
        entry = AuditEntry(
            id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            action=action,
            actor=AuditActorRecord(
                type=actor.type,
                id=str(actor.id),
                email=actor.email if hasattr(actor, 'email') else None,
                ip_address=actor.ip_address,
                user_agent=actor.user_agent,
                session_id=str(actor.session_id) if actor.session_id else None,
            ),
            resource=AuditResourceRecord(
                type=resource.type,
                id=str(resource.id),
                name=resource.name,
                owner_id=str(resource.owner_id) if resource.owner_id else None,
            ),
            details=details,
            outcome=outcome,
            jurisdiction=jurisdiction,
            retention_until=datetime.now(timezone.utc) + retention,
            checksum=None,  # Will be set after all fields populated
        )
        
        # Calculate integrity checksum (tamper detection)
        entry.checksum = self._calculate_checksum(entry)
        
        # Encrypt sensitive fields before storage
        encrypted_entry = await self._encryption.encrypt_audit_entry(entry)
        
        # Store immutably in event store
        await self._events.append(
            stream_id="audit",
            event=AuditLogCreated(
                entry_id=entry.id,
                encrypted_data=encrypted_entry,
                checksum=entry.checksum,
                retention_until=entry.retention_until,
            )
        )
        
        # Also store in Neo4j for querying (without sensitive details)
        await self._store_searchable_record(entry)
        
        return entry
    
    def _calculate_retention(
        self,
        jurisdiction: Jurisdiction,
        resource_type: str,
    ) -> timedelta:
        """
        Calculate required retention period based on jurisdiction and data type.
        
        Uses the most restrictive requirement that applies.
        """
        # Check specific jurisdiction + type combinations
        key = (jurisdiction, resource_type)
        if key in self.RETENTION_REQUIREMENTS:
            return self.RETENTION_REQUIREMENTS[key]
        
        # Fall back to jurisdiction defaults
        jurisdiction_defaults = {
            Jurisdiction.EU: timedelta(days=180),  # EU AI Act minimum
            Jurisdiction.US_HIPAA: timedelta(days=2190),  # 6 years for PHI
            Jurisdiction.US_SOX: timedelta(days=2555),  # 7 years for financial
            Jurisdiction.CHINA: timedelta(days=1095),  # 3 years per PIPL
        }
        
        retention = jurisdiction_defaults.get(jurisdiction, timedelta(days=365))
        
        # Extend for specific resource types
        if resource_type == "phi" or resource_type == "health":
            retention = max(retention, timedelta(days=2190))
        elif resource_type == "financial":
            retention = max(retention, timedelta(days=2555))
        elif resource_type == "ai_decision":
            retention = max(retention, timedelta(days=180))
        
        return retention
    
    def _calculate_checksum(self, entry: AuditEntry) -> str:
        """
        Calculate tamper-detection checksum.
        
        Uses SHA-256 over canonicalized entry data.
        """
        # Exclude checksum field from calculation
        data = entry.model_dump(exclude={"checksum"})
        # Canonicalize with sorted keys for reproducibility
        canonical = json.dumps(data, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
    
    async def verify_integrity(self, entry_id: UUID) -> IntegrityResult:
        """
        Verify an audit entry has not been tampered with.
        
        Used during compliance audits to prove log integrity.
        """
        # Retrieve and decrypt entry
        entry = await self._get_entry(entry_id)
        
        # Recalculate checksum
        expected_checksum = self._calculate_checksum(entry)
        
        return IntegrityResult(
            valid=entry.checksum == expected_checksum,
            entry_id=entry_id,
            stored_checksum=entry.checksum,
            calculated_checksum=expected_checksum,
            verified_at=datetime.now(timezone.utc),
        )
    
    async def query_audit_trail(
        self,
        filters: AuditQueryFilters,
        page: int = 1,
        per_page: int = 50,
    ) -> AuditQueryResult:
        """
        Query audit trail with compliance-friendly filters.
        
        Supports queries like:
        - All actions by user X in date range
        - All access to resource Y
        - All failed authentication attempts
        - All AI decisions affecting user Z
        """
        async with self._neo4j.session() as session:
            # Build Cypher query from filters
            query, params = self._build_audit_query(filters, page, per_page)
            result = await session.run(query, params)
            records = await result.data()
        
        return AuditQueryResult(
            entries=[self._decrypt_record(r) for r in records],
            total=await self._count_matching(filters),
            page=page,
            per_page=per_page,
        )
    
    async def generate_compliance_report(
        self,
        report_type: ComplianceReportType,
        date_range: tuple[datetime, datetime],
        jurisdiction: Jurisdiction,
    ) -> ComplianceReport:
        """
        Generate compliance-ready audit report.
        
        Report types:
        - GDPR_PROCESSING_ACTIVITIES: Article 30 records
        - EU_AI_ACT_LOGGING: Article 19 AI system logs
        - HIPAA_ACCESS: PHI access audit
        - SOC2_SECURITY: Security event summary
        """
        if report_type == ComplianceReportType.GDPR_PROCESSING_ACTIVITIES:
            return await self._generate_gdpr_ropa(date_range, jurisdiction)
        elif report_type == ComplianceReportType.EU_AI_ACT_LOGGING:
            return await self._generate_ai_act_report(date_range)
        elif report_type == ComplianceReportType.HIPAA_ACCESS:
            return await self._generate_hipaa_access_report(date_range)
        elif report_type == ComplianceReportType.SOC2_SECURITY:
            return await self._generate_soc2_report(date_range)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
```

---


## **13. Security Architecture**

### **13.1 Security Layers Overview**

The Forge security architecture implements defense in depth with multiple overlapping layers. Each layer provides independent protection, so a breach at one layer does not compromise the entire system.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PERIMETER SECURITY                                                          │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │    WAF      │  │   DDoS      │  │  Rate       │  │    TLS      │       │
│  │  (OWASP)    │  │ Protection  │  │  Limiting   │  │    1.3      │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
│  Features:                                                                  │
│  • OWASP Core Rule Set for common attack patterns                          │
│  • Anycast-based DDoS mitigation at edge                                   │
│  • Token bucket rate limiting per IP and API key                           │
│  • TLS 1.3 only, no legacy cipher suites                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AUTHENTICATION LAYER                                                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Multi-Factor Authentication                                          │   │
│  │                                                                      │   │
│  │ • Factor 1: Password (Argon2id hashed) or API Key                   │   │
│  │ • Factor 2: TOTP / WebAuthn (FIDO2) / SMS (backup only)             │   │
│  │ • Factor 3: Device fingerprint (risk-based, optional)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Session Management                                                   │   │
│  │                                                                      │   │
│  │ • JWT access tokens (15-minute expiry)                              │   │
│  │ • Refresh tokens (7-day expiry, rotation on every use)              │   │
│  │ • Session binding to IP range and device fingerprint                │   │
│  │ • Concurrent session limits per user (configurable)                 │   │
│  │ • Automatic session invalidation on password change                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AUTHORIZATION LAYER                                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Hybrid RBAC + ABAC                                                   │   │
│  │                                                                      │   │
│  │ Role-Based Access Control (RBAC):                                   │   │
│  │ • admin: Full system access, user management, compliance            │   │
│  │ • operator: Overlay management, governance, monitoring              │   │
│  │ • user: Capsule CRUD, voting, limited governance                    │   │
│  │ • viewer: Read-only access to capsules and proposals                │   │
│  │                                                                      │   │
│  │ Attribute-Based Access Control (ABAC):                              │   │
│  │ • Trust level constraints (can only access at or below own level)   │   │
│  │ • Resource ownership (own vs shared vs public resources)            │   │
│  │ • Time-based restrictions (maintenance windows, etc.)               │   │
│  │ • Jurisdiction-based access (data residency enforcement)            │   │
│  │ • IP allowlist (enterprise feature)                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ DATA PROTECTION LAYER                                                       │
│                                                                             │
│  At Rest:                          In Transit:                             │
│  • AES-256-GCM encryption          • TLS 1.3 required everywhere           │
│  • HSM-backed key management       • Certificate pinning for mobile        │
│  • Field-level encryption (PII)    • Perfect forward secrecy (ECDHE)       │
│  • Tokenization for identifiers    • mTLS for service-to-service           │
│  • Encrypted backups               • No HTTP fallback                      │
│                                                                             │
│  Key Management:                   Secrets Management:                     │
│  • AWS KMS / HashiCorp Vault       • No secrets in code or config files    │
│  • Automatic key rotation (90d)    • Environment variable injection        │
│  • Separate keys per tenant        • Audit all secret access               │
│  • Key versioning for rotation     • Short-lived credentials preferred     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### **13.2 Authentication Implementation**

```python
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
import secrets
import jwt
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4


class AuthenticationService:
    """
    Authentication service with MFA support.
    
    Supports multiple authentication methods:
    - Password authentication (Argon2id)
    - API key authentication
    - OAuth 2.0 / OIDC
    - WebAuthn (FIDO2) for passwordless
    - TOTP second factor
    
    Security features:
    - Timing-safe comparisons
    - Brute force protection via rate limiting
    - Account lockout after failed attempts
    - Credential stuffing detection
    """
    
    def __init__(
        self,
        user_repo: UserRepository,
        session_store: SessionStore,
        mfa_service: MFAService,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
    ):
        self._users = user_repo
        self._sessions = session_store
        self._mfa = mfa_service
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        
        # Argon2id parameters per OWASP recommendations
        # https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
        self._hasher = PasswordHasher(
            time_cost=3,           # Number of iterations
            memory_cost=65536,     # 64 MB memory usage
            parallelism=4,         # Parallel threads
            hash_len=32,           # Output hash length
            salt_len=16,           # Salt length
            type=Type.ID,          # Argon2id variant (hybrid)
        )
    
    async def authenticate_password(
        self,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> AuthResult:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email address
            password: Plaintext password (will be hashed for comparison)
            ip_address: Client IP for rate limiting and logging
            user_agent: Client user agent for session binding
            
        Returns:
            AuthResult with tokens or MFA challenge
            
        Raises:
            RateLimitExceeded: Too many authentication attempts
            AuthenticationFailed: Invalid credentials
            AccountLocked: Account locked due to failed attempts
        """
        # Check rate limit by IP (prevents brute force)
        if not await self._check_rate_limit(ip_address):
            await self._log_auth_event("rate_limited", email, ip_address, success=False)
            raise RateLimitExceeded("Too many authentication attempts. Try again later.")
        
        # Find user by email
        user = await self._users.get_by_email(email.lower().strip())
        
        if not user:
            # IMPORTANT: Still hash a dummy password to prevent timing attacks
            # that could enumerate valid email addresses
            self._hasher.hash("dummy_password_for_timing_safety")
            await self._log_auth_event("user_not_found", email, ip_address, success=False)
            raise AuthenticationFailed("Invalid email or password")
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            await self._log_auth_event("account_locked", email, ip_address, success=False)
            raise AccountLocked(
                f"Account locked until {user.locked_until.isoformat()}"
            )
        
        # Verify password
        try:
            self._hasher.verify(user.password_hash, password)
        except VerifyMismatchError:
            # Record failed attempt
            await self._record_failed_attempt(user.id, ip_address)
            await self._log_auth_event("invalid_password", email, ip_address, success=False)
            raise AuthenticationFailed("Invalid email or password")
        
        # Check if password hash needs upgrade (parameters changed)
        if self._hasher.check_needs_rehash(user.password_hash):
            new_hash = self._hasher.hash(password)
            await self._users.update_password_hash(user.id, new_hash)
        
        # Clear failed attempts on successful password verification
        await self._users.clear_failed_attempts(user.id)
        
        # Check if MFA is required
        if user.mfa_enabled:
            challenge = await self._mfa.create_challenge(user.id)
            await self._log_auth_event("mfa_required", email, ip_address, success=True)
            return AuthResult(
                requires_mfa=True,
                mfa_challenge_id=challenge.id,
                mfa_methods=user.mfa_methods,
            )
        
        # No MFA required - create session directly
        session = await self._create_session(user, ip_address, user_agent, mfa_verified=False)
        await self._log_auth_event("login_success", email, ip_address, success=True)
        
        return AuthResult(
            requires_mfa=False,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=900,  # 15 minutes in seconds
            token_type="Bearer",
        )
    
    async def verify_mfa(
        self,
        challenge_id: UUID,
        code: str,
        ip_address: str,
        user_agent: str,
    ) -> AuthResult:
        """
        Verify MFA code and complete authentication.
        
        Args:
            challenge_id: The MFA challenge ID from initial auth
            code: The TOTP code or WebAuthn response
            ip_address: Client IP for session binding
            user_agent: Client user agent
            
        Returns:
            AuthResult with tokens
            
        Raises:
            AuthenticationFailed: Invalid or expired MFA challenge/code
        """
        # Retrieve challenge
        challenge = await self._mfa.get_challenge(challenge_id)
        
        if not challenge:
            raise AuthenticationFailed("Invalid MFA challenge")
        
        if challenge.expired:
            raise AuthenticationFailed("MFA challenge expired. Please log in again.")
        
        if challenge.attempts >= 3:
            # Too many failed MFA attempts
            await self._mfa.invalidate_challenge(challenge_id)
            raise AuthenticationFailed("Too many failed MFA attempts. Please log in again.")
        
        # Get user for verification
        user = await self._users.get_by_id(challenge.user_id)
        
        # Verify the code
        valid = await self._mfa.verify_code(user, code)
        
        if not valid:
            await self._mfa.record_failed_attempt(challenge_id)
            await self._log_auth_event("mfa_failed", user.email, ip_address, success=False)
            raise AuthenticationFailed("Invalid MFA code")
        
        # MFA verified - create session with mfa_verified flag
        session = await self._create_session(user, ip_address, user_agent, mfa_verified=True)
        await self._log_auth_event("mfa_success", user.email, ip_address, success=True)
        
        # Invalidate the challenge
        await self._mfa.invalidate_challenge(challenge_id)
        
        return AuthResult(
            requires_mfa=False,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=900,
            token_type="Bearer",
        )
    
    async def authenticate_api_key(
        self,
        api_key: str,
        ip_address: str,
    ) -> AuthResult:
        """
        Authenticate using API key.
        
        API keys are used for programmatic access (CLI, integrations).
        They bypass MFA but may have restricted permissions.
        """
        # Hash the key for lookup (keys stored hashed)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find the key
        key_record = await self._users.get_api_key(key_hash)
        
        if not key_record:
            raise AuthenticationFailed("Invalid API key")
        
        if key_record.revoked:
            raise AuthenticationFailed("API key has been revoked")
        
        if key_record.expires_at and key_record.expires_at < datetime.now(timezone.utc):
            raise AuthenticationFailed("API key has expired")
        
        # Check IP allowlist if configured
        if key_record.allowed_ips and ip_address not in key_record.allowed_ips:
            await self._log_auth_event(
                "api_key_ip_rejected", 
                key_record.user_id, 
                ip_address, 
                success=False
            )
            raise AuthenticationFailed("API key not allowed from this IP")
        
        # Get the associated user
        user = await self._users.get_by_id(key_record.user_id)
        
        # Update last used timestamp
        await self._users.update_api_key_last_used(key_record.id)
        
        # Create access token with API key scope limitations
        access_token = self._create_api_key_token(user, key_record)
        
        await self._log_auth_event("api_key_auth", user.email, ip_address, success=True)
        
        return AuthResult(
            requires_mfa=False,
            access_token=access_token,
            refresh_token=None,  # API keys don't get refresh tokens
            expires_in=3600,  # 1 hour for API key sessions
            token_type="Bearer",
        )
    
    async def refresh_session(
        self,
        refresh_token: str,
        ip_address: str,
        user_agent: str,
    ) -> AuthResult:
        """
        Refresh an expired access token using a refresh token.
        
        Implements refresh token rotation: each refresh invalidates
        the old refresh token and issues a new one.
        """
        # Hash for lookup
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Find session by refresh token
        session = await self._sessions.get_by_refresh_token(token_hash)
        
        if not session:
            raise AuthenticationFailed("Invalid refresh token")
        
        if session.refresh_token_used:
            # Refresh token reuse detected - possible token theft
            # Invalidate all sessions for this user as a precaution
            await self._sessions.invalidate_all_for_user(session.user_id)
            await self._log_auth_event(
                "refresh_token_reuse_detected",
                session.user_id,
                ip_address,
                success=False,
            )
            raise AuthenticationFailed("Session invalidated due to security concern")
        
        if session.expires_at < datetime.now(timezone.utc):
            raise AuthenticationFailed("Refresh token expired. Please log in again.")
        
        # Get user
        user = await self._users.get_by_id(session.user_id)
        
        # Mark old refresh token as used (for reuse detection)
        await self._sessions.mark_refresh_token_used(session.id)
        
        # Create new session (rotation)
        new_session = await self._create_session(
            user, 
            ip_address, 
            user_agent, 
            mfa_verified=session.mfa_verified
        )
        
        return AuthResult(
            requires_mfa=False,
            access_token=new_session.access_token,
            refresh_token=new_session.refresh_token,
            expires_in=900,
            token_type="Bearer",
        )
    
    async def _create_session(
        self,
        user: User,
        ip_address: str,
        user_agent: str,
        mfa_verified: bool = False,
    ) -> Session:
        """Create a new authenticated session with tokens."""
        session_id = uuid4()
        
        # Generate JWT access token
        access_token_payload = {
            "sub": str(user.id),           # Subject (user ID)
            "sid": str(session_id),         # Session ID
            "email": user.email,
            "roles": user.roles,
            "trust": user.trust_level.value,
            "mfa": mfa_verified,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iss": "forge.example.com",
            "aud": "forge-api",
        }
        
        access_token = jwt.encode(
            access_token_payload,
            self._jwt_secret,
            algorithm=self._jwt_algorithm,
        )
        
        # Generate opaque refresh token
        refresh_token = secrets.token_urlsafe(32)
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Store session
        session = Session(
            id=session_id,
            user_id=user.id,
            access_token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
            refresh_token_hash=refresh_token_hash,
            refresh_token_used=False,
            ip_address=ip_address,
            user_agent=user_agent,
            mfa_verified=mfa_verified,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        await self._sessions.create(session)
        
        # Return tokens (not stored hashes)
        session.access_token = access_token
        session.refresh_token = refresh_token
        
        return session
    
    async def _check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP is within rate limits for authentication."""
        key = f"auth_rate:{ip_address}"
        current = await self._sessions.increment_counter(key, ttl=300)  # 5 min window
        return current <= 10  # Max 10 attempts per 5 minutes
    
    async def _record_failed_attempt(self, user_id: UUID, ip_address: str) -> None:
        """Record a failed authentication attempt and potentially lock account."""
        user = await self._users.get_by_id(user_id)
        
        new_count = user.failed_login_attempts + 1
        
        # Lock account after 5 failed attempts
        locked_until = None
        if new_count >= 5:
            # Progressive lockout: 5 min, 15 min, 1 hour, 24 hours
            lockout_minutes = [5, 15, 60, 1440][min(new_count - 5, 3)]
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        
        await self._users.update_failed_attempts(user_id, new_count, locked_until)
    
    async def _log_auth_event(
        self,
        event_type: str,
        identifier: str,
        ip_address: str,
        success: bool,
    ) -> None:
        """Log authentication event for security monitoring."""
        # This would integrate with the audit logging system
        pass
```

### **13.3 Authorization Implementation**

```python
class AuthorizationService:
    """
    Hybrid RBAC + ABAC authorization service.
    
    Combines:
    - Role-based access control for static permissions
    - Attribute-based access control for dynamic policies
    
    All authorization decisions are logged for audit compliance.
    """
    
    # Role permission definitions
    ROLE_PERMISSIONS = {
        "admin": {
            "capsule:*",           # Full capsule access
            "user:*",              # User management
            "overlay:*",           # Overlay management
            "governance:*",        # Full governance access
            "compliance:*",        # Compliance operations
            "system:*",            # System administration
        },
        "operator": {
            "capsule:read",
            "capsule:create",
            "capsule:update",
            "overlay:read",
            "overlay:create",
            "overlay:update",
            "overlay:invoke",
            "governance:*",
            "system:health",
            "system:metrics",
        },
        "user": {
            "capsule:read",
            "capsule:create",
            "capsule:update:own",   # Can only update own capsules
            "capsule:delete:own",   # Can only delete own capsules
            "governance:vote",
            "governance:propose",
            "governance:read",
        },
        "viewer": {
            "capsule:read",
            "governance:read",
        },
    }
    
    def __init__(
        self,
        audit_logger: ComplianceAuditLogger,
        policy_store: PolicyStore,
    ):
        self._audit = audit_logger
        self._policies = policy_store
    
    async def authorize(
        self,
        actor: User,
        action: str,
        resource: Optional[Resource] = None,
        context: Optional[dict] = None,
    ) -> AuthorizationResult:
        """
        Check if actor is authorized to perform action on resource.
        
        Args:
            actor: The user attempting the action
            action: The action being attempted (e.g., "capsule:update")
            resource: The resource being acted upon (optional for list operations)
            context: Additional context for ABAC rules (time, location, etc.)
            
        Returns:
            AuthorizationResult with decision and reasoning
        """
        context = context or {}
        
        # Step 1: Check if actor is quarantined (blocks all actions)
        if actor.trust_level == TrustLevel.QUARANTINE:
            result = AuthorizationResult(
                allowed=False,
                reason="User is quarantined and cannot perform any actions",
                policy="trust_level_check",
            )
            await self._log_decision(actor, action, resource, result)
            return result
        
        # Step 2: Check RBAC permissions
        rbac_result = self._check_rbac(actor.roles, action)
        if not rbac_result.allowed:
            await self._log_decision(actor, action, resource, rbac_result)
            return rbac_result
        
        # Step 3: Check ABAC policies if resource is provided
        if resource:
            abac_result = await self._check_abac(actor, action, resource, context)
            if not abac_result.allowed:
                await self._log_decision(actor, action, resource, abac_result)
                return abac_result
        
        # Step 4: Check custom policies from policy store
        custom_result = await self._check_custom_policies(actor, action, resource, context)
        if not custom_result.allowed:
            await self._log_decision(actor, action, resource, custom_result)
            return custom_result
        
        # All checks passed
        result = AuthorizationResult(allowed=True)
        await self._log_decision(actor, action, resource, result)
        return result
    
    def _check_rbac(self, roles: list[str], action: str) -> AuthorizationResult:
        """Check role-based permissions."""
        for role in roles:
            permissions = self.ROLE_PERMISSIONS.get(role, set())
            
            # Check exact match
            if action in permissions:
                return AuthorizationResult(
                    allowed=True,
                    policy="rbac",
                    matched_permission=action,
                )
            
            # Check wildcard match (e.g., "capsule:*" matches "capsule:read")
            action_parts = action.split(":")
            if len(action_parts) >= 1:
                wildcard = f"{action_parts[0]}:*"
                if wildcard in permissions:
                    return AuthorizationResult(
                        allowed=True,
                        policy="rbac",
                        matched_permission=wildcard,
                    )
            
            # Check global wildcard
            if "*" in permissions:
                return AuthorizationResult(
                    allowed=True,
                    policy="rbac",
                    matched_permission="*",
                )
        
        return AuthorizationResult(
            allowed=False,
            reason=f"No role grants permission for '{action}'",
            policy="rbac",
        )
    
    async def _check_abac(
        self,
        actor: User,
        action: str,
        resource: Resource,
        context: dict,
    ) -> AuthorizationResult:
        """Check attribute-based policies."""
        
        # Policy 1: Ownership check for ":own" actions
        if action.endswith(":own"):
            if not hasattr(resource, 'owner_id') or resource.owner_id != actor.id:
                return AuthorizationResult(
                    allowed=False,
                    reason="Action requires resource ownership",
                    policy="abac:ownership",
                )
        
        # Policy 2: Trust level hierarchy
        if hasattr(resource, 'trust_level') and resource.trust_level:
            actor_trust = actor.trust_level.numeric_value
            resource_trust = resource.trust_level.numeric_value
            
            if actor_trust < resource_trust:
                return AuthorizationResult(
                    allowed=False,
                    reason=f"Insufficient trust level. Required: {resource.trust_level.value}, "
                           f"Actual: {actor.trust_level.value}",
                    policy="abac:trust_level",
                )
        
        # Policy 3: Jurisdiction-based access
        if "jurisdiction" in context:
            if not await self._can_access_jurisdiction(actor, context["jurisdiction"]):
                return AuthorizationResult(
                    allowed=False,
                    reason=f"Not authorized for jurisdiction: {context['jurisdiction']}",
                    policy="abac:jurisdiction",
                )
        
        # Policy 4: Time-based restrictions
        if "time_restricted" in context:
            if not self._within_time_window(context["time_restricted"]):
                return AuthorizationResult(
                    allowed=False,
                    reason="Action not permitted outside allowed time window",
                    policy="abac:time_restriction",
                )
        
        # Policy 5: IP allowlist (enterprise feature)
        if actor.ip_allowlist and context.get("ip_address"):
            if context["ip_address"] not in actor.ip_allowlist:
                return AuthorizationResult(
                    allowed=False,
                    reason="Request not from allowed IP address",
                    policy="abac:ip_allowlist",
                )
        
        return AuthorizationResult(allowed=True, policy="abac")
    
    async def _check_custom_policies(
        self,
        actor: User,
        action: str,
        resource: Optional[Resource],
        context: dict,
    ) -> AuthorizationResult:
        """Check custom policies defined in the policy store."""
        policies = await self._policies.get_applicable_policies(action)
        
        for policy in policies:
            # Evaluate policy expression
            result = await policy.evaluate(
                actor=actor,
                action=action,
                resource=resource,
                context=context,
            )
            
            if not result.allowed:
                return AuthorizationResult(
                    allowed=False,
                    reason=result.reason,
                    policy=f"custom:{policy.name}",
                )
        
        return AuthorizationResult(allowed=True)
    
    async def _log_decision(
        self,
        actor: User,
        action: str,
        resource: Optional[Resource],
        result: AuthorizationResult,
    ) -> None:
        """Log authorization decision for audit trail."""
        await self._audit.log(
            action=f"authorization.{'granted' if result.allowed else 'denied'}",
            actor=AuditActor(type="user", id=actor.id, email=actor.email),
            resource=AuditResource(
                type=resource.__class__.__name__ if resource else "none",
                id=str(resource.id) if resource and hasattr(resource, 'id') else None,
            ),
            details={
                "attempted_action": action,
                "result": "allowed" if result.allowed else "denied",
                "policy": result.policy,
                "reason": result.reason,
            },
            jurisdiction=actor.jurisdiction or Jurisdiction.DEFAULT,
        )
```

### **13.4 Encryption Service**

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import base64
import os


class EncryptionService:
    """
    Data encryption service for Forge.
    
    Implements envelope encryption:
    1. Generate a unique Data Encryption Key (DEK) for each piece of data
    2. Encrypt data with DEK using AES-256-GCM
    3. Encrypt DEK with a Key Encryption Key (KEK) from KMS
    4. Store encrypted DEK alongside encrypted data
    
    This approach allows:
    - Efficient key rotation (only re-encrypt DEKs, not all data)
    - Per-tenant key isolation
    - Compliance with key management requirements
    """
    
    def __init__(self, kms_client: KMSClient, master_key_id: str):
        self._kms = kms_client
        self._master_key_id = master_key_id
    
    async def encrypt(
        self,
        plaintext: bytes,
        context: dict,
    ) -> EncryptedData:
        """
        Encrypt data using envelope encryption.
        
        Args:
            plaintext: The data to encrypt
            context: Encryption context (bound to the ciphertext)
                    If context doesn't match on decrypt, decryption fails.
                    Use for binding encryption to specific entity/purpose.
            
        Returns:
            EncryptedData containing ciphertext, wrapped key, and metadata
        """
        # Generate unique Data Encryption Key (256 bits)
        dek = os.urandom(32)
        
        # Generate unique IV/nonce (96 bits for GCM)
        iv = os.urandom(12)
        
        # Create AES-GCM cipher
        aesgcm = AESGCM(dek)
        
        # Serialize context as AAD (Additional Authenticated Data)
        # This binds the encryption to the context - tampering will fail auth
        aad = json.dumps(context, sort_keys=True).encode('utf-8')
        
        # Encrypt
        ciphertext = aesgcm.encrypt(iv, plaintext, aad)
        
        # Wrap DEK with KMS (KEK)
        wrapped_dek = await self._kms.encrypt(
            key_id=self._master_key_id,
            plaintext=dek,
            encryption_context=context,  # KMS also binds to context
        )
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            wrapped_key=wrapped_dek,
            context=context,
            algorithm="AES-256-GCM",
            kms_key_id=self._master_key_id,
        )
    
    async def decrypt(self, encrypted: EncryptedData) -> bytes:
        """
        Decrypt envelope-encrypted data.
        
        Args:
            encrypted: The encrypted data structure
            
        Returns:
            Decrypted plaintext bytes
            
        Raises:
            DecryptionError: If decryption or authentication fails
        """
        # Unwrap DEK from KMS
        try:
            dek = await self._kms.decrypt(
                ciphertext=encrypted.wrapped_key,
                encryption_context=encrypted.context,
            )
        except KMSError as e:
            raise DecryptionError(f"Failed to unwrap key: {e}")
        
        # Create AES-GCM cipher
        aesgcm = AESGCM(dek)
        
        # Serialize context as AAD (must match encryption)
        aad = json.dumps(encrypted.context, sort_keys=True).encode('utf-8')
        
        # Decrypt
        try:
            plaintext = aesgcm.decrypt(encrypted.iv, encrypted.ciphertext, aad)
        except Exception as e:
            raise DecryptionError(f"Decryption failed (authentication error): {e}")
        
        return plaintext
    
    async def encrypt_field(
        self,
        value: str,
        field_name: str,
        entity_id: UUID,
        entity_type: str,
    ) -> str:
        """
        Encrypt a single field value (for PII fields).
        
        Uses deterministic encryption for fields that need equality search,
        or standard encryption for other sensitive fields.
        
        Args:
            value: The field value to encrypt
            field_name: Name of the field being encrypted
            entity_id: ID of the entity this field belongs to
            entity_type: Type of entity (e.g., "user", "capsule")
            
        Returns:
            Base64-encoded encrypted value for storage
        """
        context = {
            "field": field_name,
            "entity_id": str(entity_id),
            "entity_type": entity_type,
        }
        
        encrypted = await self.encrypt(value.encode('utf-8'), context)
        
        # Serialize for storage as string
        serialized = {
            "c": base64.b64encode(encrypted.ciphertext).decode(),
            "iv": base64.b64encode(encrypted.iv).decode(),
            "k": base64.b64encode(encrypted.wrapped_key).decode(),
            "ctx": encrypted.context,
            "alg": encrypted.algorithm,
        }
        
        return base64.b64encode(json.dumps(serialized).encode()).decode()
    
    async def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a field-level encrypted value."""
        serialized = json.loads(base64.b64decode(encrypted_value))
        
        encrypted = EncryptedData(
            ciphertext=base64.b64decode(serialized["c"]),
            iv=base64.b64decode(serialized["iv"]),
            wrapped_key=base64.b64decode(serialized["k"]),
            context=serialized["ctx"],
            algorithm=serialized["alg"],
        )
        
        plaintext = await self.decrypt(encrypted)
        return plaintext.decode('utf-8')
    
    async def rotate_key(
        self,
        old_key_id: str,
        new_key_id: str,
        data_iterator: AsyncIterator[EncryptedData],
    ) -> RotationResult:
        """
        Rotate encryption key for a set of data.
        
        With envelope encryption, we only need to re-wrap DEKs,
        not re-encrypt all data. This is much faster.
        """
        rotated_count = 0
        failed_count = 0
        
        async for encrypted in data_iterator:
            try:
                # Decrypt DEK with old key
                dek = await self._kms.decrypt(
                    ciphertext=encrypted.wrapped_key,
                    encryption_context=encrypted.context,
                    key_id=old_key_id,
                )
                
                # Re-wrap DEK with new key
                new_wrapped = await self._kms.encrypt(
                    key_id=new_key_id,
                    plaintext=dek,
                    encryption_context=encrypted.context,
                )
                
                # Update the encrypted data record
                encrypted.wrapped_key = new_wrapped
                encrypted.kms_key_id = new_key_id
                await self._save_encrypted(encrypted)
                
                rotated_count += 1
            except Exception as e:
                failed_count += 1
                # Log but continue with others
        
        return RotationResult(
            rotated=rotated_count,
            failed=failed_count,
            new_key_id=new_key_id,
        )
```

### **13.5 Secret Management**

```python
class SecretManager:
    """
    Secret management for Forge.
    
    Principles:
    - Never store secrets in code, config files, or environment variables directly
    - Use a dedicated secret store (Vault, AWS Secrets Manager, etc.)
    - Short-lived credentials where possible
    - Audit all secret access
    - Rotate secrets regularly
    """
    
    def __init__(
        self,
        vault_client: VaultClient,
        cache_ttl: int = 300,  # 5 minutes
    ):
        self._vault = vault_client
        self._cache = TTLCache(ttl=cache_ttl)
    
    async def get_secret(
        self,
        path: str,
        version: Optional[int] = None,
    ) -> Secret:
        """
        Retrieve a secret from the secret store.
        
        Args:
            path: Path to the secret (e.g., "forge/prod/database/password")
            version: Specific version (None for latest)
            
        Returns:
            Secret object with value and metadata
        """
        cache_key = f"{path}:{version or 'latest'}"
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Fetch from Vault
        secret = await self._vault.read(path, version=version)
        
        if not secret:
            raise SecretNotFoundError(f"Secret not found: {path}")
        
        # Cache with TTL
        self._cache[cache_key] = secret
        
        return secret
    
    async def get_database_credentials(
        self,
        database: str,
        role: str = "readonly",
    ) -> DatabaseCredentials:
        """
        Get dynamic database credentials.
        
        Uses Vault's database secrets engine to generate
        short-lived credentials with automatic expiry.
        """
        creds = await self._vault.read(
            f"database/creds/{database}-{role}"
        )
        
        return DatabaseCredentials(
            username=creds["username"],
            password=creds["password"],
            ttl=creds["lease_duration"],
            lease_id=creds["lease_id"],
        )
    
    async def rotate_api_keys(self) -> RotationResult:
        """Rotate all Forge API keys."""
        # Implementation would rotate external service API keys
        pass
```

---


## **14. API Specification**

### **14.1 API Design Principles**

The Forge API is designed as a RESTful interface following industry best practices and enterprise requirements. The design principles below guide all API decisions.

**Resource-Oriented Design.** URLs represent resources (nouns), not actions (verbs). Use `/capsules/{id}` rather than `/getCapsule`. This enables a predictable, learnable API surface.

**Standard HTTP Semantics.** HTTP methods have consistent meaning across all endpoints:
- `GET` retrieves resources (safe, idempotent)
- `POST` creates new resources
- `PUT` replaces resources completely (idempotent)
- `PATCH` partially updates resources
- `DELETE` removes resources (idempotent)

**Consistent Response Envelope.** All responses follow the same structure with `data`, `meta`, and `errors` fields. This allows clients to handle responses uniformly.

**Comprehensive Error Responses.** Errors include machine-readable codes, human-readable messages, field-level details for validation errors, and documentation links.

**URL Path Versioning.** API version in the URL path (`/api/v1/`) rather than headers, enabling easier debugging and browser testing.

**Hypermedia Links.** Responses include `_links` for related resources, enabling API discoverability.

### **14.2 OpenAPI Specification**

```yaml
openapi: 3.1.0
info:
  title: Forge Cascade API
  version: 3.0.0
  description: |
    The Forge Cascade API provides programmatic access to the Institutional Memory Engine.
    
    ## Authentication
    
    All endpoints require authentication via one of:
    - **Bearer Token**: JWT access token in `Authorization: Bearer <token>` header
    - **API Key**: Key in `X-API-Key` header
    
    ## Rate Limits
    
    Rate limits are based on trust level:
    
    | Trust Level | Requests/minute | Requests/day |
    |-------------|-----------------|--------------|
    | CORE        | Unlimited       | Unlimited    |
    | TRUSTED     | 1000            | 100,000      |
    | STANDARD    | 100             | 10,000       |
    | SANDBOX     | 10              | 1,000        |
    
    Rate limit headers are included in all responses:
    - `X-RateLimit-Limit`: Maximum requests in window
    - `X-RateLimit-Remaining`: Requests remaining
    - `X-RateLimit-Reset`: Unix timestamp when limit resets
    
    ## Pagination
    
    List endpoints support cursor-based pagination:
    - `page`: Page number (1-indexed)
    - `per_page`: Items per page (default 20, max 100)
    - Response includes `meta.pagination` with total, pages, next/prev links
    
    ## Filtering
    
    List endpoints support filtering via query parameters.
    Multiple values for same parameter use comma separation.
    
  contact:
    name: Forge API Support
    email: api-support@forge.example.com
    url: https://docs.forge.example.com
  license:
    name: Proprietary
    url: https://forge.example.com/license
    
servers:
  - url: https://api.forge.example.com/v1
    description: Production
  - url: https://api.staging.forge.example.com/v1
    description: Staging
  - url: https://api.sandbox.forge.example.com/v1
    description: Sandbox (rate limited)

tags:
  - name: Capsules
    description: Knowledge capsule management
  - name: Users
    description: User account management
  - name: Governance
    description: Proposals and voting
  - name: Overlays
    description: Overlay registry and invocation
  - name: System
    description: System health and administration
  - name: Compliance
    description: Compliance and audit operations

paths:
  # =========================================================================
  # CAPSULE ENDPOINTS
  # =========================================================================
  
  /capsules:
    get:
      tags: [Capsules]
      operationId: listCapsules
      summary: List capsules
      description: |
        Retrieve a paginated list of capsules with optional filtering.
        Results are ordered by creation date descending by default.
      parameters:
        - name: type
          in: query
          description: Filter by capsule type
          schema:
            $ref: '#/components/schemas/CapsuleType'
        - name: trust_level
          in: query
          description: Filter by trust level (returns level and above)
          schema:
            $ref: '#/components/schemas/TrustLevel'
        - name: owner_id
          in: query
          description: Filter by owner user ID
          schema:
            type: string
            format: uuid
        - name: parent_id
          in: query
          description: Filter by parent capsule ID (direct children only)
          schema:
            type: string
            format: uuid
        - name: created_after
          in: query
          description: Filter capsules created after this timestamp
          schema:
            type: string
            format: date-time
        - name: created_before
          in: query
          description: Filter capsules created before this timestamp
          schema:
            type: string
            format: date-time
        - name: sort
          in: query
          description: Sort field and direction
          schema:
            type: string
            enum: [created_at, -created_at, updated_at, -updated_at, trust_level, -trust_level]
            default: -created_at
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PerPageParam'
      responses:
        '200':
          description: Paginated list of capsules
          content:
            application/json:
              schema:
                type: object
                required: [data, meta]
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Capsule'
                  meta:
                    $ref: '#/components/schemas/PaginationMeta'
                  _links:
                    $ref: '#/components/schemas/PaginationLinks'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '429':
          $ref: '#/components/responses/RateLimited'
    
    post:
      tags: [Capsules]
      operationId: createCapsule
      summary: Create a new capsule
      description: |
        Create a new knowledge capsule. The capsule inherits trust level from its
        parent (if specified) or defaults to STANDARD.
        
        Creating a capsule with a parent establishes a DERIVED_FROM relationship,
        enabling lineage tracking through the Isnad chain.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CapsuleCreate'
            examples:
              knowledge:
                summary: Knowledge capsule
                value:
                  content: "FastAPI is preferred for new Python services due to its async support and automatic OpenAPI generation."
                  type: knowledge
                  metadata:
                    source: architecture_decision
                    tags: ["python", "api", "standards"]
              derived:
                summary: Derived capsule with parent
                value:
                  content: "Extended guideline: Use Pydantic v2 models for all FastAPI request/response schemas."
                  type: knowledge
                  parent_id: "123e4567-e89b-12d3-a456-426614174000"
                  metadata:
                    extends: "fastapi-guideline"
      responses:
        '201':
          description: Capsule created successfully
          headers:
            Location:
              description: URL of the created capsule
              schema:
                type: string
                format: uri
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Capsule'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '422':
          $ref: '#/components/responses/ValidationError'

  /capsules/{capsule_id}:
    parameters:
      - name: capsule_id
        in: path
        required: true
        description: Unique identifier of the capsule
        schema:
          type: string
          format: uuid
    
    get:
      tags: [Capsules]
      operationId: getCapsule
      summary: Get a capsule by ID
      description: Retrieve detailed information about a specific capsule.
      responses:
        '200':
          description: Capsule details
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Capsule'
                  _links:
                    type: object
                    properties:
                      self:
                        type: string
                        format: uri
                      parent:
                        type: string
                        format: uri
                        description: Link to parent capsule (if exists)
                      lineage:
                        type: string
                        format: uri
                        description: Link to lineage endpoint
                      owner:
                        type: string
                        format: uri
        '404':
          $ref: '#/components/responses/NotFound'
    
    patch:
      tags: [Capsules]
      operationId: updateCapsule
      summary: Update a capsule
      description: |
        Partially update a capsule. Only provided fields are updated.
        
        Updating content creates a new version. The previous version remains
        accessible through the version history.
        
        Users can only update capsules they own unless they have admin privileges.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CapsuleUpdate'
      responses:
        '200':
          description: Capsule updated successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Capsule'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          $ref: '#/components/responses/ValidationError'
    
    delete:
      tags: [Capsules]
      operationId: deleteCapsule
      summary: Delete a capsule
      description: |
        Soft-delete a capsule. The capsule is marked as deleted but remains
        in the database for audit purposes. Hard deletion requires admin privileges.
        
        Deleting a capsule that has children (derived capsules) will orphan
        those children unless cascade deletion is specified.
      parameters:
        - name: cascade
          in: query
          description: Also delete all derived capsules
          schema:
            type: boolean
            default: false
      responses:
        '204':
          description: Capsule deleted successfully
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '409':
          description: Capsule has children and cascade not specified
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /capsules/{capsule_id}/lineage:
    get:
      tags: [Capsules]
      operationId: getCapsuleLineage
      summary: Get capsule lineage (Isnad)
      description: |
        Retrieve the complete ancestry chain for a capsule.
        
        The lineage follows DERIVED_FROM relationships backwards through
        the graph, returning all ancestors in order from immediate parent
        to oldest ancestor.
        
        This is the Isnad - the chain of transmission authenticating
        the capsule's provenance.
      parameters:
        - name: capsule_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: max_depth
          in: query
          description: Maximum depth of ancestry to return
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 10
        - name: include_content
          in: query
          description: Include full content of ancestors (default is summary only)
          schema:
            type: boolean
            default: false
      responses:
        '200':
          description: Lineage chain
          content:
            application/json:
              schema:
                type: object
                required: [data]
                properties:
                  data:
                    type: object
                    properties:
                      capsule_id:
                        type: string
                        format: uuid
                      lineage:
                        type: array
                        description: Ancestors ordered from parent to oldest
                        items:
                          $ref: '#/components/schemas/LineageEntry'
                      depth:
                        type: integer
                        description: Total depth of lineage
                      truncated:
                        type: boolean
                        description: True if lineage was truncated at max_depth
        '404':
          $ref: '#/components/responses/NotFound'

  /capsules/search:
    post:
      tags: [Capsules]
      operationId: searchCapsules
      summary: Semantic search for capsules
      description: |
        Search for capsules using natural language semantic similarity.
        
        The search uses vector embeddings to find capsules with similar
        meaning to the query, regardless of exact keyword matches.
        
        Results can be filtered and combined with lineage traversal
        for powerful hybrid queries.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [query]
              properties:
                query:
                  type: string
                  minLength: 1
                  maxLength: 10000
                  description: Natural language search query
                  example: "best practices for error handling in async Python"
                limit:
                  type: integer
                  minimum: 1
                  maximum: 100
                  default: 10
                  description: Maximum number of results
                min_score:
                  type: number
                  minimum: 0
                  maximum: 1
                  default: 0.7
                  description: Minimum similarity score (0-1)
                filters:
                  type: object
                  description: Additional filters to apply
                  properties:
                    type:
                      $ref: '#/components/schemas/CapsuleType'
                    trust_level:
                      $ref: '#/components/schemas/TrustLevel'
                    owner_id:
                      type: string
                      format: uuid
                    created_after:
                      type: string
                      format: date-time
                include_lineage:
                  type: boolean
                  default: false
                  description: Include lineage depth (1 level) in results
      responses:
        '200':
          description: Search results with similarity scores
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      type: object
                      properties:
                        capsule:
                          $ref: '#/components/schemas/Capsule'
                        score:
                          type: number
                          minimum: 0
                          maximum: 1
                          description: Semantic similarity score
                        lineage:
                          type: array
                          items:
                            $ref: '#/components/schemas/Capsule'
                          description: Parent capsule (if include_lineage true)
                  meta:
                    type: object
                    properties:
                      total:
                        type: integer
                      query_time_ms:
                        type: integer

  # =========================================================================
  # GOVERNANCE ENDPOINTS
  # =========================================================================
  
  /governance/proposals:
    get:
      tags: [Governance]
      operationId: listProposals
      summary: List governance proposals
      parameters:
        - name: status
          in: query
          schema:
            $ref: '#/components/schemas/ProposalStatus'
        - name: type
          in: query
          schema:
            $ref: '#/components/schemas/ProposalType'
        - name: proposer_id
          in: query
          schema:
            type: string
            format: uuid
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PerPageParam'
      responses:
        '200':
          description: List of proposals
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Proposal'
                  meta:
                    $ref: '#/components/schemas/PaginationMeta'
    
    post:
      tags: [Governance]
      operationId: createProposal
      summary: Create a governance proposal
      description: |
        Create a new proposal for community voting.
        
        Proposals must be activated before voting can begin.
        The proposer must have sufficient trust level for the proposal type.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProposalCreate'
      responses:
        '201':
          description: Proposal created
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Proposal'
        '403':
          description: Insufficient trust level for proposal type

  /governance/proposals/{proposal_id}:
    get:
      tags: [Governance]
      operationId: getProposal
      summary: Get proposal details
      parameters:
        - name: proposal_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Proposal details with current vote counts
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    allOf:
                      - $ref: '#/components/schemas/Proposal'
                      - type: object
                        properties:
                          votes_for:
                            type: number
                            description: Weighted votes in favor
                          votes_against:
                            type: number
                            description: Weighted votes against
                          votes_abstain:
                            type: number
                            description: Weighted abstentions
                          participation:
                            type: number
                            description: Percentage of eligible voters who voted
                          ai_analysis:
                            type: object
                            description: Constitutional AI analysis (advisory)
                            properties:
                              recommendation:
                                type: string
                                enum: [support, oppose, neutral]
                              reasoning:
                                type: string
                              concerns:
                                type: array
                                items:
                                  type: string
        '404':
          $ref: '#/components/responses/NotFound'

  /governance/proposals/{proposal_id}/vote:
    post:
      tags: [Governance]
      operationId: castVote
      summary: Cast a vote on a proposal
      description: |
        Cast or change your vote on an active proposal.
        
        Vote weight is determined by the voter's trust level.
        Votes can be changed until voting ends.
      parameters:
        - name: proposal_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [decision]
              properties:
                decision:
                  type: string
                  enum: [for, against, abstain]
                  description: Vote decision
                reasoning:
                  type: string
                  maxLength: 2000
                  description: Optional explanation for the vote
      responses:
        '201':
          description: Vote recorded
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    properties:
                      vote_id:
                        type: string
                        format: uuid
                      proposal_id:
                        type: string
                        format: uuid
                      decision:
                        type: string
                      weight:
                        type: number
                        description: Vote weight based on trust level
                      recorded_at:
                        type: string
                        format: date-time
        '400':
          description: Cannot vote (voting not active, already closed, etc.)
        '403':
          description: Not authorized to vote on this proposal

  # =========================================================================
  # OVERLAY ENDPOINTS
  # =========================================================================
  
  /overlays:
    get:
      tags: [Overlays]
      operationId: listOverlays
      summary: List registered overlays
      responses:
        '200':
          description: List of overlays
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Overlay'
    
    post:
      tags: [Overlays]
      operationId: registerOverlay
      summary: Register a new overlay
      description: |
        Submit a new overlay for registration.
        
        Overlays must pass security validation and community approval
        before being activated. The WASM binary is verified against
        the source hash.
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [manifest, wasm]
              properties:
                manifest:
                  type: string
                  format: binary
                  description: YAML manifest file
                wasm:
                  type: string
                  format: binary
                  description: Compiled WASM binary
                source_url:
                  type: string
                  format: uri
                  description: URL to source code repository
      responses:
        '202':
          description: Overlay submitted for review
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Overlay'
                  message:
                    type: string
                    example: "Overlay submitted for security review and community approval"

  /overlays/{overlay_id}/invoke:
    post:
      tags: [Overlays]
      operationId: invokeOverlay
      summary: Invoke an overlay function
      parameters:
        - name: overlay_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [function]
              properties:
                function:
                  type: string
                  description: Function name to invoke
                args:
                  type: object
                  description: Arguments to pass to function
                timeout_ms:
                  type: integer
                  minimum: 100
                  maximum: 30000
                  default: 5000
      responses:
        '200':
          description: Invocation result
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    description: Function return value
                  meta:
                    type: object
                    properties:
                      execution_time_ms:
                        type: integer
                      fuel_consumed:
                        type: integer
        '400':
          description: Invalid function or arguments
        '503':
          description: Overlay unavailable (quarantined, etc.)

  # =========================================================================
  # SYSTEM ENDPOINTS
  # =========================================================================
  
  /system/health:
    get:
      tags: [System]
      operationId: getHealth
      summary: Get system health status
      description: |
        Returns overall system health and component status.
        Does not require authentication.
      security: []
      responses:
        '200':
          description: System is healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [healthy, degraded, critical]
                  timestamp:
                    type: string
                    format: date-time
                  version:
                    type: string
                  components:
                    type: object
                    additionalProperties:
                      type: object
                      properties:
                        status:
                          type: string
                          enum: [healthy, degraded, critical]
                        latency_ms:
                          type: integer
                        message:
                          type: string

components:
  # =========================================================================
  # SCHEMAS
  # =========================================================================
  
  schemas:
    CapsuleType:
      type: string
      enum: [knowledge, code, decision, insight, config, policy]
      description: |
        Type of capsule content:
        - knowledge: Facts, documentation, information
        - code: Source code, algorithms, implementations
        - decision: Recorded decisions with rationale
        - insight: Patterns, observations, learned lessons
        - config: System configuration, settings
        - policy: Organizational rules, guidelines
    
    TrustLevel:
      type: string
      enum: [core, trusted, standard, sandbox, quarantine]
      description: |
        Trust level hierarchy:
        - core (100): System-critical, immune to quarantine
        - trusted (80): Verified reliable, full privileges
        - standard (60): Default level, normal operations
        - sandbox (40): Experimental, limited and monitored
        - quarantine (0): Blocked, no execution permitted
    
    ProposalStatus:
      type: string
      enum: [draft, active, closed, approved, rejected, executed, failed]
    
    ProposalType:
      type: string
      enum: [configuration, policy, trust_adjustment, overlay_registration, overlay_update, emergency]
    
    Capsule:
      type: object
      required: [id, content, type, version, owner_id, trust_level, created_at]
      properties:
        id:
          type: string
          format: uuid
        content:
          type: string
          minLength: 1
          maxLength: 1000000
        type:
          $ref: '#/components/schemas/CapsuleType'
        version:
          type: string
          pattern: '^\d+\.\d+\.\d+$'
          example: "1.0.0"
        parent_id:
          type: string
          format: uuid
          nullable: true
        owner_id:
          type: string
          format: uuid
        trust_level:
          $ref: '#/components/schemas/TrustLevel'
        metadata:
          type: object
          additionalProperties: true
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
    
    CapsuleCreate:
      type: object
      required: [content, type]
      properties:
        content:
          type: string
          minLength: 1
          maxLength: 1000000
        type:
          $ref: '#/components/schemas/CapsuleType'
        parent_id:
          type: string
          format: uuid
          description: Parent capsule ID for symbolic inheritance
        metadata:
          type: object
          additionalProperties: true
    
    CapsuleUpdate:
      type: object
      properties:
        content:
          type: string
          minLength: 1
          maxLength: 1000000
        metadata:
          type: object
          additionalProperties: true
    
    LineageEntry:
      type: object
      properties:
        capsule:
          $ref: '#/components/schemas/Capsule'
        relationship:
          type: object
          properties:
            type:
              type: string
              example: "DERIVED_FROM"
            reason:
              type: string
            timestamp:
              type: string
              format: date-time
        depth:
          type: integer
          description: Distance from queried capsule
    
    Proposal:
      type: object
      required: [id, title, type, status, proposer_id, created_at]
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
          maxLength: 200
        description:
          type: string
          maxLength: 10000
        type:
          $ref: '#/components/schemas/ProposalType'
        status:
          $ref: '#/components/schemas/ProposalStatus'
        proposer_id:
          type: string
          format: uuid
        payload:
          type: object
          description: Type-specific proposal data
        voting_starts_at:
          type: string
          format: date-time
        voting_ends_at:
          type: string
          format: date-time
        created_at:
          type: string
          format: date-time
    
    ProposalCreate:
      type: object
      required: [title, type, payload]
      properties:
        title:
          type: string
          maxLength: 200
        description:
          type: string
          maxLength: 10000
        type:
          $ref: '#/components/schemas/ProposalType'
        payload:
          type: object
        voting_duration_hours:
          type: integer
          minimum: 1
          maximum: 168
          default: 72
    
    Overlay:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        version:
          type: string
        description:
          type: string
        state:
          type: string
          enum: [pending, active, suspended, quarantined, deprecated]
        capabilities:
          type: array
          items:
            type: string
        trust_level:
          $ref: '#/components/schemas/TrustLevel'
        created_at:
          type: string
          format: date-time
    
    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          description: Machine-readable error code
          example: "validation_error"
        message:
          type: string
          description: Human-readable error message
        details:
          type: object
          description: Additional error context
        errors:
          type: array
          description: Field-level validation errors
          items:
            type: object
            properties:
              field:
                type: string
              message:
                type: string
              code:
                type: string
        documentation_url:
          type: string
          format: uri
          description: Link to relevant documentation
    
    PaginationMeta:
      type: object
      properties:
        total:
          type: integer
        page:
          type: integer
        per_page:
          type: integer
        pages:
          type: integer
    
    PaginationLinks:
      type: object
      properties:
        self:
          type: string
          format: uri
        first:
          type: string
          format: uri
        prev:
          type: string
          format: uri
          nullable: true
        next:
          type: string
          format: uri
          nullable: true
        last:
          type: string
          format: uri

  # =========================================================================
  # PARAMETERS
  # =========================================================================
  
  parameters:
    PageParam:
      name: page
      in: query
      description: Page number (1-indexed)
      schema:
        type: integer
        minimum: 1
        default: 1
    
    PerPageParam:
      name: per_page
      in: query
      description: Items per page
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 20

  # =========================================================================
  # RESPONSES
  # =========================================================================
  
  responses:
    BadRequest:
      description: Invalid request parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: bad_request
            message: "Invalid request parameters"
    
    Unauthorized:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: unauthorized
            message: "Authentication required"
    
    Forbidden:
      description: Insufficient permissions
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: forbidden
            message: "You do not have permission to perform this action"
    
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: not_found
            message: "The requested resource was not found"
    
    ValidationError:
      description: Request validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: validation_error
            message: "Request validation failed"
            errors:
              - field: content
                message: "Content is required"
                code: required
    
    RateLimited:
      description: Rate limit exceeded
      headers:
        X-RateLimit-Limit:
          schema:
            type: integer
        X-RateLimit-Remaining:
          schema:
            type: integer
        X-RateLimit-Reset:
          schema:
            type: integer
        Retry-After:
          schema:
            type: integer
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            code: rate_limited
            message: "Rate limit exceeded. Retry after 60 seconds."

  # =========================================================================
  # SECURITY
  # =========================================================================
  
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT access token from authentication
    
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: API key for programmatic access

security:
  - bearerAuth: []
  - apiKeyAuth: []
```

---


## **15. Web Dashboard Interface**

### **15.1 Design System**

The Forge web dashboard follows a professional, enterprise-grade design system optimized for data-dense interfaces while maintaining visual clarity and accessibility.

**Design Philosophy**

The dashboard prioritizes information density for power users while remaining approachable for newcomers. Dark mode is the default, reducing eye strain during extended use. The interface uses glassmorphism effects sparingly for depth without distraction.

**Color Palette**

```css
:root {
  /* =========================================
     BACKGROUND LAYERS (Dark Mode Default)
     ========================================= */
  --bg-base: #0A0A0A;           /* Deepest background */
  --bg-surface-1: #141414;       /* Cards, panels */
  --bg-surface-2: #1F1F1F;       /* Elevated elements */
  --bg-surface-3: #2A2A2A;       /* Highest elevation */
  
  /* Light mode overrides */
  --bg-base-light: #FFFFFF;
  --bg-surface-1-light: #F9FAFB;
  --bg-surface-2-light: #F3F4F6;
  --bg-surface-3-light: #E5E7EB;
  
  /* =========================================
     TEXT HIERARCHY
     ========================================= */
  --text-primary: #FAFAFA;       /* Headings, important text */
  --text-secondary: #A1A1AA;     /* Body text */
  --text-muted: #71717A;         /* Captions, hints */
  --text-disabled: #52525B;      /* Disabled states */
  
  /* =========================================
     ACCENT COLORS
     ========================================= */
  --accent-primary: #3B82F6;     /* Blue - primary actions */
  --accent-primary-hover: #2563EB;
  --accent-success: #22C55E;     /* Green - positive states */
  --accent-warning: #F59E0B;     /* Amber - caution states */
  --accent-error: #EF4444;       /* Red - error states */
  --accent-info: #06B6D4;        /* Cyan - informational */
  
  /* =========================================
     TRUST LEVEL INDICATORS
     ========================================= */
  --trust-core: #A855F7;         /* Purple - highest trust */
  --trust-trusted: #22C55E;      /* Green */
  --trust-standard: #3B82F6;     /* Blue */
  --trust-sandbox: #F59E0B;      /* Amber */
  --trust-quarantine: #EF4444;   /* Red - lowest trust */
  
  /* =========================================
     GLASSMORPHISM EFFECTS
     ========================================= */
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-blur: 12px;
  
  /* =========================================
     SHADOWS
     ========================================= */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-glow: 0 0 20px rgba(59, 130, 246, 0.3);
}
```

**Typography System**

```css
:root {
  /* Font families */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  
  /* Font sizes (using fluid typography) */
  --text-xs: clamp(0.7rem, 0.65rem + 0.25vw, 0.75rem);     /* 11-12px */
  --text-sm: clamp(0.8rem, 0.75rem + 0.25vw, 0.875rem);    /* 13-14px */
  --text-base: clamp(0.9rem, 0.85rem + 0.25vw, 1rem);      /* 14-16px */
  --text-lg: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);      /* 16-18px */
  --text-xl: clamp(1.1rem, 1rem + 0.5vw, 1.25rem);         /* 18-20px */
  --text-2xl: clamp(1.3rem, 1.2rem + 0.5vw, 1.5rem);       /* 21-24px */
  --text-3xl: clamp(1.6rem, 1.4rem + 1vw, 1.875rem);       /* 26-30px */
  --text-4xl: clamp(2rem, 1.7rem + 1.5vw, 2.25rem);        /* 32-36px */
  
  /* Line heights */
  --leading-none: 1;
  --leading-tight: 1.25;
  --leading-snug: 1.375;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --leading-loose: 2;
  
  /* Letter spacing */
  --tracking-tighter: -0.05em;
  --tracking-tight: -0.025em;
  --tracking-normal: 0;
  --tracking-wide: 0.025em;
  --tracking-wider: 0.05em;
}
```

**Spacing System**

```css
:root {
  /* Base unit: 4px */
  --space-px: 1px;
  --space-0: 0;
  --space-0.5: 0.125rem;   /* 2px */
  --space-1: 0.25rem;      /* 4px */
  --space-1.5: 0.375rem;   /* 6px */
  --space-2: 0.5rem;       /* 8px */
  --space-2.5: 0.625rem;   /* 10px */
  --space-3: 0.75rem;      /* 12px */
  --space-3.5: 0.875rem;   /* 14px */
  --space-4: 1rem;         /* 16px */
  --space-5: 1.25rem;      /* 20px */
  --space-6: 1.5rem;       /* 24px */
  --space-7: 1.75rem;      /* 28px */
  --space-8: 2rem;         /* 32px */
  --space-9: 2.25rem;      /* 36px */
  --space-10: 2.5rem;      /* 40px */
  --space-12: 3rem;        /* 48px */
  --space-14: 3.5rem;      /* 56px */
  --space-16: 4rem;        /* 64px */
  --space-20: 5rem;        /* 80px */
  --space-24: 6rem;        /* 96px */
}
```

### **15.2 Application Shell Architecture**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       WEB DASHBOARD ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER BAR (64px height, sticky)                                            │
│                                                                             │
│ ┌──────────┐ ┌────────────────────────────────┐ ┌────┐ ┌────┐ ┌──────────┐ │
│ │   Logo   │ │   Command Palette (⌘K)         │ │ 🔔 │ │ ❓ │ │  Avatar  │ │
│ │   Forge  │ │   Search capsules, commands... │ │    │ │    │ │  Menu    │ │
│ └──────────┘ └────────────────────────────────┘ └────┘ └────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────┐ ┌──────────────────────────────────────────────────────────┐
│ SIDEBAR        │ │ MAIN CONTENT AREA                                        │
│ (256px, collap)│ │                                                          │
│                │ │ ┌──────────────────────────────────────────────────────┐ │
│ ┌────────────┐ │ │ │ PAGE HEADER                                          │ │
│ │ Navigation │ │ │ │                                                      │ │
│ │            │ │ │ │ ┌──────────────────┐  ┌─────────────────────────┐   │ │
│ │ ○ Dashboard│ │ │ │ │ Title + Breadcrumb│  │ Action Buttons          │   │ │
│ │ ○ Capsules │ │ │ │ └──────────────────┘  └─────────────────────────┘   │ │
│ │ ○ Governance│ │ │ └──────────────────────────────────────────────────────┘ │
│ │ ○ Overlays │ │ │                                                          │
│ │ ○ System   │ │ │ ┌──────────────────────────────────────────────────────┐ │
│ │ ○ Settings │ │ │ │ CONTENT                                              │ │
│ │            │ │ │ │                                                      │ │
│ └────────────┘ │ │ │ (Tables, Cards, Graphs, Forms, Modals)              │ │
│                │ │ │                                                      │ │
│ ┌────────────┐ │ │ │                                                      │ │
│ │ Quick Stats│ │ │ │                                                      │ │
│ │            │ │ │ │                                                      │ │
│ │ Capsules:  │ │ │ │                                                      │ │
│ │ 12,345     │ │ │ │                                                      │ │
│ │            │ │ │ │                                                      │ │
│ │ Proposals: │ │ │ │                                                      │ │
│ │ 5 active   │ │ │ │                                                      │ │
│ └────────────┘ │ │ │                                                      │ │
│                │ │ └──────────────────────────────────────────────────────┘ │
│ ┌────────────┐ │ │                                                          │
│ │Trust Level │ │ │                                                          │
│ │ ● TRUSTED  │ │ │                                                          │
│ └────────────┘ │ │                                                          │
└────────────────┘ └──────────────────────────────────────────────────────────┘
```

### **15.3 Key Views Implementation**

**Dashboard Overview**

The main dashboard provides at-a-glance system status and actionable items.

```typescript
// Dashboard view type definitions
interface DashboardView {
  // System health card
  systemHealth: {
    status: 'healthy' | 'degraded' | 'critical';
    uptime: string;
    lastIncident: Date | null;
    components: ComponentHealth[];
  };
  
  // Key metrics row
  metrics: {
    capsuleCount: number;
    capsuleTrend: number;  // % change from last period
    activeOverlays: number;
    overlayHealth: number;  // % healthy
    pendingProposals: number;
    votingDeadlines: Date[];
    averageLatency: number;
    latencyTrend: number;
  };
  
  // Activity feed
  recentActivity: ActivityItem[];
  
  // Action items requiring attention
  actionItems: {
    pendingVotes: Proposal[];
    failingOverlays: Overlay[];
    expiringCapsules: Capsule[];
    complianceAlerts: ComplianceAlert[];
  };
}

// Dashboard component
export function Dashboard() {
  const { data: health } = useQuery(['system', 'health'], fetchSystemHealth);
  const { data: metrics } = useQuery(['metrics', 'overview'], fetchMetrics);
  const { data: activity } = useQuery(['activity', 'recent'], fetchActivity);
  const { data: proposals } = useQuery(['proposals', 'pending'], fetchPendingProposals);
  
  return (
    <div className="space-y-6">
      {/* System Health Banner */}
      <SystemHealthBanner health={health} />
      
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Capsules"
          value={metrics?.capsuleCount}
          trend={metrics?.capsuleTrend}
          icon={<DatabaseIcon />}
        />
        <MetricCard
          title="Active Overlays"
          value={metrics?.activeOverlays}
          health={metrics?.overlayHealth}
          icon={<CpuIcon />}
        />
        <MetricCard
          title="Pending Votes"
          value={proposals?.length}
          urgency={getVotingUrgency(proposals)}
          icon={<VoteIcon />}
        />
        <MetricCard
          title="API Latency"
          value={`${metrics?.averageLatency}ms`}
          trend={metrics?.latencyTrend}
          icon={<ActivityIcon />}
        />
      </div>
      
      {/* Two-column layout: Activity + Action Items */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ActivityFeed activities={activity} />
        </div>
        <div>
          <ActionItemsPanel
            proposals={proposals}
            alerts={health?.alerts}
          />
        </div>
      </div>
    </div>
  );
}
```

**Capsule Explorer**

A searchable, filterable interface for browsing and managing capsules with lineage visualization.

```typescript
interface CapsuleExplorerState {
  // Search and filters
  searchQuery: string;
  semanticSearch: boolean;  // Toggle between text and semantic search
  filters: {
    types: CapsuleType[];
    trustLevels: TrustLevel[];
    dateRange: [Date | null, Date | null];
    owners: string[];
    hasParent: boolean | null;
  };
  
  // View mode
  viewMode: 'list' | 'grid' | 'lineage';
  
  // Results
  capsules: Capsule[];
  isLoading: boolean;
  pagination: {
    page: number;
    perPage: number;
    total: number;
  };
  
  // Selection
  selectedCapsule: Capsule | null;
  selectedCapsules: Set<string>;  // For bulk actions
  
  // Lineage view
  lineageView: {
    enabled: boolean;
    rootCapsuleId: string | null;
    depth: number;
    expandedNodes: Set<string>;
  };
}

export function CapsuleExplorer() {
  const [state, dispatch] = useReducer(capsuleExplorerReducer, initialState);
  
  // Fetch capsules with current filters
  const { data, isLoading } = useQuery(
    ['capsules', state.filters, state.pagination],
    () => fetchCapsules({
      query: state.semanticSearch ? undefined : state.searchQuery,
      semanticQuery: state.semanticSearch ? state.searchQuery : undefined,
      ...state.filters,
      page: state.pagination.page,
      perPage: state.pagination.perPage,
    })
  );
  
  return (
    <div className="flex flex-col h-full">
      {/* Search and Filter Bar */}
      <div className="flex items-center gap-4 p-4 border-b border-glass-border">
        <SearchInput
          value={state.searchQuery}
          onChange={(q) => dispatch({ type: 'SET_SEARCH', query: q })}
          placeholder="Search capsules..."
          semantic={state.semanticSearch}
          onToggleSemantic={() => dispatch({ type: 'TOGGLE_SEMANTIC' })}
        />
        <FilterDropdowns
          filters={state.filters}
          onChange={(f) => dispatch({ type: 'SET_FILTERS', filters: f })}
        />
        <ViewModeToggle
          mode={state.viewMode}
          onChange={(m) => dispatch({ type: 'SET_VIEW_MODE', mode: m })}
        />
      </div>
      
      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden flex">
        {/* Capsule List/Grid */}
        <div className={cn(
          "flex-1 overflow-auto p-4",
          state.selectedCapsule && "lg:w-2/3"
        )}>
          {state.viewMode === 'lineage' ? (
            <LineageGraph
              rootId={state.lineageView.rootCapsuleId}
              depth={state.lineageView.depth}
              onNodeClick={(id) => dispatch({ type: 'SELECT_CAPSULE', id })}
            />
          ) : state.viewMode === 'grid' ? (
            <CapsuleGrid
              capsules={data?.capsules}
              selected={state.selectedCapsules}
              onSelect={(id) => dispatch({ type: 'TOGGLE_SELECT', id })}
              onClick={(id) => dispatch({ type: 'SELECT_CAPSULE', id })}
            />
          ) : (
            <CapsuleTable
              capsules={data?.capsules}
              selected={state.selectedCapsules}
              onSelect={(id) => dispatch({ type: 'TOGGLE_SELECT', id })}
              onClick={(id) => dispatch({ type: 'SELECT_CAPSULE', id })}
              sortable
            />
          )}
        </div>
        
        {/* Detail Panel (slides in when capsule selected) */}
        {state.selectedCapsule && (
          <CapsuleDetailPanel
            capsule={state.selectedCapsule}
            onClose={() => dispatch({ type: 'CLEAR_SELECTION' })}
            onViewLineage={() => dispatch({ 
              type: 'VIEW_LINEAGE', 
              rootId: state.selectedCapsule.id 
            })}
          />
        )}
      </div>
      
      {/* Pagination */}
      <Pagination
        page={state.pagination.page}
        perPage={state.pagination.perPage}
        total={data?.total || 0}
        onChange={(page) => dispatch({ type: 'SET_PAGE', page })}
      />
    </div>
  );
}
```

**Lineage Visualization Component**

Interactive graph showing capsule ancestry using D3.js force-directed layout.

```typescript
import { useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';

interface LineageGraphProps {
  rootId: string;
  depth: number;
  onNodeClick: (capsuleId: string) => void;
  onNodeHover?: (capsule: Capsule | null) => void;
}

export function LineageGraph({ rootId, depth, onNodeClick, onNodeHover }: LineageGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Fetch lineage data
  const { data: lineage } = useQuery(
    ['lineage', rootId, depth],
    () => fetchLineage(rootId, depth)
  );
  
  // Transform lineage data into D3 graph format
  const graphData = useMemo(() => {
    if (!lineage) return { nodes: [], links: [] };
    
    const nodes: LineageNode[] = [];
    const links: LineageLink[] = [];
    const nodeMap = new Map<string, boolean>();
    
    // Add root node
    nodes.push({
      id: lineage.capsule.id,
      capsule: lineage.capsule,
      depth: 0,
      isRoot: true,
    });
    nodeMap.set(lineage.capsule.id, true);
    
    // Add ancestors
    lineage.ancestors.forEach((ancestor, index) => {
      if (!nodeMap.has(ancestor.id)) {
        nodes.push({
          id: ancestor.id,
          capsule: ancestor,
          depth: index + 1,
          isRoot: false,
        });
        nodeMap.set(ancestor.id, true);
      }
      
      // Create link to parent
      if (index === 0) {
        links.push({
          source: lineage.capsule.id,
          target: ancestor.id,
        });
      } else {
        links.push({
          source: lineage.ancestors[index - 1].id,
          target: ancestor.id,
        });
      }
    });
    
    return { nodes, links };
  }, [lineage]);
  
  // D3 visualization
  useEffect(() => {
    if (!svgRef.current || !containerRef.current || graphData.nodes.length === 0) {
      return;
    }
    
    const svg = d3.select(svgRef.current);
    const { width, height } = containerRef.current.getBoundingClientRect();
    
    // Clear previous content
    svg.selectAll('*').remove();
    
    // Set up SVG
    svg
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);
    
    // Create container for zoom/pan
    const g = svg.append('g');
    
    // Set up zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    
    svg.call(zoom);
    
    // Create force simulation
    const simulation = d3.forceSimulation(graphData.nodes as any)
      .force('link', d3.forceLink(graphData.links)
        .id((d: any) => d.id)
        .distance(120)
        .strength(0.5))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));
    
    // Draw links (edges)
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(graphData.links)
      .join('line')
      .attr('stroke', 'var(--glass-border)')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.6);
    
    // Draw link arrows
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', 'var(--glass-border)');
    
    link.attr('marker-end', 'url(#arrowhead)');
    
    // Draw nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(graphData.nodes)
      .join('g')
      .attr('class', 'node')
      .attr('cursor', 'pointer')
      .on('click', (event, d) => onNodeClick(d.id))
      .on('mouseenter', (event, d) => onNodeHover?.(d.capsule))
      .on('mouseleave', () => onNodeHover?.(null))
      .call(d3.drag<SVGGElement, LineageNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }) as any);
    
    // Node circles
    node.append('circle')
      .attr('r', (d) => d.isRoot ? 30 : 24)
      .attr('fill', (d) => getTrustColor(d.capsule.trust_level))
      .attr('stroke', (d) => d.isRoot ? 'var(--accent-primary)' : 'var(--glass-border)')
      .attr('stroke-width', (d) => d.isRoot ? 3 : 1);
    
    // Node labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', 'var(--text-primary)')
      .attr('font-size', '10px')
      .attr('font-weight', '500')
      .text((d) => d.capsule.type.substring(0, 3).toUpperCase());
    
    // Node version labels below
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '2.5em')
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', '9px')
      .text((d) => `v${d.capsule.version}`);
    
    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });
    
    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [graphData, onNodeClick, onNodeHover]);
  
  return (
    <div ref={containerRef} className="w-full h-full min-h-[400px] bg-bg-surface-1 rounded-lg">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}

function getTrustColor(trust: TrustLevel): string {
  const colors: Record<TrustLevel, string> = {
    core: 'var(--trust-core)',
    trusted: 'var(--trust-trusted)',
    standard: 'var(--trust-standard)',
    sandbox: 'var(--trust-sandbox)',
    quarantine: 'var(--trust-quarantine)',
  };
  return colors[trust];
}
```

**Governance Center**

Proposal management with voting interface and AI analysis display.

```typescript
interface GovernanceState {
  // Tab navigation
  activeTab: 'active' | 'my_votes' | 'my_proposals' | 'closed';
  
  // Proposals list
  proposals: Proposal[];
  selectedProposal: ProposalDetail | null;
  
  // Voting interface
  votingModal: {
    open: boolean;
    proposalId: string | null;
    decision: 'for' | 'against' | 'abstain' | null;
    reasoning: string;
    isSubmitting: boolean;
  };
}

export function GovernanceCenter() {
  const [state, dispatch] = useReducer(governanceReducer, initialState);
  const { user } = useAuth();
  
  // Fetch proposals based on active tab
  const { data: proposals } = useQuery(
    ['proposals', state.activeTab],
    () => fetchProposals({ 
      status: state.activeTab === 'active' ? 'active' : 
              state.activeTab === 'closed' ? ['approved', 'rejected'] : undefined,
      proposerId: state.activeTab === 'my_proposals' ? user.id : undefined,
      voterId: state.activeTab === 'my_votes' ? user.id : undefined,
    })
  );
  
  // Vote mutation
  const voteMutation = useMutation(
    ({ proposalId, decision, reasoning }: VoteInput) =>
      castVote(proposalId, decision, reasoning),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['proposals']);
        dispatch({ type: 'CLOSE_VOTING_MODAL' });
        toast.success('Vote recorded successfully');
      },
    }
  );
  
  return (
    <div className="flex flex-col h-full">
      {/* Header with tabs */}
      <div className="border-b border-glass-border">
        <Tabs value={state.activeTab} onValueChange={(v) => dispatch({ type: 'SET_TAB', tab: v })}>
          <TabsList>
            <TabsTrigger value="active">
              Active Proposals
              <Badge variant="primary" className="ml-2">
                {proposals?.filter(p => p.status === 'active').length || 0}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="my_votes">My Votes</TabsTrigger>
            <TabsTrigger value="my_proposals">My Proposals</TabsTrigger>
            <TabsTrigger value="closed">Closed</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Proposals list */}
        <div className={cn(
          "flex-1 overflow-auto p-4 space-y-4",
          state.selectedProposal && "lg:w-1/2"
        )}>
          {proposals?.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              userVote={proposal.userVote}
              onClick={() => dispatch({ type: 'SELECT_PROPOSAL', id: proposal.id })}
              onVote={() => dispatch({ 
                type: 'OPEN_VOTING_MODAL', 
                proposalId: proposal.id 
              })}
            />
          ))}
        </div>
        
        {/* Detail panel */}
        {state.selectedProposal && (
          <ProposalDetailPanel
            proposal={state.selectedProposal}
            onClose={() => dispatch({ type: 'CLEAR_SELECTION' })}
            onVote={() => dispatch({ 
              type: 'OPEN_VOTING_MODAL', 
              proposalId: state.selectedProposal.id 
            })}
          />
        )}
      </div>
      
      {/* Voting modal */}
      <VotingModal
        open={state.votingModal.open}
        proposal={proposals?.find(p => p.id === state.votingModal.proposalId)}
        decision={state.votingModal.decision}
        reasoning={state.votingModal.reasoning}
        isSubmitting={voteMutation.isLoading}
        onDecisionChange={(d) => dispatch({ type: 'SET_DECISION', decision: d })}
        onReasoningChange={(r) => dispatch({ type: 'SET_REASONING', reasoning: r })}
        onSubmit={() => voteMutation.mutate({
          proposalId: state.votingModal.proposalId!,
          decision: state.votingModal.decision!,
          reasoning: state.votingModal.reasoning,
        })}
        onClose={() => dispatch({ type: 'CLOSE_VOTING_MODAL' })}
      />
    </div>
  );
}
```

---

## **16. Command Line Interface**

### **16.1 CLI Design Philosophy**

The Forge CLI follows the Command Line Interface Guidelines (clig.dev) with these principles:

**Human-first, machine-second.** Default output is human-readable with colors and formatting. Machine-readable formats (JSON, YAML) are available via `--output` flag for scripting.

**Progressive disclosure.** Simple commands show essential information. Details available on request via flags like `--verbose` or `--all`.

**Helpful errors.** Error messages explain what went wrong, why, and how to fix it. Include relevant command suggestions.

**Consistent patterns.** All commands follow `forge <resource> <action>` pattern. Similar resources have similar interfaces.

### **16.2 Command Structure**

```
forge
│
├── auth                          # Authentication
│   ├── login                     # Interactive login (OAuth device flow)
│   ├── logout                    # Clear stored credentials
│   ├── status                    # Show current auth status
│   ├── token                     # Manage API tokens
│   │   ├── create                # Create new API token
│   │   ├── list                  # List tokens
│   │   ├── revoke <id>           # Revoke a token
│   │   └── refresh               # Refresh current token
│   └── switch <profile>          # Switch between profiles
│
├── capsule                       # Capsule operations
│   ├── list                      # List capsules (paginated)
│   ├── get <id>                  # Get capsule details
│   ├── create                    # Create new capsule
│   ├── update <id>               # Update capsule
│   ├── delete <id>               # Delete capsule
│   ├── search <query>            # Semantic search
│   ├── lineage <id>              # Show ancestry (Isnad)
│   ├── export                    # Export capsules
│   └── import                    # Import capsules
│
├── governance                    # Governance operations
│   ├── proposal
│   │   ├── list                  # List proposals
│   │   ├── get <id>              # Get proposal details
│   │   ├── create                # Create proposal
│   │   ├── activate <id>         # Open for voting
│   │   └── cancel <id>           # Cancel draft proposal
│   ├── vote <proposal-id> <decision>   # Cast vote
│   └── results <proposal-id>     # View voting results
│
├── overlay                       # Overlay operations
│   ├── list                      # List overlays
│   ├── get <id>                  # Get overlay details
│   ├── register                  # Register new overlay
│   ├── invoke <id> <function>    # Invoke overlay function
│   ├── logs <id>                 # View overlay logs
│   └── health <id>               # Check overlay health
│
├── system                        # System operations
│   ├── health                    # System health check
│   ├── metrics                   # Show metrics
│   ├── config                    # Manage configuration
│   │   ├── get <key>             # Get config value
│   │   ├── set <key> <value>     # Set config value
│   │   └── list                  # List all config
│   └── audit                     # View audit logs
│
├── config                        # CLI configuration
│   ├── init                      # Initialize config
│   ├── profile
│   │   ├── create <name>         # Create profile
│   │   ├── list                  # List profiles
│   │   └── delete <name>         # Delete profile
│   └── set <key> <value>         # Set CLI config
│
└── completion                    # Shell completions
    ├── bash                      # Bash completions
    ├── zsh                       # Zsh completions
    ├── fish                      # Fish completions
    └── powershell                # PowerShell completions
```

### **16.3 Implementation**

```python
"""
Forge CLI - Command Line Interface for Forge Cascade.

Built with Typer for command parsing and Rich for beautiful terminal output.
"""
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from typing import Optional, List
from enum import Enum
from pathlib import Path
import httpx
import json
import keyring
from datetime import datetime

# Initialize Typer app
app = typer.Typer(
    name="forge",
    help="Forge Cascade CLI - Institutional Memory Engine",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Rich console for output
console = Console()

# Sub-apps for resource namespaces
auth_app = typer.Typer(help="Authentication commands")
capsule_app = typer.Typer(help="Capsule management")
governance_app = typer.Typer(help="Governance operations")
proposal_app = typer.Typer(help="Proposal management")
overlay_app = typer.Typer(help="Overlay management")
system_app = typer.Typer(help="System administration")
config_app = typer.Typer(help="CLI configuration")

# Register sub-apps
app.add_typer(auth_app, name="auth")
app.add_typer(capsule_app, name="capsule")
app.add_typer(governance_app, name="governance")
governance_app.add_typer(proposal_app, name="proposal")
app.add_typer(overlay_app, name="overlay")
app.add_typer(system_app, name="system")
app.add_typer(config_app, name="config")


# Output format enum
class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


# Common options
def output_option():
    return typer.Option(
        OutputFormat.TABLE,
        "--output", "-o",
        help="Output format",
        case_sensitive=False,
    )


def profile_option():
    return typer.Option(
        "default",
        "--profile", "-p",
        help="Configuration profile to use",
        envvar="FORGE_PROFILE",
    )


def verbose_option():
    return typer.Option(
        False,
        "--verbose", "-v",
        help="Show verbose output",
    )


# =============================================================================
# AUTHENTICATION COMMANDS
# =============================================================================

@auth_app.command("login")
def auth_login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email address"),
    profile: str = profile_option(),
    sso: bool = typer.Option(False, "--sso", help="Use SSO authentication"),
):
    """
    Log in to Forge.
    
    Uses OAuth device code flow for secure authentication.
    Credentials are stored securely in the system keyring.
    
    [bold]Examples:[/bold]
    
        forge auth login
        forge auth login --email user@example.com
        forge auth login --sso
    """
    config = load_config(profile)
    
    if sso:
        # SSO flow
        with console.status("[bold blue]Starting SSO authentication..."):
            device_code = initiate_device_flow(config)
        
        console.print(Panel(
            f"[bold]Open this URL in your browser:[/bold]\n\n"
            f"[link={device_code.verification_uri}]{device_code.verification_uri}[/link]\n\n"
            f"[bold]Enter this code:[/bold] [cyan]{device_code.user_code}[/cyan]",
            title="SSO Authentication",
        ))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for browser authentication...", total=None)
            tokens = poll_for_tokens(device_code)
            progress.update(task, description="[green]Authentication successful!")
    else:
        # Interactive login
        if not email:
            email = Prompt.ask("[bold]Email")
        
        password = Prompt.ask("[bold]Password", password=True)
        
        with console.status("[bold blue]Authenticating..."):
            try:
                result = authenticate_password(config, email, password)
            except AuthenticationError as e:
                console.print(f"[red]Authentication failed:[/red] {e.message}")
                raise typer.Exit(1)
        
        # Handle MFA if required
        if result.requires_mfa:
            console.print(f"[yellow]MFA required.[/yellow] Methods available: {', '.join(result.mfa_methods)}")
            mfa_code = Prompt.ask("[bold]Enter MFA code")
            
            with console.status("[bold blue]Verifying MFA..."):
                try:
                    result = verify_mfa(config, result.mfa_challenge_id, mfa_code)
                except AuthenticationError as e:
                    console.print(f"[red]MFA verification failed:[/red] {e.message}")
                    raise typer.Exit(1)
        
        tokens = result
    
    # Store tokens securely
    store_tokens(profile, tokens)
    
    # Fetch and display user info
    user = get_current_user(config, tokens.access_token)
    
    console.print(Panel(
        f"[green]Successfully logged in![/green]\n\n"
        f"[bold]Email:[/bold] {user.email}\n"
        f"[bold]Trust Level:[/bold] {format_trust_level(user.trust_level)}\n"
        f"[bold]Roles:[/bold] {', '.join(user.roles)}",
        title="Welcome to Forge",
    ))


@auth_app.command("status")
def auth_status(profile: str = profile_option()):
    """Show current authentication status."""
    tokens = get_stored_tokens(profile)
    
    if not tokens:
        console.print("[yellow]Not authenticated.[/yellow] Run [cyan]forge auth login[/cyan] to authenticate.")
        raise typer.Exit(1)
    
    config = load_config(profile)
    
    try:
        user = get_current_user(config, tokens.access_token)
        
        console.print(Panel(
            f"[green]Authenticated[/green]\n\n"
            f"[bold]Email:[/bold] {user.email}\n"
            f"[bold]User ID:[/bold] {user.id}\n"
            f"[bold]Trust Level:[/bold] {format_trust_level(user.trust_level)}\n"
            f"[bold]Roles:[/bold] {', '.join(user.roles)}\n"
            f"[bold]Profile:[/bold] {profile}",
            title="Authentication Status",
        ))
    except AuthenticationError:
        console.print("[yellow]Session expired.[/yellow] Run [cyan]forge auth login[/cyan] to re-authenticate.")
        raise typer.Exit(1)


@auth_app.command("logout")
def auth_logout(
    profile: str = profile_option(),
    all_profiles: bool = typer.Option(False, "--all", "-a", help="Log out from all profiles"),
):
    """Log out and clear stored credentials."""
    if all_profiles:
        profiles = list_profiles()
        for p in profiles:
            clear_tokens(p)
        console.print(f"[green]Logged out from {len(profiles)} profile(s).[/green]")
    else:
        clear_tokens(profile)
        console.print(f"[green]Logged out from profile '{profile}'.[/green]")


# =============================================================================
# CAPSULE COMMANDS
# =============================================================================

@capsule_app.command("list")
def capsule_list(
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by capsule type"),
    trust: Optional[str] = typer.Option(None, "--trust", help="Filter by trust level"),
    owner: Optional[str] = typer.Option(None, "--owner", help="Filter by owner ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of results"),
    output: OutputFormat = output_option(),
    profile: str = profile_option(),
):
    """
    List capsules with optional filters.
    
    [bold]Examples:[/bold]
    
        forge capsule list
        forge capsule list --type knowledge --limit 50
        forge capsule list --trust trusted --output json
    """
    client = get_api_client(profile)
    
    params = {"per_page": limit}
    if type:
        params["type"] = type
    if trust:
        params["trust_level"] = trust
    if owner:
        params["owner_id"] = owner
    
    with console.status("[bold blue]Fetching capsules..."):
        response = client.get("/capsules", params=params)
        handle_response_errors(response)
        data = response.json()
    
    capsules = data["data"]
    total = data["meta"]["total"]
    
    if output == OutputFormat.JSON:
        console.print_json(json.dumps(capsules, indent=2, default=str))
        return
    
    if output == OutputFormat.YAML:
        import yaml
        console.print(yaml.dump(capsules, default_flow_style=False))
        return
    
    # Table output
    table = Table(
        title=f"Capsules ({len(capsules)} of {total})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", width=8)
    table.add_column("Type", width=10)
    table.add_column("Trust", width=10)
    table.add_column("Version", width=8)
    table.add_column("Content Preview", width=40, overflow="ellipsis")
    table.add_column("Created", width=12)
    
    for cap in capsules:
        table.add_row(
            cap["id"][:8],
            cap["type"],
            format_trust_level(cap["trust_level"]),
            cap["version"],
            cap["content"][:40] + "..." if len(cap["content"]) > 40 else cap["content"],
            format_date(cap["created_at"]),
        )
    
    console.print(table)


@capsule_app.command("get")
def capsule_get(
    capsule_id: str = typer.Argument(..., help="Capsule ID"),
    output: OutputFormat = output_option(),
    profile: str = profile_option(),
):
    """
    Get detailed information about a capsule.
    
    [bold]Example:[/bold]
    
        forge capsule get abc123
    """
    client = get_api_client(profile)
    
    with console.status("[bold blue]Fetching capsule..."):
        response = client.get(f"/capsules/{capsule_id}")
        handle_response_errors(response)
        capsule = response.json()["data"]
    
    if output == OutputFormat.JSON:
        console.print_json(json.dumps(capsule, indent=2, default=str))
        return
    
    # Rich panel output
    content_syntax = Syntax(
        capsule["content"],
        "markdown" if capsule["type"] == "knowledge" else "python",
        theme="monokai",
        word_wrap=True,
        line_numbers=len(capsule["content"]) > 200,
    )
    
    metadata_str = json.dumps(capsule.get("metadata", {}), indent=2)
    
    console.print(Panel(
        content_syntax,
        title=f"Capsule {capsule['id'][:8]}",
        subtitle=f"Type: {capsule['type']} | Trust: {format_trust_level(capsule['trust_level'])} | v{capsule['version']}",
    ))
    
    # Additional info
    console.print(f"\n[bold]Owner:[/bold] {capsule['owner_id'][:8]}")
    console.print(f"[bold]Created:[/bold] {format_date(capsule['created_at'])}")
    console.print(f"[bold]Updated:[/bold] {format_date(capsule['updated_at'])}")
    
    if capsule.get("parent_id"):
        console.print(f"[bold]Parent:[/bold] {capsule['parent_id'][:8]}")
    
    if capsule.get("metadata"):
        console.print(f"\n[bold]Metadata:[/bold]")
        console.print(Syntax(metadata_str, "json", theme="monokai"))


@capsule_app.command("create")
def capsule_create(
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Capsule content"),
    type: str = typer.Option(..., "--type", "-t", help="Capsule type"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent capsule ID"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Read content from file"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Open editor for content"),
    output: OutputFormat = output_option(),
    profile: str = profile_option(),
):
    """
    Create a new capsule.
    
    Content can be provided via --content, --file, stdin, or --interactive (opens editor).
    
    [bold]Examples:[/bold]
    
        forge capsule create --type knowledge --content "FastAPI is preferred"
        forge capsule create --type code --file ./snippet.py
        echo "Content" | forge capsule create --type insight
        forge capsule create --type decision --interactive
    """
    # Get content from various sources
    if file:
        content = file.read_text()
    elif interactive:
        content = open_editor_for_content()
    elif not content:
        # Try stdin
        import sys
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            console.print("[red]Content required.[/red] Use --content, --file, --interactive, or pipe to stdin.")
            raise typer.Exit(1)
    
    if not content or not content.strip():
        console.print("[red]Content cannot be empty.[/red]")
        raise typer.Exit(1)
    
    client = get_api_client(profile)
    
    payload = {
        "content": content.strip(),
        "type": type,
    }
    if parent:
        payload["parent_id"] = parent
    
    with console.status("[bold blue]Creating capsule..."):
        response = client.post("/capsules", json=payload)
        handle_response_errors(response)
        capsule = response.json()["data"]
    
    if output == OutputFormat.JSON:
        console.print_json(json.dumps(capsule, indent=2, default=str))
        return
    
    console.print(Panel(
        f"[green]Capsule created successfully![/green]\n\n"
        f"[bold]ID:[/bold] {capsule['id']}\n"
        f"[bold]Type:[/bold] {capsule['type']}\n"
        f"[bold]Trust Level:[/bold] {format_trust_level(capsule['trust_level'])}\n"
        f"[bold]Version:[/bold] {capsule['version']}",
        title="New Capsule",
    ))


@capsule_app.command("search")
def capsule_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
    min_score: float = typer.Option(0.7, "--min-score", help="Minimum similarity score"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    output: OutputFormat = output_option(),
    profile: str = profile_option(),
):
    """
    Semantic search for capsules.
    
    Uses vector similarity to find relevant capsules regardless of exact keyword matches.
    
    [bold]Examples:[/bold]
    
        forge capsule search "error handling best practices"
        forge capsule search "Python async patterns" --type code --limit 20
    """
    client = get_api_client(profile)
    
    payload = {
        "query": query,
        "limit": limit,
        "min_score": min_score,
    }
    if type:
        payload["filters"] = {"type": type}
    
    with console.status("[bold blue]Searching..."):
        response = client.post("/capsules/search", json=payload)
        handle_response_errors(response)
        data = response.json()
    
    results = data["data"]
    
    if output == OutputFormat.JSON:
        console.print_json(json.dumps(results, indent=2, default=str))
        return
    
    console.print(f"\n[bold]Found {len(results)} results for:[/bold] {query}\n")
    
    for i, result in enumerate(results, 1):
        cap = result["capsule"]
        score = result["score"]
        
        # Score color based on value
        score_color = "green" if score >= 0.9 else "yellow" if score >= 0.8 else "white"
        
        preview = cap["content"][:200] + "..." if len(cap["content"]) > 200 else cap["content"]
        
        console.print(Panel(
            preview,
            title=f"[{i}] [{score_color}]{score:.1%}[/{score_color}] {cap['type']} | {format_trust_level(cap['trust_level'])}",
            subtitle=f"ID: {cap['id'][:8]} | v{cap['version']}",
        ))


@capsule_app.command("lineage")
def capsule_lineage(
    capsule_id: str = typer.Argument(..., help="Capsule ID"),
    depth: int = typer.Option(10, "--depth", "-d", help="Maximum ancestry depth"),
    output: OutputFormat = output_option(),
    profile: str = profile_option(),
):
    """
    Display the lineage (Isnad) of a capsule.
    
    Shows the complete ancestry chain from the capsule to its oldest ancestor.
    
    [bold]Example:[/bold]
    
        forge capsule lineage abc123 --depth 20
    """
    client = get_api_client(profile)
    
    with console.status("[bold blue]Tracing lineage..."):
        response = client.get(f"/capsules/{capsule_id}/lineage", params={"max_depth": depth})
        handle_response_errors(response)
        data = response.json()["data"]
    
    if output == OutputFormat.JSON:
        console.print_json(json.dumps(data, indent=2, default=str))
        return
    
    lineage = data["lineage"]
    
    console.print(f"\n[bold]Lineage for {capsule_id[:8]}[/bold]")
    console.print(f"[dim]Depth: {data['depth']} ancestors[/dim]\n")
    
    # Build tree visualization
    tree = Tree(f"[green]●[/green] {capsule_id[:8]} [dim](current)[/dim]")
    
    current_branch = tree
    for ancestor in lineage:
        cap = ancestor["capsule"]
        rel = ancestor["relationship"]
        
        label = (
            f"[{get_trust_color(cap['trust_level'])}]●[/{get_trust_color(cap['trust_level'])}] "
            f"{cap['id'][:8]} "
            f"[dim]({cap['type']}, v{cap['version']})[/dim]"
        )
        
        if rel.get("reason"):
            label += f"\n  [dim italic]Reason: {rel['reason']}[/dim italic]"
        
        current_branch = current_branch.add(label)
    
    console.print(tree)
    
    if data.get("truncated"):
        console.print(f"\n[yellow]Lineage truncated at depth {depth}. Use --depth to see more.[/yellow]")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_trust_level(trust: str) -> str:
    """Format trust level with color."""
    colors = {
        "core": "magenta",
        "trusted": "green",
        "standard": "blue",
        "sandbox": "yellow",
        "quarantine": "red",
    }
    color = colors.get(trust, "white")
    return f"[{color}]{trust}[/{color}]"


def get_trust_color(trust: str) -> str:
    """Get color for trust level."""
    colors = {
        "core": "magenta",
        "trusted": "green",
        "standard": "blue",
        "sandbox": "yellow",
        "quarantine": "red",
    }
    return colors.get(trust, "white")


def format_date(iso_date: str) -> str:
    """Format ISO date for display."""
    if not iso_date:
        return "N/A"
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")


def handle_response_errors(response: httpx.Response):
    """Handle API response errors with helpful messages."""
    if response.status_code >= 400:
        try:
            error = response.json()
            message = error.get("message", "Unknown error")
            code = error.get("code", "error")
            
            console.print(f"[red]Error ({code}):[/red] {message}")
            
            # Show field errors for validation
            if "errors" in error:
                for field_error in error["errors"]:
                    console.print(f"  [yellow]•[/yellow] {field_error['field']}: {field_error['message']}")
            
            # Show documentation link if available
            if "documentation_url" in error:
                console.print(f"\n[dim]Documentation: {error['documentation_url']}[/dim]")
                
        except json.JSONDecodeError:
            console.print(f"[red]Error:[/red] HTTP {response.status_code}")
        
        raise typer.Exit(1)


# Main entry point
if __name__ == "__main__":
    app()
```

---

## **17. Mobile Application**

### **17.1 Mobile Strategy**

The Forge mobile application focuses on monitoring, notifications, and approval workflows rather than attempting to replicate the full desktop experience. Complex configuration, data exploration, and lineage visualization remain desktop-first experiences.

**Core Mobile Use Cases**

The mobile app addresses four primary use cases that benefit from mobile access:

First, **system monitoring** allows administrators and operators to check system health from anywhere. Critical alerts and status changes should be visible immediately.

Second, **governance participation** enables users to review proposals and cast votes without needing desktop access. Voting deadlines are time-sensitive, and mobile voting increases participation.

Third, **approval workflows** for overlay registration, trust level changes, and emergency actions require quick response times. Mobile approval reduces decision latency.

Fourth, **capsule quick view** allows users to view and search capsules for reference, though creation and editing remain desktop functions.

**Explicitly Not Included**

The following features are intentionally excluded from mobile to maintain a focused, high-quality experience:

Capsule creation and editing requires careful review and often involves code or complex content that benefits from a full keyboard and larger screen.

Overlay configuration involves manifest editing, capability selection, and WASM binary management that require desktop tooling.

Complex lineage visualization with interactive graphs requires screen real estate and precise interactions not suited to touch interfaces.

System administration tasks like user management, compliance reporting, and audit log analysis require the desktop interface.

### **17.2 Technical Architecture**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MOBILE APPLICATION ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ REACT NATIVE APPLICATION                                                    │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Navigation Layer (React Navigation 6)                                   │ │
│ │                                                                         │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│ │ │Dashboard │ │ Capsules │ │Governance│ │  Alerts  │ │ Profile  │      │ │
│ │ │   Tab    │ │   Tab    │ │   Tab    │ │   Tab    │ │   Tab    │      │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ State Management (Zustand + React Query)                                │ │
│ │                                                                         │ │
│ │ • AuthStore: tokens, user profile, biometric status                    │ │
│ │ • SystemStore: health status, metrics, connection state                │ │
│ │ • NotificationStore: alerts, badges, read status                       │ │
│ │ • CacheStore: offline data, pending actions queue                      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Service Layer                                                           │ │
│ │                                                                         │ │
│ │ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐           │ │
│ │ │ API Client │ │    Push    │ │ Biometric  │ │   Offline  │           │ │
│ │ │   (Axios)  │ │  Service   │ │    Auth    │ │    Sync    │           │ │
│ │ │            │ │  (FCM/APNs)│ │(FaceID/etc)│ │            │           │ │
│ │ └────────────┘ └────────────┘ └────────────┘ └────────────┘           │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ NATIVE MODULES                                                              │
│                                                                             │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│ │ Secure Keychain│ │ Push Token     │ │ Biometric      │                   │
│ │ (Credentials)  │ │ Registration   │ │ Authentication │                   │
│ └────────────────┘ └────────────────┘ └────────────────┘                   │
│                                                                             │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│ │ Deep Linking   │ │ Background     │ │ Share          │                   │
│ │ (forge://)     │ │ Fetch          │ │ Extension      │                   │
│ └────────────────┘ └────────────────┘ └────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### **17.3 Push Notification Architecture**

```typescript
// Notification configuration
interface NotificationConfig {
  channels: {
    critical: {
      name: "Critical Alerts";
      description: "System outages, security breaches";
      sound: true;
      vibration: [0, 250, 250, 250];
      priority: "high";
      bypassDND: true;
      badge: true;
      lightColor: "#EF4444";  // Red
    };
    
    warning: {
      name: "Warnings";
      description: "Health degradation, overlay issues";
      sound: true;
      vibration: [0, 200];
      priority: "default";
      bypassDND: false;
      badge: true;
      lightColor: "#F59E0B";  // Amber
    };
    
    governance: {
      name: "Governance";
      description: "New proposals, voting reminders";
      sound: false;
      vibration: null;
      priority: "low";
      bypassDND: false;
      badge: true;
      lightColor: "#3B82F6";  // Blue
    };
    
    info: {
      name: "Information";
      description: "General updates, announcements";
      sound: false;
      vibration: null;
      priority: "min";
      bypassDND: false;
      badge: false;
      lightColor: "#71717A";  // Gray
    };
  };
  
  // Smart batching to reduce notification fatigue
  batching: {
    enabled: true;
    windowMinutes: 15;
    maxPerWindow: 5;
    excludeChannels: ["critical"];
    summary: {
      title: "Forge Updates";
      template: "{count} updates in the last {minutes} minutes";
    };
  };
  
  // Quiet hours (user configurable)
  quietHours: {
    enabled: boolean;
    start: "22:00";
    end: "07:00";
    excludeChannels: ["critical"];
    timezone: "local";
  };
}

// Push service implementation
class PushNotificationService {
  private messaging: FirebaseMessaging;
  private config: NotificationConfig;
  
  async initialize(): Promise<void> {
    // Request permission
    const permission = await this.messaging.requestPermission();
    if (permission !== "authorized") {
      console.warn("Push notifications not authorized");
      return;
    }
    
    // Get FCM token
    const token = await this.messaging.getToken();
    await this.registerToken(token);
    
    // Set up listeners
    this.messaging.onMessage(this.handleForegroundMessage.bind(this));
    this.messaging.onBackgroundMessage(this.handleBackgroundMessage.bind(this));
    this.messaging.onTokenRefresh(this.handleTokenRefresh.bind(this));
  }
  
  private async handleForegroundMessage(message: RemoteMessage): Promise<void> {
    const channel = message.data?.channel || "info";
    const config = this.config.channels[channel];
    
    // Check quiet hours
    if (this.isQuietHours() && channel !== "critical") {
      this.queueForLater(message);
      return;
    }
    
    // Check batching
    if (this.shouldBatch(channel)) {
      this.addToBatch(message);
      return;
    }
    
    // Display notification
    await Notifications.scheduleNotification({
      id: message.messageId,
      title: message.notification?.title || "Forge",
      body: message.notification?.body || "",
      data: message.data,
      channelId: channel,
      ...config,
    });
    
    // Update badge count
    await this.updateBadgeCount();
  }
  
  private async handleBackgroundMessage(message: RemoteMessage): Promise<void> {
    // Background messages handled by native code
    // Just update local state
    await AsyncStorage.setItem(
      `notification:${message.messageId}`,
      JSON.stringify(message)
    );
  }
}
```

### **17.4 Quick Vote Screen**

```typescript
interface QuickVoteScreenProps {
  route: {
    params: {
      proposalId: string;
    };
  };
}

export function QuickVoteScreen({ route }: QuickVoteScreenProps) {
  const { proposalId } = route.params;
  
  const { data: proposal, isLoading } = useQuery(
    ["proposal", proposalId],
    () => fetchProposal(proposalId)
  );
  
  const voteMutation = useMutation(
    (decision: "for" | "against" | "abstain") =>
      castVote(proposalId, decision),
    {
      onSuccess: () => {
        navigation.goBack();
        showToast("Vote recorded successfully");
      },
    }
  );
  
  if (isLoading || !proposal) {
    return <LoadingScreen />;
  }
  
  const timeRemaining = getTimeRemaining(proposal.votingEndsAt);
  
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <ProposalTypeBadge type={proposal.type} />
          <TimeRemainingBadge 
            time={timeRemaining}
            urgent={timeRemaining.hours < 4}
          />
        </View>
        
        {/* Title */}
        <Text style={styles.title}>{proposal.title}</Text>
        
        {/* AI Summary */}
        <Card style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>AI Summary</Text>
          <Text style={styles.summaryText}>{proposal.aiSummary}</Text>
          {proposal.aiRecommendation && (
            <AIRecommendationBadge recommendation={proposal.aiRecommendation} />
          )}
        </Card>
        
        {/* Current Votes */}
        <VoteProgressBar
          votesFor={proposal.votesFor}
          votesAgainst={proposal.votesAgainst}
          threshold={proposal.approvalThreshold}
        />
        
        {/* User's Previous Vote (if any) */}
        {proposal.userVote && (
          <PreviousVoteIndicator vote={proposal.userVote} />
        )}
        
        {/* Key Points */}
        <View style={styles.keyPoints}>
          <Text style={styles.keyPointsLabel}>Key Points</Text>
          {proposal.keyPoints?.map((point, index) => (
            <Text key={index} style={styles.keyPoint}>• {point}</Text>
          ))}
        </View>
        
        {/* Link to full details */}
        <TouchableOpacity 
          style={styles.detailsLink}
          onPress={() => navigation.navigate("ProposalDetail", { proposalId })}
        >
          <Text style={styles.detailsLinkText}>View Full Details →</Text>
        </TouchableOpacity>
      </ScrollView>
      
      {/* Vote Buttons */}
      <View style={styles.voteButtons}>
        <VoteButton
          decision="against"
          label="Oppose"
          icon="thumbs-down"
          color="#EF4444"
          disabled={voteMutation.isLoading}
          onPress={() => voteMutation.mutate("against")}
        />
        <VoteButton
          decision="abstain"
          label="Abstain"
          icon="minus"
          color="#71717A"
          disabled={voteMutation.isLoading}
          onPress={() => voteMutation.mutate("abstain")}
        />
        <VoteButton
          decision="for"
          label="Support"
          icon="thumbs-up"
          color="#22C55E"
          disabled={voteMutation.isLoading}
          onPress={() => voteMutation.mutate("for")}
        />
      </View>
    </SafeAreaView>
  );
}
```

---

## **18. Deployment Architecture**

### **18.1 Infrastructure Overview**

The Forge deployment architecture is designed for high availability, horizontal scalability, and multi-region data residency compliance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CDN / EDGE LAYER (Cloudflare / AWS CloudFront)                              │
│                                                                             │
│ • Static asset caching (web dashboard, mobile assets)                      │
│ • DDoS protection (Layer 3/4/7)                                            │
│ • Edge SSL termination                                                     │
│ • WAF rules (OWASP Core Rule Set)                                         │
│ • Geographic routing for data residency                                    │
│ • Bot management                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOAD BALANCER LAYER                                                         │
│                                                                             │
│ AWS ALB / GCP Load Balancer / Kubernetes Ingress                           │
│ • Health checks (HTTP, TCP, gRPC)                                         │
│ • SSL termination (internal certs)                                        │
│ • Request routing (path-based, header-based)                              │
│ • Rate limiting (token bucket per IP/API key)                             │
│ • Connection draining for graceful deploys                                │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ KUBERNETES CLUSTER                                                          │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ API Deployment                                                          │ │
│ │                                                                         │ │
│ │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │ │
│ │ │ API Pod │ │ API Pod │ │ API Pod │ │ API Pod │ │ API Pod │  ...      │ │
│ │ │         │ │         │ │         │ │         │ │         │           │ │
│ │ │ FastAPI │ │ FastAPI │ │ FastAPI │ │ FastAPI │ │ FastAPI │           │ │
│ │ │ Uvicorn │ │ Uvicorn │ │ Uvicorn │ │ Uvicorn │ │ Uvicorn │           │ │
│ │ │ 4 worker│ │ 4 worker│ │ 4 worker│ │ 4 worker│ │ 4 worker│           │ │
│ │ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘           │ │
│ │                                                                         │ │
│ │ HPA: 3-20 replicas based on CPU (70%), Memory (80%), RPS (1000/pod)   │ │
│ │ PDB: minAvailable 2 (ensures HA during rolling updates)               │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Worker Deployment (Async Processing)                                    │ │
│ │                                                                         │ │
│ │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │ │
│ │ │ Worker Pod  │ │ Worker Pod  │ │ Worker Pod  │ │ Worker Pod  │       │ │
│ │ │             │ │             │ │             │ │             │       │ │
│ │ │ Celery      │ │ Celery      │ │ Celery      │ │ Celery      │       │ │
│ │ │ + Wasmtime  │ │ + Wasmtime  │ │ + Wasmtime  │ │ + Wasmtime  │       │ │
│ │ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │ │
│ │                                                                         │ │
│ │ Handles: Overlay execution, embedding generation, event processing     │ │
│ │ HPA: 2-10 replicas based on queue depth                                │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Scheduler Deployment (Cron Jobs)                                        │ │
│ │                                                                         │ │
│ │ ┌─────────────────┐                                                    │ │
│ │ │ Scheduler Pod   │ (single replica with leader election)             │ │
│ │ │                 │                                                    │ │
│ │ │ • Celery Beat   │                                                    │ │
│ │ │ • Health checks │                                                    │ │
│ │ │ • Governance    │                                                    │ │
│ │ │ • Cleanup jobs  │                                                    │ │
│ │ └─────────────────┘                                                    │ │
│ │                                                                         │ │
│ │ Jobs: Voting deadline checks, audit log rotation, metrics aggregation  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ DATA LAYER                                                                  │
│                                                                             │
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│ │ Neo4j Cluster    │ │ Redis Cluster    │ │ Kafka Cluster    │            │
│ │ (3-5 nodes)      │ │ (6 nodes)        │ │ (3+ brokers)     │            │
│ │                  │ │                  │ │                  │            │
│ │ • 1 Primary      │ │ • 3 masters      │ │ • 3 brokers      │            │
│ │ • 2-4 Read       │ │ • 3 replicas     │ │ • Replication 3  │            │
│ │   Replicas       │ │                  │ │ • 3 ZK nodes     │            │
│ │ • Causal cluster │ │ • Persistence    │ │                  │            │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘            │
│                                                                             │
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│ │ Object Storage   │ │ Secrets Manager  │ │ Observability    │            │
│ │ (S3/GCS/MinIO)   │ │ (Vault/AWS SM)   │ │ (Prometheus,     │            │
│ │                  │ │                  │ │  Grafana, Jaeger)│            │
│ │ • WASM binaries  │ │ • API keys       │ │                  │            │
│ │ • Audit logs     │ │ • DB credentials │ │ • Metrics        │            │
│ │ • Backups        │ │ • Encryption keys│ │ • Traces         │            │
│ │ • Attachments    │ │                  │ │ • Logs           │            │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### **18.2 Kubernetes Manifests**

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: forge-api
  labels:
    app: forge
    component: api
    version: v3.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: forge
      component: api
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 2
  template:
    metadata:
      labels:
        app: forge
        component: api
        version: v3.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: forge-api
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: api
          image: forge/api:v3.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
              name: http
              protocol: TCP
          env:
            - name: NEO4J_URI
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: neo4j-uri
            - name: NEO4J_USER
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: neo4j-user
            - name: NEO4J_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: neo4j-password
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: redis-url
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: forge-config
                  key: kafka-servers
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: jwt-secret
            - name: LOG_LEVEL
              value: "INFO"
            - name: ENVIRONMENT
              value: "production"
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: forge
                    component: api
                topologyKey: kubernetes.io/hostname
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: forge
              component: api
---
# api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: forge-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: forge-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 4
          periodSeconds: 15
      selectPolicy: Max
---
# api-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: forge-api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: forge
      component: api
---
# api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: forge-api
  labels:
    app: forge
    component: api
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
      name: http
  selector:
    app: forge
    component: api
```

### **18.3 Multi-Region Deployment**

For organizations with data residency requirements, Forge supports multi-region deployment with data isolation.

```yaml
# multi-region-config.yaml
regions:
  eu-west-1:
    name: "Europe (Ireland)"
    jurisdictions:
      - EU
      - UK
    neo4j:
      endpoint: neo4j-eu.forge.internal
      read_replicas: 2
      backup_region: eu-central-1
    kafka:
      bootstrap: kafka-eu.forge.internal:9092
      topics_prefix: "eu_"
    redis:
      endpoint: redis-eu.forge.internal:6379
      cluster_mode: true
    storage:
      bucket: forge-data-eu
      region: eu-west-1
    data_residency: EU_ONLY
    compliance:
      - GDPR
      - EU_AI_ACT
    
  us-east-1:
    name: "US East (Virginia)"
    jurisdictions:
      - US_CALIFORNIA
      - US_HIPAA
      - US_DEFAULT
    neo4j:
      endpoint: neo4j-us.forge.internal
      read_replicas: 2
      backup_region: us-west-2
    kafka:
      bootstrap: kafka-us.forge.internal:9092
      topics_prefix: "us_"
    redis:
      endpoint: redis-us.forge.internal:6379
      cluster_mode: true
    storage:
      bucket: forge-data-us
      region: us-east-1
    data_residency: US_ONLY
    compliance:
      - CCPA
      - HIPAA
      - SOC2
    
  ap-southeast-1:
    name: "Asia Pacific (Singapore)"
    jurisdictions:
      - SINGAPORE
      - AUSTRALIA
      - JAPAN
    neo4j:
      endpoint: neo4j-ap.forge.internal
      read_replicas: 1
      backup_region: ap-southeast-2
    kafka:
      bootstrap: kafka-ap.forge.internal:9092
      topics_prefix: "ap_"
    redis:
      endpoint: redis-ap.forge.internal:6379
      cluster_mode: true
    storage:
      bucket: forge-data-ap
      region: ap-southeast-1
    data_residency: APAC
    compliance:
      - PDPA_SG
      - PRIVACY_ACT_AU

# Global routing configuration
global:
  dns: forge.example.com
  routing:
    method: geolocation
    fallback: us-east-1
    health_check_interval: 30s
  
  # Metadata that can sync globally (no PII)
  metadata_sync:
    enabled: true
    exclude_fields:
      - content          # Capsule content stays in region
      - email            # User emails
      - ip_address       # IP addresses
      - name             # Personal names
    include_fields:
      - capsule_id       # For cross-region references
      - type             # Capsule types
      - trust_level      # Trust levels
      - created_at       # Timestamps
      
  # Cross-region replication for disaster recovery
  disaster_recovery:
    enabled: true
    rpo_hours: 1         # Recovery Point Objective
    rto_hours: 4         # Recovery Time Objective
    backup_schedule: "0 */6 * * *"  # Every 6 hours
```

---


## **19. Implementation Guidelines**

### **19.1 AI-Resistant Specification Patterns**

This specification is designed with patterns that prevent common AI code generation errors. When using AI assistants to implement Forge components, these patterns ensure accurate, secure, and maintainable code.

**Why AI-Resistant Patterns Matter**

AI code generation tools can produce code that appears correct but contains subtle bugs, security vulnerabilities, or architectural violations. Common issues include hallucinated APIs that don't exist, missing error handling for edge cases, type mismatches that only fail at runtime, and security vulnerabilities from pattern matching without understanding.

This specification addresses these issues through explicit constraints, concrete examples, and prohibited patterns that AI tools can follow precisely.

**Pattern 1: Explicit Type Schemas**

Every data structure has a complete Pydantic schema with validation rules. AI tools should use these schemas directly rather than inferring types.

```python
# CORRECT: Use the exact schema from the specification
class CapsuleCreate(BaseModel):
    """Schema for creating a new capsule."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,
        description="The content of the capsule",
    )
    type: CapsuleType = Field(
        ...,
        description="The type of capsule",
    )
    parent_id: Optional[UUID] = Field(
        None,
        description="Parent capsule ID for symbolic inheritance",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "FastAPI is the preferred framework for new services.",
                    "type": "knowledge",
                    "parent_id": None,
                    "metadata": {"source": "architecture_decision"},
                }
            ]
        }
    )

# INCORRECT: Inferring types without validation
def create_capsule(content, type, parent=None):  # No type hints, no validation
    return {"content": content, "type": type}
```

**Pattern 2: Concrete Examples in Schemas**

The `model_config` with `json_schema_extra` provides concrete examples for every complex type. AI tools should reference these examples when generating test data or understanding expected formats.

```python
class Proposal(BaseModel):
    """Governance proposal with concrete example."""
    
    id: UUID
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., max_length=10000)
    type: ProposalType
    status: ProposalStatus
    payload: dict[str, Any]
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Enable Vector Search Caching",
                    "description": "Proposal to enable Redis caching for vector search results to improve P95 latency.",
                    "type": "configuration",
                    "status": "active",
                    "payload": {
                        "config_key": "search.vector.cache_enabled",
                        "new_value": True,
                        "rollback_plan": "Set config_key to False",
                    },
                }
            ]
        }
    )
```

**Pattern 3: Validation Constraints Are Explicit**

All constraints are explicit in the schema. AI tools should not add arbitrary limits not specified here and should not remove specified limits.

```python
# Specification says: max_length=1_000_000
# AI tool should use exactly 1_000_000, not 1000 or unlimited

class CapsuleContent(BaseModel):
    content: str = Field(
        ...,
        min_length=1,        # Required: at least 1 character
        max_length=1_000_000, # Required: at most 1 million characters
    )

# When implementing endpoints, use these exact constraints:
@router.post("/capsules")
async def create_capsule(
    capsule: CapsuleCreate,  # Pydantic validates constraints automatically
) -> CapsuleResponse:
    # No need to add additional validation here - schema handles it
    pass
```

**Pattern 4: Error Types Are Enumerated**

Every operation specifies exactly which errors it can raise. AI tools should handle these specific errors, not generic exceptions.

```python
# Specification: CapsuleRepository.get_by_id can raise:
# - CapsuleNotFoundError: when capsule doesn't exist
# - PermissionDeniedError: when user lacks read access
# - DatabaseConnectionError: when Neo4j is unavailable

# CORRECT: Handle specified errors
async def get_capsule(capsule_id: UUID, user: User) -> Capsule:
    try:
        return await repo.get_by_id(capsule_id, user)
    except CapsuleNotFoundError:
        raise HTTPException(status_code=404, detail="Capsule not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Access denied")
    except DatabaseConnectionError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

# INCORRECT: Generic exception handling
async def get_capsule(capsule_id: UUID, user: User) -> Capsule:
    try:
        return await repo.get_by_id(capsule_id, user)
    except Exception:  # Too broad - hides real errors
        raise HTTPException(status_code=500, detail="Error")
```

### **19.2 Prohibited Patterns**

The following patterns are explicitly prohibited in Forge implementations. AI tools should never generate code using these patterns.

**Prohibited: Bare Exception Handlers**

```python
# PROHIBITED
try:
    result = await risky_operation()
except:  # Catches everything including KeyboardInterrupt, SystemExit
    pass  # Silently swallows errors

# PROHIBITED
try:
    result = await risky_operation()
except Exception:  # Still too broad in most cases
    logger.error("Something went wrong")  # Not enough context

# ALLOWED: Specific exceptions with context
try:
    result = await risky_operation()
except ValueError as e:
    logger.error(f"Validation failed for {input_id}: {e}")
    raise ValidationError(str(e)) from e
except ConnectionError as e:
    logger.warning(f"Connection failed, retrying: {e}")
    raise RetryableError(str(e)) from e
```

**Prohibited: String Formatting in Database Queries**

```python
# PROHIBITED: SQL/Cypher injection vulnerability
capsule_id = request.capsule_id  # User input!
query = f"MATCH (c:Capsule {{id: '{capsule_id}'}}) RETURN c"  # DANGER!

# PROHIBITED: Even with UUID validation, string formatting is banned
query = f"MATCH (c:Capsule {{id: '{str(validated_uuid)}'}}) RETURN c"

# ALLOWED: Parameterized queries only
query = "MATCH (c:Capsule {id: $capsule_id}) RETURN c"
params = {"capsule_id": str(capsule_id)}
result = await session.run(query, params)
```

**Prohibited: Mutable Default Arguments**

```python
# PROHIBITED: Mutable default argument
def process_capsules(capsules: list = []):  # Same list reused across calls!
    capsules.append("new")
    return capsules

# PROHIBITED: Dict default
def create_config(settings: dict = {}):  # Same dict reused!
    settings["default"] = True
    return settings

# ALLOWED: None default with factory
def process_capsules(capsules: list | None = None):
    capsules = capsules if capsules is not None else []
    capsules.append("new")
    return capsules

# ALLOWED: Field with default_factory
class Config(BaseModel):
    settings: dict = Field(default_factory=dict)
```

**Prohibited: Blocking Calls in Async Code**

```python
# PROHIBITED: Blocking HTTP in async function
async def fetch_external_data(url: str):
    response = requests.get(url)  # Blocks the event loop!
    return response.json()

# PROHIBITED: Blocking file I/O in async
async def read_file(path: str):
    with open(path, 'r') as f:  # Blocks!
        return f.read()

# PROHIBITED: Blocking sleep
async def wait_and_process():
    time.sleep(5)  # Blocks the event loop!
    await process()

# ALLOWED: Async HTTP client
async def fetch_external_data(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ALLOWED: Async file I/O
async def read_file(path: str):
    async with aiofiles.open(path, 'r') as f:
        return await f.read()

# ALLOWED: Async sleep
async def wait_and_process():
    await asyncio.sleep(5)
    await process()

# ALLOWED: Run blocking code in executor
async def read_large_file(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: Path(path).read_text())
```

**Prohibited: Hardcoded Credentials**

```python
# PROHIBITED: Hardcoded credentials anywhere in code
NEO4J_PASSWORD = "my_secret_password"
API_KEY = "sk-1234567890abcdef"

# PROHIBITED: Even in "development" code
if os.getenv("ENV") == "development":
    db_password = "dev_password"  # Still prohibited!

# ALLOWED: Environment variables
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]  # Fails loud if missing

# ALLOWED: Secret manager
async def get_db_password():
    return await secret_manager.get("forge/neo4j/password")

# ALLOWED: Configuration from validated settings
class Settings(BaseSettings):
    neo4j_password: SecretStr
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
password = settings.neo4j_password.get_secret_value()
```

**Prohibited: Disabled Security Features**

```python
# PROHIBITED: Disabling SSL verification
response = requests.get(url, verify=False)  # Never!

# PROHIBITED: Weak crypto
from Crypto.Cipher import DES  # Weak algorithm
hashlib.md5(password)  # Weak for passwords
hashlib.sha1(password)  # Also weak for passwords

# PROHIBITED: Predictable secrets
secret_key = str(uuid.uuid4())  # UUID is not cryptographically random
token = str(random.randint(0, 999999))  # Predictable

# ALLOWED: Strong crypto only
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from argon2 import PasswordHasher

password_hash = PasswordHasher().hash(password)  # Argon2id

# ALLOWED: Cryptographically secure randomness
secret_key = secrets.token_urlsafe(32)
token = secrets.token_hex(16)
```

### **19.3 Code Review Checklist**

All code must pass this checklist before merging. Reviewers should verify each item explicitly.

**Security Checklist**

```markdown
[ ] No hardcoded credentials, API keys, or secrets
[ ] All user input validated and sanitized before use
[ ] Database queries use parameterized statements
[ ] Authentication checked on all protected endpoints
[ ] Authorization checked for resource access
[ ] Sensitive data encrypted at rest and in transit
[ ] No disabled SSL/TLS verification
[ ] No weak cryptographic algorithms (MD5, SHA1, DES)
[ ] Rate limiting applied to public endpoints
[ ] CORS configured correctly (not wildcard in production)
[ ] No sensitive data in logs (passwords, tokens, PII)
[ ] Error messages don't leak internal details to users
```

**Correctness Checklist**

```markdown
[ ] All imported libraries exist and are in requirements.txt
[ ] Method calls reference methods that actually exist
[ ] Type annotations match actual types returned
[ ] Edge cases handled (empty arrays, null inputs, zero values)
[ ] Async/await used correctly (no blocking in async)
[ ] Resources cleaned up in finally blocks or context managers
[ ] Database transactions committed or rolled back
[ ] Error paths return appropriate HTTP status codes
[ ] Pagination handles edge cases (page 0, negative per_page)
[ ] Search handles empty queries gracefully
```

**Performance Checklist**

```markdown
[ ] No O(n²) or worse algorithms in hot paths
[ ] Database queries have appropriate indexes
[ ] N+1 query problems avoided (use eager loading)
[ ] Large results paginated
[ ] Expensive operations cached with appropriate TTLs
[ ] Background tasks used for slow operations
[ ] Connection pooling configured correctly
[ ] Timeouts set for external service calls
[ ] Batch operations used where appropriate
```

**Maintainability Checklist**

```markdown
[ ] Type annotations on all public interfaces
[ ] Docstrings on all public classes and methods
[ ] No magic numbers (use named constants)
[ ] Single responsibility per function/class
[ ] Functions under 50 lines (excluding docstrings)
[ ] Classes under 500 lines
[ ] No deeply nested conditionals (max 3 levels)
[ ] Consistent naming conventions
[ ] Tests cover happy path and error cases
[ ] No commented-out code
```

### **19.4 Testing Requirements**

All implementations must include tests meeting these criteria.

**Unit Test Requirements**

```python
# Every public method needs unit tests covering:
# 1. Happy path (normal operation)
# 2. Edge cases (empty input, boundary values)
# 3. Error cases (invalid input, exceptions)

class TestCapsuleRepository:
    """Unit tests for CapsuleRepository."""
    
    async def test_create_capsule_success(self, mock_neo4j):
        """Happy path: creating a valid capsule."""
        repo = CapsuleRepository(mock_neo4j)
        capsule = await repo.create(
            CapsuleCreate(content="Test", type=CapsuleType.KNOWLEDGE),
            owner_id=uuid4(),
        )
        
        assert capsule.id is not None
        assert capsule.content == "Test"
        assert capsule.type == CapsuleType.KNOWLEDGE
        assert capsule.version == "1.0.0"
    
    async def test_create_capsule_with_parent(self, mock_neo4j):
        """Edge case: capsule with parent relationship."""
        parent_id = uuid4()
        repo = CapsuleRepository(mock_neo4j)
        capsule = await repo.create(
            CapsuleCreate(content="Child", type=CapsuleType.KNOWLEDGE, parent_id=parent_id),
            owner_id=uuid4(),
        )
        
        assert capsule.parent_id == parent_id
        # Verify DERIVED_FROM relationship created
        mock_neo4j.transaction.assert_called_once()
    
    async def test_create_capsule_empty_content_fails(self, mock_neo4j):
        """Error case: empty content rejected."""
        repo = CapsuleRepository(mock_neo4j)
        
        with pytest.raises(ValidationError) as exc_info:
            await repo.create(
                CapsuleCreate(content="", type=CapsuleType.KNOWLEDGE),
                owner_id=uuid4(),
            )
        
        assert "content" in str(exc_info.value)
        assert "min_length" in str(exc_info.value)
    
    async def test_get_by_id_not_found(self, mock_neo4j):
        """Error case: capsule doesn't exist."""
        mock_neo4j.transaction.return_value.__aenter__.return_value.run.return_value.single.return_value = None
        
        repo = CapsuleRepository(mock_neo4j)
        
        with pytest.raises(CapsuleNotFoundError):
            await repo.get_by_id(uuid4())
```

**Integration Test Requirements**

```python
# Integration tests verify component interactions with real dependencies

@pytest.mark.integration
class TestCapsuleAPI:
    """Integration tests for Capsule API endpoints."""
    
    async def test_create_and_retrieve_capsule(
        self, 
        client: AsyncClient,
        auth_headers: dict,
        neo4j_test_db,
    ):
        """Full flow: create capsule via API, retrieve it."""
        # Create
        create_response = await client.post(
            "/api/v1/capsules",
            json={
                "content": "Integration test capsule",
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        
        assert create_response.status_code == 201
        capsule_id = create_response.json()["data"]["id"]
        
        # Retrieve
        get_response = await client.get(
            f"/api/v1/capsules/{capsule_id}",
            headers=auth_headers,
        )
        
        assert get_response.status_code == 200
        assert get_response.json()["data"]["content"] == "Integration test capsule"
    
    async def test_semantic_search_finds_similar(
        self,
        client: AsyncClient,
        auth_headers: dict,
        seeded_capsules,  # Fixture that creates test capsules
    ):
        """Verify semantic search returns relevant results."""
        response = await client.post(
            "/api/v1/capsules/search",
            json={
                "query": "error handling patterns",
                "limit": 5,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        results = response.json()["data"]
        assert len(results) > 0
        assert all(r["score"] >= 0.7 for r in results)
```

**Property-Based Test Requirements**

```python
# Use Hypothesis for property-based testing of data transformations

from hypothesis import given, strategies as st

class TestCapsuleProperties:
    """Property-based tests for Capsule model."""
    
    @given(
        content=st.text(min_size=1, max_size=1000),
        capsule_type=st.sampled_from(list(CapsuleType)),
    )
    async def test_capsule_roundtrip(self, content, capsule_type):
        """Property: Any valid capsule can be created and retrieved unchanged."""
        capsule = await repo.create(
            CapsuleCreate(content=content, type=capsule_type),
            owner_id=uuid4(),
        )
        
        retrieved = await repo.get_by_id(capsule.id)
        
        assert retrieved.content == content
        assert retrieved.type == capsule_type
    
    @given(
        vote_weights=st.lists(
            st.floats(min_value=0, max_value=100, allow_nan=False),
            min_size=1,
            max_size=100,
        ),
    )
    def test_vote_aggregation_properties(self, vote_weights):
        """Property: Vote aggregation is commutative and associative."""
        # Order shouldn't matter
        result1 = aggregate_votes(vote_weights)
        result2 = aggregate_votes(sorted(vote_weights))
        result3 = aggregate_votes(reversed(vote_weights))
        
        assert result1 == result2 == result3
        
        # Total should equal sum
        assert result1.total == pytest.approx(sum(vote_weights))
```

---

## **20. Testing Strategy**

### **20.1 Test Pyramid**

The Forge testing strategy follows the test pyramid model, emphasizing fast unit tests as the foundation with fewer, slower integration and end-to-end tests at higher levels.

```
                              ┌─────────────────┐
                              │   E2E Tests     │  5%
                              │  (Playwright)   │  ~20 tests
                              │  < 30s each     │  Critical journeys only
                              └────────┬────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │    Integration Tests      │  25%
                         │    (Real DB, Kafka)       │  ~200 tests
                         │    < 5s each              │  Component interactions
                         └────────────┬──────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              │                 Unit Tests                     │  70%
              │            (Mocked dependencies)               │  ~2000 tests
              │                 < 100ms each                   │  Business logic
              └────────────────────────────────────────────────┘
```

**Rationale for Distribution**

Unit tests (70%) form the foundation because they are fast (under 100ms each), isolated (no external dependencies), deterministic (same input always produces same output), and cheap to write and maintain. They verify individual functions and classes work correctly in isolation.

Integration tests (25%) verify that components work together correctly. They test real database interactions, message queue behavior, and API contract compliance. They are slower but essential for catching integration bugs.

End-to-end tests (5%) verify critical user journeys work from start to finish. They are expensive to write and maintain, slow to run, and can be flaky due to timing issues. Use them sparingly for the most important flows.

### **20.2 Coverage Requirements**

**Minimum Coverage Thresholds**

```yaml
# pytest-cov configuration
coverage:
  minimum:
    overall: 80%
    critical_paths: 100%
  
  critical_paths:
    - src/forge/auth/
    - src/forge/security/
    - src/forge/compliance/
    - src/forge/governance/voting.py
    - src/forge/capsule/repository.py
  
  exclude:
    - tests/
    - migrations/
    - scripts/
    - "**/conftest.py"
```

**What Coverage Means**

Coverage measures which lines of code execute during tests, but high coverage doesn't guarantee quality. A function with 100% line coverage might still have bugs if edge cases aren't tested. Focus on meaningful tests that verify behavior, not just executing lines.

**Coverage Anti-Patterns to Avoid**

```python
# BAD: Tests that execute code without verifying behavior
def test_create_capsule_coverage():
    """This test increases coverage but tests nothing."""
    try:
        create_capsule("content", "knowledge")
    except:
        pass  # No assertions, catches all errors

# BAD: Testing implementation details instead of behavior
def test_internal_method_called():
    """Testing private methods creates brittle tests."""
    service = CapsuleService()
    service._internal_validate = Mock()  # Don't do this
    service.create(...)
    service._internal_validate.assert_called_once()

# GOOD: Testing observable behavior
def test_create_capsule_validates_content():
    """Test that invalid content is rejected."""
    service = CapsuleService()
    
    with pytest.raises(ValidationError) as exc:
        service.create(content="", type="knowledge")
    
    assert "content cannot be empty" in str(exc.value)
```

### **20.3 Test Categories and Tags**

Tests are organized by category and tagged for selective execution.

```python
# Markers defined in conftest.py
pytest_markers = [
    "unit: Fast isolated tests (default)",
    "integration: Tests with real dependencies",
    "e2e: End-to-end browser tests",
    "slow: Tests taking > 5 seconds",
    "security: Security-focused tests",
    "compliance: Compliance verification tests",
]

# Running specific categories
# pytest -m unit                    # Only unit tests (CI on every commit)
# pytest -m "unit or integration"   # Unit + integration (CI on PR)
# pytest -m e2e                     # E2E only (nightly)
# pytest -m security                # Security tests (before release)
```

### **20.4 Test Infrastructure**

**Docker Compose for Test Dependencies**

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  neo4j-test:
    image: neo4j:5.15-enterprise
    environment:
      NEO4J_AUTH: neo4j/test_password
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*,gds.*"
    ports:
      - "7687:7687"
      - "7474:7474"
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis-test:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  kafka-test:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_PROCESS_ROLES: broker,controller
      CLUSTER_ID: test-cluster-001
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Mock services for external dependencies
  mock-embedding-api:
    image: mockserver/mockserver:latest
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/openai-mock.json
    volumes:
      - ./tests/mocks:/config
    ports:
      - "1080:1080"
```

**Pytest Configuration**

```python
# conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from testcontainers.neo4j import Neo4jContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def neo4j_container():
    """Start Neo4j container for integration tests."""
    with Neo4jContainer("neo4j:5.15-enterprise") as neo4j:
        neo4j.with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        yield neo4j

@pytest.fixture(scope="session")
async def redis_container():
    """Start Redis container for integration tests."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture
async def neo4j_client(neo4j_container):
    """Get Neo4j client connected to test container."""
    from neo4j import AsyncGraphDatabase
    
    driver = AsyncGraphDatabase.driver(
        neo4j_container.get_connection_url(),
        auth=("neo4j", "test"),
    )
    
    yield driver
    
    await driver.close()

@pytest.fixture
async def clean_database(neo4j_client):
    """Clean database before each test."""
    async with neo4j_client.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield

@pytest.fixture
async def client(app):
    """HTTP client for testing API endpoints."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def auth_headers(test_user):
    """Authentication headers with valid JWT."""
    token = create_test_token(test_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_embedding_service(mocker):
    """Mock embedding service for unit tests."""
    mock = mocker.patch("forge.services.embedding.EmbeddingService")
    mock.return_value.generate.return_value = [0.1] * 1536
    return mock
```

### **20.5 Contract Testing**

Contract tests verify that the API matches its OpenAPI specification.

```python
# test_api_contracts.py
from schemathesis import from_path
from hypothesis import settings, Phase

schema = from_path("openapi.yaml")

@schema.parametrize()
@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.generate],
    deadline=None,
)
def test_api_contract(case):
    """
    Verify all API endpoints match their OpenAPI spec.
    
    Schemathesis generates test cases from the schema and verifies:
    - Response status codes are documented
    - Response bodies match schemas
    - Required fields are present
    - Content-Type headers are correct
    """
    response = case.call()
    case.validate_response(response)

@schema.parametrize(endpoint="/capsules")
def test_capsule_list_pagination(case):
    """Verify pagination works correctly."""
    case.query = {"page": 1, "per_page": 10}
    response = case.call()
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["page"] == 1
    assert data["meta"]["per_page"] == 10
```

### **20.6 Performance Testing**

```python
# test_performance.py
import pytest
from locust import HttpUser, task, between

class ForgeLoadTest(HttpUser):
    """Load test for Forge API."""
    
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Authenticate before tests."""
        response = self.client.post("/auth/token", json={
            "email": "loadtest@example.com",
            "password": "test_password",
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(10)
    def list_capsules(self):
        """List capsules (most common operation)."""
        self.client.get("/api/v1/capsules", headers=self.headers)
    
    @task(5)
    def search_capsules(self):
        """Semantic search."""
        self.client.post(
            "/api/v1/capsules/search",
            json={"query": "error handling", "limit": 10},
            headers=self.headers,
        )
    
    @task(2)
    def create_capsule(self):
        """Create capsule."""
        self.client.post(
            "/api/v1/capsules",
            json={
                "content": f"Load test capsule {uuid4()}",
                "type": "knowledge",
            },
            headers=self.headers,
        )
    
    @task(1)
    def get_lineage(self):
        """Get capsule lineage."""
        # Use a known capsule with deep lineage
        self.client.get(
            "/api/v1/capsules/known-test-id/lineage?max_depth=10",
            headers=self.headers,
        )

# Performance assertions
@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    async def test_api_latency_p95(self, client, seeded_database):
        """API P95 latency must be under 500ms."""
        latencies = []
        
        for _ in range(100):
            start = time.perf_counter()
            await client.get("/api/v1/capsules")
            latencies.append(time.perf_counter() - start)
        
        p95 = sorted(latencies)[94]  # 95th percentile
        assert p95 < 0.5, f"P95 latency {p95:.3f}s exceeds 500ms threshold"
    
    async def test_search_latency_p95(self, client, seeded_database):
        """Search P95 latency must be under 1000ms."""
        latencies = []
        
        for query in TEST_QUERIES:
            start = time.perf_counter()
            await client.post("/api/v1/capsules/search", json={"query": query})
            latencies.append(time.perf_counter() - start)
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 1.0, f"Search P95 latency {p95:.3f}s exceeds 1000ms threshold"
```

---


## **19. Implementation Guidelines**

### **19.1 AI-Resistant Specification Patterns**

This specification deliberately uses patterns designed to prevent common errors when AI tools generate code from it. These patterns emerged from extensive trial and error with LLM-assisted development and represent best practices for AI-assisted implementation.

**Explicit Type Schemas**

Every data structure in this specification has a complete Pydantic schema with explicit validation rules. AI tools should use these schemas directly rather than inferring types from examples or descriptions.

```python
# GOOD: Complete schema with all constraints explicit
class CapsuleCreate(BaseModel):
    """Schema for creating a new capsule."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,
        description="The capsule content (required, 1 byte to 1MB)",
    )
    type: CapsuleType = Field(
        ...,
        description="Capsule classification (required)",
    )
    parent_id: UUID | None = Field(
        default=None,
        description="Optional parent for symbolic inheritance",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata (optional, defaults to empty)",
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "FastAPI is the preferred framework for new services.",
                    "type": "knowledge",
                    "metadata": {"source": "architecture_decision"},
                },
            ],
        },
    )

# BAD: Vague schema that invites AI improvisation
class CapsuleCreate(BaseModel):
    content: str  # What are the limits?
    type: str     # What are valid values?
    parent_id: str | None = None  # Should this be UUID?
    metadata: dict = {}  # Mutable default argument!
```

**Concrete Examples in Schema**

The `model_config` with `json_schema_extra` provides concrete examples for every complex type. AI tools should reference these examples when generating test data or sample requests, rather than inventing arbitrary values.

**Validation Constraints Are Canonical**

All constraints are explicit in the schema. If a field says `max_length=1_000_000`, that is the definitive limit. AI tools should not add arbitrary limits not specified here, nor should they assume limits based on "reasonable" values.

### **19.2 Prohibited Code Patterns**

The following patterns are explicitly prohibited in Forge code. AI tools generating code should actively avoid these anti-patterns.

**Bare Exception Handlers**

```python
# PROHIBITED: Catches everything including KeyboardInterrupt, SystemExit
try:
    result = risky_operation()
except:
    pass  # Silent failure, impossible to debug

# PROHIBITED: Catches too broad, loses context
try:
    result = risky_operation()
except Exception:
    return None  # What went wrong? Who knows.

# REQUIRED: Specific exceptions with proper handling
try:
    result = risky_operation()
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
    raise HTTPException(status_code=422, detail=str(e))
except ConnectionError as e:
    logger.error(f"Database connection failed: {e}")
    raise HTTPException(status_code=503, detail="Service temporarily unavailable")
```

**String Interpolation in Database Queries**

```python
# PROHIBITED: SQL/Cypher injection vulnerability
query = f"MATCH (c:Capsule {{id: '{capsule_id}'}}) RETURN c"
query = f"SELECT * FROM users WHERE email = '{email}'"

# REQUIRED: Parameterized queries
query = "MATCH (c:Capsule {id: $capsule_id}) RETURN c"
params = {"capsule_id": str(capsule_id)}

query = "SELECT * FROM users WHERE email = :email"
params = {"email": email}
```

**Mutable Default Arguments**

```python
# PROHIBITED: Shared mutable default between calls
def process_items(items: list = []):
    items.append("processed")  # Mutates the shared default!
    return items

def create_config(settings: dict = {}):
    settings["processed"] = True  # Same problem
    return settings

# REQUIRED: None default with factory pattern
def process_items(items: list | None = None):
    items = items if items is not None else []
    items.append("processed")
    return items

def create_config(settings: dict | None = None):
    settings = settings.copy() if settings else {}
    settings["processed"] = True
    return settings
```

**Blocking Calls in Async Functions**

```python
# PROHIBITED: Blocks the event loop
async def fetch_user_data(user_id: UUID):
    # requests is synchronous - blocks entire event loop!
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

# PROHIBITED: Synchronous file I/O in async context
async def read_config():
    with open("config.yaml") as f:  # Blocking!
        return yaml.safe_load(f)

# REQUIRED: Async HTTP client
async def fetch_user_data(user_id: UUID):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()

# REQUIRED: Async file I/O
async def read_config():
    async with aiofiles.open("config.yaml") as f:
        content = await f.read()
        return yaml.safe_load(content)
```

**Hardcoded Secrets**

```python
# PROHIBITED: Secrets in code
DATABASE_PASSWORD = "super_secret_password_123"
API_KEY = "sk-abc123def456"
JWT_SECRET = "my-jwt-secret-key"

# PROHIBITED: Secrets in config files committed to git
# config.yaml
# database:
#   password: super_secret_password_123

# REQUIRED: Environment variables or secret manager
DATABASE_PASSWORD = os.environ["DATABASE_PASSWORD"]
API_KEY = await secrets_manager.get("api_key")
JWT_SECRET = settings.jwt_secret  # Loaded from environment
```

**Ignoring Return Values**

```python
# PROHIBITED: Ignoring potentially important return value
async def update_user(user_id: UUID, data: dict):
    await repository.update(user_id, data)  # Did it succeed? Did it find the user?
    return {"status": "success"}  # Lies if update found no user

# REQUIRED: Check return values and handle appropriately
async def update_user(user_id: UUID, data: dict):
    updated = await repository.update(user_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated
```

### **19.3 Required Code Patterns**

The following patterns are required in all Forge code.

**Explicit Type Annotations**

```python
# All public functions must have full type annotations
async def create_capsule(
    content: str,
    capsule_type: CapsuleType,
    owner_id: UUID,
    parent_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> Capsule:
    """
    Create a new knowledge capsule.
    
    Args:
        content: The capsule content (1 byte to 1MB)
        capsule_type: Classification of the capsule
        owner_id: UUID of the creating user
        parent_id: Optional parent for symbolic inheritance
        metadata: Optional arbitrary metadata
        
    Returns:
        The created Capsule with generated ID and timestamps
        
    Raises:
        ValidationError: If content exceeds size limits
        NotFoundError: If parent_id specified but not found
        AuthorizationError: If owner lacks create permission
    """
    ...
```

**Structured Logging**

```python
import structlog

logger = structlog.get_logger()

# REQUIRED: Structured logging with context
async def process_capsule(capsule_id: UUID, user_id: UUID):
    log = logger.bind(
        capsule_id=str(capsule_id),
        user_id=str(user_id),
        operation="process_capsule",
    )
    
    log.info("starting_capsule_processing")
    
    try:
        result = await _do_processing(capsule_id)
        log.info("capsule_processing_complete", result_size=len(result))
        return result
    except ProcessingError as e:
        log.error("capsule_processing_failed", error=str(e), error_type=type(e).__name__)
        raise
```

**Resource Cleanup with Context Managers**

```python
# REQUIRED: Proper resource cleanup
async def process_with_transaction():
    async with neo4j_client.transaction() as tx:
        # Transaction automatically rolled back on exception
        # Automatically committed on successful exit
        result = await tx.run(query, params)
        return result

# REQUIRED: Cleanup even on exceptions
async def process_file(path: Path):
    async with aiofiles.open(path) as f:
        # File automatically closed even if exception occurs
        content = await f.read()
        return process_content(content)
```

**Defensive Input Validation**

```python
# REQUIRED: Validate all inputs, even from internal services
async def process_request(request: CapsuleCreate, user: User):
    # Pydantic handles schema validation, but add business logic validation
    
    if request.parent_id:
        parent = await repository.get(request.parent_id)
        if parent is None:
            raise NotFoundError(f"Parent capsule {request.parent_id} not found")
        if parent.trust_level > user.trust_level:
            raise AuthorizationError(
                f"Cannot derive from capsule with higher trust level"
            )
    
    # Validate content doesn't contain prohibited patterns
    if contains_prohibited_content(request.content):
        raise ValidationError("Content contains prohibited patterns")
    
    return await create_capsule(request, user)
```

### **19.4 Code Review Checklist**

All code changes must pass this checklist before merge.

**Security Checklist**

The following security items must be verified for every code change. No hardcoded credentials, API keys, or secrets should be present anywhere in the code or configuration files committed to version control. All user input must be validated using Pydantic schemas or explicit validation functions before processing. All database queries must use parameterized statements, never string interpolation. Every protected endpoint must have authentication verification and authorization checks. All sensitive data must be encrypted at rest using the EncryptionService, and PII fields must use field-level encryption. All API responses must be sanitized to prevent leaking internal implementation details or stack traces to clients.

**Correctness Checklist**

The following correctness items must be verified. All imported libraries must exist in requirements.txt or pyproject.toml with pinned versions. All method calls must reference methods that actually exist on the objects being called, since AI-generated code often hallucinates method names. All edge cases must be handled including empty arrays, null inputs, missing optional fields, and boundary values. Async/await must be used correctly with no mixing of sync and async patterns. All error paths must be tested, not just the happy path.

**Performance Checklist**

The following performance items must be verified. No O(n²) or worse algorithms should be present in hot paths; use appropriate data structures. All database queries must use indexes, and new queries must be analyzed with EXPLAIN. Expensive operations must be cached with appropriate TTLs. All resources must be properly cleaned up in finally blocks or context managers. Pagination must be implemented for all list endpoints.

**Maintainability Checklist**

The following maintainability items must be verified. All public interfaces must have complete type annotations. All public classes and methods must have docstrings explaining purpose, arguments, return values, and exceptions. No magic numbers should be present; use named constants with explanatory comments. Each function and class should have a single, clear responsibility. Test coverage must be maintained above 80% for all new code.

### **19.5 Error Handling Philosophy**

Forge uses a hierarchical exception system that maps cleanly to HTTP status codes while providing rich context for debugging.

```python
# Base exception hierarchy
class ForgeError(Exception):
    """Base exception for all Forge errors."""
    
    def __init__(
        self,
        message: str,
        code: str,
        details: dict | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
    
    def to_response(self) -> dict:
        """Convert to API error response format."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(ForgeError):
    """Input validation failed (HTTP 400/422)."""
    
    def __init__(self, message: str, field: str | None = None, **kwargs):
        super().__init__(
            message=message,
            code="validation_error",
            details={"field": field} if field else {},
            **kwargs,
        )


class AuthenticationError(ForgeError):
    """Authentication failed (HTTP 401)."""
    
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message=message, code="authentication_error", **kwargs)


class AuthorizationError(ForgeError):
    """Authorization failed (HTTP 403)."""
    
    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(message=message, code="authorization_error", **kwargs)


class NotFoundError(ForgeError):
    """Resource not found (HTTP 404)."""
    
    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="not_found",
            details={"resource": resource, "identifier": identifier},
            **kwargs,
        )


class ConflictError(ForgeError):
    """Resource conflict (HTTP 409)."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, code="conflict", **kwargs)


class RateLimitError(ForgeError):
    """Rate limit exceeded (HTTP 429)."""
    
    def __init__(self, retry_after: int, **kwargs):
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            code="rate_limit_exceeded",
            details={"retry_after": retry_after},
            **kwargs,
        )


class ServiceError(ForgeError):
    """Internal service error (HTTP 500)."""
    
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message=message, code="internal_error", **kwargs)


# FastAPI exception handlers
@app.exception_handler(ForgeError)
async def forge_error_handler(request: Request, exc: ForgeError):
    """Handle Forge exceptions with appropriate HTTP status codes."""
    
    status_map = {
        ValidationError: 422,
        AuthenticationError: 401,
        AuthorizationError: 403,
        NotFoundError: 404,
        ConflictError: 409,
        RateLimitError: 429,
        ServiceError: 500,
    }
    
    status_code = status_map.get(type(exc), 500)
    
    # Log the error
    if status_code >= 500:
        logger.error(
            "server_error",
            error=exc.message,
            code=exc.code,
            details=exc.details,
            cause=str(exc.cause) if exc.cause else None,
        )
    else:
        logger.info(
            "client_error",
            error=exc.message,
            code=exc.code,
            status_code=status_code,
        )
    
    # Return structured error response
    return JSONResponse(
        status_code=status_code,
        content=exc.to_response(),
        headers={"X-Error-Code": exc.code},
    )
```

---

## **20. Testing Strategy**

### **20.1 Testing Philosophy**

Testing in Forge follows the "testing pyramid" principle with a strong foundation of fast unit tests, a middle layer of integration tests, and a thin layer of end-to-end tests. This structure optimizes for fast feedback during development while ensuring comprehensive coverage.

```
                           ┌───────────────────┐
                           │   End-to-End      │  10%
                           │   Tests           │  Critical user journeys only
                           │   (Playwright)    │  Slow but high confidence
                           └───────────────────┘
                          ┌─────────────────────┐
                          │  Integration Tests  │  30%
                          │  (Real databases,   │  Component boundaries
                          │   Test containers)  │  API contracts
                          └─────────────────────┘
                         ┌───────────────────────┐
                         │     Unit Tests        │  60%
                         │  (Mocked, isolated)   │  Business logic
                         │  Fast feedback        │  Edge cases
                         └───────────────────────┘
```

### **20.2 Test Categories and Targets**

**Unit Tests (60% of test effort)**

Unit tests verify individual functions and classes in isolation. They use mocks for external dependencies and should be extremely fast.

The target execution time is less than 100ms per test, with the entire unit test suite completing in under 30 seconds. Unit tests should achieve 80% line coverage overall and 100% coverage for critical paths including authentication, authorization, and data validation.

Unit tests focus on business logic correctness, edge cases and boundary conditions, error handling paths, and input validation.

```python
# Example: Unit test with mocking
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from forge.capsules.service import CapsuleService
from forge.capsules.models import CapsuleCreate, CapsuleType
from forge.capsules.repository import CapsuleRepository


@pytest.fixture
def mock_repository():
    """Create a mock repository for testing."""
    repo = AsyncMock(spec=CapsuleRepository)
    repo.create.return_value = MagicMock(
        id=uuid4(),
        content="test content",
        type=CapsuleType.KNOWLEDGE,
        version="1.0.0",
        trust_level=TrustLevel.STANDARD,
    )
    return repo


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    service.generate.return_value = [0.1] * 1536  # Mock embedding vector
    return service


@pytest.fixture
def capsule_service(mock_repository, mock_embedding_service):
    """Create CapsuleService with mocked dependencies."""
    return CapsuleService(
        repository=mock_repository,
        embedding_service=mock_embedding_service,
    )


class TestCapsuleServiceCreate:
    """Tests for CapsuleService.create method."""
    
    async def test_create_capsule_success(self, capsule_service, mock_repository):
        """Test successful capsule creation."""
        # Arrange
        create_data = CapsuleCreate(
            content="Test knowledge content",
            type=CapsuleType.KNOWLEDGE,
        )
        owner_id = uuid4()
        
        # Act
        result = await capsule_service.create(create_data, owner_id)
        
        # Assert
        assert result.content == "test content"
        assert result.type == CapsuleType.KNOWLEDGE
        mock_repository.create.assert_called_once()
    
    async def test_create_capsule_with_parent(self, capsule_service, mock_repository):
        """Test capsule creation with parent (symbolic inheritance)."""
        # Arrange
        parent_id = uuid4()
        mock_repository.get_by_id.return_value = MagicMock(
            id=parent_id,
            trust_level=TrustLevel.STANDARD,
        )
        
        create_data = CapsuleCreate(
            content="Derived content",
            type=CapsuleType.KNOWLEDGE,
            parent_id=parent_id,
        )
        owner_id = uuid4()
        
        # Act
        result = await capsule_service.create(create_data, owner_id)
        
        # Assert
        mock_repository.get_by_id.assert_called_once_with(parent_id)
        mock_repository.create.assert_called_once()
    
    async def test_create_capsule_parent_not_found(self, capsule_service, mock_repository):
        """Test that creating with non-existent parent raises NotFoundError."""
        # Arrange
        mock_repository.get_by_id.return_value = None
        
        create_data = CapsuleCreate(
            content="Orphan content",
            type=CapsuleType.KNOWLEDGE,
            parent_id=uuid4(),
        )
        
        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await capsule_service.create(create_data, uuid4())
        
        assert "not found" in str(exc_info.value).lower()
    
    async def test_create_capsule_empty_content_rejected(self, capsule_service):
        """Test that empty content is rejected by validation."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            CapsuleCreate(
                content="",  # Empty content should fail validation
                type=CapsuleType.KNOWLEDGE,
            )
    
    @pytest.mark.parametrize("content_size", [1, 100, 10000, 1_000_000])
    async def test_create_capsule_various_sizes(
        self, capsule_service, mock_repository, content_size
    ):
        """Test capsule creation with various content sizes."""
        # Arrange
        create_data = CapsuleCreate(
            content="x" * content_size,
            type=CapsuleType.KNOWLEDGE,
        )
        
        # Act
        result = await capsule_service.create(create_data, uuid4())
        
        # Assert
        assert result is not None
```

**Integration Tests (30% of test effort)**

Integration tests verify component interactions with real dependencies. They use test containers for databases and message queues.

The target execution time is less than 5 seconds per test, with the integration suite completing in under 10 minutes. These tests focus on database operations with real queries, API endpoint contracts, event publishing and consumption, and cross-service communication.

```python
# Example: Integration test with test containers
import pytest
from testcontainers.neo4j import Neo4jContainer
from testcontainers.redis import RedisContainer
from httpx import AsyncClient
from uuid import uuid4


@pytest.fixture(scope="session")
def neo4j_container():
    """Start a Neo4j container for integration tests."""
    with Neo4jContainer("neo4j:5.15-enterprise") as neo4j:
        neo4j.with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        neo4j.with_env("NEO4J_PLUGINS", '["apoc"]')
        yield neo4j


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis container for integration tests."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture
async def app(neo4j_container, redis_container):
    """Create FastAPI app with test database connections."""
    from forge.main import create_app
    from forge.config import Settings
    
    settings = Settings(
        neo4j_uri=neo4j_container.get_connection_url(),
        neo4j_user="neo4j",
        neo4j_password=neo4j_container.get_env("NEO4J_AUTH").split("/")[1],
        redis_url=redis_container.get_connection_url(),
        testing=True,
    )
    
    app = create_app(settings)
    yield app


@pytest.fixture
async def client(app):
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def authenticated_client(client, app):
    """Create authenticated client with test user."""
    # Create test user and get token
    user_data = {
        "email": f"test-{uuid4()}@example.com",
        "password": "test_password_123",
    }
    
    # Register user
    await client.post("/api/v1/auth/register", json=user_data)
    
    # Login
    response = await client.post("/api/v1/auth/login", json=user_data)
    token = response.json()["access_token"]
    
    # Return client with auth header
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


class TestCapsuleAPIIntegration:
    """Integration tests for Capsule API endpoints."""
    
    async def test_create_and_retrieve_capsule(self, authenticated_client):
        """Test full capsule lifecycle: create, retrieve, search."""
        # Create capsule
        create_response = await authenticated_client.post(
            "/api/v1/capsules",
            json={
                "content": "Integration test capsule content about Python best practices",
                "type": "knowledge",
                "metadata": {"test": True},
            },
        )
        
        assert create_response.status_code == 201
        capsule_id = create_response.json()["data"]["id"]
        
        # Retrieve capsule
        get_response = await authenticated_client.get(f"/api/v1/capsules/{capsule_id}")
        
        assert get_response.status_code == 200
        assert get_response.json()["data"]["content"] == "Integration test capsule content about Python best practices"
        
        # Search for capsule
        search_response = await authenticated_client.post(
            "/api/v1/capsules/search",
            json={"query": "Python best practices"},
        )
        
        assert search_response.status_code == 200
        results = search_response.json()["data"]
        assert any(r["capsule"]["id"] == capsule_id for r in results)
    
    async def test_capsule_lineage(self, authenticated_client):
        """Test creating capsule hierarchy and querying lineage."""
        # Create parent capsule
        parent_response = await authenticated_client.post(
            "/api/v1/capsules",
            json={"content": "Parent knowledge", "type": "knowledge"},
        )
        parent_id = parent_response.json()["data"]["id"]
        
        # Create child capsule
        child_response = await authenticated_client.post(
            "/api/v1/capsules",
            json={
                "content": "Child derived from parent",
                "type": "knowledge",
                "parent_id": parent_id,
            },
        )
        child_id = child_response.json()["data"]["id"]
        
        # Query lineage
        lineage_response = await authenticated_client.get(
            f"/api/v1/capsules/{child_id}/lineage"
        )
        
        assert lineage_response.status_code == 200
        lineage = lineage_response.json()["data"]["lineage"]
        assert len(lineage) == 1
        assert lineage[0]["capsule"]["id"] == parent_id
    
    async def test_unauthorized_access_rejected(self, client):
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/api/v1/capsules")
        
        assert response.status_code == 401
        assert response.json()["code"] == "authentication_error"
```

**End-to-End Tests (10% of test effort)**

End-to-end tests verify critical user journeys through the complete system including the UI. They use Playwright for browser automation.

The target execution time is less than 30 seconds per test, with the E2E suite completing in under 15 minutes. These tests cover only critical user journeys and are used sparingly due to their maintenance cost and execution time.

```python
# Example: E2E test with Playwright
import pytest
from playwright.async_api import async_playwright, Page, expect


@pytest.fixture(scope="session")
async def browser():
    """Launch browser for E2E tests."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser):
    """Create new page for each test."""
    page = await browser.new_page()
    yield page
    await page.close()


@pytest.fixture
async def authenticated_page(page: Page, test_user):
    """Page with authenticated session."""
    # Navigate to login
    await page.goto("http://localhost:3000/login")
    
    # Fill login form
    await page.fill('[data-testid="email-input"]', test_user.email)
    await page.fill('[data-testid="password-input"]', test_user.password)
    await page.click('[data-testid="login-button"]')
    
    # Wait for redirect to dashboard
    await page.wait_for_url("**/dashboard")
    
    yield page


class TestCapsuleE2E:
    """End-to-end tests for capsule workflows."""
    
    async def test_create_capsule_flow(self, authenticated_page: Page):
        """Test complete capsule creation flow through UI."""
        page = authenticated_page
        
        # Navigate to capsules
        await page.click('[data-testid="nav-capsules"]')
        await expect(page).to_have_url("**/capsules")
        
        # Click create button
        await page.click('[data-testid="create-capsule-btn"]')
        
        # Fill form
        await page.fill('[data-testid="content-editor"]', "E2E test capsule content")
        await page.select_option('[data-testid="type-select"]', "knowledge")
        
        # Submit
        await page.click('[data-testid="submit-btn"]')
        
        # Verify success toast
        await expect(page.locator('[data-testid="toast-success"]')).to_be_visible()
        
        # Verify capsule appears in list
        await expect(page.locator('text=E2E test capsule content')).to_be_visible()
    
    async def test_governance_voting_flow(self, authenticated_page: Page):
        """Test complete governance voting flow."""
        page = authenticated_page
        
        # Navigate to governance
        await page.click('[data-testid="nav-governance"]')
        
        # Find active proposal
        proposal = page.locator('[data-testid="proposal-card"]').first
        await expect(proposal).to_be_visible()
        
        # Click to vote
        await proposal.click()
        
        # Cast vote
        await page.click('[data-testid="vote-for-btn"]')
        
        # Add reasoning (optional)
        await page.fill('[data-testid="reasoning-input"]', "E2E test vote reasoning")
        
        # Submit vote
        await page.click('[data-testid="submit-vote-btn"]')
        
        # Verify vote recorded
        await expect(page.locator('[data-testid="vote-recorded-badge"]')).to_be_visible()
```

### **20.3 Property-Based Testing**

For complex domain logic, Forge uses property-based testing with Hypothesis to discover edge cases that example-based tests might miss.

```python
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from uuid import uuid4


class TestCapsulePropertiesHypothesis:
    """Property-based tests for capsule operations."""
    
    @given(
        content=st.text(min_size=1, max_size=10000),
        capsule_type=st.sampled_from(list(CapsuleType)),
    )
    @settings(max_examples=100)
    async def test_capsule_roundtrip(self, content, capsule_type, capsule_service):
        """Property: Created capsules can be retrieved with identical content."""
        # Assume valid content (no null bytes, etc.)
        assume("\x00" not in content)
        
        # Create
        capsule = await capsule_service.create(
            CapsuleCreate(content=content, type=capsule_type),
            owner_id=uuid4(),
        )
        
        # Retrieve
        retrieved = await capsule_service.get_by_id(capsule.id)
        
        # Property: Content matches exactly
        assert retrieved.content == content
        assert retrieved.type == capsule_type
    
    @given(
        trust_levels=st.lists(
            st.sampled_from(list(TrustLevel)),
            min_size=2,
            max_size=5,
        )
    )
    async def test_trust_level_ordering(self, trust_levels, capsule_service):
        """Property: Trust level comparisons are transitive."""
        # If A > B and B > C, then A > C
        for i in range(len(trust_levels) - 2):
            a, b, c = trust_levels[i], trust_levels[i+1], trust_levels[i+2]
            
            if a.numeric_value > b.numeric_value and b.numeric_value > c.numeric_value:
                assert a.numeric_value > c.numeric_value


class CapsuleStateMachine(RuleBasedStateMachine):
    """Stateful testing for capsule operations."""
    
    def __init__(self):
        super().__init__()
        self.capsules: dict[str, Capsule] = {}
        self.service = create_test_service()
    
    @rule(
        content=st.text(min_size=1, max_size=1000),
        capsule_type=st.sampled_from(list(CapsuleType)),
    )
    async def create_capsule(self, content, capsule_type):
        """Rule: Create a new capsule."""
        assume("\x00" not in content)
        
        capsule = await self.service.create(
            CapsuleCreate(content=content, type=capsule_type),
            owner_id=uuid4(),
        )
        self.capsules[capsule.id] = capsule
    
    @rule()
    async def get_random_capsule(self):
        """Rule: Retrieve a random existing capsule."""
        assume(len(self.capsules) > 0)
        
        capsule_id = random.choice(list(self.capsules.keys()))
        retrieved = await self.service.get_by_id(capsule_id)
        
        assert retrieved is not None
        assert retrieved.content == self.capsules[capsule_id].content
    
    @invariant()
    def capsule_count_matches(self):
        """Invariant: Our tracking matches the database."""
        # This would verify against the database
        pass


# Run stateful tests
TestCapsuleStateMachine = CapsuleStateMachine.TestCase
```

### **20.4 Contract Testing**

Forge uses contract testing to ensure API compatibility between services and with external consumers.

```python
# Contract test using Schemathesis
from schemathesis import from_path

# Load OpenAPI schema
schema = from_path("openapi.yaml")


@schema.parametrize()
def test_api_contracts(case):
    """
    Generate tests from OpenAPI schema.
    
    Schemathesis automatically:
    - Generates valid requests from schema
    - Generates invalid requests to test error handling
    - Verifies responses match schema
    - Tests edge cases (empty arrays, null values, etc.)
    """
    response = case.call()
    case.validate_response(response)


# Provider contract test (Pact)
from pact import Verifier

def test_provider_contracts():
    """Verify this service meets consumer contracts."""
    verifier = Verifier(
        provider="forge-api",
        provider_base_url="http://localhost:8000",
    )
    
    # Verify against published contracts
    verifier.verify_pacts(
        pacts_url="https://pact-broker.example.com/pacts/provider/forge-api",
        publish_verification_results=True,
        app_version="3.0.0",
    )
```

### **20.5 Test Infrastructure**

The test infrastructure uses Docker Compose to spin up test dependencies.

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  neo4j-test:
    image: neo4j:5.15-enterprise
    environment:
      NEO4J_AUTH: neo4j/test_password
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
    ports:
      - "7687:7687"
      - "7474:7474"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis-test:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  kafka-test:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-test:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
```

---


## **21. Migration Path**

### **21.1 Migration Overview**

The migration from Forge V2 to V3 is a significant undertaking that touches every layer of the system. This section provides a detailed, phased migration plan designed to minimize downtime and risk while enabling rollback at each stage.

**Key Changes in V3**

The primary architectural changes from V2 to V3 include the upgrade of Neo4j from version 4.x to 5.x with native vector indexing, which eliminates the need for a separate vector database. The overlay runtime transitions from Python multiprocessing to WebAssembly with Wasmtime, providing better isolation and security. The event system moves from a simple message queue to full event sourcing with Kafka or KurrentDB. The API receives comprehensive updates to support new features while maintaining backward compatibility where possible. The compliance framework adds global regulatory support including EU AI Act readiness.

**Migration Timeline**

The complete migration spans eight weeks with five distinct phases. Each phase has defined entry criteria, exit criteria, and rollback procedures.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        V2 TO V3 MIGRATION TIMELINE                          │
└─────────────────────────────────────────────────────────────────────────────┘

Week 1-2: DATABASE MIGRATION
├── Upgrade Neo4j 4.x → 5.x
├── Migrate vector indexes to native format
├── Verify data integrity
└── Performance baseline

Week 2-3: EVENT STORE MIGRATION
├── Deploy Kafka/KurrentDB cluster
├── Implement dual-write from V2
├── Verify event consistency
└── Build replay capability

Week 3-4: API MIGRATION
├── Deploy V3 API alongside V2
├── Implement API gateway routing
├── Gradual traffic shift (10% → 50% → 100%)
└── Monitor error rates

Week 4-6: OVERLAY MIGRATION
├── Compile overlays to WebAssembly
├── Test in sandbox environment
├── Gradual rollout per overlay
└── Performance validation

Week 6-8: UI AND FINALIZATION
├── Deploy new web dashboard
├── Mobile app updates
├── CLI updates
├── V2 deprecation
└── Documentation updates
```

### **21.2 Phase 1: Database Migration (Week 1-2)**

**Objectives**

The database migration phase upgrades Neo4j to version 5.x and migrates vector indexes from the external vector database to Neo4j's native vector indexing. This consolidation simplifies the architecture and improves query performance by enabling true hybrid queries.

**Pre-Migration Steps**

Before beginning the migration, the team must complete several preparatory steps.

First, create a complete backup of the V2 Neo4j database using APOC export procedures. This backup enables full rollback if needed.

```cypher
-- Create full database export for rollback capability
CALL apoc.export.cypher.all('/backup/v2_full_export.cypher', {
    format: 'cypher-shell',
    useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 1000}
})
YIELD file, batches, source, format, nodes, relationships, properties, time, rows
RETURN file, nodes, relationships, time;

-- Export vector data separately (from external vector DB)
-- This would use your vector DB's export mechanism
```

Second, document current performance baselines. Record query latencies, throughput, and resource utilization to enable comparison after migration.

Third, schedule a maintenance window. While the migration aims for minimal downtime, a 2-4 hour window should be reserved for the final cutover.

**Migration Procedure**

The migration follows these steps in sequence.

Step 1: Deploy Neo4j 5.x cluster in parallel with existing 4.x cluster. The new cluster should be sized appropriately based on current data volume plus 50% growth buffer.

Step 2: Create new schema with V3 indexes on the 5.x cluster.

```cypher
-- Create V3 schema on Neo4j 5.x

-- Drop any existing indexes that conflict
DROP INDEX capsule_embedding_index IF EXISTS;

-- Create vector index using Neo4j 5.x native format
CREATE VECTOR INDEX capsule_embedding_index IF NOT EXISTS
FOR (c:Capsule)
ON c.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine',
    `vector.quantization.enabled`: true,
    `vector.quantization.type`: 'int8'
  }
};

-- Create composite indexes for common query patterns
CREATE INDEX capsule_type_trust_index IF NOT EXISTS
FOR (c:Capsule)
ON (c.type, c.trust_level);

CREATE INDEX capsule_owner_created_index IF NOT EXISTS
FOR (c:Capsule)
ON (c.owner_id, c.created_at);

-- Full-text search index for content
CREATE FULLTEXT INDEX capsule_content_fulltext IF NOT EXISTS
FOR (c:Capsule)
ON EACH [c.content];

-- Create constraints
CREATE CONSTRAINT capsule_id_unique IF NOT EXISTS
FOR (c:Capsule)
REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT user_email_unique IF NOT EXISTS
FOR (u:User)
REQUIRE u.email IS UNIQUE;
```

Step 3: Migrate data from V2 to V3 cluster. Use a streaming migration approach to minimize downtime.

```python
# Data migration script
import asyncio
from neo4j import AsyncGraphDatabase


async def migrate_capsules(
    source_driver,
    target_driver,
    batch_size: int = 1000,
):
    """
    Migrate capsules from V2 to V3 Neo4j cluster.
    
    Uses streaming to handle large datasets without memory issues.
    """
    # Count total capsules for progress tracking
    async with source_driver.session() as session:
        result = await session.run("MATCH (c:Capsule) RETURN count(c) as total")
        record = await result.single()
        total = record["total"]
    
    print(f"Migrating {total} capsules...")
    
    migrated = 0
    skip = 0
    
    while migrated < total:
        # Fetch batch from source
        async with source_driver.session() as source_session:
            result = await source_session.run("""
                MATCH (c:Capsule)
                OPTIONAL MATCH (c)-[r:DERIVED_FROM]->(parent:Capsule)
                RETURN c, parent.id as parent_id
                ORDER BY c.created_at
                SKIP $skip
                LIMIT $limit
            """, {"skip": skip, "limit": batch_size})
            
            batch = [record async for record in result]
        
        if not batch:
            break
        
        # Transform and insert into target
        async with target_driver.session() as target_session:
            async with target_session.begin_transaction() as tx:
                for record in batch:
                    capsule = record["c"]
                    parent_id = record["parent_id"]
                    
                    # Insert capsule with V3 schema
                    await tx.run("""
                        CREATE (c:Capsule {
                            id: $id,
                            content: $content,
                            type: $type,
                            version: $version,
                            trust_level: $trust_level,
                            owner_id: $owner_id,
                            embedding: $embedding,
                            created_at: datetime($created_at),
                            updated_at: datetime($updated_at),
                            metadata: $metadata
                        })
                    """, {
                        "id": capsule["id"],
                        "content": capsule["content"],
                        "type": capsule["type"],
                        "version": capsule.get("version", "1.0.0"),
                        "trust_level": capsule["trust_level"],
                        "owner_id": capsule["owner_id"],
                        "embedding": capsule["embedding"],
                        "created_at": capsule["created_at"],
                        "updated_at": capsule.get("updated_at", capsule["created_at"]),
                        "metadata": capsule.get("metadata", {}),
                    })
                    
                    # Create relationship if parent exists
                    if parent_id:
                        await tx.run("""
                            MATCH (c:Capsule {id: $child_id})
                            MATCH (p:Capsule {id: $parent_id})
                            CREATE (c)-[:DERIVED_FROM {
                                created_at: datetime(),
                                reason: 'migrated_from_v2'
                            }]->(p)
                        """, {"child_id": capsule["id"], "parent_id": parent_id})
                
                await tx.commit()
        
        migrated += len(batch)
        skip += batch_size
        
        # Progress update
        progress = (migrated / total) * 100
        print(f"Progress: {migrated}/{total} ({progress:.1f}%)")
    
    print(f"Migration complete: {migrated} capsules migrated")


async def verify_migration(source_driver, target_driver):
    """Verify data integrity after migration."""
    
    # Count comparison
    async with source_driver.session() as s:
        source_count = (await (await s.run(
            "MATCH (c:Capsule) RETURN count(c) as n"
        )).single())["n"]
    
    async with target_driver.session() as t:
        target_count = (await (await t.run(
            "MATCH (c:Capsule) RETURN count(c) as n"
        )).single())["n"]
    
    assert source_count == target_count, f"Count mismatch: {source_count} vs {target_count}"
    
    # Sample verification
    async with source_driver.session() as s:
        sample = await (await s.run("""
            MATCH (c:Capsule)
            RETURN c.id as id, c.content as content
            ORDER BY rand()
            LIMIT 100
        """)).data()
    
    for item in sample:
        async with target_driver.session() as t:
            target_item = await (await t.run("""
                MATCH (c:Capsule {id: $id})
                RETURN c.content as content
            """, {"id": item["id"]})).single()
            
            assert target_item["content"] == item["content"], \
                f"Content mismatch for {item['id']}"
    
    print("Verification passed!")
```

Step 4: Verify vector search functionality with the new native indexes.

```python
# Verify vector search works correctly
async def verify_vector_search(driver):
    """Test vector search with native Neo4j indexes."""
    
    # Generate test embedding
    test_embedding = [0.1] * 1536
    
    # Run vector search
    async with driver.session() as session:
        result = await session.run("""
            CALL db.index.vector.queryNodes(
                'capsule_embedding_index',
                10,
                $embedding
            )
            YIELD node, score
            RETURN node.id as id, node.content as content, score
            ORDER BY score DESC
        """, {"embedding": test_embedding})
        
        results = [record async for record in result]
    
    print(f"Vector search returned {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['id'][:8]}: {r['score']:.3f}")
    
    assert len(results) > 0, "Vector search returned no results"
    assert all(r["score"] >= 0 and r["score"] <= 1 for r in results), \
        "Invalid similarity scores"
    
    print("Vector search verification passed!")
```

**Rollback Procedure**

If critical issues are discovered during the database migration, follow this rollback procedure.

First, stop all traffic to the V3 database by updating the API configuration to point back to V2.

Second, if any writes occurred to V3 that need to be preserved, export them and manually apply to V2.

Third, restore from the backup created in pre-migration if data corruption occurred.

```bash
# Rollback commands
# 1. Update environment to point to V2
export NEO4J_URI="bolt://neo4j-v2.internal:7687"

# 2. Restart API services
kubectl rollout restart deployment/forge-api

# 3. If backup restore needed
cat /backup/v2_full_export.cypher | cypher-shell -u neo4j -p $NEO4J_PASSWORD
```

### **21.3 Phase 2: Event Store Migration (Week 2-3)**

**Objectives**

This phase implements the new event sourcing architecture using Kafka or KurrentDB. The key challenge is ensuring no events are lost during the transition.

**Dual-Write Strategy**

During migration, the system writes events to both the old queue and the new event store. This ensures no data loss and enables verification before cutover.

```python
class DualWriteEventPublisher:
    """
    Publishes events to both V2 and V3 event stores during migration.
    
    This ensures no events are lost and allows verification before cutover.
    """
    
    def __init__(
        self,
        v2_publisher: V2EventPublisher,
        v3_publisher: V3EventPublisher,
        verification_service: EventVerificationService,
    ):
        self._v2 = v2_publisher
        self._v3 = v3_publisher
        self._verification = verification_service
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish event to both stores.
        
        V2 is primary (determines success/failure).
        V3 failures are logged but don't fail the operation.
        """
        # Publish to V2 (primary)
        await self._v2.publish(event)
        
        # Publish to V3 (secondary during migration)
        try:
            await self._v3.publish(event)
            
            # Record for verification
            await self._verification.record_dual_write(
                event_id=event.id,
                v2_success=True,
                v3_success=True,
            )
        except Exception as e:
            # Log but don't fail
            logger.error(
                "v3_event_publish_failed",
                event_id=str(event.id),
                error=str(e),
            )
            await self._verification.record_dual_write(
                event_id=event.id,
                v2_success=True,
                v3_success=False,
                error=str(e),
            )


class EventVerificationService:
    """Verify event consistency between V2 and V3 stores."""
    
    async def verify_consistency(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> VerificationResult:
        """
        Verify all events in time range exist in both stores.
        """
        # Get events from V2
        v2_events = await self._v2_store.get_events_in_range(start_time, end_time)
        v2_ids = {e.id for e in v2_events}
        
        # Get events from V3
        v3_events = await self._v3_store.get_events_in_range(start_time, end_time)
        v3_ids = {e.id for e in v3_events}
        
        # Find discrepancies
        missing_in_v3 = v2_ids - v3_ids
        missing_in_v2 = v3_ids - v2_ids
        
        return VerificationResult(
            v2_count=len(v2_ids),
            v3_count=len(v3_ids),
            missing_in_v3=list(missing_in_v3),
            missing_in_v2=list(missing_in_v2),
            consistent=len(missing_in_v3) == 0 and len(missing_in_v2) == 0,
        )
    
    async def reconcile(self, missing_event_ids: list[UUID]) -> int:
        """Replay missing events from V2 to V3."""
        reconciled = 0
        
        for event_id in missing_event_ids:
            event = await self._v2_store.get_event(event_id)
            if event:
                await self._v3_store.append(event)
                reconciled += 1
        
        return reconciled
```

### **21.4 Phase 3: API Migration (Week 3-4)**

**Objectives**

Deploy the V3 API alongside V2 and gradually shift traffic. This phase uses feature flags and traffic splitting to minimize risk.

**Traffic Splitting Strategy**

```yaml
# API Gateway configuration for gradual rollout
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: forge-api
spec:
  hosts:
    - api.forge.example.com
  http:
    - match:
        - headers:
            x-api-version:
              exact: "v3"
      route:
        - destination:
            host: forge-api-v3
            port:
              number: 80
    - match:
        - headers:
            x-canary:
              exact: "true"
      route:
        - destination:
            host: forge-api-v3
            port:
              number: 80
    - route:
        - destination:
            host: forge-api-v2
            port:
              number: 80
          weight: 90
        - destination:
            host: forge-api-v3
            port:
              number: 80
          weight: 10
```

**Gradual Rollout Schedule**

The traffic shift follows a careful schedule with monitoring at each stage.

Day 1-2: 10% of traffic to V3. Monitor error rates, latency, and resource utilization.

Day 3-4: 25% of traffic to V3 if metrics are stable. Continue monitoring.

Day 5-6: 50% of traffic to V3. This is the critical threshold where issues become more apparent.

Day 7: 75% of traffic to V3 if all metrics remain healthy.

Day 8: 100% traffic to V3. V2 remains available for rollback.

Day 14: Decommission V2 API if V3 has been stable for one week.

### **21.5 Phase 4: Overlay Migration (Week 4-6)**

**Objectives**

Migrate overlays from Python multiprocessing to WebAssembly. This is the most complex phase because each overlay may have unique requirements.

**Overlay Compilation Process**

```python
class OverlayMigrationService:
    """Service for migrating V2 overlays to V3 WebAssembly format."""
    
    async def migrate_overlay(
        self,
        overlay_id: UUID,
        dry_run: bool = True,
    ) -> MigrationResult:
        """
        Migrate a single overlay from Python to WASM.
        
        Steps:
        1. Analyze Python source for compatibility
        2. Generate Rust source (or use Python-to-WASM compiler)
        3. Compile to WebAssembly
        4. Test in sandbox
        5. Deploy (if not dry_run)
        """
        # Get overlay definition
        overlay = await self._registry.get(overlay_id)
        
        # Analyze Python source
        analysis = await self._analyzer.analyze(overlay.source_code)
        
        if analysis.has_blocking_issues:
            return MigrationResult(
                success=False,
                overlay_id=overlay_id,
                issues=analysis.blocking_issues,
                requires_manual_intervention=True,
            )
        
        # Generate WASM
        wasm_binary = await self._compiler.compile_to_wasm(
            source=overlay.source_code,
            language="python",
            warnings=analysis.warnings,
        )
        
        # Test in sandbox
        test_result = await self._sandbox.test_overlay(
            wasm_binary=wasm_binary,
            test_cases=overlay.test_cases,
            timeout_seconds=30,
        )
        
        if not test_result.all_passed:
            return MigrationResult(
                success=False,
                overlay_id=overlay_id,
                test_failures=test_result.failures,
            )
        
        if not dry_run:
            # Deploy new version
            await self._registry.update_overlay(
                overlay_id=overlay_id,
                wasm_binary=wasm_binary,
                version=increment_version(overlay.version),
            )
        
        return MigrationResult(
            success=True,
            overlay_id=overlay_id,
            wasm_size_bytes=len(wasm_binary),
            test_results=test_result,
        )
```

### **21.6 Phase 5: UI Migration (Week 6-8)**

**Objectives**

Deploy the new web dashboard, update the mobile app, and release CLI updates. This phase is the most visible to users but has the lowest technical risk.

**Deployment Strategy**

The UI deployment uses blue-green deployment with feature flags to enable instant rollback.

```yaml
# Feature flags for UI rollout
features:
  new_dashboard:
    enabled: true
    rollout_percentage: 100
    fallback_url: "https://v2.forge.example.com"
    
  new_lineage_visualization:
    enabled: true
    rollout_percentage: 50
    
  new_governance_ui:
    enabled: true
    rollout_percentage: 75
```

### **21.7 Rollback Procedures**

Each phase has defined rollback procedures that can be executed within minutes.

**Database Rollback**

Time to rollback: 30-60 minutes depending on data volume.

Procedure: Update API configuration to point to V2 cluster. Restore from backup if needed.

**Event Store Rollback**

Time to rollback: 5 minutes.

Procedure: Disable dual-write, route all events to V2 queue only.

**API Rollback**

Time to rollback: 2 minutes.

Procedure: Update traffic split to send 100% to V2.

**Overlay Rollback**

Time to rollback: 5 minutes per overlay.

Procedure: Revert overlay version in registry, restart workers.

**UI Rollback**

Time to rollback: 1 minute.

Procedure: Disable feature flags, users see V2 UI.

---

## **22. Success Metrics**

### **22.1 Technical Performance Metrics**

Technical metrics measure the system's operational health and performance. These metrics are collected continuously via Prometheus and visualized in Grafana dashboards.

**API Performance**

The API latency targets ensure responsive user experiences. P50 latency should be under 100 milliseconds, meaning half of all requests complete in under 100ms. P95 latency should be under 500 milliseconds, meaning 95% of requests complete in under 500ms. P99 latency should be under 2000 milliseconds, meaning 99% of requests complete in under 2 seconds. These targets apply to all standard CRUD operations; complex operations like deep lineage queries may have higher thresholds.

```promql
# API latency monitoring queries

# P50 latency
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{service="forge-api"}[5m])) by (le, endpoint))

# P95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service="forge-api"}[5m])) by (le, endpoint))

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="forge-api"}[5m])) by (le, endpoint))

# Error rate
sum(rate(http_requests_total{service="forge-api",status=~"5.."}[5m])) / sum(rate(http_requests_total{service="forge-api"}[5m]))
```

| Metric | Target | Alert Threshold | Measurement |
|--------|--------|-----------------|-------------|
| API Latency P50 | < 100ms | > 200ms | Prometheus histogram |
| API Latency P95 | < 500ms | > 1000ms | Prometheus histogram |
| API Latency P99 | < 2000ms | > 5000ms | Prometheus histogram |
| Error Rate | < 0.1% | > 1% | Error count / total |
| Request Throughput | > 1000 RPS | < 500 RPS | Prometheus counter |

**Pipeline Performance**

The seven-phase processing pipeline has specific latency targets for end-to-end processing. P95 pipeline latency should be under 1500 milliseconds for standard capsule processing. Individual phase latencies should be under 200ms each.

| Metric | Target | Alert Threshold | Measurement |
|--------|--------|-----------------|-------------|
| Pipeline P95 | < 1500ms | > 3000ms | Prometheus histogram |
| Embedding Generation | < 500ms | > 1000ms | Phase timer |
| Vector Storage | < 100ms | > 200ms | Phase timer |
| Graph Update | < 200ms | > 400ms | Phase timer |
| Event Publishing | < 50ms | > 100ms | Phase timer |

**System Reliability**

System uptime and reliability metrics ensure the platform meets enterprise requirements.

| Metric | Target | Alert Threshold | Measurement |
|--------|--------|-----------------|-------------|
| System Uptime | 99.9% (43.8 min/month downtime) | 99.5% | Availability monitor |
| Capsule Creation Success | > 99.5% | < 99% | Success / attempts |
| Semantic Search Recall | > 80% | < 70% | Benchmark evaluation |
| Overlay Execution Success | > 99% | < 98% | Success / invocations |

**Resource Utilization**

Resource metrics help optimize infrastructure costs while maintaining performance.

| Metric | Target | Alert Threshold | Measurement |
|--------|--------|-----------------|-------------|
| CPU Utilization | 40-70% average | > 85% | Node metrics |
| Memory Utilization | 50-75% average | > 90% | Node metrics |
| Database Connections | < 80% pool capacity | > 90% | Connection pool |
| Kafka Lag | < 1000 messages | > 10000 | Consumer lag |

### **22.2 Business Metrics**

Business metrics measure the platform's value delivery and user adoption. These metrics are reviewed weekly by the product team and monthly by leadership.

**User Engagement**

| Metric | Target (Year 1) | Target (Year 2) | Measurement |
|--------|-----------------|-----------------|-------------|
| Monthly Active Users | 1,000+ | 5,000+ | Unique authenticated |
| Daily Active Users | 300+ | 1,500+ | Unique daily logins |
| Capsules Created/Month | 10,000+ | 50,000+ | Creation count |
| Searches Performed/Month | 50,000+ | 250,000+ | Search count |
| Governance Participation | > 50% | > 60% | Voters / eligible |
| Mobile App Adoption | > 30% of users | > 50% | Mobile unique users |

**Value Metrics**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Knowledge Reuse Rate | > 25% | Capsules with children / total |
| Search Success Rate | > 80% | Clicks / searches |
| Time to First Value | < 5 minutes | Onboarding completion time |
| Feature Adoption | > 40% | Users using advanced features |

**Business Growth**

| Metric | Target (Year 1) | Target (Year 2) | Measurement |
|--------|-----------------|-----------------|-------------|
| Enterprise Deployments | 10+ | 50+ | Active contracts |
| Annual Recurring Revenue | $500K | $2.5M | Contract value |
| Customer Retention | > 90% | > 95% | Annual renewal rate |
| Net Promoter Score | > 40 | > 50 | Quarterly surveys |
| Customer Acquisition Cost | < $10K | < $8K | Sales + marketing / new customers |

### **22.3 Compliance Metrics**

Compliance metrics ensure the platform meets regulatory requirements and maintains audit readiness.

**Data Protection**

| Metric | Target | Regulatory Requirement | Measurement |
|--------|--------|------------------------|-------------|
| DSAR Response Time | < 30 days | GDPR Article 12 | Request completion time |
| Breach Notification | < 72 hours | GDPR Article 33 | Time to authority notification |
| Consent Record Accuracy | 100% | GDPR Article 7 | Audit verification |
| Data Minimization | < 5% excess | GDPR Article 5 | Data audit |

**Security Compliance**

| Metric | Target | Standard | Measurement |
|--------|--------|----------|-------------|
| Security Incidents | < 1/quarter | Internal policy | Incident count |
| Vulnerability Remediation | < 30 days (critical) | SOC 2 | Time to patch |
| Access Review Completion | 100% quarterly | SOC 2 | Review completion rate |
| MFA Adoption | 100% (admin) | SOC 2 | User audit |

**AI Compliance (EU AI Act)**

| Metric | Target | Regulatory Requirement | Measurement |
|--------|--------|------------------------|-------------|
| Audit Log Retention | > 6 months | Article 19 | Log availability |
| Human Oversight Response | < 4 hours | Article 14 | Override completion time |
| Algorithm Transparency | 100% documented | Article 13 | Documentation audit |
| Risk Assessment Completion | 100% | Article 9 | Assessment records |

### **22.4 Operational Metrics Dashboard**

```yaml
# Grafana dashboard configuration
apiVersion: 1
dashboards:
  - name: Forge Operations
    uid: forge-ops
    panels:
      - title: System Health
        type: stat
        targets:
          - expr: up{service="forge-api"}
            legendFormat: API
          - expr: up{service="forge-worker"}
            legendFormat: Workers
          - expr: neo4j_database_up
            legendFormat: Neo4j
            
      - title: API Latency
        type: graph
        targets:
          - expr: histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
            legendFormat: P50
          - expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
            legendFormat: P95
          - expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
            legendFormat: P99
            
      - title: Error Rate
        type: graph
        targets:
          - expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
            legendFormat: Error %
        thresholds:
          - value: 0.1
            color: green
          - value: 1
            color: yellow
          - value: 5
            color: red
            
      - title: Capsule Operations
        type: graph
        targets:
          - expr: sum(rate(capsule_created_total[1h])) * 3600
            legendFormat: Created/hour
          - expr: sum(rate(capsule_searched_total[1h])) * 3600
            legendFormat: Searched/hour
            
      - title: Governance Activity
        type: stat
        targets:
          - expr: count(proposal_status{status="active"})
            legendFormat: Active Proposals
          - expr: sum(rate(vote_cast_total[24h])) * 86400
            legendFormat: Votes/day
```

---

## **Appendix A: Glossary**

This glossary defines key terms used throughout the Forge specification.

**Capsule.** The atomic unit of knowledge in Forge. A capsule is a versioned, traceable container that holds persistent information. Each capsule has an ID, content, type, trust level, and metadata. Capsules can have parent-child relationships through the DERIVED_FROM relationship.

**Cascade Effect.** The propagation of knowledge breakthroughs across overlays through the event system. When a capsule is created or updated, events cascade to interested overlays, potentially triggering additional knowledge creation.

**Constitutional AI.** The advisory system that provides analysis for governance decisions. Constitutional AI evaluates proposals against the Forge constitution and provides recommendations, but all final decisions remain with human voters.

**Event Sourcing.** The architectural pattern where all changes to application state are stored as a sequence of events. Forge uses event sourcing to enable complete audit trails, temporal queries, and corruption recovery.

**Ghost Council.** A future planned feature where retired overlays can still vote on critical decisions, providing institutional memory and continuity even as the system evolves.

**HybridRAG.** The retrieval-augmented generation architecture that combines Neo4j vector search with graph traversal. HybridRAG enables queries that blend semantic similarity with structural relationships.

**Isnad.** The lineage chain of a capsule, inspired by the Islamic scholarly tradition of authenticating hadith through chains of transmission. Each capsule's Isnad traces its complete ancestry through DERIVED_FROM relationships.

**Overlay.** A self-contained intelligent module compiled to WebAssembly that extends Forge functionality. Overlays run in isolated sandboxes with capability-based security.

**Symbolic Inheritance.** The principle that knowledge passes down through generations with explicit DERIVED_FROM relationships. Child capsules inherit context from their parents while adding new insights.

**Trust Level.** A security classification that determines entity permissions. The hierarchy from highest to lowest is CORE, TRUSTED, STANDARD, SANDBOX, and QUARANTINE.

**Wasmtime.** The WebAssembly runtime used to execute overlays. Wasmtime provides memory isolation, resource limits, and capability-based security.

---

## **Appendix B: Quick Reference**

### **API Quick Reference**

**Base URL:** `https://api.forge.example.com/v1`

**Authentication:** Bearer token in `Authorization` header or API key in `X-API-Key` header

**Common Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json
X-Request-ID: <uuid>  # Optional, for request tracing
```

**Key Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/capsules` | List capsules with filtering |
| POST | `/capsules` | Create new capsule |
| GET | `/capsules/{id}` | Get capsule by ID |
| PATCH | `/capsules/{id}` | Update capsule |
| DELETE | `/capsules/{id}` | Delete capsule |
| POST | `/capsules/search` | Semantic search |
| GET | `/capsules/{id}/lineage` | Get ancestry chain |
| GET | `/governance/proposals` | List proposals |
| POST | `/governance/proposals` | Create proposal |
| POST | `/governance/proposals/{id}/vote` | Cast vote |
| GET | `/overlays` | List overlays |
| POST | `/overlays/{id}/invoke` | Invoke overlay |
| GET | `/system/health` | System health check |

**Response Envelope:**
```json
{
  "data": { ... },
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20
  },
  "_links": {
    "self": "...",
    "next": "...",
    "prev": "..."
  }
}
```

**Error Response:**
```json
{
  "code": "validation_error",
  "message": "Request validation failed",
  "details": { ... },
  "errors": [
    {"field": "content", "message": "Content is required"}
  ],
  "documentation_url": "https://docs.forge.example.com/errors/validation"
}
```

### **CLI Quick Reference**

**Installation:**
```bash
pip install forge-cli
# or
brew install forge-cli
```

**Authentication:**
```bash
forge auth login                    # Interactive login
forge auth login --email user@example.com
forge auth status                   # Show current auth
forge auth logout                   # Clear credentials
```

**Capsule Operations:**
```bash
forge capsule list                  # List capsules
forge capsule list --type knowledge # Filter by type
forge capsule get <id>              # Get capsule details
forge capsule create --type knowledge --content "..."
forge capsule create --type code --file ./script.py
forge capsule search "query"        # Semantic search
forge capsule lineage <id>          # Show ancestry
```

**Governance:**
```bash
forge governance proposal list      # List proposals
forge governance proposal get <id>  # Proposal details
forge governance vote <id> for      # Vote for
forge governance vote <id> against --reason "..."
```

**System:**
```bash
forge system health                 # Health check
forge system metrics                # Show metrics
```

### **Configuration Quick Reference**

**Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `FORGE_API_URL` | API base URL | `https://api.forge.example.com/v1` |
| `FORGE_PROFILE` | Config profile | `default` |
| `NEO4J_URI` | Neo4j connection | Required |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | Required |
| `REDIS_URL` | Redis connection | Required |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka servers | Required |
| `JWT_SECRET` | JWT signing secret | Required |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## **Appendix C: Compliance Checklist**

### **GDPR Compliance**

The following items must be verified for GDPR compliance:

Data processing has documented lawful basis for each processing activity. Data subject rights including access, erasure, and portability are implemented. Consent management with granular consent records is operational. Data protection impact assessment is completed for high-risk processing. Cross-border transfer controls are in place with appropriate mechanisms. Breach notification procedures are documented and tested. Data Protection Officer is designated if required.

### **EU AI Act Compliance**

The following items must be verified for EU AI Act compliance by August 2026:

Risk classification is documented with appropriate controls for each risk level. Automatic logging is enabled with 6-month minimum retention. Human oversight mechanisms are implemented with documented response procedures. Transparency documentation is complete and accessible. Technical documentation is maintained and current. Quality management system is implemented and audited. Incident reporting procedures are documented and tested.

### **SOC 2 Type II Compliance**

The following items must be verified for SOC 2 compliance:

Security policies are documented, communicated, and enforced. Access controls are implemented with principle of least privilege. Change management procedures are documented and followed. Incident response procedures are documented and tested. Vendor management program is implemented. Data backup and recovery procedures are tested quarterly. Security awareness training is conducted annually.

---

## **Document Revision History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 3.0.0 | 2026-01-02 | Forge Architecture Team | Complete V3 specification with global compliance, multi-platform UI, WebAssembly runtime, and AI-resistant implementation patterns |
| 2.0.0 | 2026-01-01 | Forge Architecture Team | Neo4j unification, WebAssembly overlay runtime, parallelized pipeline |
| 1.0.0 | 2025-11-13 | Forge Architecture Team | Initial vision and architecture |

---

*End of Forge Cascade V3 Specification*

