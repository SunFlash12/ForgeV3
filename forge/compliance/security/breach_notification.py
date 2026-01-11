"""
Forge Compliance Framework - Breach Notification Service

Automated breach detection, assessment, and notification:
- Per-jurisdiction deadline calculation
- Regulatory notification templates
- Affected individual notifications
- Incident response workflow
- Evidence preservation

Implements requirements from:
- GDPR Article 33-34 (72-hour DPA notification)
- CCPA §1798.82 (expedient notification)
- HIPAA Breach Notification Rule (60 days)
- State breach notification laws (varies)
- LGPD Article 48
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import (
    Jurisdiction,
    DataClassification,
    BreachSeverity,
)

logger = structlog.get_logger(__name__)


class BreachType(str, Enum):
    """Types of data breaches."""
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    UNAUTHORIZED_DISCLOSURE = "unauthorized_disclosure"
    DATA_THEFT = "data_theft"
    DATA_EXFILTRATION = "data_exfiltration"
    RANSOMWARE = "ransomware"
    LOST_DEVICE = "lost_device"
    ACCIDENTAL_DISCLOSURE = "accidental_disclosure"
    INSIDER_THREAT = "insider_threat"
    PHISHING = "phishing"
    SYSTEM_COMPROMISE = "system_compromise"
    VENDOR_BREACH = "vendor_breach"
    PHYSICAL_BREACH = "physical_breach"


class BreachStatus(str, Enum):
    """Breach incident status."""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    ASSESSED = "assessed"
    NOTIFYING = "notifying"
    REMEDIATED = "remediated"
    CLOSED = "closed"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class NotificationRecipient(str, Enum):
    """Types of breach notification recipients."""
    SUPERVISORY_AUTHORITY = "supervisory_authority"
    DATA_SUBJECTS = "data_subjects"
    MEDIA = "media"
    LAW_ENFORCEMENT = "law_enforcement"
    PAYMENT_BRANDS = "payment_brands"
    HHS_OCR = "hhs_ocr"
    STATE_ATTORNEY_GENERAL = "state_attorney_general"


@dataclass
class BreachIncident:
    """Data breach incident record."""
    incident_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Discovery
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    discovered_by: str = ""
    discovery_method: str = ""  # automated, employee_report, external_report, audit
    
    # Classification
    breach_type: BreachType = BreachType.UNAUTHORIZED_ACCESS
    severity: BreachSeverity = BreachSeverity.MEDIUM
    status: BreachStatus = BreachStatus.DETECTED
    
    # Scope
    data_categories: list[DataClassification] = field(default_factory=list)
    data_elements: list[str] = field(default_factory=list)
    # e.g., ["name", "email", "ssn", "credit_card"]
    
    jurisdictions: list[Jurisdiction] = field(default_factory=list)
    record_count: int = 0
    affected_systems: list[str] = field(default_factory=list)
    
    # Timeline
    breach_occurred_at: datetime | None = None  # When breach actually happened
    contained_at: datetime | None = None
    remediated_at: datetime | None = None
    closed_at: datetime | None = None
    
    # Assessment
    risk_assessment: str = ""
    likely_harm: bool = False
    encryption_in_place: bool = False
    
    # Notifications
    dpa_notification_required: bool = False
    dpa_notification_deadline: datetime | None = None
    individual_notification_required: bool = False
    individual_notification_deadline: datetime | None = None
    
    # Response
    response_lead: str = ""
    investigation_notes: str = ""
    root_cause: str = ""
    remediation_actions: list[str] = field(default_factory=list)


@dataclass
class NotificationRecord:
    """Record of breach notification sent."""
    notification_id: str = field(default_factory=lambda: str(uuid4()))
    incident_id: str = ""
    
    # Recipient
    recipient_type: str = ""  # dpa, individual, media, hhs
    recipient_id: str = ""
    recipient_email: str = ""
    jurisdiction: Jurisdiction = Jurisdiction.GLOBAL
    
    # Content
    notification_type: str = ""  # initial, supplemental, final
    subject: str = ""
    content_hash: str = ""
    
    # Status
    status: NotificationStatus = NotificationStatus.PENDING
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    
    # Tracking
    deadline: datetime | None = None
    is_overdue: bool = False


@dataclass
class JurisdictionDeadline:
    """Notification deadline for a specific jurisdiction."""
    jurisdiction: Jurisdiction
    deadline: datetime
    deadline_hours: int
    notification_to: str  # "dpa", "individuals", "both"
    notes: str = ""


@dataclass
class DeadlineAlert:
    """Alert for an approaching or missed deadline."""
    incident_id: str
    jurisdiction: Jurisdiction
    deadline: datetime
    deadline_type: str  # "dpa", "individual"
    alert_level: str  # "warning", "urgent", "critical", "overdue"
    hours_remaining: float
    alert_sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Alert thresholds in hours before deadline
DEADLINE_ALERT_THRESHOLDS = {
    "warning": 24,    # 24 hours before
    "urgent": 12,     # 12 hours before
    "critical": 6,    # 6 hours before
    "imminent": 1,    # 1 hour before
}


class BreachNotificationService:
    """
    Breach detection, assessment, and notification service.
    
    Manages the complete incident response lifecycle with
    automated deadline tracking and notification generation.
    """
    
    def __init__(self, alert_callback: callable | None = None):
        """
        Initialize breach notification service.

        Args:
            alert_callback: Optional async callback function for sending deadline alerts.
                            Signature: async def callback(alert: DeadlineAlert) -> None
        """
        self._incidents: dict[str, BreachIncident] = {}
        self._notifications: dict[str, list[NotificationRecord]] = {}

        # Track sent alerts to prevent duplicates: {incident_id}_{alert_level}
        self._sent_alerts: set[str] = set()

        # Callback for sending deadline alerts
        self._alert_callback = alert_callback

        # Notification deadlines by jurisdiction (hours from discovery)
        self._jurisdiction_deadlines = {
            Jurisdiction.EU: {"dpa": 72, "individuals": 0},  # Without undue delay
            Jurisdiction.UK: {"dpa": 72, "individuals": 0},
            Jurisdiction.US_CALIFORNIA: {"dpa": 72, "individuals": 72},  # Expedient
            Jurisdiction.BRAZIL: {"dpa": 72, "individuals": 0},  # Reasonable time
            Jurisdiction.AUSTRALIA: {"dpa": 72, "individuals": 720},  # 30 days
            Jurisdiction.SINGAPORE: {"dpa": 72, "individuals": 72},
            Jurisdiction.INDIA: {"dpa": 72, "individuals": 0},
            Jurisdiction.CHINA: {"dpa": 72, "individuals": 0},
            # US States with specific requirements
            Jurisdiction.US_COLORADO: {"dpa": 0, "individuals": 720},  # 30 days
            Jurisdiction.US_VIRGINIA: {"dpa": 0, "individuals": 1440},  # 60 days
        }
        
        # HIPAA specific (for PHI breaches)
        self._hipaa_deadlines = {
            "hhs": 1440,  # 60 days for <500 records, immediate for 500+
            "individuals": 1440,  # 60 days
            "media": 1440,  # 60 days (if 500+ in state)
        }
    
    # ───────────────────────────────────────────────────────────────
    # INCIDENT MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    async def report_breach(
        self,
        discovered_by: str,
        discovery_method: str,
        breach_type: BreachType,
        severity: BreachSeverity,
        data_categories: list[DataClassification],
        data_elements: list[str],
        jurisdictions: list[Jurisdiction],
        record_count: int,
        affected_systems: list[str],
        breach_occurred_at: datetime | None = None,
        encryption_in_place: bool = False,
    ) -> BreachIncident:
        """
        Report a new data breach incident.
        
        Automatically calculates notification deadlines.
        """
        incident = BreachIncident(
            discovered_by=discovered_by,
            discovery_method=discovery_method,
            breach_type=breach_type,
            severity=severity,
            data_categories=data_categories,
            data_elements=data_elements,
            jurisdictions=jurisdictions,
            record_count=record_count,
            affected_systems=affected_systems,
            breach_occurred_at=breach_occurred_at or datetime.now(UTC),
            encryption_in_place=encryption_in_place,
        )
        
        # Assess notification requirements
        incident = self._assess_notification_requirements(incident)
        
        # Calculate deadlines
        deadlines = self._calculate_deadlines(incident)
        if deadlines:
            # Use most urgent deadline
            urgent = min(deadlines, key=lambda d: d.deadline)
            incident.dpa_notification_deadline = urgent.deadline
        
        # Check if individual notification required
        incident.individual_notification_required = self._requires_individual_notification(incident)
        
        # Store incident
        self._incidents[incident.incident_id] = incident
        self._notifications[incident.incident_id] = []
        
        logger.critical(
            "breach_reported",
            incident_id=incident.incident_id,
            severity=severity.value,
            record_count=record_count,
            dpa_deadline=incident.dpa_notification_deadline.isoformat() if incident.dpa_notification_deadline else None,
        )
        
        return incident
    
    def _assess_notification_requirements(
        self,
        incident: BreachIncident,
    ) -> BreachIncident:
        """Assess if breach requires notification."""
        # GDPR: Risk to rights and freedoms
        # Default to requiring notification unless clearly no risk
        
        high_risk_data = {
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.PCI,
            DataClassification.FINANCIAL,
        }
        
        # High risk categories always require notification
        if any(cat in high_risk_data for cat in incident.data_categories):
            incident.dpa_notification_required = True
            incident.likely_harm = True
        
        # Check for sensitive data elements
        sensitive_elements = {
            "ssn", "social_security", "passport", "drivers_license",
            "credit_card", "bank_account", "health_record", "medical",
            "biometric", "password", "credentials",
        }
        
        if any(elem.lower() in sensitive_elements for elem in incident.data_elements):
            incident.dpa_notification_required = True
            incident.likely_harm = True
        
        # Large scale breaches always require notification
        if incident.record_count >= 500:
            incident.dpa_notification_required = True
        
        # Encryption may exempt from notification in some jurisdictions
        if incident.encryption_in_place:
            incident.risk_assessment = "Data was encrypted - reduced risk"
            # But still assess based on other factors
        
        return incident
    
    def _requires_individual_notification(
        self,
        incident: BreachIncident,
    ) -> bool:
        """Determine if individual notification is required."""
        # High risk to individuals
        if incident.likely_harm:
            return True
        
        # Large scale
        if incident.record_count >= 500:
            return True
        
        # Sensitive data types
        sensitive = {
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.PCI,
        }
        
        if any(cat in sensitive for cat in incident.data_categories):
            return True
        
        return False
    
    def _calculate_deadlines(
        self,
        incident: BreachIncident,
    ) -> list[JurisdictionDeadline]:
        """Calculate notification deadlines for all affected jurisdictions."""
        deadlines = []
        discovery = incident.discovered_at
        
        for jurisdiction in incident.jurisdictions:
            hours = self._jurisdiction_deadlines.get(jurisdiction, {}).get("dpa", 72)
            
            deadline = JurisdictionDeadline(
                jurisdiction=jurisdiction,
                deadline=discovery + timedelta(hours=hours),
                deadline_hours=hours,
                notification_to="dpa",
            )
            deadlines.append(deadline)
        
        # Add HIPAA deadlines if PHI involved
        if DataClassification.PHI in incident.data_categories:
            if incident.record_count >= 500:
                # Immediate notification required
                deadlines.append(JurisdictionDeadline(
                    jurisdiction=Jurisdiction.US_FEDERAL,
                    deadline=discovery + timedelta(hours=72),
                    deadline_hours=72,
                    notification_to="hhs",
                    notes="500+ records - immediate HHS notification",
                ))
            else:
                # Annual batch notification acceptable
                deadlines.append(JurisdictionDeadline(
                    jurisdiction=Jurisdiction.US_FEDERAL,
                    deadline=discovery + timedelta(hours=self._hipaa_deadlines["hhs"]),
                    deadline_hours=self._hipaa_deadlines["hhs"],
                    notification_to="hhs",
                ))
        
        return deadlines
    
    # ───────────────────────────────────────────────────────────────
    # INCIDENT RESPONSE WORKFLOW
    # ───────────────────────────────────────────────────────────────
    
    async def update_status(
        self,
        incident_id: str,
        status: BreachStatus,
        notes: str = "",
        updated_by: str = "",
    ) -> BreachIncident:
        """Update incident status through the response workflow."""
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")
        
        old_status = incident.status
        incident.status = status
        
        # Update timestamps
        if status == BreachStatus.CONTAINED:
            incident.contained_at = datetime.now(UTC)
        elif status == BreachStatus.REMEDIATED:
            incident.remediated_at = datetime.now(UTC)
        elif status == BreachStatus.CLOSED:
            incident.closed_at = datetime.now(UTC)
        
        if notes:
            incident.investigation_notes += f"\n[{datetime.now(UTC).isoformat()}] {notes}"
        
        logger.info(
            "breach_status_updated",
            incident_id=incident_id,
            old_status=old_status.value,
            new_status=status.value,
            updated_by=updated_by,
        )
        
        return incident
    
    async def record_root_cause(
        self,
        incident_id: str,
        root_cause: str,
        remediation_actions: list[str],
    ) -> BreachIncident:
        """Record root cause analysis and remediation plan."""
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")
        
        incident.root_cause = root_cause
        incident.remediation_actions = remediation_actions
        
        logger.info(
            "breach_root_cause_recorded",
            incident_id=incident_id,
        )
        
        return incident
    
    # ───────────────────────────────────────────────────────────────
    # NOTIFICATIONS
    # ───────────────────────────────────────────────────────────────
    
    async def send_dpa_notification(
        self,
        incident_id: str,
        jurisdiction: Jurisdiction,
        recipient_email: str,
    ) -> NotificationRecord:
        """
        Send notification to Data Protection Authority.
        
        Per GDPR Article 33.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")
        
        # Generate notification content
        content = self._generate_dpa_notification(incident, jurisdiction)
        
        notification = NotificationRecord(
            incident_id=incident_id,
            recipient_type="dpa",
            recipient_email=recipient_email,
            jurisdiction=jurisdiction,
            notification_type="initial",
            subject=f"Data Breach Notification - {incident.incident_id}",
            status=NotificationStatus.PENDING,
            deadline=incident.dpa_notification_deadline,
        )
        
        # In production, actually send the notification
        notification.sent_at = datetime.now(UTC)
        notification.status = NotificationStatus.SENT
        
        self._notifications[incident_id].append(notification)
        
        logger.info(
            "dpa_notification_sent",
            incident_id=incident_id,
            jurisdiction=jurisdiction.value,
        )
        
        return notification
    
    def _generate_dpa_notification(
        self,
        incident: BreachIncident,
        jurisdiction: Jurisdiction,
    ) -> str:
        """Generate DPA notification content per GDPR Article 33."""
        return f"""
DATA BREACH NOTIFICATION

Incident Reference: {incident.incident_id}
Date of Discovery: {incident.discovered_at.strftime('%Y-%m-%d %H:%M UTC')}
Date Breach Occurred: {incident.breach_occurred_at.strftime('%Y-%m-%d %H:%M UTC') if incident.breach_occurred_at else 'Under investigation'}

1. NATURE OF THE BREACH
Type: {incident.breach_type.value}
Description: {incident.investigation_notes or 'Under investigation'}

2. DATA CATEGORIES AFFECTED
{', '.join(cat.value for cat in incident.data_categories)}

3. DATA ELEMENTS AFFECTED
{', '.join(incident.data_elements)}

4. APPROXIMATE NUMBER OF DATA SUBJECTS
{incident.record_count:,}

5. DATA PROTECTION OFFICER CONTACT
[DPO Contact Information]

6. LIKELY CONSEQUENCES
{'High risk to rights and freedoms of data subjects' if incident.likely_harm else 'Assessment ongoing'}

7. MEASURES TAKEN
Status: {incident.status.value}
Containment: {'Yes' if incident.contained_at else 'In progress'}
Remediation Actions:
{chr(10).join('- ' + action for action in incident.remediation_actions) if incident.remediation_actions else '- Under development'}

8. ADDITIONAL INFORMATION
{incident.risk_assessment or 'To be provided'}

This notification is made in accordance with Article 33 of the GDPR.
We will provide supplementary information as our investigation progresses.
"""
    
    async def send_individual_notifications(
        self,
        incident_id: str,
        affected_individuals: list[dict[str, str]],
    ) -> list[NotificationRecord]:
        """
        Send notifications to affected individuals.
        
        Per GDPR Article 34.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")
        
        notifications = []
        
        for individual in affected_individuals:
            content = self._generate_individual_notification(
                incident,
                individual.get("name", ""),
            )
            
            notification = NotificationRecord(
                incident_id=incident_id,
                recipient_type="individual",
                recipient_id=individual.get("id", ""),
                recipient_email=individual.get("email", ""),
                notification_type="initial",
                subject="Important: Security Incident Notification",
                status=NotificationStatus.PENDING,
            )
            
            # In production, send via email service
            notification.sent_at = datetime.now(UTC)
            notification.status = NotificationStatus.SENT
            
            notifications.append(notification)
            self._notifications[incident_id].append(notification)
        
        logger.info(
            "individual_notifications_sent",
            incident_id=incident_id,
            count=len(notifications),
        )
        
        return notifications
    
    def _generate_individual_notification(
        self,
        incident: BreachIncident,
        recipient_name: str,
    ) -> str:
        """Generate individual notification content."""
        return f"""
