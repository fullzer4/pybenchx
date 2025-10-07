"""Render benchmark runs as Chart.js HTML documents."""

from __future__ import annotations

import html
import json
from typing import Iterable

from ..run_model import Run, VariantResult

_UNITS: tuple[tuple[str, float], ...] = (
    ("ns", 1.0),
    ("µs", 1_000.0),
    ("ms", 1_000_000.0),
    ("s", 1_000_000_000.0),
)


def _auto_unit(values: Iterable[float]) -> tuple[str, float]:
    max_v = max(values) if values else 0.0
    for idx, (name, scale) in enumerate(_UNITS):
        if idx == len(_UNITS) - 1:
            return name, scale
        next_scale = _UNITS[idx + 1][1]
        if max_v < next_scale:
            return name, scale
    return _UNITS[-1]


def _resolve_unit(values: Iterable[float], unit: str | None) -> tuple[str, float]:
    if not unit or unit == "auto":
        return _auto_unit(values)
    unit_map = {name: scale for name, scale in _UNITS}
    if unit not in unit_map:
        raise ValueError(f"unknown unit: {unit}")
    return unit, unit_map[unit]


def _variant_payload(results: Iterable[VariantResult]) -> list[dict[str, object]]:
    payload = []
    for res in results:
        payload.append(
            {
                "name": res.name,
                "group": res.group,
                "mean_ns": res.stats.mean,
                "baseline": res.baseline,
                "repeat": res.repeat,
                "n": res.n,
                "min_ns": res.stats.min,
                "max_ns": res.stats.max,
                "p99_ns": res.stats.p99,
            }
        )
    return payload
def render_run_chart(
    run: Run,
    *,
    title: str | None = None,
    unit: str | None = "auto",
) -> str:
    """Render a simple HTML page with a bar chart for the given run."""
    results = list(run.results)
    payload = _variant_payload(results)
    values_ns = [item["mean_ns"] for item in payload]
    resolved_unit, scale = _resolve_unit(values_ns, unit)

    scaled_values = []
    for v in values_ns:
        if v != v:  # NaN guard
            scaled_values.append(None)
        else:
            scaled_values.append(round(v / scale, 6))

    dataset = []
    for item, scaled in zip(payload, scaled_values):
        dataset.append(
            {
                "label": item["name"],
                "group": item["group"],
                "value": scaled,
                "baseline": item["baseline"],
                "mean_ns": item["mean_ns"],
                "repeat": item["repeat"],
                "n": item["n"],
                "min_ns": item["min_ns"],
                "max_ns": item["max_ns"],
                "p99_ns": item["p99_ns"],
            }
        )

    page_title = title or f"PyBenchX run — profile {run.meta.profile}"
    escaped_title = html.escape(page_title)
    meta_info = {
        "tool_version": run.meta.tool_version,
        "started_at": run.meta.started_at,
        "duration_s": run.meta.duration_s,
        "profile": run.meta.profile,
        "budget_ns": run.meta.budget_ns,
        "python_version": run.meta.python_version,
        "os": run.meta.os,
        "cpu": run.meta.cpu,
    }

    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>{title}</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js\"></script>
  <style>
    :root {{
      color-scheme: light dark;
      font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    }}
    body {{
      margin: 2rem;
      line-height: 1.5;
    }}
    .meta {{
      margin-bottom: 1.5rem;
    }}
    .meta dt {{
      font-weight: 600;
    }}
    canvas {{
      max-width: 960px;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <section class=\"meta\">
    <dl>
      <dt>Started</dt>
      <dd>{started_at}</dd>
      <dt>Profile</dt>
      <dd>{profile}</dd>
      <dt>Duration (s)</dt>
      <dd>{duration:.3f}</dd>
      <dt>Python</dt>
      <dd>{python_version}</dd>
      <dt>OS</dt>
      <dd>{os}</dd>
      <dt>CPU</dt>
      <dd>{cpu}</dd>
    </dl>
  </section>
  <canvas id=\"benchChart\" height=\"400\"></canvas>
  <script>
    const DATA = {data};
    const meta = {meta};
    const labels = DATA.map(d => d.label);
    const colors = DATA.map(d => d.baseline ? '#d97706' : '#2563eb');

    const chart = new Chart(document.getElementById('benchChart'), {{
      type: 'bar',
      data: {{
        labels,
        datasets: [{{
          label: `mean ({unit})`,
          data: DATA.map(d => d.value),
          backgroundColor: colors,
          borderRadius: 4,
        }}],
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: true }},
          tooltip: {{
            callbacks: {{
              label: (ctx) => {{
                const item = DATA[ctx.dataIndex];
                const meanNs = item.mean_ns.toLocaleString();
                const minNs = item.min_ns.toLocaleString();
                const maxNs = item.max_ns.toLocaleString();
                const p99Ns = item.p99_ns.toLocaleString();
                return [
                  `${{ctx.dataset.label}}: ${{ctx.formattedValue}}`,
                  `mean (ns): ${{meanNs}}`,
                  `min/max (ns): ${{minNs}} – ${{maxNs}}`,
                  `p99 (ns): ${{p99Ns}}`,
                  `repeat: ${{item.repeat}}, n: ${{item.n}}`
                ];
              }}
            }}
          }},
        }},
        scales: {{
          y: {{
            beginAtZero: true,
            title: {{ display: true, text: 'mean ({unit})' }},
          }}
        }},
      }},
    }});
  </script>
</body>
</html>
""".format(
        title=escaped_title,
        unit=resolved_unit,
        data=json.dumps(dataset),
        meta=json.dumps(meta_info),
        started_at=html.escape(meta_info["started_at"] or "-"),
        profile=html.escape(meta_info["profile"] or "-"),
        duration=meta_info["duration_s"],
        python_version=html.escape(meta_info["python_version"] or "-"),
        os=html.escape(meta_info["os"] or "-"),
        cpu=html.escape(meta_info["cpu"] or "-"),
    )


__all__ = ["render_run_chart"]
