"""SVG Status Badge Generator for Harness Benchmark 2.0."""

from __future__ import annotations

from pathlib import Path


class BadgeGenerator:
    """Generates shields.io-compatible SVGs for repository READMEs and benchmark reports."""

    @staticmethod
    def generate_svg(label: str, value: str, color: str = "#4c1") -> str:
        """Generate a clean SVG status badge."""
        label_len = len(label) * 7 + 10
        val_len = len(value) * 7 + 10
        total_width = label_len + val_len

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_len}" height="20" fill="#555"/>
    <rect x="{label_len}" width="{val_len}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="{label_len * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(label_len - 10) * 10}">{label}</text>
    <text x="{label_len * 5}" y="140" transform="scale(.1)" fill="#fff" textLength="{(label_len - 10) * 10}">{label}</text>
    <text aria-hidden="true" x="{(label_len + val_len / 2) * 10}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(val_len - 10) * 10}">{value}</text>
    <text x="{(label_len + val_len / 2) * 10}" y="140" transform="scale(.1)" fill="#fff" textLength="{(val_len - 10) * 10}">{value}</text>
  </g>
</svg>"""

    @classmethod
    def export_badges(
        cls,
        output_dir: Path,
        mcp_improvement_pct: float = 0.0,
        lsp_error_reduction_pct: float = 0.0,
        full_stack_pass_rate: float = 0.0,
    ) -> dict[str, Path]:
        """Export SVG badges to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        badges = {}

        # 1. MCP Improvement Badge
        mcp_color = "#4c1" if mcp_improvement_pct >= 0 else "#e05d44"
        mcp_svg = cls.generate_svg("MCP-Improvement", f"{mcp_improvement_pct:+.1f}%", mcp_color)
        mcp_path = output_dir / "badge-mcp-improvement.svg"
        mcp_path.write_text(mcp_svg, encoding="utf-8")
        badges["mcp"] = mcp_path

        # 2. LSP Error Reduction Badge
        lsp_color = "#007ec6" if lsp_error_reduction_pct >= 0 else "#e05d44"
        lsp_svg = cls.generate_svg("LSP-Error-Reduction", f"{lsp_error_reduction_pct:.1f}%", lsp_color)
        lsp_path = output_dir / "badge-lsp-reduction.svg"
        lsp_path.write_text(lsp_svg, encoding="utf-8")
        badges["lsp"] = lsp_path

        # 3. Full Stack Pass Rate Badge
        fs_color = "#4c1" if full_stack_pass_rate >= 0.8 else "#dfb317" if full_stack_pass_rate >= 0.5 else "#e05d44"
        fs_svg = cls.generate_svg("Full-Stack-Pass@1", f"{full_stack_pass_rate * 100:.1f}%", fs_color)
        fs_path = output_dir / "badge-full-stack-pass.svg"
        fs_path.write_text(fs_svg, encoding="utf-8")
        badges["full_stack"] = fs_path

        return badges
