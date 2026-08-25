"""
fcov_forge/ai_extractor/extractor.py
======================================
AI-powered extraction of feature/covergroup/coverpoint/bin definitions
from specification documents (PDF text, register maps, micro-architecture docs).

Uses Anthropic Claude API to intelligently parse documents and produce
structured FCovForge YAML output.

Workflow:
  1. Load and chunk source document
  2. For each chunk, prompt LLM to extract feature coverage information
  3. Merge and deduplicate extracted features
  4. Validate and produce final YAML
"""

from __future__ import annotations
import os
import json
import re
import textwrap
from pathlib import Path
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pdfplumber
        PDF_AVAILABLE = True
        PDF_BACKEND = "pdfplumber"
    except ImportError:
        PDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_document(path: str | Path) -> str:
    """Load text from a document file (PDF, TXT, MD)."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".txt" or suffix == ".md":
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        return _load_pdf(path)

    # Fallback: try reading as text
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"Cannot load document {path}: {e}")


def _load_pdf(path: Path) -> str:
    """Extract text from PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        pass

    try:
        import PyPDF2
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n\n".join(text_parts)
    except ImportError:
        raise ImportError(
            "PDF extraction requires pdfplumber or PyPDF2: "
            "pip install pdfplumber"
        )


def chunk_text(text: str, max_chars: int = 8000, overlap: int = 500) -> list[str]:
    """Split text into overlapping chunks for LLM processing."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # Try to break at paragraph boundary
        break_at = text.rfind("\n\n", start, end)
        if break_at > start + max_chars // 2:
            end = break_at
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# LLM extraction prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert in VLSI/SoC verification and SystemVerilog functional coverage.
Your task is to analyze hardware specification documents and extract information needed to write
functional coverage for device features.

You will output ONLY valid JSON (no markdown, no preamble) in this exact schema:

{
  "features": [
    {
      "name": "snake_case_feature_name",
      "description": "brief description",
      "tags": ["tag1", "tag2"],
      "covergroups": [
        {
          "name": "cg_name",
          "clock": "posedge clk",
          "comment": "what this covergroup measures",
          "coverpoints": [
            {
              "name": "cp_name",
              "variable": "signal_name",
              "comment": "what this measures",
              "bins": [
                {"name": "BIN_NAME", "values": [1, 2, 3]},
                {"name": "BIN_RANGE", "ranges": [[0, 15]]},
                {"name": "BIN_TRANS", "type": "transition",
                 "transitions": [["IDLE", "ACTIVE", "DONE"]]},
                {"name": "BIN_DEFAULT", "type": "default"},
                {"name": "BIN_IGNORE", "type": "ignore", "values": [255]}
              ]
            }
          ]
        }
      ]
    }
  ]
}

Rules:
- Extract REAL features and signals from the document
- Use snake_case for all names
- BIN names should be UPPER_CASE
- Include realistic value ranges based on the spec
- For bus widths, create bins like BIN_8BIT, BIN_16BIT, BIN_32BIT, BIN_64BIT
- For state machines, create transition bins for state sequences
- For registers/fields, create bins for each legal value range
- If no clear features are found, return {"features": []}
- ALWAYS output valid JSON and nothing else
"""

EXTRACTION_PROMPT_TEMPLATE = """Analyze this hardware specification excerpt and extract functional coverage features.

DOCUMENT EXCERPT:
{text}

Extract features related to: {focus}

Remember: Output ONLY valid JSON, no other text."""


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class AIExtractor:
    """
    Extracts FCovForge feature definitions from hardware spec documents
    using Claude LLM.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package required: pip install anthropic")

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model

    def extract_from_text(
        self,
        text: str,
        focus: str = "all device features",
        max_chunks: int = 10,
    ) -> dict:
        """
        Extract features from a text document.
        Returns the merged feature dictionary.
        """
        chunks = chunk_text(text)
        if len(chunks) > max_chunks:
            # Sample evenly across the document
            step = len(chunks) // max_chunks
            chunks = chunks[::step][:max_chunks]

        all_features = {}

        for i, chunk in enumerate(chunks):
            print(f"  [AI Extractor] Processing chunk {i+1}/{len(chunks)}...")
            result = self._extract_chunk(chunk, focus)
            if result and "features" in result:
                for feat in result["features"]:
                    name = feat.get("name", "")
                    if not name:
                        continue
                    if name not in all_features:
                        all_features[name] = feat
                    else:
                        # Merge: add new covergroups
                        existing_cg_names = {
                            cg["name"] for cg in all_features[name].get("covergroups", [])
                        }
                        for cg in feat.get("covergroups", []):
                            if cg["name"] not in existing_cg_names:
                                all_features[name].setdefault("covergroups", []).append(cg)

        return {"features": list(all_features.values())}

    def extract_from_file(
        self,
        path: str | Path,
        focus: str = "all device features",
        output_yaml: Optional[str | Path] = None,
    ) -> dict:
        """Load a document and extract features from it."""
        import yaml

        print(f"[AI Extractor] Loading document: {path}")
        text = load_document(path)
        print(f"[AI Extractor] Document loaded ({len(text):,} chars). Extracting...")

        result = self.extract_from_text(text, focus)

        if output_yaml:
            output_yaml = Path(output_yaml)
            output_yaml.parent.mkdir(parents=True, exist_ok=True)
            with open(output_yaml, "w") as f:
                yaml.dump(result, f, default_flow_style=False, sort_keys=False)
            print(f"[AI Extractor] Wrote {len(result['features'])} features to {output_yaml}")

        return result

    def _extract_chunk(self, text: str, focus: str) -> Optional[dict]:
        """Send one chunk to Claude and parse the JSON response."""
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            text=text[:7500],  # Safety trim
            focus=focus,
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Strip any accidental markdown fences
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            return json.loads(raw)

        except json.JSONDecodeError as e:
            print(f"    ⚠ JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"    ⚠ API error: {e}")
            return None

    def suggest_crosses(self, features: list[dict]) -> list[dict]:
        """
        Use Claude to suggest meaningful feature crosses based on
        the extracted features.
        """
        feature_summary = json.dumps(
            [{"name": f["name"], "description": f.get("description", "")} for f in features],
            indent=2
        )

        prompt = f"""Given these hardware features extracted from a spec:
{feature_summary}

