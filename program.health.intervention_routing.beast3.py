# program.health.intervention_routing.beast3.py
# Beast System 3.0 — Deterministic Intervention Routing Engine

from dataclasses import dataclass, field
import time
import hashlib

@dataclass
class InterventionEvent:
    family_id: str
    priority: str
    interventions: list
    triggers: dict
    ts: float = field(default_factory=time.time)
    hash: str = ""

    def finalize(self):
        serialized = f"{self.family_id}{self.priority}{self.interventions}{self.triggers}{self.ts}".encode("utf-8")
        self.hash = hashlib.sha256(serialized).hexdigest()

@dataclass
class InterventionProfile:
    family_id: str
    events: list = field(default_factory=list)
    last_update: float = field(default_factory=time.time)

    def add_event(self, event: InterventionEvent):
        event.finalize()
        self.events.append(event)
        self.last_update = event.ts

class InterventionRoutingEngine:
    def __init__(self, kernel, scoring_engine, vitals_engine, continuity_engine, program_engine):
        self.kernel = kernel
        self.scoring_engine = scoring_engine
        self.vitals_engine = vitals_engine
        self.continuity_engine = continuity_engine
        self.program_engine = program_engine
        self.routing_profiles = {}

    def create_profile(self, family_id: str):
        profile = InterventionProfile(family_id)
        self.routing_profiles[family_id] = profile

        return self.kernel.dispatch(
            module="health.intervention_routing",
            action="create_profile",
            payload={"family_id": family_id}
        )

    def route(self, family_id: str):
        # Retrieve latest packets from upstream modules
        score_profile = self.scoring_engine.get_scores(family_id)
        vitals_profile = self.vitals_engine.get_packets(family_id)
        continuity_profile = self.continuity_engine.get_packets(family_id)
        program_profile = self.program_engine.get_profile(family_id)

        if not score_profile or not score_profile.packets:
            raise ValueError("Missing scoring data")
        if not vitals_profile or not vitals_profile.packets:
            raise ValueError("Missing vitals data")
        if not continuity_profile or not continuity_profile.packets:
            raise ValueError("Missing continuity data")

        latest_score = score_profile.packets[-1]
        latest_vitals = vitals_profile.packets[-1]
        latest_continuity = continuity_profile.packets[-1]

        # Determine priority level
        priority = "low"
        if latest_score.score < 0.40 or latest_vitals.emergency or latest_continuity.escalation_required:
            priority = "high"
        elif latest_score.score < 0.55:
            priority = "medium"

        # Intervention recommendations
        interventions = []

        # Vitals-based interventions
        if latest_vitals.emergency:
            interventions.append("emergency_medical_support")
        elif len(latest_vitals.risk_flags) >= 2:
            interventions.append("medical_checkin")

        # Continuity-based interventions
        if latest_continuity.escalation_required:
            interventions.append("care_escalation")
        elif latest_continuity.continuity_score < 0.55:
            interventions.append("care_followup")

        # Wellbeing score interventions
        if latest_score.score < 0.40:
            interventions.append("intensive_support")
        elif latest_score.score < 0.55:
            interventions.append("community_support")

        # Program-based interventions
        if program_profile:
            for pid, enrollment in program_profile.enrollments.items():
                if not enrollment["completed"]:
                    interventions.append(f"program_phase_support:{pid}:{enrollment['current_phase']}")

        triggers = {
            "well_score": latest_score.score,
            "vitals_emergency": latest_vitals.emergency,
            "continuity_escalation": latest_continuity.escalation_required,
            "risk_flags": latest_score.risk_flags + latest_vitals.risk_flags
        }

        event = InterventionEvent(
            family_id=family_id,
            priority=priority,
            interventions=interventions,
            triggers=triggers
        )

        profile = self.routing_profiles[family_id]
        profile.add_event(event)

        return self.kernel.dispatch(
            module="health.intervention_routing",
            action="route",
            payload={
                "family_id": family_id,
                "priority": priority,
                "interventions": interventions,
                "triggers": triggers
            }
        )

    def get_events(self, family_id: str):
        return self.routing_profiles.get(family_id, None)
