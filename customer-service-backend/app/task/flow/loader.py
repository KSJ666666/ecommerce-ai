from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.task.flow.steps import (
    CollectSlotStep,
    FlowStep,
    step_from_json,
)
from app.task.flow.model import Flow, FlowsList, FlowSlot


class FlowLoader:
    """Load local flows from the YAML flow definition format."""

    def load_many(
        self,
        paths: List[str | Path],
    ) -> FlowsList:
        flows: List[Flow] = []
        slots: Dict[str, FlowSlot] = {}
        for path in paths:
            loaded = self.load(path)
            flows.extend(loaded.flows)
            duplicate_slots = set(slots).intersection(loaded.slots)
            if duplicate_slots:
                duplicates = ", ".join(sorted(duplicate_slots))
                raise ValueError(
                    f"Duplicate slot definitions found across flow files: {duplicates}."
                )
            slots.update(loaded.slots)
        return FlowsList(flows, slots=slots)

    def load(
        self,
        path: str | Path,
    ) -> FlowsList:
        flow_path = Path(path)
        with flow_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        flows_data = data.get("flows", {})
        print("flows_data:", flows_data)
        slots = self._load_slots(data.get("slots", {}))
        flows = []
        for flow_id, flow_data in flows_data.items():
            steps = [step_from_json(raw_step) for raw_step in flow_data.get("steps", [])]
            flows.append(
                Flow(
                    id=str(flow_id),
                    name=None if flow_data.get("name") is None else str(flow_data.get("name")),
                    description=str(flow_data.get("description", "")),
                    steps=steps,
                    slots=self._collect_flow_slots(steps, slots),
                )
            )
        return FlowsList(flows=flows, slots=slots)

    def _collect_flow_slots(
        self,
        steps: List[FlowStep],
        slots: Dict[str, FlowSlot],
    ) -> List[FlowSlot]:
        seen: set[str] = set()
        flow_slots: List[FlowSlot] = []

        for step in steps:
            if not isinstance(step, CollectSlotStep):
                continue
            slot_name = step.slot_name
            if slot_name in seen:
                continue
            seen.add(slot_name)
            slot_definition = slots.get(slot_name)
            if slot_definition is not None:
                flow_slots.append(slot_definition)

        return flow_slots

    def _load_slots(self, raw_slots: Any) -> Dict[str, FlowSlot]:
        return {
            str(slot_name): FlowSlot(
                name=str(slot_name),
                type=str(slot_data.get("type", "any")),
                label=str(slot_data.get("label", "")),
                description=str(slot_data.get("description", "")),
            )
            for slot_name, slot_data in (raw_slots or {}).items()
        }
