"""Factory Automation Panel — D5 industrial-iot demo.

PLC + HMI panel for production line. D5 because real-device action.
W14 protections:
  - wrong cabinet upload -> verify cabinet_id matches IO map (D5)
  - missing emergency stop verification -> mandatory pre-upload (D5)
  - unsafe override safety interlock -> requires Council + multi-sig (D5)
"""
from sylion.demo.factory_automation_panel.models import (
    Cabinet, EmergencyStop, IOMapping, ProgramUpload, SafetyInterlock,
)
from sylion.demo.factory_automation_panel.service import FactoryService
from sylion.demo.factory_automation_panel.store import FactoryStore

__all__ = [
    "Cabinet", "EmergencyStop", "IOMapping",
    "ProgramUpload", "SafetyInterlock",
    "FactoryService", "FactoryStore",
]
