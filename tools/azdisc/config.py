"""Configuration dataclass and loader for azdisc."""
import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class AppConfig:
    app: str
    subscriptions: List[str]
    seedResourceGroups: List[str]
    outputDir: str
    includeRbac: bool = False


def load_config(path: str) -> AppConfig:
    """Load and validate JSON config file into AppConfig."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    required = ("app", "subscriptions", "seedResourceGroups", "outputDir")
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required config field: {key}")

    return AppConfig(
        app=data["app"],
        subscriptions=data["subscriptions"],
        seedResourceGroups=data["seedResourceGroups"],
        outputDir=data["outputDir"],
        includeRbac=data.get("includeRbac", False),
    )