Suggest meaningful feature-level crosses that should be verified.
A feature cross verifies device behavior when multiple features interact simultaneously.

Output ONLY valid JSON:
{{
  "feature_crosses": [
    {{
      "name": "cross_name",
      "targets": ["feature1.covergroup1", "feature2.covergroup2"],
      "comment": "why this cross matters"
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw).get("feature_crosses", [])
        except Exception as e:
            print(f"  ⚠ Cross suggestion failed: {e}")
            return []


# ---------------------------------------------------------------------------
# Register map extractor (for common register-based coverage)
# ---------------------------------------------------------------------------

class RegisterMapExtractor:
    """
    Specialized extractor for register map documents (Excel/CSV/text).
    Generates coverpoints for register field values.
    """

    def extract_from_csv(self, path: str | Path) -> list[dict]:
        """
        Extract register coverage from a CSV register map.
        Expected columns: register_name, field_name, bit_range, access, reset_value, description
        """
        import csv
        features = {}

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                reg_name = row.get("register_name", "").strip()
                field_name = row.get("field_name", "").strip()
                access = row.get("access", "RW").strip().upper()
                description = row.get("description", "").strip()

                if not reg_name or not field_name:
                    continue

                # One feature per register
                feat_name = f"{reg_name.lower()}_feature"
                if feat_name not in features:
                    features[feat_name] = {
                        "name": feat_name,
                        "description": f"Register coverage for {reg_name}",
                        "covergroups": []
                    }

                # Parse bit range e.g. "[7:0]" or "7:0"
                bit_range = row.get("bit_range", "0").strip().strip("[]")
                if ":" in bit_range:
                    hi, lo = bit_range.split(":")
                    width = int(hi) - int(lo) + 1
                    max_val = (1 << width) - 1
                else:
                    width = 1
                    max_val = 1

                # Build bins based on field width and access type
                bins = self._make_field_bins(field_name, width, max_val, access)

                cg_name = f"{reg_name.lower()}_fields_cg"
                # Find or create this CG
                cg = next((c for c in features[feat_name]["covergroups"] if c["name"] == cg_name), None)
                if cg is None:
                    cg = {"name": cg_name, "coverpoints": []}
                    features[feat_name]["covergroups"].append(cg)

                cg["coverpoints"].append({
                    "name": f"{field_name.lower()}_cp",
                    "variable": f"{reg_name.lower()}_{field_name.lower()}",
                    "comment": description,
                    "bins": bins,
                })

        return list(features.values())

    def _make_field_bins(self, field_name: str, width: int, max_val: int, access: str) -> list[dict]:
        bins = []

        if width == 1:
            bins = [
                {"name": "BIN_CLEAR", "values": [0]},
                {"name": "BIN_SET", "values": [1]},
            ]
        elif width <= 4:
            bins = [
                {"name": "BIN_ZERO", "values": [0]},
                {"name": "BIN_ONES", "values": [max_val]},
                {"name": "BIN_MID", "ranges": [[1, max_val - 1]]},
            ]
        elif width <= 8:
            bins = [
                {"name": "BIN_ZERO", "values": [0]},
                {"name": "BIN_LOW", "ranges": [[1, max_val // 4]]},
                {"name": "BIN_MID", "ranges": [[max_val // 4 + 1, 3 * max_val // 4]]},
                {"name": "BIN_HIGH", "ranges": [[3 * max_val // 4 + 1, max_val - 1]]},
                {"name": "BIN_ONES", "values": [max_val]},
            ]
        else:
            bins = [
                {"name": "BIN_ZERO", "values": [0]},
                {"name": "BIN_LOW_QUARTER", "ranges": [[1, max_val // 4]]},
                {"name": "BIN_MID_HALF", "ranges": [[max_val // 4 + 1, 3 * max_val // 4]]},
                {"name": "BIN_HIGH_QUARTER", "ranges": [[3 * max_val // 4 + 1, max_val - 1]]},
                {"name": "BIN_ONES", "values": [max_val]},
            ]

        if access == "RO":
            bins.append({"name": "BIN_IGNORE_WRITE", "type": "ignore", "values": []})

        return bins
