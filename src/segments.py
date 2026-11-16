"""Read each firm's reportable business segments and their revenue from its 10-K XBRL data,
then map segments to sectors with transparent rules.

Every 10-K since ~2019 ships a machine-readable XBRL "instance" file next to the HTML
(named like jpm-20251231_htm.xml). In it, segment revenue is a fact such as
us-gaap:Revenues whose context carries the dimension
    us-gaap:StatementBusinessSegmentsAxis = jpm:AssetWealthManagementMember
We read those facts for the fiscal year the 10-K reports.
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
SEGMENT_AXIS = "StatementBusinessSegmentsAxis"
# Extra axes that do not change what the number means: "operating segments" vs eliminations, and
# Prudential-style divisions that just group segments.
ALLOWED_EXTRA_AXES = {"ConsolidationItemsAxis", "DivisionAxis"}
# Axes that split ONE segment into parts (Prudential: Retirement Strategies = Institutional +
# Individual). Parts are summed, but only when the filing gives no total for that segment.
SUB_AXES = {"BusinessAxis", "SubsegmentsAxis"}

# Revenue concepts to try, in order (banks and insurers use different ones)
REVENUE_CONCEPTS = [
    "Revenues",
    "RevenuesNetOfInterestExpense",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",     # Bank of America
]


@dataclass
class SegmentRevenue:
    concept: str = ""
    fiscal_year_end: str = ""
    segments: dict[str, float] = field(default_factory=dict)   # member qname -> revenue
    consolidated: float | None = None

    def share(self, member: str) -> float:
        positives = sum(v for v in self.segments.values() if v > 0)
        base = self.consolidated if self.consolidated and self.consolidated > 0 else positives
        return self.segments[member] / base if base else 0.0


# ------------------------------------------------------------------ XBRL parsing
def _local(qname: str) -> str:
    """'us-gaap:Revenues' or '{ns}Revenues' -> 'Revenues'."""
    return qname.split("}")[-1].split(":")[-1]


def parse_contexts(root: ET.Element) -> dict[str, dict]:
    ctx = {}
    for c in root.iter(f"{XBRLI}context"):
        period = c.find(f"{XBRLI}period")
        start = period.findtext(f"{XBRLI}startDate")
        end = period.findtext(f"{XBRLI}endDate") or period.findtext(f"{XBRLI}instant")
        dims = {}
        for m in c.iter(f"{XBRLDI}explicitMember"):
            dims[_local(m.get("dimension", ""))] = (m.text or "").strip()
        ctx[c.get("id")] = {"start": start, "end": end, "dims": dims}
    return ctx


def segment_revenue(instance_xml: bytes, fiscal_year_end: str,
                    concepts: list[str] | None = None) -> SegmentRevenue | None:
    """Full-year revenue by reportable segment, or None if the firm reports no segments."""
    root = ET.fromstring(instance_xml)
    contexts = parse_contexts(root)
    fy_end = date.fromisoformat(fiscal_year_end)

    def full_year(cid: str) -> bool:
        c = contexts.get(cid)
        if not c or not c["start"] or not c["end"]:
            return False
        s, e = date.fromisoformat(c["start"]), date.fromisoformat(c["end"])
        return e == fy_end and 330 <= (e - s).days <= 400

    for concept in (concepts or REVENUE_CONCEPTS):
        seg, parts, total = {}, {}, None
        for el in root.iter():
            if _local(el.tag) != concept or not el.get("contextRef") or not el.text:
                continue
            cid = el.get("contextRef")
            if not full_year(cid):
                continue
            try:
                value = float(el.text.strip())
            except ValueError:
                continue
            dims = contexts[cid]["dims"]
            if not dims:
                total = value if total is None else total
            elif SEGMENT_AXIS in dims:
                extra = dims.get("ConsolidationItemsAxis", "")
                if extra and "OperatingSegments" not in extra:
                    continue
                other = set(dims) - {SEGMENT_AXIS} - ALLOWED_EXTRA_AXES
                if not other:
                    seg.setdefault(dims[SEGMENT_AXIS], value)
                elif len(other) == 1 and other <= SUB_AXES:
                    parts.setdefault(dims[SEGMENT_AXIS], {})[dims[other.pop()]] = value
        for member, sub in parts.items():
            seg.setdefault(member, sum(sub.values()))
        if len(seg) >= 2:
            return SegmentRevenue(concept, fiscal_year_end, seg, total)
    return None


def member_label(member_qname: str) -> str:
    """'jpm:ConsumerCommunityBankingMember' -> 'Consumer Community Banking'."""
    name = _local(member_qname)
    name = re.sub(r"(Segment)?Member$", "", name)
    name = re.sub(r"^Segment(?=[A-Z])", "", name)          # Principal: SegmentCorporateMember
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return name.strip()


def find_instance_name(index_items: list[str]) -> str | None:
    """Pick the XBRL instance file out of a filing's file list."""
    for n in index_items:
        if n.endswith("_htm.xml"):
            return n
    skip = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml", "FilingSummary.xml")
    xmls = [n for n in index_items if n.endswith(".xml") and not n.endswith(skip)]
    return xmls[0] if len(xmls) == 1 else None


# ------------------------------------------------------------------ segment -> sector rules
@dataclass
class Rule:
    pattern: re.Pattern
    sectors: set[str]
    exclude: bool
    firm_id: str = ""        # blank = applies to every firm
    note: str = ""


def load_rules(path: Path) -> list[Rule]:
    rules = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rules.append(Rule(re.compile(r["pattern"], re.I),
                              {s.strip() for s in r["sectors"].split(";") if s.strip()},
                              r["exclude"].strip().lower() == "y", r.get("firm_id", "").strip(),
                              r.get("note", "")))
    return rules


def map_segment(label: str, firm_id: str, rules: list[Rule]) -> tuple[set[str], str]:
    """(sectors, explanation). Firm-specific rules are checked first and win outright."""
    for r in rules:
        if r.firm_id == firm_id and r.pattern.search(label):
            return (set() if r.exclude else r.sectors), f"firm rule: {r.note or r.pattern.pattern}"
    for r in rules:
        if not r.firm_id and r.exclude and r.pattern.search(label):
            return set(), "not a business line (corporate/other)"
    sectors, used = set(), []
    for r in rules:
        if not r.firm_id and not r.exclude and r.pattern.search(label):
            sectors |= r.sectors
            used.append(r.pattern.pattern)
    return sectors, ("rule: " + " + ".join(used)) if used else "UNMAPPED - add a rule"
