"""Render a PlantUML diagram to SVG using the plantuml jar."""
import os
import subprocess

from tools.azdisc.arg import AzDiscError


def render(puml_path: str, output_dir: str, plantuml_jar: str = None) -> str:
    """
    Render a .puml file to SVG using the plantuml jar.

    Returns the path to the generated SVG file.
    Raises AzDiscError on failure.
    """
    jar = plantuml_jar or os.environ.get("PLANTUML_JAR") or "plantuml.jar"
    os.makedirs(output_dir, exist_ok=True)

    cmd = ["java", "-jar", jar, "-tsvg", "-o", os.path.abspath(output_dir), puml_path]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise AzDiscError(
            f"plantuml render failed for {puml_path}",
            cmd=cmd,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    base = os.path.splitext(os.path.basename(puml_path))[0]
    svg_path = os.path.join(output_dir, base + ".svg")
    return svg_path
