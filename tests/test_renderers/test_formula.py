"""Formula renders LaTeX as MathML at render time, with no JavaScript (#3)."""
from __future__ import annotations

import subprocess
import sys

import pytest

import briefing as bf
from briefing.renderers.formula import latex_to_mathml
from tests.html_helpers import find_one, parse


def _render(latex: str, **kwargs: str) -> str:
    return bf.stringify(bf.Formula(latex, **kwargs))


class TestConversion:
    def test_fraction_becomes_mathml(self):
        soup = parse(_render(r"\frac{a}{b}"))
        math = find_one(soup, ".bf-formula__content math")
        assert math.get("display") == "block"
        frac = find_one(math, "mfrac")
        assert [c.get_text() for c in frac.find_all(recursive=False)] == ["a", "b"]

    @pytest.mark.parametrize(
        ("latex", "element"),
        [
            (r"\sqrt{x^2 + 1}", "msqrt"),
            (r"\sum_{i=1}^{n} x_i", "munderover"),
            (r"\int_0^1 f(x)\,dx", "msubsup"),
            (r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}", "mtable"),
            (r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i", "mover"),
            (r"\mathbb{R}^n", "msup"),
        ],
    )
    def test_common_latex(self, latex: str, element: str):
        mathml = latex_to_mathml(latex)
        assert mathml is not None
        assert find_one(parse(mathml), element) is not None

    def test_no_javascript_or_delimiters(self):
        html = _render(r"\frac{a}{b}")
        assert "\\(" not in html
        assert "MathJax" not in html and "katex" not in html.lower()

    def test_output_is_deterministic(self):
        assert latex_to_mathml(r"\frac{a}{b} + \alpha") == latex_to_mathml(r"\frac{a}{b} + \alpha")

    def test_caption_still_rendered(self):
        soup = parse(_render("x^2", caption="Square"))
        assert find_one(soup, ".bf-formula__caption").get_text() == "Square"


class TestFallback:
    """LaTeX that can't be converted safely shows its source and a visible warning."""

    @pytest.mark.parametrize(
        "latex",
        [
            r"\frac{a}{",  # unbalanced
            r"\notacommand{x}",  # unknown command
            r"\text{<script>bf_xss()</script>}",  # markup the converter would pass through
            r"\href{javascript:bf_xss()}{x}",  # links are not allowed in formulas
            r"\color{rgb(1,2,3)}{x}",  # attribute values are plain tokens only
        ],
    )
    def test_shows_source_and_warning(self, latex: str):
        with pytest.warns(UserWarning, match="Formula"):
            html = _render(latex)
        soup = parse(html)
        assert soup.select(".bf-formula math") == []
        assert soup.select(".bf-formula script") == []
        assert find_one(soup, ".bf-formula__source").get_text() == latex
        assert "LaTeX source" in find_one(soup, ".bf-formula__error").get_text()

    def test_latex_to_mathml_returns_none(self):
        assert latex_to_mathml(r"\frac{a}{") is None


def test_import_briefing_does_not_import_latex2mathml():
    code = "import sys, briefing; print('latex2mathml' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