Dear {recipient_name or 'Valued Customer'},

We are writing to inform you of a security incident that may have affected 
your personal information.

WHAT HAPPENED
On {incident.discovered_at.strftime('%B %d, %Y')}, we discovered that 
{incident.breach_type.value.replace('_', ' ')} occurred, which may have 
resulted in unauthorized access to some of your personal information.

WHAT INFORMATION WAS INVOLVED
The following types of information may have been affected:
{', '.join(incident.data_elements)}

WHAT WE ARE DOING
We have taken immediate steps to address this incident:
{chr(10).join('• ' + action for action in incident.remediation_actions) if incident.remediation_actions else '• Investigation ongoing'}

WHAT YOU CAN DO
We recommend that you:
• Monitor your accounts for any suspicious activity
• Review your credit reports
• Be cautious of phishing emails or calls
• Consider placing a fraud alert on your credit file

FOR MORE INFORMATION
If you have questions, please contact our dedicated response team:
[Contact Information]

We sincerely apologize for any inconvenience this may cause and are 
committed to protecting your information.

Sincerely,
[Organization Name]
"""
    
    # ───────────────────────────────────────────────────────────────
    # MONITORING / REPORTING
    # ───────────────────────────────────────────────────────────────
    
    def get_overdue_notifications(self) -> list[dict[str, Any]]:
        """Get list of overdue notifications."""
        overdue = []
        now = datetime.now(UTC)
        
        for incident_id, incident in self._incidents.items():
            if incident.status in {BreachStatus.CLOSED, BreachStatus.REMEDIATED}:
                continue
            
            notifications = self._notifications.get(incident_id, [])
            dpa_sent = any(
                n.recipient_type == "dpa" and n.status == NotificationStatus.SENT
                for n in notifications
            )
            
            if incident.dpa_notification_required and not dpa_sent:
                if incident.dpa_notification_deadline and now > incident.dpa_notification_deadline:
                    overdue.append({
                        "incident_id": incident_id,
                        "type": "dpa",
                        "deadline": incident.dpa_notification_deadline.isoformat(),
                        "hours_overdue": (now - incident.dpa_notification_deadline).total_seconds() / 3600,
                    })
        
        return overdue
    
    def get_incident_summary(self, incident_id: str) -> dict[str, Any]:
        """Get comprehensive incident summary for reporting."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return {}
        
        notifications = self._notifications.get(incident_id, [])
        
        return {
            "incident_id": incident.incident_id,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "breach_type": incident.breach_type.value,
            "timeline": {
                "occurred": incident.breach_occurred_at.isoformat() if incident.breach_occurred_at else None,
                "discovered": incident.discovered_at.isoformat(),
                "contained": incident.contained_at.isoformat() if incident.contained_at else None,
                "remediated": incident.remediated_at.isoformat() if incident.remediated_at else None,
                "closed": incident.closed_at.isoformat() if incident.closed_at else None,
            },
            "scope": {
                "record_count": incident.record_count,
                "data_categories": [c.value for c in incident.data_categories],
                "data_elements": incident.data_elements,
                "jurisdictions": [j.value for j in incident.jurisdictions],
                "affected_systems": incident.affected_systems,
            },
            "notifications": {
                "dpa_required": incident.dpa_notification_required,
                "dpa_deadline": incident.dpa_notification_deadline.isoformat() if incident.dpa_notification_deadline else None,
                "dpa_sent": any(n.recipient_type == "dpa" and n.status == NotificationStatus.SENT for n in notifications),
                "individual_required": incident.individual_notification_required,
                "individuals_notified": len([n for n in notifications if n.recipient_type == "individual"]),
            },
            "assessment": {
                "likely_harm": incident.likely_harm,
                "encryption_in_place": incident.encryption_in_place,
                "root_cause": incident.root_cause,
            },
            "remediation": incident.remediation_actions,
        }
    
    def get_metrics(self) -> dict[str, Any]:
        """Get breach metrics for compliance dashboard."""
        incidents = list(self._incidents.values())

        return {
            "total_incidents": len(incidents),
            "by_status": {
                status.value: len([i for i in incidents if i.status == status])
                for status in BreachStatus
            },
            "by_severity": {
                severity.value: len([i for i in incidents if i.severity == severity])
                for severity in BreachSeverity
            },
            "total_records_affected": sum(i.record_count for i in incidents),
            "notifications_sent": sum(
                len(self._notifications.get(i.incident_id, []))
                for i in incidents
            ),
            "overdue_notifications": len(self.get_overdue_notifications()),
        }

    # ───────────────────────────────────────────────────────────────
    # DEADLINE ALERTING (Security Audit Fix)
    # ───────────────────────────────────────────────────────────────

    def get_approaching_deadlines(self) -> list[DeadlineAlert]:
        """
        Get list of incidents with approaching deadlines.

        Returns alerts at various thresholds (24h, 12h, 6h, 1h before deadline).
        """
        alerts = []
        now = datetime.now(UTC)

        for incident_id, incident in self._incidents.items():
            # Skip closed/remediated incidents
            if incident.status in {BreachStatus.CLOSED, BreachStatus.REMEDIATED}:
                continue

            # Skip if notification not required
            if not incident.dpa_notification_required:
                continue

            # Check if DPA notification already sent
            notifications = self._notifications.get(incident_id, [])
            dpa_sent = any(
                n.recipient_type == "dpa" and n.status == NotificationStatus.SENT
                for n in notifications
            )

            if dpa_sent:
                continue

            # Check deadline
            if not incident.dpa_notification_deadline:
                continue

            deadline = incident.dpa_notification_deadline
            time_remaining = (deadline - now).total_seconds() / 3600  # hours

            # Determine alert level based on time remaining
            if time_remaining < 0:
                alert_level = "overdue"
            elif time_remaining <= DEADLINE_ALERT_THRESHOLDS["imminent"]:
                alert_level = "imminent"
            elif time_remaining <= DEADLINE_ALERT_THRESHOLDS["critical"]:
                alert_level = "critical"
            elif time_remaining <= DEADLINE_ALERT_THRESHOLDS["urgent"]:
                alert_level = "urgent"
            elif time_remaining <= DEADLINE_ALERT_THRESHOLDS["warning"]:
                alert_level = "warning"
            else:
                continue  # No alert needed yet

            # Create alert for each affected jurisdiction
            for jurisdiction in incident.jurisdictions:
                alerts.append(DeadlineAlert(
                    incident_id=incident_id,
                    jurisdiction=jurisdiction,
                    deadline=deadline,
                    deadline_type="dpa",
                    alert_level=alert_level,
                    hours_remaining=time_remaining,
                ))

        return alerts

    async def check_and_alert_deadlines(self) -> list[DeadlineAlert]:
        """
        Check all deadlines and send alerts for approaching/missed ones.

        This method should be called periodically (e.g., every 15 minutes)
        by a scheduler to ensure timely alerts.

        Returns:
            List of new alerts that were sent.
        """
        alerts = self.get_approaching_deadlines()
        sent_alerts = []

        for alert in alerts:
            # Create unique key for this alert to prevent duplicates
            alert_key = f"{alert.incident_id}_{alert.alert_level}"

            # Skip if already sent this alert level for this incident
            if alert_key in self._sent_alerts:
                continue

            # Mark as sent
            self._sent_alerts.add(alert_key)

            # Log the alert
            if alert.alert_level == "overdue":
                logger.critical(
                    "breach_deadline_overdue",
                    incident_id=alert.incident_id,
                    jurisdiction=alert.jurisdiction.value,
                    deadline=alert.deadline.isoformat(),
                    hours_overdue=abs(alert.hours_remaining),
                )
            else:
                logger.warning(
                    "breach_deadline_approaching",
                    incident_id=alert.incident_id,
                    jurisdiction=alert.jurisdiction.value,
                    deadline=alert.deadline.isoformat(),
                    hours_remaining=alert.hours_remaining,
                    alert_level=alert.alert_level,
                )

            # Send alert via callback if configured
            if self._alert_callback:
                try:
                    await self._alert_callback(alert)
                except Exception as e:
                    logger.error(
                        "deadline_alert_callback_failed",
                        incident_id=alert.incident_id,
                        error=str(e),
                    )

            sent_alerts.append(alert)

        return sent_alerts

    def set_alert_callback(self, callback: callable) -> None:
        """
        Set the callback function for deadline alerts.

        Args:
            callback: Async function with signature: async def(alert: DeadlineAlert) -> None
        """
        self._alert_callback = callback

    def get_alert_summary(self) -> dict[str, Any]:
        """Get summary of current deadline alert status."""
        alerts = self.get_approaching_deadlines()

        return {
            "total_alerts": len(alerts),
            "by_level": {
                level: len([a for a in alerts if a.alert_level == level])
                for level in ["warning", "urgent", "critical", "imminent", "overdue"]
            },
            "alerts": [
                {
                    "incident_id": a.incident_id,
                    "jurisdiction": a.jurisdiction.value,
                    "deadline": a.deadline.isoformat(),
                    "alert_level": a.alert_level,
                    "hours_remaining": round(a.hours_remaining, 1),
                }
                for a in alerts
            ],
        }

    def clear_sent_alerts_for_incident(self, incident_id: str) -> int:
        """
        Clear sent alert tracking for an incident.

        Call this when an incident is resolved or notification is sent
        to allow fresh alerts if needed in the future.

        Returns:
            Number of alerts cleared.
        """
        to_remove = [key for key in self._sent_alerts if key.startswith(f"{incident_id}_")]
        for key in to_remove:
            self._sent_alerts.discard(key)
        return len(to_remove)


# Global service instance
_breach_service: BreachNotificationService | None = None


def get_breach_notification_service() -> BreachNotificationService:
    """Get the global breach notification service."""
    global _breach_service
    if _breach_service is None:
        _breach_service = BreachNotificationService()
    return _breach_service
