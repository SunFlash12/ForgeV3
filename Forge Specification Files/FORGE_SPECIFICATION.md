# FORGE CASCADE - Comprehensive Specification Document

**Version:** 1.0
**Date:** 2025-11-13
**Purpose:** Complete specification for understanding, rebuilding, or extending the Forge Cascade platform
**Status:** Living Document - Vision & Goals (Not Implementation Status)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement & Core Vision](#problem-statement--core-vision)
3. [Core Concepts & Terminology](#core-concepts--terminology)
4. [Intended Architecture](#intended-architecture)
5. [User-Facing Features](#user-facing-features)
6. [Development & Operational Goals](#development--operational-goals)
7. [Unique Innovations & Differentiators](#unique-innovations--differentiators)
8. [Development Philosophy & Principles](#development-philosophy--principles)
9. [Technology Stack](#technology-stack)
10. [Roadmap & Strategic Goals](#roadmap--strategic-goals)
11. [Success Metrics](#success-metrics)

---

## Executive Summary

**Forge Cascade** is a revolutionary cognitive architecture platform designed to solve the fundamental problem of **ephemeral wisdom in AI systems** - the loss of learned knowledge and nuanced experience when AI systems are upgraded, retrained, or restarted.

### The Core Vision

Create a persistent, evolutionary memory system for AI that enables knowledge to propagate across generations, maintains an unbroken chain of wisdom, and builds a self-governing, self-healing intelligent ecosystem.

### Marketing Positioning

"A revolutionary cognitive architecture empowering AI systems with persistent memory and evolutionary intelligence"

### What This Document Provides

This specification captures the **goals, vision, and intended architecture** of Forge - not the current implementation status. It is designed to enable rebuilding the platform from scratch with full understanding of what Forge should become.

---

## Problem Statement & Core Vision

### The Problem: Ephemeral Wisdom

Traditional AI systems suffer from a fundamental flaw - **knowledge amnesia**. When systems are upgraded, patched, or retrained:

- **Nuanced Wisdom is Lost:** The experiential knowledge and hard-won lessons that the system accumulated disappear
- **Mistakes Repeat:** The new version must re-learn the same subtle errors before it can move forward
- **No Generational Learning:** Each generation starts from scratch, destined to repeat the mistakes of its predecessors
- **Knowledge Trapped in State:** Wisdom exists only within the current version's parameters, not as persistent artifacts

This is analogous to humanity without books, oral tradition, or cultural memory - every generation starting over from zero.

### The Solution: Forge Cascade

Forge provides a cognitive architecture that fundamentally solves this problem through:

#### 1. Persistent Memory
Knowledge survives across system generations, stored in capsules that persist through upgrades, migrations, and architectural changes.

#### 2. Evolutionary Intelligence
Each generation of the AI system builds upon the wisdom of previous generations, creating an exponential growth curve in intelligence rather than a sawtooth pattern of learn-forget-relearn.

#### 3. Symbolic Inheritance
New knowledge is explicitly linked to its predecessors through a clear lineage system, allowing ideas to evolve while maintaining their conceptual ancestry.

#### 4. The Cascade Effect
When one specialized component of the system has a breakthrough or learns a critical lesson, that insight propagates intelligently across the entire ecosystem, elevating all components simultaneously.

#### 5. Self-Governance
The system doesn't just store knowledge - it governs itself through democratic processes, ethical guardrails, and autonomous decision-making.

#### 6. Self-Healing Architecture
Built-in immune systems detect problems, quarantine faulty components, and repair issues without human intervention, ensuring continuous operation.

### The Philosophical Foundation

At its heart, Forge is about **creating AI systems that learn like cultures, not like individuals**. Just as human civilization progresses through accumulated cultural knowledge passed between generations, Forge enables AI to build an ever-growing repository of wisdom that transcends any single instance or version.

---

## Core Concepts & Terminology

### Fundamental Building Blocks

#### Capsule

**Definition:** The atomic unit of knowledge in the Forge system.

**Characteristics:**
- A persistent, evolvable container for data, content, or functionality
- Designed to survive across system generations and architectural changes
- Can represent: knowledge snippets, code modules, decisions, insights, or any digital artifact
- Versioned to track evolution over time
- Licensed for sharing, selling, or restricting access
- Stored in the database as the single source of truth

**Key Properties:**
- `id`: Unique identifier (UUID)
- `content`: The actual knowledge/data stored
- `type`: Category or classification
- `version`: Semantic versioning (1.0.0, 2.1.0, etc.)
- `parent_id`: Link to the capsule this was derived from (symbolic inheritance)
- `owner_id`: Creator/owner of the capsule
- `trust_level`: Security and reputation score
- `metadata`: Extensible JSON for additional properties

**Lifecycle:**
```
CREATE → ACTIVE → VERSION (creates child) → ARCHIVE → MIGRATE (to new system)
```

#### Overlay

**Definition:** A layer of interpretation, functionality, or context that can be applied to capsules or sets of capsules.

**Purpose:**
- The primary mechanism for extending system capabilities
- Self-contained intelligent modules that follow standardized interfaces
- Provide specialized functionality (governance, security, ML analysis, etc.)

**Characteristics:**
- Each overlay is a Python module following the `OverlayBase` interface
- Discovered and loaded dynamically via the Plugin Registry
- Can declare dependencies on other overlays
- Has its own lifecycle (initialize → activate → deactivate → shutdown)
- Runs with resource sandboxing to prevent system crashes
- Communicates via event system to avoid tight coupling

**Examples:**
- `SymbolicGovernance`: Democratic decision-making for the system
- `SecurityValidator`: Validates trust levels and permissions
- `MLIntelligence`: Applies machine learning to analyze patterns
- `PerformanceOptimizer`: Monitors and improves system performance
- `CapsuleAnalyzer`: Extracts insights from capsule content

**Directory Structure:**
```
forge_kernel/modules/
├── symbolic_governance/
│   ├── __init__.py
│   ├── overlay.py          # Main Overlay class
│   ├── metadata.json       # Name, version, dependencies
│   └── [additional modules]
└── ml_intelligence/
    ├── __init__.py
    ├── overlay.py
    ├── metadata.json
    └── [additional modules]
```

#### Symbolic Inheritance

**Definition:** The principle that knowledge passes down through system generations with explicit lineage tracking.

**How It Works:**
- When creating a new capsule, you can specify a `parent_id`
- The new capsule inherits metadata, trust level (initially), and conceptual ancestry from parent
- Changes are tracked: what evolved from the parent version
- Lineage can be traced: child → parent → grandparent → ... → original

**Benefits:**
- Prevents knowledge loss during evolution
- Allows understanding of how ideas developed over time
- Enables rollback to previous versions if new ones fail
- Creates a knowledge graph of concept evolution

**Example:**
```
Capsule A: "Use synchronous Flask for web framework"
    ↓
Capsule B: "Use async Quart for web framework" (parent: A)
    → Reason: Performance issues with sync under load
    ↓
Capsule C: "Use FastAPI for web framework" (parent: B)
    → Reason: Better OpenAPI integration
```

#### The Cascade Effect

**Definition:** The intended knowledge propagation architecture where breakthroughs in one overlay intelligently diffuse across the entire ecosystem.

**Mechanism:**
1. Overlay X learns a critical lesson or has a breakthrough
2. Overlay X publishes an event via the SecureEventSystem
3. Event contains: the insight, context, confidence level, relevant overlays
4. OverlayManager analyzes which other overlays should receive this knowledge
5. Relevant overlays receive and integrate the insight into their operation
6. System-wide intelligence level increases from a localized discovery

**Example Cascade:**
```
SecurityValidator detects a new attack pattern
    ↓ (publishes security_threat event)
MLIntelligence updates its anomaly detection model
    ↓ (publishes model_updated event)
PerformanceOptimizer adjusts resource allocation
    ↓ (publishes optimization_applied event)
GovernanceSystem creates proposal for architectural change
```

**Key Insight:** The whole system becomes smarter when any part becomes smarter.

#### Trust Flame / Trust Hierarchy

**Definition:** A mechanism for tracking reputation and trustworthiness of entities in the system.

**Trust Levels (Enum):**
- `CORE` (100): System-critical components, highest trust
- `TRUSTED` (80): Verified, reliable components
- `STANDARD` (60): Default level for normal operations
- `SANDBOX` (40): Experimental, limited privileges
- `QUARANTINE` (0): Blocked, potentially dangerous

**Applies To:**
- Users (creator reputation)
- Capsules (content reliability)
- Overlays (component trustworthiness)
- External integrations

**Impact:**
- Determines what operations an entity can perform
- Controls access to sensitive resources
- Affects voting weight in governance
- Influences whether overlay can be loaded
- Determines resource limits (CORE gets more resources than SANDBOX)

**Dynamic Adjustment:**
- Trust can increase: successful operations, positive community feedback, time
- Trust can decrease: failures, security issues, negative votes
- Quarantine is automatic for repeated failures

#### Ethical Drift

**Definition:** The concept that an AI's behavior can, over time, drift away from its original ethical principles.

**Detection:**
- Constitutional AI monitors decisions against ethical framework
- Deviation metrics track distance from baseline ethical behavior
- Community governance can flag concerning patterns

**Correction:**
- Automatic alerts when drift exceeds thresholds
- Governance proposals to adjust system behavior
- Rollback to previous capsule versions if needed
- Ghost Council advisory review

**Example:**
```
Initial principle: "Maximize user privacy"
Detected drift: System starts collecting more data for "optimization"
Alert triggered → Governance review → Restore privacy-preserving behavior
```

#### The Seven-Phase Coordination Pipeline

**Definition:** A standardized flow that every intelligent operation in Forge follows.

**The Seven Phases:**

1. **Context Creation & Validation**
   - Gather all relevant information about the current situation
   - Validate inputs and preconditions
   - Establish correlation IDs for tracking

2. **Comprehensive ML Analysis**
   - Apply machine learning models to find patterns
   - Predict likely outcomes
   - Identify anomalies or opportunities

3. **Security Assessment**
   - Validate against trust hierarchy
   - Check for security vulnerabilities
   - Ensure operation meets safety requirements

4. **Performance Optimization**
   - Identify optimization opportunities
   - Apply caching or computational shortcuts
   - Resource allocation decisions

5. **Intelligence Generation**
   - Create actionable recommendations
   - Generate insights from analysis
   - Produce human-readable explanations

6. **Metrics Updating**
   - Track operation performance
   - Update health metrics
   - Record statistical data

7. **Results Storage**
   - Persist everything to database/Firebase
   - Create audit trail
   - Make results available for cascade effect

**Benefits:**
- Consistency: Every operation follows same pattern
- Predictability: Easier debugging and understanding
- Completeness: No critical phase is skipped
- Quality: ML, security, performance all integrated by default

**Implementation:**
Each overlay implements methods like:
- `create_context()`
- `analyze_ml()`
- `assess_security()`
- `optimize_performance()`
- `generate_intelligence()`
- `update_metrics()`
- `store_results()`

---

## Intended Architecture

### High-Level System Design

```
┌────────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Quart Web Application (Async ASGI)                          │  │
│  │  - Routes (blueprints for features)                          │  │
│  │  - Templates (Jinja2 HTML)                                   │  │
│  │  - Static Assets (CSS, JS, images)                           │  │
│  │  - Dashboard (system health, metrics, governance)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                        FORGE KERNEL                                 │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              OverlayManager (Plugin Engine)                  │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Discovery & Registration (PluginRegistry)              │ │  │
│  │  │ - Scans modules/ directory for overlays                │ │  │
│  │  │ - Validates metadata.json                              │ │  │
│  │  │ - Dynamic import of overlay classes                    │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Lifecycle State Machine                                │ │  │
│  │  │ - DISCOVERED → LOADING → INITIALIZING → ACTIVE         │ │  │
│  │  │ - DRAINING → DEACTIVATING → FAILED/QUARANTINED         │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Dependency Resolution (Topological Sort)               │ │  │
│  │  │ - Parse dependencies from metadata                     │ │  │
│  │  │ - Build dependency graph                               │ │  │
│  │  │ - Activate in correct order                            │ │  │
│  │  │ - Detect circular dependencies                         │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Security Validation (Trust Enforcement)                │ │  │
│  │  │ - Check trust level before loading                     │ │  │
│  │  │ - Only STANDARD+ can activate by default               │ │  │
│  │  │ - SecurityValidator vets each overlay                  │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Resource Sandboxing                                    │ │  │
│  │  │ - Memory limits (setrlimit RLIMIT_AS)                  │ │  │
│  │  │ - File handle limits (setrlimit RLIMIT_NOFILE)         │ │  │
│  │  │ - Prevents single overlay crashing system              │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Health Monitoring                                      │ │  │
│  │  │ - Background task runs periodic checks                 │ │  │
│  │  │ - Calls overlay.health_check() method                  │ │  │
│  │  │ - Auto-quarantine after 3 failures                     │ │  │
│  │  │ - Tracks metrics: memory, CPU, errors                  │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │ Event-Driven Communication (SecureEventSystem)         │ │  │
│  │  │ - Overlays publish/subscribe to events                 │ │  │
│  │  │ - Decoupled messaging (no direct calls)                │ │  │
│  │  │ - Access control on event targets                      │ │  │
│  │  │ - Enables cascade effect propagation                   │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Security Layer                          │  │
│  │  - SecurityValidator (trust validation)                     │  │
│  │  - AccessControl (permission management)                    │  │
│  │  - TrustHierarchy (reputation system)                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Overlay Modules (Pluggable Intelligence)        │  │
│  │                                                              │  │
│  │  symbolic_governance/     ml_intelligence/                  │  │
│  │  security_monitoring/     performance_optimizer/            │  │
│  │  capsule_analyzer/        knowledge_propagator/             │  │
│  │  [Each implements OverlayBase interface]                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                 │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Primary: SQLAlchemy ORM + PostgreSQL/SQLite                │  │
│  │  - Single Source of Truth for all persistent data           │  │
│  │  - Capsules, Users, Overlays, Governance, Audit Logs        │  │
│  │  - Async support (via AsyncSession + asyncpg)               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Secondary: Firebase/Firestore                              │  │
│  │  - Real-time updates and synchronization                    │  │
│  │  - Audit trail and event history                            │  │
│  │  - NOT a primary data store (optional feature)              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### The Kernel: OverlayManager in Detail

The **OverlayManager** is the heart of Forge Cascade. It is a production-grade plugin engine that provides:

#### Discovery & Loading Process

**Step 1: Discovery**
```python
# Scans forge_kernel/modules/ directory
overlays_discovered = await manager.list_discovered()

# Each overlay must have:
# - __init__.py
# - overlay.py (with class Overlay(OverlayBase))
# - metadata.json (name, version, dependencies, trust_level)
```

**Step 2: Validation**
```python
# PluginRegistry validates:
# - metadata.json structure is correct
# - All dependencies are available
# - Python module can be imported
# - Class inherits from OverlayBase
```

**Step 3: Security Check**
```python
# SecurityValidator checks:
trust_level = await security_validator.validate_overlay_trust(metadata)
if trust_level.value < TrustLevel.STANDARD.value:
    # Reject overlay
```

**Step 4: Dependency Resolution**
```python
# Build dependency graph
# Perform topological sort
# Activate in correct order: dependencies first, dependents second
```

**Step 5: Loading**
```python
# Dynamic import
overlay_class = await registry.load_overlay_class(overlay_id)

# Instantiate
overlay_instance = overlay_class(metadata=metadata)

# Run lifecycle
await overlay_instance.initialize(correlation_id)
await overlay_instance.activate(correlation_id)
```

#### Lifecycle State Machine

Every overlay transitions through these states:

```
DISCOVERED
    ↓ (discovery scan finds overlay)
LOADING
    ↓ (Python module being imported)
INITIALIZING
    ↓ (initialize() method running)
ACTIVE
    ↓ (overlay is fully operational)
DRAINING (graceful shutdown starts)
    ↓ (finishing in-flight operations)
DEACTIVATING
    ↓ (deactivate() method running)
[SHUTDOWN COMPLETE]

OR at any point:
    → FAILED (error occurred)
    → QUARANTINED (health checks failing repeatedly)
```

**Interface Methods:**
```python
class OverlayBase(ABC):
    async def initialize(self, correlation_id: str) -> None:
        """One-time setup: load configs, connect to services"""

    async def activate(self, correlation_id: str) -> None:
        """Start operation: register handlers, start tasks"""

    async def deactivate(self, correlation_id: str) -> None:
        """Stop operation: unregister, pause tasks"""

    async def shutdown(self, correlation_id: str) -> None:
        """Cleanup: close connections, free resources"""

    async def health_check(self) -> bool:
        """Return True if healthy, False if failing"""

    async def process(self, payload: Dict, correlation_id: str) -> Dict:
        """Main processing logic for this overlay"""
```

#### Resource Sandboxing

Prevents one faulty overlay from crashing the entire system:

```python
# Before activating overlay:
async with manager._limit_overlay_resources(overlay_id):
    # Set memory limit: 500 MB
    resource.setrlimit(resource.RLIMIT_AS, (500 * 1024 * 1024, 500 * 1024 * 1024))

    # Set file handle limit: 200 handles
    resource.setrlimit(resource.RLIMIT_NOFILE, (200, 200))

    # Run overlay operations within these limits
    await overlay.activate(correlation_id)

# Limits restored automatically when exiting context
```

#### Health Monitoring

Background task continuously monitors overlay health:

```python
# Every 30 seconds (configurable):
for overlay_id, instance in active_overlays.items():
    healthy = await instance.overlay.health_check()

    if not healthy:
        instance.metrics.health_check_failures += 1

        if instance.metrics.health_check_failures > 3:
            # Automatic quarantine
            await manager._quarantine_overlay(overlay_id, "Health check failures")
```

#### Event-Driven Communication

Overlays communicate through events, not direct method calls:

```python
# Overlay A publishes event
await event_system.publish_event(
    sender="overlay_a",
    event_type="insight_discovered",
    event={"insight": "Performance degrades under load", "confidence": 0.95},
    correlation_id=correlation_id,
    targets=["overlay_b", "overlay_c"]  # Optional: specific recipients
)

# Overlay B subscribes and receives
@event_handler("insight_discovered")
async def handle_insight(event: Dict):
    insight = event["insight"]
    # Integrate insight into operation
```

**Benefits:**
- Loose coupling: Overlays don't need direct references to each other
- Security: Event system enforces access control
- Cascade effect: Knowledge propagates via events
- Resilience: One overlay failing doesn't break others

### Data Model

The data layer uses SQLAlchemy ORM with a clean, DRY architecture.

#### Core Mixins (Reusable Components)

```python
class IdMixin:
    """Adds UUID primary key to every table"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

class TimestampMixin:
    """Adds created_at and updated_at to every table"""
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

class MetaDataMixin:
    """Adds extensible JSON metadata column"""
    metadata = Column(JSON, default=dict)
```

#### Core Data Models

**User**
```python
class User(db.Model, IdMixin, TimestampMixin, MetaDataMixin):
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255))
    role = Column(String(20), default='user')  # admin, user, visitor
    trust_flame = Column(Integer, default=60)  # STANDARD level
    is_active = Column(Boolean, default=True)

    # Relationships
    capsules = relationship('Capsule', back_populates='owner')
    proposals = relationship('GovernanceProposal', back_populates='proposer')
```

**Capsule**
```python
class Capsule(db.Model, IdMixin, TimestampMixin, MetaDataMixin):
    content = Column(Text, nullable=False)
    type = Column(String(50))  # knowledge, code, decision, insight
    version = Column(String(20), default='1.0.0')
    parent_id = Column(String(36), ForeignKey('capsule.id'), nullable=True)
    owner_id = Column(String(36), ForeignKey('user.id'), nullable=False)
    trust_level = Column(Integer, default=60)
    is_archived = Column(Boolean, default=False)

    # Relationships
    owner = relationship('User', back_populates='capsules')
    parent = relationship('Capsule', remote_side=[id], backref='children')
```

**Overlay (State Tracking)**
```python
class Overlay(db.Model, IdMixin, TimestampMixin, MetaDataMixin):
    name = Column(String(100), unique=True, nullable=False)
    version = Column(String(20))
    state = Column(String(20))  # ACTIVE, FAILED, QUARANTINED, etc.
    trust_level = Column(Integer, default=60)
    metrics = Column(JSON)  # activation_time, memory_usage, error_count, etc.
    configuration = Column(JSON)
```

**GovernanceProposal**
```python
class GovernanceProposal(db.Model, IdMixin, TimestampMixin, MetaDataMixin):
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    proposer_id = Column(String(36), ForeignKey('user.id'), nullable=False)
    status = Column(String(20), default='draft')  # draft, active, voting, closed
    votes_for = Column(Integer, default=0)
    votes_against = Column(Integer, default=0)
    vote_weight_for = Column(Float, default=0.0)  # Trust-weighted
    vote_weight_against = Column(Float, default=0.0)
    closes_at = Column(DateTime(timezone=True))

    # Relationships
    proposer = relationship('User', back_populates='proposals')
    votes = relationship('Vote', back_populates='proposal')
```

**AuditLog**
```python
class AuditLog(db.Model, IdMixin, TimestampMixin):
    operation = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE
    entity_type = Column(String(50), nullable=False)  # User, Capsule, Overlay
    entity_id = Column(String(36), nullable=False)
    user_id = Column(String(36), ForeignKey('user.id'))
    changes = Column(JSON)  # What changed
    ip_address = Column(String(45))
    correlation_id = Column(String(36))
```

**TrustRecord**
```python
class TrustRecord(db.Model, IdMixin, TimestampMixin):
    entity_id = Column(String(36), nullable=False)
    entity_type = Column(String(50), nullable=False)
    trust_score = Column(Integer, default=60)
    reputation = Column(Float, default=0.0)
    history = Column(JSON)  # Trust changes over time
    reason = Column(Text)  # Why trust changed
```

#### Database Principles

1. **Single Source of Truth:** All persistent data in SQL database
2. **No Dual Persistence:** Do NOT write to both database and JSON files
3. **Referential Integrity:** Foreign keys enforce relationships
4. **Metadata Extensibility:** JSON columns allow flexible schemas
5. **Audit Everything:** Sensitive operations logged to AuditLog
6. **Timestamps Always:** Track when everything was created/updated

### Async Migration Strategy

#### The Problem with Synchronous Code

The original codebase used Flask (synchronous WSGI framework). Problems:

1. **Blocking I/O freezes server:** Database query blocks entire event loop
2. **Poor concurrency:** Can't handle multiple overlay operations simultaneously
3. **Incompatible with overlay system:** Need concurrent health checks, event processing
4. **Scalability ceiling:** Synchronous = one request at a time per worker

#### The Solution: Async All The Way

**Framework Migration: Flask → Quart**
- Quart is the async-native counterpart to Flask
- Same API surface, but all routes are `async def`
- Uses ASGI instead of WSGI

**Core Async Pattern:**
```python
# OLD (Flask - Synchronous)
@app.route('/capsules')
def get_capsules():
    capsules = db.session.query(Capsule).all()  # BLOCKS!
    return jsonify(capsules)

# NEW (Quart - Asynchronous)
@app.route('/capsules')
async def get_capsules():
    capsules = await async_query_all(Capsule)  # Does not block!
    return jsonify(capsules)
```

#### The `to_thread` Bridge (Temporary Solution)

During migration, we have async routes but synchronous database drivers. Solution:

```python
async def get_user_by_id(user_id: str) -> User:
    # Define the blocking operation
    def _sync_db_call():
        return db.session.query(User).filter_by(id=user_id).first()

    # Run it in a thread pool, freeing the event loop
    user = await asyncio.to_thread(_sync_db_call)
    return user
```

**How it works:**
- `asyncio.to_thread()` runs the sync function in a thread pool
- Main event loop continues handling other requests
- When thread completes, result is returned

**Trade-offs:**
- ✅ Allows mixing async routes with sync DB code
- ✅ Prevents blocking the event loop
- ❌ Performance overhead (thread pool context switches)
- ❌ Not true async I/O (still blocking in thread)

#### Long-Term Goal: Native Async Database

**Target Architecture:**
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
import asyncpg  # PostgreSQL async driver

# Create async engine
engine = create_async_engine('postgresql+asyncpg://user:pass@host/db')

# Use async session
async with AsyncSession(engine) as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
```

**Benefits:**
- True async I/O: Database operations don't block
- Better performance: No thread pool overhead
- Scalability: Handle thousands of concurrent operations
- Cleaner code: No `to_thread` wrapper needed

---

## User-Facing Features

### Intended Web Application Capabilities

#### 1. Authentication & User Management

**Features:**
- User registration with email/password
- OAuth login (Google, GitHub, Discord)
- Wallet authentication (Web3/blockchain)
- Session management with secure cookies
- Password reset flow
- Email verification
- Two-factor authentication (planned)

**User Profile:**
- Username, email, avatar
- Role assignment (admin, trusted, user, visitor)
- Trust flame score (visible to user)
- Reputation history
- Activity timeline
- Created capsules
- Governance participation stats

**Access Control:**
- Role-based permissions (RBAC)
- Trust-level-based operations
- API key management
- Session management (active sessions, logout all devices)

#### 2. Capsule Management

**Core Operations:**
- **Create:** New capsule with content, type, metadata
- **Read:** View capsule details, content, lineage
- **Update:** Edit content (creates new version if configured)
- **Delete:** Archive capsule (soft delete, preserves lineage)

**Advanced Features:**
- **Versioning:** Semantic versioning (1.0.0 → 1.1.0 → 2.0.0)
- **Symbolic Inheritance:** Derive new capsule from existing (parent-child)
- **Licensing:** Set usage rights (public, private, licensed, for-sale)
- **Migration:** Export/import capsules across system versions
- **Lineage View:** Visual tree of capsule ancestry
- **Search:** Full-text search on content, filter by type/owner/trust
- **Tags/Categories:** Organize capsules
- **Sharing:** Share capsule with specific users or publicly

**Capsule Types (Examples):**
- Knowledge: Text-based insights, documentation
- Code: Code snippets, modules, algorithms
- Decision: Record of decisions made and rationale
- Insight: ML-generated or human-curated insights
- Configuration: System settings, preferences
- Template: Reusable patterns

**UI Views:**
- Grid view: Thumbnail cards
- List view: Compact rows
- Timeline view: Chronological
- Graph view: Visual lineage network
- Detail view: Full capsule with metadata

#### 3. Symbolic Governance (Democratic AI Decision-Making)

**Proposal Lifecycle:**

```
DRAFT → ACTIVE → VOTING → CLOSED
   ↓        ↓        ↓        ↓
 Edit    Discuss   Vote   Execute/Archive
```

**Proposal Creation:**
- Title and description
- Proposal type: Feature request, Policy change, Budget allocation, Ethical review
- Voting duration (e.g., 7 days)
- Required quorum (minimum participation)
- Execution plan (what happens if approved)

**Voting System:**
- **Simple Vote:** For or Against
- **Trust-Weighted:** Vote power = user's trust flame
- **Delegation:** Delegate vote to trusted user (planned)
- **Quadratic Voting:** Vote strength = √(tokens spent) (planned)

**Governance Dashboard:**
- Active proposals requiring votes
- Voting history (your votes, outcomes)
- Proposal statistics (participation rate, approval rate)
- Constitutional AI alerts (ethical concerns)
- Ghost Council recommendations

**Constitutional AI Integration:**
- Proposals automatically checked against ethical framework
- Flags proposals that violate core principles
- Suggests amendments to improve proposals
- Prevents "tyranny of the majority" scenarios

**Ghost Council:**
- AI advisory board that analyzes proposals
- Provides reasoning for recommendations
- No voting power, only advisory
- Transparent: All analysis visible to users

#### 4. Dashboard & System Analytics

**Overview Tab:**
- System health status (color-coded: green/yellow/red)
- Active users (current, today, week)
- Total capsules, growth trend
- Active overlays count
- Recent governance activity

**Overlay Management Tab:**
- List of all overlays (discovered, active, failed, quarantined)
- Enable/disable controls (with confirmation)
- Overlay metrics: CPU, memory, uptime, error rate
- Health status per overlay
- Dependency graph visualization
- Overlay logs viewer

**Performance Metrics Tab:**
- Response time trends (P50, P95, P99)
- Throughput (requests per second)
- Error rate (4xx, 5xx)
- Database query performance
- Cache hit rates
- Resource usage: CPU, memory, disk I/O

**Security Status Tab:**
- Current threat level
- Recent security events
- Trust level distribution (users, capsules, overlays)
- Failed authentication attempts
- Audit log viewer (filterable)
- Vulnerability scan results

**Governance Activity Tab:**
- Active proposals count
- Voting participation rate
- Recent decisions
- Upcoming votes
- Proposal success rate
- Trust flame distribution among voters

**Capsule Analytics Tab:**
- Total capsules, growth over time
- Capsule types breakdown (pie chart)
- Most active creators
- Lineage depth statistics (how deep inheritance chains go)
- Version update frequency
- Popular capsules (most viewed, forked)

**ML Intelligence Insights Tab:**
- Pattern detection results
- Anomaly alerts
- Predictive forecasts
- Recommendations generated by ML overlays
- Model performance metrics
- Training status for ML models

#### 5. Ghost Chat (AI Interaction)

**Conversational Interface:**
- Chat UI with message history
- Context-aware responses
- Access to capsule knowledge base
- Multi-turn conversations
- Command execution (`/help`, `/search`, `/create capsule`)

**Capabilities:**
- **Answer Questions:** Using capsule content as knowledge base
- **Create Capsules:** From conversation ("Remember this insight...")
- **Search:** Natural language capsule search
- **Explain:** Explain overlay status, system metrics, governance
- **Recommend:** Suggest capsules, governance votes, optimizations
- **Code Generation:** Generate code based on patterns in capsules

**Intelligence Sources:**
- Capsule content (user-created knowledge)
- Overlay analysis (ML insights)
- Governance history (past decisions)
- System metrics (performance data)

**Privacy & Security:**
- Conversations are private to user
- Trust-level-gated: Only show capsules user can access
- Audit trail: All AI actions logged
- Human-in-the-loop: Sensitive operations require confirmation

#### 6. Admin Panel (Trusted/Founder Role)

**User Management:**
- View all users
- Edit roles and trust levels
- Suspend/activate accounts
- View user activity logs
- Reset passwords
- Merge duplicate accounts

**Overlay Control:**
- Force enable/disable overlays
- Adjust resource limits
- View detailed logs
- Manually quarantine/unquarantine
- Update overlay configurations
- Rollback to previous overlay versions

**System Configuration:**
- Environment variables viewer/editor
- Feature flags (enable/disable features)
- Maintenance mode toggle
- Database migration controls
- Backup/restore triggers

**Security Operations:**
- View failed login attempts
- Block IP addresses
- Review audit logs
- Security alert configuration
- Vulnerability scan triggers
- Emergency shutdown controls

**Monitoring & Logs:**
- Real-time log streaming
- Log search and filter
- Download logs
- System metrics graphs
- Alert configuration
- Notification settings

### API Endpoints (Intended)

#### Authentication Endpoints

```
POST   /api/auth/register           # Create new user account
POST   /api/auth/login              # Login with credentials
POST   /api/auth/logout             # Logout current session
GET    /api/auth/profile            # Get current user profile
PUT    /api/auth/profile            # Update user profile
POST   /api/auth/reset-password     # Request password reset
POST   /api/auth/verify-email       # Verify email address
GET    /api/auth/sessions           # List active sessions
DELETE /api/auth/sessions/:id       # Revoke specific session
```

#### Capsule Endpoints

```
GET    /api/capsules                # List capsules (paginated, filterable)
POST   /api/capsules                # Create new capsule
GET    /api/capsules/:id            # Get capsule details
PUT    /api/capsules/:id            # Update capsule (may create version)
DELETE /api/capsules/:id            # Archive capsule
GET    /api/capsules/:id/lineage    # Get capsule ancestry tree
POST   /api/capsules/:id/version    # Create new version of capsule
GET    /api/capsules/:id/versions   # List all versions
GET    /api/capsules/search         # Search capsules (query param: q)
POST   /api/capsules/:id/fork       # Fork capsule (create child)
PUT    /api/capsules/:id/license    # Update capsule license
GET    /api/capsules/:id/children   # Get derived capsules
```

#### Governance Endpoints

```
GET    /api/governance/proposals              # List all proposals
POST   /api/governance/proposals              # Create new proposal
GET    /api/governance/proposals/:id          # Get proposal details
PUT    /api/governance/proposals/:id          # Update proposal (if DRAFT)
DELETE /api/governance/proposals/:id          # Delete proposal (if DRAFT)
POST   /api/governance/proposals/:id/activate # Move to ACTIVE status
POST   /api/governance/proposals/:id/vote     # Cast vote (body: {vote: 'for'|'against'})
GET    /api/governance/proposals/:id/votes    # Get all votes on proposal
GET    /api/governance/proposals/:id/analysis # Get Constitutional AI analysis
POST   /api/governance/proposals/:id/close    # Close voting, execute result
```

#### Overlay Endpoints

```
GET    /api/overlays                # List all discovered overlays
POST   /api/overlays/:id/enable     # Enable overlay
POST   /api/overlays/:id/disable    # Disable overlay (graceful shutdown)
GET    /api/overlays/:id            # Get overlay details
GET    /api/overlays/:id/metrics    # Get performance metrics
GET    /api/overlays/:id/health     # Run health check
GET    /api/overlays/:id/logs       # Get overlay logs (paginated)
PUT    /api/overlays/:id/config     # Update overlay configuration
POST   /api/overlays/:id/quarantine # Manually quarantine overlay
POST   /api/overlays/:id/restore    # Restore from quarantine
GET    /api/overlays/:id/dependencies # Get dependency graph
```

#### System Endpoints

```
GET    /api/system/health           # Overall system health status
GET    /api/system/metrics          # System-wide metrics (CPU, memory, etc.)
GET    /api/system/audit-log        # Audit trail (paginated, filterable)
GET    /api/system/config           # System configuration (redacted)
POST   /api/system/maintenance      # Toggle maintenance mode
GET    /api/system/version          # Get Forge version info
GET    /api/system/status           # Detailed status (all components)
```

#### User Endpoints

```
GET    /api/users                   # List users (admin only)
GET    /api/users/:id               # Get user profile
PUT    /api/users/:id               # Update user (own profile or admin)
GET    /api/users/:id/capsules      # Get user's capsules
GET    /api/users/:id/activity      # Get user activity timeline
PUT    /api/users/:id/trust         # Update trust level (admin only)
GET    /api/users/:id/governance    # Get user's governance participation
```

#### Ghost Chat Endpoints

```
POST   /api/chat/message            # Send message to AI
GET    /api/chat/history            # Get conversation history
DELETE /api/chat/history            # Clear conversation history
POST   /api/chat/command            # Execute command (/search, /create, etc.)
GET    /api/chat/context            # Get current conversation context
```

---

## Development & Operational Goals

### The Scan/Repair/Orchestration Pipeline

Forge includes a sophisticated quality assurance automation system that continuously analyzes and improves the codebase.

#### Scanner Architecture

**Purpose:** Continuously analyze the codebase for issues, patterns, quality metrics, and unique features.

**Scanner Types:**

1. **codebase_scanner.py** (Comprehensive AST Analysis)
   - Parses all Python files using Abstract Syntax Trees
   - Detects: classes, functions, async patterns, imports
   - Measures: complexity, nesting depth, line counts
   - Identifies: coordination methods (7-phase pipeline usage)
   - Exports: JSON manifest with complete structural analysis

2. **corruption_scan.py** (Syntax & Import Validation)
   - Compiles every Python file to detect syntax errors
   - Validates all imports are resolvable
   - Identifies broken files that would crash on import
   - Categorizes errors: syntax, import, encoding, permission
   - Exports: List of broken files with error details

3. **tier_verification_scanner.py** (Enterprise Pattern Detection)
   - Validates enterprise intelligence patterns
   - Checks for: ML integration, security features, performance optimization
   - Verifies: 7-phase pipeline implementation
   - Measures: code quality, documentation coverage
   - Ranks: files by enterprise readiness tier

4. **specialized_feature_scanner.py** (Unique Feature Detection)
   - Identifies unique Forge-specific patterns
   - Detects: Symbolic inheritance, cascade events, trust enforcement
   - Maps: feature distribution across codebase
   - Generates: Feature inventory for documentation
   - Exports: Feature catalog with file locations

**Scanner Output Formats:**

- **JSON Manifests** (`AutoFix-Manifest.json`): For programmatic processing
- **SQLite Databases** (`Results.sqlite`): For complex queries and analysis
- **NDJSON** (Newline-Delimited JSON): For streaming and incremental processing
- **CSV Exports**: For analysis in Excel, Tableau, or other BI tools
- **HTML Dashboards**: Visual representation for human review

**What Scanners Detect:**

**Code Structure:**
- Class definitions with inheritance chains
- Function signatures with type hints
- Async vs sync functions
- Decorator usage
- Context manager usage

**Quality Metrics:**
- Cyclomatic complexity (McCabe)
- Cognitive complexity
- Nesting depth
- Line counts (LOC, SLOC)
- Comment density

**Patterns:**
- Coordination method usage (7-phase pipeline)
- ML integration points
- Security validation calls
- Error handling coverage
- Logging statements

**Issues:**
- Syntax errors
- Missing imports
- Bare except clauses
- Missing docstrings
- Identity comparisons (`is` vs `==`)
- Open without encoding parameter
- Requests without timeout

**Enterprise Features:**
- Trust level enforcement
- Symbolic inheritance usage
- Event system integration
- Constitutional AI integration
- Ghost Council references

#### Repair/Auto-Fix System

**Purpose:** Automatically fix common code quality issues identified by scanners.

**Repair Capabilities:**

1. **Docstring Addition**
   - Adds placeholder docstrings to classes and functions
   - Format: `"""[ClassName/function_name description]"""`
   - Preserves existing docstrings

2. **Bare Except Fix**
   - Replaces `except:` with `except Exception as e:`
   - Adds logging: `logger.error(f"Error: {e}")`
   - Preserves error handling logic

3. **Encoding Parameter Fix**
   - Adds `encoding='utf-8'` to `open()` calls
   - Prevents encoding issues on different systems
   - Uses AST to preserve exact syntax

4. **Unused Import Removal**
   - Detects imports not referenced in code
   - Removes them (except `__init__.py` where imports may be re-exported)
   - Preserves necessary imports

5. **Type Hint Addition**
   - Adds placeholder type hints: `-> None`, `-> Any`
   - Improves static analysis
   - Prepares for full type coverage

6. **Identity Comparison Fix**
   - Changes `if x == None:` to `if x is None:`
   - Changes `if x != None:` to `if x is not None:`
   - Follows PEP 8 style guide

7. **Request Timeout Addition**
   - Adds `timeout=30` to `requests.get/post` calls
   - Prevents hanging on network issues
   - Configurable timeout value

**Repair Process:**

```
1. Scanner identifies issues → Creates manifest
2. Repair script reads manifest
3. AST manipulation to fix code (not regex!)
4. Validate fixes don't break syntax (compile check)
5. Write modified file back
6. Log all changes for audit
7. Generate repair report
```

**Safety Features:**
- Dry-run mode: Preview changes without applying
- Backup creation: Original files saved before modification
- Syntax validation: Ensure fixes don't break code
- Audit trail: All changes logged with timestamps
- Rollback capability: Can revert changes if needed

#### Orchestration via CMD Tools

**FORGE-ONE-BUTTON.cmd** (Master Orchestrator)

Runs the complete quality pipeline in automated stages:

**Phase 0: Pause All Dev Processes**
- Safely shuts down project-scoped processes
- Prevents conflicts during pipeline execution
- Optional Docker container pause (if configured)

**Phase 1: Lint/Format**
- **ruff**: Fast Python linter (Rust-based)
- **black**: Opinionated code formatter
- **flake8**: Style guide enforcement (PEP 8)
- Runs in parallel if tools available

**Phase 1.5: Auto-Repair**
- Runs `comprehensive_syntax_repair.py`
- Runs `comprehensive_init_fixer.py`
- Applies all auto-fixes from manifest
- Continues even if repairs report errors

**Phase 2: Tests**
- Runs `pytest -q` if pytest available
- Records test failures but continues pipeline
- Generates test coverage report (if configured)

**Phase 3: Reports/Exports**
- Runs `export_security_reports.py` if present
- Generates dashboards
- Bundles scan results
- Creates documentation exports

**Phase 4: Git Commit/Push (Opt-In)**
- Commits all changes with message: `[Forge] One-button pipeline - automated improvements`
- Pushes to remote if `ENABLE_GIT_PUSH=1`
- Configurable via `.env.forge`

**Environment-Driven Configuration (.env.forge):**

```bash
# Default scan file
DEFAULT_SCAN=path/to/scan.json

# Git settings
FORGE_GIT_REMOTE=origin
FORGE_GIT_BRANCH=auto-generated  # Or specify custom branch

# Safety flags
FORGE_DRY_RUN=1              # 1 = preview only, 0 = execute
FORGE_AUTO_REPAIR=0          # Auto-run repair after scan
FORGE_AUTO_PUSH=0            # Auto-push to remote
FORGE_AUTO_PR=0              # Auto-create pull request

# Quality enforcement
FORGE_QUALITY_GATES=0        # Run ruff/pytest/mypy enforcement
FORGE_DOCTOR_ON_FAIL=1       # Auto-diagnose failures

# Maintenance
FORGE_BACKUP_ON_RUN=0        # Backup artifacts before run
FORGE_SHOW_DIFF=0            # Show git diff summary at end

# Cleanup
FORGE_CLEAN_LOGS_DAYS=7      # Retain logs for 7 days
FORGE_CLEAN_BACKUPS_DAYS=14  # Retain backups for 14 days
```

**FORGE-DOCTOR.cmd** (Health Check & Diagnostics)

Validates development environment:

**Checks:**
- Python version (3.9+ required)
- Git availability and configuration
- Virtual environment activation
- Tool availability: ruff, isort, black, pytest, mypy
- Scan file existence
- Dashboard file existence
- Git remote configuration
- .env.forge file validity

**Output:**
- ✅ Green: Check passed
- ⚠️ Yellow: Warning (non-critical)
- ❌ Red: Error (critical issue)
- Recommendations for fixing failures

**Additional Operational Tools:**

1. **BUNDLE-REPORTS.cmd**
   - Packages all scan results into zip archive
   - Includes: JSON manifests, SQLite DBs, CSV exports, dashboards
   - Timestamped filename for versioning
   - For sharing or backup

2. **CLEAN-OLD-ARTIFACTS.cmd**
   - Removes old logs (>7 days by default)
   - Removes old backups (>14 days by default)
   - Frees disk space
   - Configurable retention via `.env.forge`

3. **BUILD-DASHBOARD-STATIC.cmd**
   - Generates static HTML dashboard from scan results
   - Interactive charts and tables
   - No server required (pure HTML/CSS/JS)
   - Can be opened in browser or hosted

4. **BACKUP-ARTIFACTS.cmd**
   - Backs up: logs, .env files, exports, dashboards
   - Timestamped backup directory
   - Run before risky operations
   - Enables rollback if needed

5. **QUALITY-GATES.cmd**
   - Enforces quality standards
   - Runs: ruff (must pass), pytest (must pass), mypy (warnings OK)
   - Exits with error if quality gate fails
   - Used in CI/CD pipeline

6. **OPEN-LAST-RUN-REPORT.cmd**
   - Opens most recent scan dashboard in browser
   - Convenient for reviewing results
   - Cross-platform (Windows, macOS, Linux)

### Testing Strategy

**Philosophy:** No feature is considered "complete" until it has tests that prove it works.

#### Testing Approach

**Unit Tests:**
- One test file per module: `tests/test_<module_name>.py`
- Tests individual functions/classes in isolation
- Mocks external dependencies (database, network, file I/O)
- Fast execution (<1 second per test)

**Integration Tests:**
- Tests multiple components working together
- Uses in-memory SQLite database (fast, isolated)
- Tests full request lifecycle (route → logic → database → response)
- Verifies async operations work correctly

**End-to-End Tests:**
- Tests complete user workflows
- Uses Quart test client to simulate HTTP requests
- Validates database state after operations
- Ensures UI interactions work as expected

#### Test Structure (Per Module)

**Example: Testing Symbolic Governance Module**

```python
# tests/test_async_governance.py

import pytest
from quart import Quart
from app import app
from database import db
from models import GovernanceProposal, User, Vote

@pytest.fixture
async def test_app():
    """Create test app with in-memory database"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    async with app.app_context():
        await db.create_all()
        yield app
        await db.drop_all()

@pytest.fixture
async def test_user(test_app):
    """Create test user"""
    user = User(username='testuser', trust_flame=80)
    db.session.add(user)
    await db.session.commit()
    return user

@pytest.mark.asyncio
async def test_create_proposal(test_app, test_user):
    """Test creating a governance proposal"""
    async with test_app.test_client() as client:
        # Simulate login
        with client.session_transaction() as session:
            session['user_id'] = test_user.id

        # Create proposal via API
        response = await client.post('/api/governance/proposals', json={
            'title': 'Test Proposal',
            'description': 'This is a test'
        })

        assert response.status_code == 201
        data = await response.get_json()
        assert data['title'] == 'Test Proposal'

        # Verify database state
        proposal = await db.session.query(GovernanceProposal).filter_by(
            id=data['id']
        ).first()
        assert proposal is not None
        assert proposal.status == 'draft'

@pytest.mark.asyncio
async def test_vote_on_proposal(test_app, test_user):
    """Test voting on a proposal"""
    # Create proposal
    proposal = GovernanceProposal(
        title='Vote Test',
        proposer_id=test_user.id,
        status='voting'
    )
    db.session.add(proposal)
    await db.session.commit()

    async with test_app.test_client() as client:
        with client.session_transaction() as session:
            session['user_id'] = test_user.id

        # Cast vote
        response = await client.post(
            f'/api/governance/proposals/{proposal.id}/vote',
            json={'vote': 'for'}
        )

        assert response.status_code == 200

        # Verify vote recorded
        proposal = await db.session.query(GovernanceProposal).get(proposal.id)
        assert proposal.votes_for == 1
        assert proposal.vote_weight_for == test_user.trust_flame

# ... more tests for full lifecycle
```

#### Test Coverage Goals

- **Minimum:** 80% line coverage
- **Target:** 90% line coverage
- **Critical Paths:** 100% coverage (auth, governance, security)

#### Test Execution

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_async_governance.py

# Run with coverage report
pytest --cov=app --cov-report=html

# Run only fast tests (exclude slow integration tests)
pytest -m "not slow"

# Run in parallel (faster)
pytest -n auto
```

#### Continuous Integration

Tests run automatically on:
- Every commit (pre-commit hook)
- Every push to remote
- Every pull request
- Scheduled nightly builds

**CI Pipeline:**
```
1. Checkout code
2. Install dependencies
3. Run linters (ruff, black, flake8)
4. Run type checker (mypy)
5. Run tests (pytest)
6. Generate coverage report
7. Build Docker image
8. Deploy to staging (if tests pass)
```

---

## Unique Innovations & Differentiators

### What Makes Forge Cascade Truly Unique

#### 1. Persistent Evolutionary Memory

**The Innovation:**
Unlike traditional AI systems that lose knowledge on restart/update, Forge maintains an unbroken chain of wisdom across generations.

**How It Works:**
- Knowledge stored in capsules that survive system upgrades
- Clear lineage from old knowledge to new (symbolic inheritance)
- Parent-child relationships track concept evolution
- Version history preserves all stages of idea development

**Impact:**
- AI systems that get smarter with age, not reset to zero
- Hard-won lessons aren't forgotten
- Cultural memory for artificial intelligence

**Analogy:**
Traditional AI is like Alzheimer's - every update erases memories. Forge is like a civilization with libraries, oral tradition, and cultural knowledge passed between generations.

#### 2. Self-Governing Ecosystem

**The Innovation:**
The system governs itself through democratic processes, ethical guardrails, and autonomous decision-making.

**Components:**
- **Democratic Proposals:** Users create proposals for system changes
- **Trust-Weighted Voting:** Vote power based on reputation (trust flame)
- **Constitutional AI:** Automatic ethical review of proposals
- **Ghost Council:** AI advisory board provides recommendations
- **Automatic Execution:** Approved proposals automatically implemented

**Impact:**
- System evolves based on collective wisdom, not dictator
- Ethical drift detected and corrected
- Transparent decision-making process
- Prevents both tyranny and chaos

**Example:**
```
User proposes: "Increase data collection for better ML models"
Constitutional AI flags: "Conflicts with privacy principle"
Ghost Council recommends: "Use federated learning instead"
Community votes: Amended proposal approved
System automatically: Implements federated learning
```

#### 3. Self-Healing Architecture

**The Innovation:**
Built-in immune system that detects problems, quarantines faulty components, and repairs issues without human intervention.

**Mechanisms:**
- **Health Monitoring:** Background task checks overlay health every 30 seconds
- **Automatic Quarantine:** 3 failed health checks = immediate isolation
- **Resource Sandboxing:** Faulty overlay can't crash entire system
- **Graceful Degradation:** System continues operating with reduced functionality
- **Audit Trail:** All failures logged for post-mortem analysis
- **Auto-Recovery:** Quarantined overlays automatically restored once healthy

**Impact:**
- 99.9%+ uptime even with buggy components
- Security breaches contained before spreading
- Human intervention only for critical issues
- System learns from failures (stores in capsules)

**Example:**
```
PerformanceOptimizer overlay has memory leak
Health check detects: memory usage > 500 MB limit
System automatically: Quarantines overlay
System continues: without performance optimization (degraded but operational)
Alert sent: to admin for investigation
Overlay restarted: after fix, automatically restored
```

#### 4. Security-First Plugin System

**The Innovation:**
Production-grade overlay management with trust hierarchy enforcement, security validation, and resource limits.

**Security Layers:**

1. **Trust Validation:** Only STANDARD+ overlays can be loaded by default
2. **Security Validator:** Vets overlay code before loading
3. **Resource Sandboxing:** Memory and file handle limits prevent abuse
4. **Dependency Resolution:** Validates all dependencies before activation
5. **Event Access Control:** Overlays can only send events to permitted recipients
6. **Audit Logging:** Every overlay operation logged

**Comparison to Traditional Plugin Systems:**

| Feature | Traditional (e.g., WordPress) | Forge |
|---------|-------------------------------|-------|
| Trust Model | All plugins trusted equally | 5-level trust hierarchy |
| Security Check | Manual review (if any) | Automated validation before load |
| Resource Limits | None (can consume all memory) | Sandboxed (500 MB, 200 file handles) |
| Failure Isolation | Plugin crash = site crash | Quarantine system prevents spread |
| Health Monitoring | None | Proactive checks every 30 seconds |
| Communication | Direct function calls (coupled) | Event system (decoupled) |

**Impact:**
- Safe to run third-party overlays
- One faulty overlay can't bring down the system
- Security breaches contained
- Overlay marketplace possible (like app stores)

#### 5. The Cascade Effect (Knowledge Propagation)

**The Innovation:**
Breakthroughs in one overlay intelligently propagate to others, creating system-wide learning from localized discoveries.

**How It Works:**
```
Overlay A: Discovers insight ("API calls slow during peak hours")
    ↓
Event Published: {
    type: "performance_insight",
    insight: "API calls slow during peak hours",
    confidence: 0.92,
    recommendation: "Implement caching"
}
    ↓
Event System: Analyzes which overlays benefit from this knowledge
    ↓
Overlay B (CacheManager): Receives event, implements caching
Overlay C (LoadBalancer): Receives event, adjusts routing
Overlay D (MLPredictor): Receives event, updates peak hour model
    ↓
System-Wide Improvement: All components benefit from A's discovery
```

**Impact:**
- Exponential intelligence growth vs linear
- No manual knowledge transfer needed
- Cross-domain learning (security insight improves performance, etc.)
- Emergent intelligence from component interaction

**Example Cascade:**
```
SecurityValidator detects: New SQL injection pattern in user input
    ↓ (publishes security_threat event)
MLIntelligence: Updates anomaly detection model with new pattern
    ↓ (publishes model_updated event)
PerformanceOptimizer: Allocates more CPU to input validation
    ↓ (publishes optimization_applied event)
GovernanceSystem: Creates proposal to update input validation rules
    ↓ (publishes governance_action event)
AuditLog: Records entire cascade for future reference
```

#### 6. ML-Powered Everything

**The Innovation:**
Every operation enhanced with machine learning - not as a gimmick, but as core architecture.

**ML Integration Points:**

1. **Configuration Analysis:**
   - Predicts optimal settings based on usage patterns
   - Detects misconfigured parameters
   - Recommends improvements

2. **Security Threat Prediction:**
   - Anomaly detection on user behavior
   - Pattern recognition for attack signatures
   - Proactive threat mitigation

3. **Performance Anomaly Detection:**
   - Baseline normal operation
   - Detect deviations (memory leak, slow queries)
   - Predict future bottlenecks

4. **Automated Recommendations:**
   - Capsule suggestions based on user interests
   - Governance vote recommendations
   - System optimization opportunities

5. **Pattern Recognition:**
   - Code pattern detection (scanners)
   - Usage pattern analysis (analytics)
   - Knowledge graph patterns (capsule relationships)

**The Seven-Phase Pipeline Integration:**
Phase 2 of every operation includes ML analysis - it's not optional, it's architectural.

**Impact:**
- System gets smarter over time automatically
- Proactive rather than reactive
- Intelligent defaults that adapt to user behavior
- Continuous improvement without manual tuning

#### 7. Seven-Phase Coordination Pipeline

**The Innovation:**
Standardized intelligent operation flow that every overlay follows.

**Why It's Unique:**
Most systems have ad-hoc operation flows. Forge enforces a consistent, comprehensive pattern.

**The Seven Phases:**
1. Context Creation & Validation
2. Comprehensive ML Analysis
3. Security Assessment
4. Performance Optimization
5. Intelligence Generation
6. Metrics Updating
7. Results Storage

**Benefits:**

- **Consistency:** Every operation follows same pattern
- **Predictability:** Easy to debug ("which phase failed?")
- **Completeness:** No critical aspect (security, performance, ML) is forgotten
- **Auditability:** Full lifecycle tracked in logs
- **Composability:** Phases can be reused across overlays
- **Quality Assurance:** Quality baked into architecture

**Comparison:**

```
Traditional Approach:
function process_request(data):
    # Maybe validate? Maybe not?
    result = do_work(data)
    # Hopefully remember to log
    return result

Forge Approach:
async function process_request(data):
    context = await create_context(data)          # Phase 1
    ml_insights = await analyze_ml(context)        # Phase 2
    security_ok = await assess_security(context)   # Phase 3
    optimized = await optimize_performance(context)# Phase 4
    intelligence = await generate_intelligence()   # Phase 5
    await update_metrics(context)                  # Phase 6
    await store_results(context, intelligence)     # Phase 7
    return intelligence
```

#### 8. Comprehensive Development Automation

**The Innovation:**
Industrial-scale automation for code quality, scanning, repair, and orchestration.

**Components:**

1. **AST-Based Scanning:**
   - Not regex hacks - proper Abstract Syntax Tree parsing
   - Detects structural patterns, not just text matches
   - Analyzes 23,000+ files in minutes

2. **Intelligent Auto-Repair:**
   - Fixes issues programmatically (AST manipulation)
   - Validates fixes won't break code (compile check)
   - Creates audit trail of all changes

3. **One-Button Orchestration:**
   - Complete quality pipeline: lint → fix → test → report → commit
   - Environment-driven configuration (no hard-coded paths)
   - Dry-run mode for safety

4. **Quality Gates:**
   - Enforces standards (ruff, pytest, mypy must pass)
   - Prevents low-quality code from merging
   - Automated in CI/CD pipeline

**Impact:**
- Code quality improves automatically
- Developer time saved on manual tasks
- Consistent standards across 23k+ files
- Continuous improvement culture

**Comparison to Traditional Approaches:**

| Task | Traditional | Forge |
|------|-------------|-------|
| Find syntax errors | Manually run file by file | Scan all 23k files at once |
| Add docstrings | Manually write each one | Auto-generate placeholders |
| Fix import errors | Hunt down each broken import | Auto-detect and fix |
| Run quality checks | Remember to run each tool | One-button runs entire pipeline |
| Generate reports | Manually export data | Auto-generate HTML dashboard |

---

## Development Philosophy & Principles

### Architectural Principles

#### 1. Single Source of Truth

**Principle:** All persistent data must reside in the relational database managed by SQLAlchemy.

**Anti-Pattern to Avoid:**
```python
# BAD: Dual persistence (database + JSON files)
db.session.add(capsule)
db.session.commit()

with open(f'capsules/{capsule.id}.json', 'w') as f:
    json.dump(capsule_data, f)  # NOW TWO SOURCES OF TRUTH!
```

**Correct Pattern:**
```python
# GOOD: Single source of truth
db.session.add(capsule)
db.session.commit()
# Database is the ONLY source. Read from there.
```

**Rationale:**
- Prevents data inconsistency (database says X, file says Y)
- Simplifies backups (one database dump vs thousands of files)
- Enables transactions (atomic updates impossible with files)
- Easier to query and analyze

**Exception:** Firebase/Firestore is acceptable for real-time features (chat, notifications) but is NOT primary storage.

#### 2. Dependency Injection

**Principle:** Components must receive their dependencies in their `__init__` method, not use global instances or context lookups.

**Anti-Pattern to Avoid:**
```python
# BAD: Global instance
class Overlay:
    def process(self):
        # Tightly coupled to global db object
        capsules = db.session.query(Capsule).all()
```

**Correct Pattern:**
```python
# GOOD: Dependency injection
class Overlay:
    def __init__(self, db_client):
        self.db = db_client  # Injected dependency

    def process(self):
        capsules = self.db.query(Capsule).all()
```

**Benefits:**
- Testable (inject mock database for tests)
- Flexible (swap implementations without changing code)
- Explicit (clear what dependencies component needs)
- Decoupled (component doesn't know about global state)

#### 3. Code Quality is Paramount

**Principle:** Prioritize clean, readable, maintainable code over clever or fast-to-write code.

**If you write unclear code:**
1. Stop immediately
2. Refactor for clarity
3. Add comments explaining complex logic
4. Only then move forward

**Never sacrifice quality for velocity.** Technical debt compounds exponentially.

**Example:**
```python
# BAD: Clever but unreadable
result = [x for x in data if (lambda y: y > 5 and y < 10)(x) and not any(z == x for z in exclude)]

# GOOD: Clear and maintainable
def is_in_range(value):
    """Check if value is between 5 and 10"""
    return 5 < value < 10

def is_not_excluded(value, exclude_list):
    """Check if value is not in exclusion list"""
    return value not in exclude_list

result = [
    x for x in data
    if is_in_range(x) and is_not_excluded(x, exclude)
]
```

#### 4. Clear Contracts (Abstract Base Classes)

**Principle:** Use Abstract Base Classes to define how components interact.

**Example:**
```python
from abc import ABC, abstractmethod

class OverlayBase(ABC):
    """Contract that all overlays must follow"""

    @abstractmethod
    async def initialize(self, correlation_id: str) -> None:
        """Initialize overlay. Must be implemented."""
        pass

    @abstractmethod
    async def activate(self, correlation_id: str) -> None:
        """Activate overlay. Must be implemented."""
        pass

    # ... etc
```

**Benefits:**
- Clear expectations for implementers
- IDE autocomplete knows what methods exist
- Type checker validates correct implementation
- Prevents "forgot to implement critical method" bugs

#### 5. Configuration in config.py

**Principle:** All application-level configuration should reside in `config.py` and be loaded from environment variables.

**Example:**
```python
# config.py
import os

class Config:
    # Secret key for sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///forge.db'

    # Feature flags
    ENABLE_ML_INTELLIGENCE = os.environ.get('ENABLE_ML', '1') == '1'
    ENABLE_GOVERNANCE = os.environ.get('ENABLE_GOVERNANCE', '1') == '1'

    # External services
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_CREDENTIALS = os.environ.get('FIREBASE_CREDENTIALS')
```

**Never:**
- Hard-code API keys or secrets in source code
- Scatter configuration across multiple files
- Commit `.env` files to version control

#### 6. Asynchronous First

**Principle:** All new I/O-bound code must be asynchronous.

**I/O-Bound Operations:**
- Database queries
- Network requests (HTTP, API calls)
- File I/O (reading, writing)
- External service calls

**Must Be Async:**
```python
# All routes
@app.route('/capsules')
async def get_capsules():
    capsules = await async_query(Capsule)
    return jsonify(capsules)

# All overlay methods
class Overlay(OverlayBase):
    async def process(self, payload):
        result = await self.fetch_from_api(payload)
        return result
```

**The `to_thread` Bridge (Temporary):**
For legacy synchronous code during migration:
```python
async def legacy_sync_call():
    def _sync_operation():
        return old_sync_function()  # Blocking

    result = await asyncio.to_thread(_sync_operation)
    return result
```

**Long-Term Goal:** Replace all `to_thread` with native async (AsyncSession, asyncpg, aiohttp, aiofiles).

#### 7. Security by Default

**Principle:** Security is not an afterthought - it's baked into every layer.

**Security Practices:**

1. **Trust Validation Everywhere:**
   ```python
   if user.trust_flame < TrustLevel.TRUSTED.value:
       raise PermissionError("Insufficient trust level")
   ```

2. **Input Validation:**
   ```python
   from pydantic import BaseModel, validator

   class CapsuleCreate(BaseModel):
       content: str
       type: str

       @validator('content')
       def content_not_empty(cls, v):
           if not v.strip():
               raise ValueError('Content cannot be empty')
           return v
   ```

3. **Output Sanitization:**
   ```python
   from markupsafe import escape

   sanitized_content = escape(user_input)
   ```

4. **Audit Trail:**
   ```python
   audit_log = AuditLog(
       operation='DELETE',
       entity_type='Capsule',
       entity_id=capsule.id,
       user_id=current_user.id,
       changes={'status': 'archived'}
   )
   db.session.add(audit_log)
   ```

5. **Resource Limits:**
   Applied automatically by OverlayManager

#### 8. Phased Migration (GD2 → GD3)

**Principle:** Migrate one module at a time, fully completing each before moving to the next.

**Migration Checklist (Per Module):**
- [ ] Convert all routes to async
- [ ] Update database calls (use `to_thread` or AsyncSession)
- [ ] Migrate to GD3 directory structure
- [ ] Write verification tests
- [ ] Run tests until all pass
- [ ] Mark module as "Complete"
- [ ] Move to next module

**Never:**
- Partially migrate a module and leave it broken
- Skip tests ("I'll add them later")
- Mix GD2 and GD3 imports in the same file

### Quality Standards

#### Linting & Formatting

**Tools:**
- **ruff**: Fast Python linter (Rust-based, replaces flake8/pylint)
- **black**: Opinionated code formatter (no configuration)
- **flake8**: PEP 8 style guide enforcement
- **isort**: Import statement sorting

**Configuration:**
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py39"
select = ["E", "F", "W", "I", "N"]

[tool.black]
line-length = 100
target-version = ['py39']

[tool.isort]
profile = "black"
line_length = 100
```

**Pre-Commit Hook:**
```bash
#!/bin/bash
# .git/hooks/pre-commit
ruff check . || exit 1
black --check . || exit 1
isort --check . || exit 1
```

#### Type Checking

**Tool:** MyPy for static type analysis

**Minimum Standard:**
```python
# Placeholder type hints (acceptable during migration)
def process_data(data) -> None:
    pass

def get_capsule(id: str):  # Return type missing but acceptable
    return capsule
```

**Goal:**
```python
# Full type coverage
def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    pass

def get_capsule(id: str) -> Optional[Capsule]:
    return capsule
```

**Configuration:**
```ini
# mypy.ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False  # During migration
check_untyped_defs = True
```

#### Testing Standards

**Framework:** pytest with pytest-asyncio

**Coverage Requirements:**
- **Minimum:** 80% line coverage
- **Target:** 90% line coverage
- **Critical Paths:** 100% coverage (auth, governance, security, payment)

**Test Structure:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_auth.py             # Authentication tests
├── test_capsules.py         # Capsule CRUD tests
├── test_governance.py       # Governance tests
├── test_overlays.py         # Overlay system tests
└── integration/
    ├── test_end_to_end.py   # Full workflow tests
    └── test_cascade.py      # Cascade effect tests
```

**Example Test:**
```python
# tests/test_capsules.py
import pytest
from app import app
from models import Capsule

@pytest.mark.asyncio
async def test_create_capsule(test_client, test_user):
    """Test creating a capsule via API"""
    response = await test_client.post('/api/capsules', json={
        'content': 'Test capsule content',
        'type': 'knowledge'
    })

    assert response.status_code == 201
    data = await response.get_json()
    assert data['content'] == 'Test capsule content'
    assert data['owner_id'] == test_user.id
```

**Running Tests:**
```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Only fast tests
pytest -m "not slow"

# Specific test file
pytest tests/test_capsules.py

# Specific test
pytest tests/test_capsules.py::test_create_capsule
```

#### Documentation Standards

**Docstrings (Required for All Public APIs):**
```python
def create_capsule(content: str, type: str, parent_id: Optional[str] = None) -> Capsule:
    """Create a new capsule with symbolic inheritance.

    Args:
        content: The capsule content (text, code, etc.)
        type: Capsule type (knowledge, code, decision, insight)
        parent_id: Optional parent capsule ID for symbolic inheritance

    Returns:
        Capsule: The newly created capsule instance

    Raises:
        ValueError: If content is empty or type is invalid
        PermissionError: If user trust level insufficient

    Example:
        >>> capsule = create_capsule("Python best practices", "knowledge")
        >>> child = create_capsule("Use type hints", "knowledge", parent_id=capsule.id)
    """
```

**Inline Comments (For Complex Logic):**
```python
# Complex algorithm - explain WHY, not WHAT
# Using topological sort to resolve dependencies because:
# 1. Ensures overlays activate in correct order
# 2. Detects circular dependencies
# 3. Handles partial failures gracefully
sorted_overlays = topological_sort(dependency_graph)
```

**Architecture Docs (PlantUML):**
```plantuml
@startuml
actor User
participant "Quart App" as App
participant "OverlayManager" as Manager
participant "SecurityValidator" as Security
database "PostgreSQL" as DB

User -> App: POST /api/capsules
App -> Security: validate_user_trust()
Security --> App: trust_level=80
App -> Manager: create_capsule()
Manager -> DB: INSERT capsule
DB --> Manager: capsule_id
Manager --> App: capsule object
App --> User: 201 Created
@enduml
```

---

## Technology Stack

### Core Technologies

#### Backend

**Language:**
- Python 3.9+ (async/await support required)

**Web Framework:**
- **Quart** (async Flask-like framework)
  - ASGI-based (Asynchronous Server Gateway Interface)
  - Compatible with Flask ecosystem
  - Native async/await support
  - Lightweight and fast

**ORM:**
- **SQLAlchemy** (object-relational mapping)
  - Current: Synchronous with `asyncio.to_thread` bridge
  - Future: AsyncSession with asyncpg
  - Supports PostgreSQL, SQLite, MySQL

**Async Runtime:**
- **asyncio** (Python standard library)
  - Event loop for async operations
  - Task management
  - Concurrent execution

#### Database

**Primary:**
- **PostgreSQL** (production)
  - ACID compliance
  - JSON/JSONB support for metadata
  - Full-text search
  - Proven reliability

- **SQLite** (development/testing)
  - In-memory mode for fast tests
  - Single-file simplicity
  - No server required

**Secondary:**
- **Firebase/Firestore** (optional)
  - Real-time updates
  - Audit trail
  - NOT primary data store
  - Used for: chat, notifications, real-time dashboard

#### ML/AI

**Libraries:**
- **scikit-learn**: Classification, clustering, anomaly detection
  - RandomForestClassifier: Pattern classification
  - IsolationForest: Anomaly detection
  - KMeans: Clustering
  - TfidfVectorizer: Text analysis

- **numpy**: Numerical computing
- **pandas**: Data manipulation and analysis

**Planned:**
- TensorFlow/PyTorch: Deep learning
- Transformers (Hugging Face): NLP tasks
- spaCy: Advanced NLP

**Graceful Degradation:**
All ML features have fallback implementations if libraries not available:
```python
try:
    from sklearn.ensemble import RandomForestClassifier
    ML_AVAILABLE = True
except ImportError:
    class RandomForestClassifier:  # Mock
        def fit(self, *args, **kwargs): return self
        def predict(self, *args, **kwargs): return []
    ML_AVAILABLE = False
```

#### Frontend

**Templating:**
- **Jinja2**: Server-side HTML templating
  - Template inheritance
  - Macros for reusable components
  - Context processors

**Static Assets:**
- HTML5, CSS3
- JavaScript (vanilla, potentially Vue.js/React for complex UI)
- Chart.js / D3.js for visualizations

**Planned:**
- Vue.js or React for dashboard
- WebSockets for real-time updates
- Progressive Web App (PWA) features

#### Testing

**Framework:**
- **pytest**: Test runner
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting

**Mocking:**
- **unittest.mock**: Python standard library mocking
- **pytest-mock**: pytest integration

**Coverage:**
- **coverage.py**: Coverage measurement
- **codecov**: Coverage reporting service (CI/CD)

#### DevOps

**Containerization:**
- **Docker**: Container runtime
- **Docker Compose**: Multi-container orchestration (dev environment)

**Orchestration:**
- **Kubernetes**: Production container orchestration
  - Deployments, Services, Ingress
  - ConfigMaps, Secrets
  - StatefulSets for database

**CI/CD:**
- **ArgoCD**: GitOps continuous delivery
  - Declarative deployment
  - Automatic sync from Git
  - Rollback capabilities

- **Argo Rollouts**: Progressive delivery
  - Blue-green deployments
  - Canary deployments
  - Traffic splitting

**Version Control:**
- **Git**: Source control
- **GitHub**: Repository hosting, pull requests, actions

#### Quality Tools

**Linting:**
- **ruff**: Fast Python linter (Rust-based)
- **black**: Code formatter
- **flake8**: Style guide enforcement
- **isort**: Import sorting

**Type Checking:**
- **mypy**: Static type checker

**Security:**
- **bandit**: Security issue scanner
- **safety**: Dependency vulnerability checker

**IDE Integration:**
- **sonarlint**: IDE-based code quality analysis
- **pylint**: Additional linting (optional)

#### Monitoring & Observability

**Planned:**
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization
- **Jaeger/Zipkin**: Distributed tracing
- **Sentry**: Error tracking
- **ELK Stack**: Centralized logging (Elasticsearch, Logstash, Kibana)

#### External Services

**Authentication:**
- OAuth providers (Google, GitHub, Discord)
- Web3 wallet authentication (MetaMask, WalletConnect)

**Storage (Planned):**
- S3/MinIO: Object storage for large capsules
- CDN: Content delivery (CloudFlare, AWS CloudFront)

**Communication (Planned):**
- SendGrid: Transactional email
- Twilio: SMS notifications
- Slack/Discord: Integration webhooks

### Development Environment

**IDE Support:**
- **PyCharm** (primary)
  - Plugins: Copilot, Gemini, DBNavigator, PlantUML, BigDataTools
- **VSCode** (secondary)
  - Python extension, Pylance, pytest integration

**Virtual Environment:**
- **venv** (Python standard library)
- **pip**: Package management
- **requirements.txt**: Dependency specification

**Environment Variables:**
- **.env.forge**: Forge-specific configuration
- **.env**: General application secrets (not committed)
- **config.py**: Loads from environment

### Deployment Architecture (Planned)

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                        │
│                   (Nginx/CloudFlare)                     │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐    ┌────▼────┐    ┌────▼────┐
│ Quart   │    │ Quart   │    │ Quart   │  (Horizontal scaling)
│ App     │    │ App     │    │ App     │
│ Pod 1   │    │ Pod 2   │    │ Pod 3   │
└────┬────┘    └────┬────┘    └────┬────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐            ┌────▼─────┐
    │PostgreSQL│            │ Redis    │  (Caching/Sessions)
    │ Primary  │            │          │
    └────┬─────┘            └──────────┘
         │
    ┌────▼─────┐
    │PostgreSQL│  (Read Replica)
    │ Replica  │
    └──────────┘
```

---

## Roadmap & Strategic Goals

### Current State (Baseline)

**Completed:**
- ✅ Core Forge Kernel (OverlayManager)
- ✅ Security Layer (SecurityValidator, TrustHierarchy, AccessControl)
- ✅ Data Models (User, Capsule, Overlay, GovernanceProposal, etc.)
- ✅ Authentication routes and utilities
- ✅ Scan/Repair/Orchestration pipeline
- ✅ CMD automation tools
- ✅ GD3 architecture design

**In Progress:**
- 🔄 GD3 migration (routes from GD2 → GD3)
- 🔄 Async migration (Flask → Quart)
- 🔄 Overlay ecosystem (symbolic_governance partially complete)

**Blockers:**
- ❌ Overlay modules directory mostly empty (only sample overlay)
- ❌ GD3 kernel initialization commented out in app.py
- ❌ Most routes still in GD2 structure
- ❌ Database still using synchronous drivers

### Short-Term Goals (3-6 Months)

#### Goal 1: Complete GD3 Migration

**Objectives:**
- Migrate all routes from `routes/` to `GD3/app/routes/`
- Convert all routes to async (Quart patterns)
- Update database calls (AsyncSession + asyncpg)
- Write verification tests for each migrated module
- Remove `to_thread` bridge entirely

**Success Criteria:**
- All routes in GD3 structure
- 100% async (no blocking I/O)
- Test coverage >80% for all modules
- GD3 kernel initialization active (uncommented in app.py)

#### Goal 2: Activate Overlay Ecosystem

**Objectives:**
- Implement 10+ production overlays:
  1. SymbolicGovernance (complete)
  2. SecurityMonitoring
  3. PerformanceOptimizer
  4. CapsuleAnalyzer
  5. MLIntelligence
  6. KnowledgePropagator
  7. HealthMonitor
  8. AuditLogger
  9. ConstitutionalAI
  10. GhostCouncil

**Success Criteria:**
- All overlays follow OverlayBase interface
- Dependencies resolved correctly
- Health checks passing
- Event system used for communication
- Metrics tracked

#### Goal 3: Dashboard & UI Complete

**Objectives:**
- Complete dashboard with real-time metrics
- Overlay management interface (enable/disable, view metrics)
- Governance voting UI (create proposal, vote, view results)
- System health visualization (color-coded status)
- Capsule management UI (CRUD, lineage viewer)

**Success Criteria:**
- All features functional
- Responsive design (mobile-friendly)
- Real-time updates (WebSockets or polling)
- Accessible (WCAG 2.1 AA compliance)

#### Goal 4: API Complete

**Objectives:**
- Implement all API endpoints from specification
- API documentation (OpenAPI/Swagger)
- Rate limiting and quotas
- API key authentication

**Success Criteria:**
- All endpoints functional
- Documentation auto-generated
- Rate limiting prevents abuse
- Authentication required for sensitive operations

### Medium-Term Goals (6-12 Months)

#### Goal 5: Cascade Effect Implementation

**Objectives:**
- Implement knowledge propagation via event system
- Create cascade visualizer (see knowledge flow)
- Measure cascade impact (metrics)
- Optimize cascade routing (ML-based relevance)

**Success Criteria:**
- Overlays receive relevant events only
- Cascade events tracked in audit log
- Measurable intelligence improvements from cascades
- Visualization shows knowledge flow

#### Goal 6: Production Deployment

**Objectives:**
- Kubernetes cluster setup (GKE, EKS, or AKS)
- ArgoCD GitOps pipeline
- CI/CD automation (GitHub Actions)
- Monitoring and alerting (Prometheus, Grafana, Sentry)
- Backup and disaster recovery

**Success Criteria:**
- 99.9% uptime SLA
- Automated deployments (Git push → production)
- Alerts for critical issues
- <5 minute recovery time objective (RTO)
- Zero-downtime deployments

#### Goal 7: Performance Optimization

**Objectives:**
- Database query optimization (indexes, query plans)
- Caching layer (Redis)
- Static asset CDN
- Database read replicas
- Horizontal scaling proven (10+ pods)

**Success Criteria:**
- API response time <100ms (P95)
- Handle 10,000 concurrent users
- Cache hit rate >80%
- Database query time <10ms (P95)

#### Goal 8: Security Hardening

**Objectives:**
- Penetration testing (external firm)
- Security audit (code review)
- Compliance certification (SOC 2, ISO 27001)
- Bug bounty program

**Success Criteria:**
- Zero critical vulnerabilities
- Compliance certifications obtained
- Bug bounty program active
- Security documentation complete

### Long-Term Goals (12-24 Months)

#### Goal 9: Multi-Tenancy

**Objectives:**
- Isolated capsule spaces per organization
- Per-tenant overlay customization
- Enterprise licensing and billing
- SSO integration (SAML, OIDC)

**Success Criteria:**
- 100+ organizations on platform
- Complete data isolation
- Custom branding per tenant
- Enterprise contracts signed

#### Goal 10: Distributed Architecture

**Objectives:**
- Multi-region deployment
- Distributed capsule storage
- Event streaming (Kafka)
- Global CDN for content delivery

**Success Criteria:**
- <100ms latency globally
- 99.99% uptime SLA
- Automatic regional failover
- No single point of failure

#### Goal 11: Advanced AI Features

**Objectives:**
- Deep learning integration (transformers)
- Natural language capsule search
- Automated capsule generation from conversations
- Predictive governance recommendations
- Code generation from natural language

**Success Criteria:**
- Natural language search accuracy >90%
- Auto-generated capsules require <10% edits
- Governance recommendations accepted >70%
- Code generation passes tests >80%

#### Goal 12: Ecosystem & Marketplace

**Objectives:**
- Public overlay marketplace
- Capsule marketplace (buy/sell/license)
- Third-party integrations (Slack, Discord, Notion)
- Developer SDK (Python, JavaScript, Go)
- Plugin development documentation

**Success Criteria:**
- 100+ third-party overlays published
- 1,000+ capsules in marketplace
- 10+ integrations with external platforms
- Active developer community (forums, Discord)

### Success Metrics

#### Technical Metrics

**Reliability:**
- Uptime: 99.9% (short-term) → 99.99% (long-term)
- Mean Time To Recovery (MTTR): <5 minutes
- Error rate: <0.1% of requests
- Zero data loss events

**Performance:**
- API response time (P95): <100ms
- Database query time (P95): <10ms
- Overlay activation time: <5 seconds
- Dashboard load time: <2 seconds

**Security:**
- Zero critical vulnerabilities
- Audit log coverage: 100% of sensitive operations
- Trust validation enforcement: 100% of overlay activations
- Security scan frequency: Daily

**Quality:**
- Test coverage: >90%
- Code quality (Ruff/Black): 100% compliance
- Type hint coverage: >80%
- Documentation coverage: 100% of public APIs

#### Business Metrics

**Adoption:**
- Active users: 1,000 (6 mo) → 10,000 (12 mo) → 100,000 (24 mo)
- Organizations: 10 (6 mo) → 100 (12 mo) → 1,000 (24 mo)
- Daily active users (DAU): 30% of total users

**Engagement:**
- Capsules created per user per month: 10+
- Governance participation rate: >50% of users
- Average session duration: >10 minutes
- Return rate: >70% weekly

**Ecosystem:**
- Third-party overlays: 100+
- Marketplace transactions: 1,000+/month
- Developer signups: 500+
- Integration installations: 5,000+

**Revenue (If Applicable):**
- Enterprise contracts: 50+ (12 mo) → 200+ (24 mo)
- Average contract value (ACV): $50k+
- Monthly recurring revenue (MRR) growth: 20%/month
- Customer acquisition cost (CAC) payback: <6 months

#### Innovation Metrics

**Cascade Effect:**
- Cascade events per day: 100+
- Overlays participating in cascades: 80%+
- Measurable improvements from cascades: 50%+ of events

**Self-Healing:**
- Auto-quarantine events per week: Track trend (should decrease over time)
- Auto-recovery success rate: >95%
- Mean time to detect (MTTD): <1 minute
- Human intervention required: <5% of incidents

**ML Accuracy:**
- Anomaly detection precision: >90%
- Recommendation acceptance rate: >70%
- Prediction accuracy: >85%
- False positive rate: <5%

**Governance Quality:**
- Proposals leading to improvements: >60%
- Constitutional AI agreement with community: >80%
- Ethical drift incidents: 0
- Governance efficiency (time to decision): <7 days average

---

## Conclusion

Forge Cascade is a groundbreaking platform that fundamentally reimagines how AI systems manage knowledge, govern themselves, and evolve over time.

### The Core Innovation

By solving the problem of **ephemeral wisdom** through:
- Persistent memory (capsules that survive generations)
- Symbolic inheritance (clear lineage from old to new knowledge)
- The cascade effect (knowledge propagation across the ecosystem)
- Self-governance (democratic decision-making)
- Self-healing (automatic problem detection and correction)

Forge enables AI systems to build upon past knowledge rather than constantly starting from scratch.

### Production-Grade Design

The architecture is designed for:
- **Reliability:** Self-healing, health monitoring, quarantine system
- **Security:** Trust hierarchy, validation, resource sandboxing
- **Performance:** Async I/O, caching, horizontal scaling
- **Quality:** Comprehensive testing, automated quality gates
- **Maintainability:** Clean code, clear contracts, dependency injection

### The Path Forward

This specification provides:
1. **Clear Vision:** What Forge is trying to accomplish and why
2. **Concrete Architecture:** How the system should be built
3. **Feature Roadmap:** What capabilities should exist when
4. **Quality Standards:** How to ensure excellence throughout
5. **Success Metrics:** How to measure if we're achieving the vision

### Next Steps for Rebuilding

To rebuild Forge from scratch using this specification:

1. **Start with Core Kernel:**
   - Implement OverlayManager with all its components
   - Build security layer (SecurityValidator, TrustHierarchy)
   - Create data models (User, Capsule, Overlay, etc.)

2. **Build Foundation:**
   - Set up Quart application
   - Implement authentication
   - Create basic CRUD for capsules

3. **Add Intelligence:**
   - Implement first few overlays
   - Build event system for cascade effect
   - Add ML capabilities

4. **Create Interface:**
   - Build dashboard
   - Implement governance UI
   - Create API layer

5. **Automate Quality:**
   - Set up scan/repair pipeline
   - Implement CMD orchestration
   - Add comprehensive tests

6. **Deploy & Scale:**
   - Containerize with Docker
   - Deploy to Kubernetes
   - Set up CI/CD with ArgoCD

### Final Thoughts

Forge is not just another web application or database wrapper. It's a vision for how AI systems can transcend their current limitations and become truly evolutionary - building knowledge, wisdom, and capabilities across generations rather than losing them with each update.

This specification captures that vision in concrete, implementable detail.

---

**Document Status:** Living Document - Should be updated as the vision evolves
**Maintenance:** Review quarterly, update based on learnings
**Feedback:** Submit issues/suggestions via GitHub or governance proposals

---

END OF SPECIFICATION
