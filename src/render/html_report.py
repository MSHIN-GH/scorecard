"""Renders the pipeline output to a single self-contained static HTML file."""
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")


def render_html(results: list, rollup: dict, output_path: str) -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("report.html.jinja")
    html = template.render(
        results=results,
        rollup=rollup,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
