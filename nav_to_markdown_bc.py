#!/usr/bin/env python3
"""
Dynamics NAV Object Parser & Migration Intelligence Tool
Supports: NAV 2009, NAV 2013-2015, Business Central (classic export)

Features:
  - Parses .txt and .fob export files
  - NAV 2009 compatibility (OEM encoding, OemCode/OemText, SECTIONS, REQUESTFORM)
  - Full variable & parameter extraction
  - Report dataset structure documentation
  - Per-object migration intelligence: algorithm summary, deprecated patterns,
    dependency graph, effort estimation, role-specific comments

Usage:
    python nav_to_markdown.py --txt objects.txt --output docs.md
    python nav_to_markdown.py --fob objects.fob --output docs.md
    python nav_to_markdown.py --dir ./exports/ --nav-version 2009 --output docs.md
    python nav_to_markdown.py --txt objects.txt --analyze --output docs.md
"""

import re
import sys
import os
import struct
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

OBJECT_TYPES = {
    1: "Table", 2: "Form", 3: "Report", 4: "Dataport",
    5: "Codeunit", 6: "XMLport", 7: "MenuSuite", 8: "Page", 9: "Query",
}
OBJECT_TYPE_NAMES = {v: k for k, v in OBJECT_TYPES.items()}

SECTION_KEYWORDS = {
    "OBJECT", "OBJECT-PROPERTIES", "PROPERTIES",
    "FIELDS", "KEYS", "FIELDGROUPS",
    "CODE", "TRIGGERS",
    "CONTROLS", "ELEMENTS",
    "REQUESTPAGE", "REQUESTFORM",   # NAV 2009: REQUESTFORM
    "LABELS", "DATASET",
    "SECTIONS",                     # NAV 2009: classic report sections
    "QUERYCOLUMNS",
}

# Deprecated C/AL calls that must be replaced in BC
DEPRECATED_PATTERNS = [
    (r'\bFORM\s*\.\s*RUN\b',          'FORM.RUN',          'Replace with PAGE.RUN in AL'),
    (r'\bFORM\s*\.\s*OPEN\b',         'FORM.OPEN',         'Replace with PAGE.RUN in AL'),
    (r'\bDATAPORT\s*\.\s*RUN\b',      'DATAPORT.RUN',      'Remove — Dataports deleted in BC; use XMLport or Data Exchange'),
    (r'\bREPORT\s*\.\s*RUNMODAL\b',   'REPORT.RUNMODAL',   'Use REPORT.RUN or Report.RunModal() in AL'),
    (r'\bCREATEFORM\b',               'CREATEFORM',        'Removed in BC — use Page.Run()'),
    (r'\bSKIPLINE\b',                 'SKIPLINE',          'Removed in BC — restructure loop'),
    (r'\bFUNCTIONS\b',                'FUNCTIONS keyword', 'Replaced by procedures in AL'),
    (r'\bOEMCODE\b',                  'OemCode type',      'Rename to Code in AL'),
    (r'\bOEMTEXT\b',                  'OemText type',      'Rename to Text in AL'),
    (r'\bLOCKTABLE\b',                'LOCKTABLE',         'Review: ensure lock is intentional, use TableLock in AL'),
    (r'\bCOMMIT\b',                   'COMMIT',            'Review: COMMIT inside loops/logic is risky — isolate in AL'),
    (r'\bERROR\s*\(',                 'ERROR()',           'Replace with Error() in AL'),
    (r'\bMESSAGE\s*\(',               'MESSAGE()',         'Replace with Message() in AL'),
    (r'\bGLOBALLANGUAGE\b',          'GLOBALLANGUAGE',    'Replaced by Language management in AL'),
    (r'CALCFIELDS.*?IN\s+LOOP',       'CALCFIELDS in loop','Performance: CALCFIELDS inside loops — move outside or use SetAutoCalcFields'),
]

# Patterns that detect what tables/objects are accessed
TABLE_ACCESS_RE = re.compile(
    r'(?:Record\s+|"?)([A-Z][A-Za-z0-9\s"]+?)(?:"\s*)?\.(FIND|GET|INSERT|MODIFY|DELETE|MODIFYALL|DELETEALL)',
    re.IGNORECASE
)
CODEUNIT_CALL_RE = re.compile(r'CODEUNIT\s*\.\s*RUN\s*\(\s*CODEUNIT\s*::\s*"?([^")]+)"?', re.IGNORECASE)
PAGE_CALL_RE     = re.compile(r'PAGE\s*\.\s*RUN\s*\(\s*PAGE\s*::\s*"?([^")]+)"?', re.IGNORECASE)
REPORT_CALL_RE   = re.compile(r'REPORT\s*\.\s*RUN\s*\(\s*REPORT\s*::\s*"?([^")]+)"?', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Encoding detection (NAV 2009 OEM support)
# ─────────────────────────────────────────────────────────────────────────────

def detect_encoding(filepath: str) -> str:
    """Try chardet first, then fall back to OEM codepage chain."""
    try:
        import chardet
        with open(filepath, 'rb') as f:
            raw = f.read(65536)
        result = chardet.detect(raw)
        if result and result.get('confidence', 0) > 0.75:
            return result['encoding']
    except ImportError:
        pass

    # Manual fallback chain
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'cp850', 'cp437', 'latin-1'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return 'latin-1'


# ─────────────────────────────────────────────────────────────────────────────
# Static code analyser
# ─────────────────────────────────────────────────────────────────────────────

class CodeAnalyser:
    """
    Performs static analysis on C/AL code blocks.
    Extracts: variables, parameters, deprecated calls, dependencies,
    report dataset structure, and generates plain-language algorithm summaries.
    """

    # VAR block: Name : [array of] Type [optional_qualifier];
    VAR_LINE_RE = re.compile(
        r'^\s*([A-Za-z_@][A-Za-z0-9_@\s]*?)\s*:\s*(Array\s*\[[\d,]+\]\s*OF\s*)?'
        r'(Record|Codeunit|Page|Report|Query|XMLport|File|Dialog|Text|Code|Integer|Decimal|'
        r'Boolean|Date|Time|DateTime|BigInteger|Guid|Option|Enum|List|Dictionary|'
        r'RecordRef|FieldRef|KeyRef|FilterPageBuilder|Notification|OutStream|InStream|'
        r'TestPage|XmlPort|MediaSet|Media|Blob|DateFormula|Duration|OemText|OemCode)'
        r'[^;]*;',
        re.IGNORECASE
    )

    PARAM_RE = re.compile(
        r'(VAR\s+)?([A-Za-z_@][A-Za-z0-9_@]*)\s*:\s*'
        r'(Record\s+"?[^;,)]+?"?|Codeunit\s+\d+|'
        r'Text\s*(?:\[\d+\])?|Code\s*(?:\[\d+\])?|Integer|Decimal|Boolean|'
        r'Date|Time|DateTime|Option|Enum\s+\S+|[A-Za-z][A-Za-z0-9]*)',
        re.IGNORECASE
    )

    RETURN_RE = re.compile(
        r'\)\s*:\s*(Text\s*(?:\[\d+\])?|Code\s*(?:\[\d+\])?|Integer|Decimal|Boolean|'
        r'Date|Time|DateTime|Option|Record\s+\S+|[A-Za-z][A-Za-z0-9]*)\s*$',
        re.IGNORECASE
    )

    # Report DataItem
    DATAITEM_RE = re.compile(
        r'\{\s*(\d+)\s*;\s*\d+\s*;DataItem;\s*([^;]+)\s*;.*?DataItemTable\s*=\s*Table(\d+)',
        re.IGNORECASE
    )
    COLUMN_RE = re.compile(
        r'\{\s*(\d+)\s*;\s*\d+\s*;Column\s*;\s*([^;]+)\s*;.*?SourceExpr\s*=\s*([^;}]+)',
        re.IGNORECASE
    )

    def analyse_object(self, obj: dict) -> dict:
        """Return an analysis dict for one NAV object."""
        result = {
            'global_vars': [],
            'deprecated_hits': [],
            'dependencies': [],
            'effort_hours': 0,
            'migration_risk': 'Low',
            'procedures_detail': [],
            'report_dataset': [],
            'algorithm_summary': '',
            'comments': {'architect': '', 'developer': '', 'pm': ''},
        }

        # Collect all code text
        all_code = '\n'.join(obj.get('raw_code', []))

        result['global_vars']     = self._extract_vars(all_code, scope='global')
        result['deprecated_hits'] = self._find_deprecated(all_code)
        result['dependencies']    = self._find_dependencies(all_code)
        result['procedures_detail'] = self._analyse_procedures(obj)

        if obj['type'] == 'Report':
            result['report_dataset'] = self._extract_report_dataset(obj)

        result['effort_hours']  = self._estimate_effort(obj, result)
        result['migration_risk'] = self._assess_risk(obj, result)
        result['algorithm_summary'] = self._summarise_algorithm(obj, result, all_code)
        result['comments'] = self._generate_role_comments(obj, result)

        return result

    # ── Variable extraction ───────────────────────────────────────────────────

    def _extract_vars(self, code: str, scope: str = 'global') -> list:
        vars_ = []
        in_var = False
        for line in code.splitlines():
            stripped = line.strip()
            if re.match(r'^VAR\s*$', stripped, re.IGNORECASE):
                in_var = True
                continue
            if in_var:
                if re.match(r'^(BEGIN|PROCEDURE|LOCAL|ON\w)', stripped, re.IGNORECASE):
                    in_var = False
                    continue
                m = re.match(
                    r'^\s*([A-Za-z_@][A-Za-z0-9_@\s]*?)\s*:\s*([^;]+?)\s*;',
                    stripped
                )
                if m:
                    name = m.group(1).strip()
                    vtype = m.group(2).strip()
                    vars_.append({
                        'name': name,
                        'type': vtype,
                        'scope': scope,
                        'description': self._infer_var_description(name, vtype),
                    })
        return vars_

    def _infer_var_description(self, name: str, vtype: str) -> str:
        if 'Record' in vtype:
            table = re.sub(r'Record\s*', '', vtype, flags=re.IGNORECASE).strip().strip('"')
            return f'Record buffer for table "{table}"'
        if 'Codeunit' in vtype:
            return f'Reference to codeunit {vtype}'
        if name.lower() in ('i', 'j', 'k', 'counter', 'cnt'):
            return 'Loop counter'
        if 'text' in vtype.lower() or 'code' in vtype.lower():
            return 'String variable'
        if 'boolean' in vtype.lower():
            return 'Flag / boolean switch'
        if 'decimal' in vtype.lower() or 'integer' in vtype.lower():
            return 'Numeric value'
        return ''

    # ── Parameters ───────────────────────────────────────────────────────────

    def _parse_procedure_signature(self, header_line: str) -> tuple:
        """Returns (params: list, return_type: str)."""
        params = []
        return_type = ''

        m_paren = re.search(r'\(([^)]*)\)', header_line)
        if m_paren:
            params_str = m_paren.group(1)
            for token in re.split(r';', params_str):
                token = token.strip()
                if not token:
                    continue
                is_var = token.upper().startswith('VAR ')
                token_clean = re.sub(r'^VAR\s+', '', token, flags=re.IGNORECASE)
                pm = re.match(r'([A-Za-z_@][A-Za-z0-9_@]*)\s*:\s*(.+)', token_clean)
                if pm:
                    params.append({
                        'name': pm.group(1).strip(),
                        'type': pm.group(2).strip(),
                        'direction': 'in/out (VAR)' if is_var else 'in',
                    })

        m_ret = self.RETURN_RE.search(header_line)
        if m_ret:
            return_type = m_ret.group(1).strip()

        return params, return_type

    def _analyse_procedures(self, obj: dict) -> list:
        details = []
        for block_list, kind in [(obj.get('triggers', []), 'trigger'),
                                  (obj.get('procedures', []), 'procedure')]:
            for block in block_list:
                name = block['name']
                body = block['body']
                first_line = body.splitlines()[0] if body.splitlines() else ''
                params, return_type = self._parse_procedure_signature(first_line)

                local_vars = self._extract_vars(body, scope='local')
                deprecated = self._find_deprecated(body)
                deps = self._find_dependencies(body)
                lines_of_code = sum(1 for l in body.splitlines()
                                    if l.strip() and not l.strip().startswith('//'))

                details.append({
                    'name': name,
                    'kind': kind,
                    'params': params,
                    'return_type': return_type,
                    'local_vars': local_vars,
                    'deprecated': deprecated,
                    'dependencies': deps,
                    'loc': lines_of_code,
                    'body': body,
                    'summary': self._summarise_proc(name, body, params, return_type),
                })
        return details

    # ── Deprecated pattern detection ─────────────────────────────────────────

    def _find_deprecated(self, code: str) -> list:
        hits = []
        for pattern, label, advice in DEPRECATED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                hits.append({'pattern': label, 'advice': advice})
        return hits

    # ── Dependency detection ──────────────────────────────────────────────────

    def _find_dependencies(self, code: str) -> list:
        deps = []
        for m in TABLE_ACCESS_RE.finditer(code):
            deps.append({'kind': 'Table', 'name': m.group(1).strip(), 'op': m.group(2)})
        for m in CODEUNIT_CALL_RE.finditer(code):
            deps.append({'kind': 'Codeunit', 'name': m.group(1).strip(), 'op': 'RUN'})
        for m in PAGE_CALL_RE.finditer(code):
            deps.append({'kind': 'Page', 'name': m.group(1).strip(), 'op': 'RUN'})
        for m in REPORT_CALL_RE.finditer(code):
            deps.append({'kind': 'Report', 'name': m.group(1).strip(), 'op': 'RUN'})
        # Deduplicate
        seen = set()
        unique = []
        for d in deps:
            k = (d['kind'], d['name'])
            if k not in seen:
                seen.add(k)
                unique.append(d)
        return unique

    # ── Report dataset ────────────────────────────────────────────────────────

    def _extract_report_dataset(self, obj: dict) -> list:
        dataset = []
        all_text = '\n'.join(obj.get('raw_code', []))

        # Parse DATASET section lines
        for line in all_text.splitlines():
            # DataItem
            m = self.DATAITEM_RE.search(line)
            if m:
                dataset.append({
                    'kind': 'DataItem',
                    'id': m.group(1),
                    'name': m.group(2).strip(),
                    'table_id': m.group(3),
                })
                continue
            # Column
            mc = self.COLUMN_RE.search(line)
            if mc:
                dataset.append({
                    'kind': 'Column',
                    'id': mc.group(1),
                    'name': mc.group(2).strip(),
                    'source': mc.group(3).strip(),
                })

        # Also try to find DataItems from properties
        props = obj.get('properties', {})
        if not dataset and 'SourceTable' in props:
            dataset.append({
                'kind': 'DataItem',
                'id': '1',
                'name': obj['name'],
                'table_id': props['SourceTable'].replace('Table', '').strip(),
            })

        return dataset

    # ── Effort estimation ─────────────────────────────────────────────────────

    def _estimate_effort(self, obj: dict, analysis: dict) -> int:
        hours = 0
        obj_type = obj['type']

        # Base by type
        base = {'Table': 2, 'Page': 3, 'Codeunit': 4, 'Report': 6,
                'Form': 8, 'Dataport': 10, 'XMLport': 3, 'Query': 2, 'MenuSuite': 4}
        hours += base.get(obj_type, 3)

        # +1 per 50 lines of code (LOC across all procs)
        total_loc = sum(p['loc'] for p in analysis.get('procedures_detail', []))
        hours += total_loc // 50

        # +2 per deprecated call
        hours += len(analysis.get('deprecated_hits', [])) * 2

        # +1 per dependency on Form/Dataport
        for d in analysis.get('dependencies', []):
            if d['kind'] in ('Form', 'Dataport'):
                hours += 2

        # Fields in tables
        hours += len(obj.get('fields', [])) // 20

        return max(1, hours)

    def _assess_risk(self, obj: dict, analysis: dict) -> str:
        dep_count = len(analysis.get('deprecated_hits', []))
        effort    = analysis.get('effort_hours', 0)
        obj_type  = obj['type']

        if obj_type in ('Form', 'Dataport') or dep_count >= 3 or effort >= 16:
            return 'High'
        if dep_count >= 1 or effort >= 8 or obj_type in ('Report', 'Codeunit'):
            return 'Medium'
        return 'Low'

    # ── Plain-language summaries ──────────────────────────────────────────────

    def _summarise_proc(self, name: str, body: str, params: list, return_type: str) -> str:
        """Generate a brief plain-language summary of a single procedure."""
        lines = [l.strip() for l in body.splitlines()
                 if l.strip() and not l.strip().startswith('//')]

        actions = []

        # What tables are read/written?
        tables_read = set(re.findall(r'(\w[\w\s"]+?)\s*\.(FIND|GET|FINDFIRST|FINDSET)', body, re.IGNORECASE))
        tables_write = set(re.findall(r'(\w[\w\s"]+?)\s*\.(INSERT|MODIFY|DELETE|MODIFYALL|DELETEALL)', body, re.IGNORECASE))

        if tables_read:
            names = ', '.join(f'"{t[0].strip()}"' for t in list(tables_read)[:3])
            actions.append(f'reads from {names}')
        if tables_write:
            names = ', '.join(f'"{t[0].strip()}"' for t in list(tables_write)[:3])
            actions.append(f'writes to {names}')

        if re.search(r'\bCOMMIT\b', body, re.IGNORECASE):
            actions.append('commits a transaction')
        if re.search(r'\bERROR\b', body, re.IGNORECASE):
            actions.append('raises errors on validation failure')
        if re.search(r'\bREPEAT\b|\bWHILE\b', body, re.IGNORECASE):
            actions.append('iterates over a dataset')
        if re.search(r'\bSENDMAIL\b|\bSMTP\b', body, re.IGNORECASE):
            actions.append('sends email')
        if re.search(r'\bFILE\b', body, re.IGNORECASE):
            actions.append('performs file I/O')

        if not actions:
            return f'Procedure `{name}` — {len(lines)} lines of C/AL logic.'

        direction = ''
        if params:
            in_params  = [p for p in params if 'in/out' not in p['direction']]
            out_params = [p for p in params if 'in/out' in p['direction']]
            if in_params:
                direction += f'Takes {", ".join(p["name"] for p in in_params[:3])} as input. '
            if out_params:
                direction += f'Returns modified {", ".join(p["name"] for p in out_params[:2])} by reference. '
        if return_type:
            direction += f'Returns `{return_type}`. '

        return f'{direction}This procedure {"; ".join(actions)}.'

    def _summarise_algorithm(self, obj: dict, analysis: dict, all_code: str) -> str:
        """Generate a paragraph describing what this object does overall."""
        name = obj['name']
        obj_type = obj['type']
        procs = analysis.get('procedures_detail', [])
        deps = analysis.get('dependencies', [])

        parts = []

        if obj_type == 'Table':
            fields = obj.get('fields', [])
            key_fields = [f['name'] for f in fields if f['no'] <= 10]
            parts.append(
                f'Table **{name}** stores data with {len(fields)} fields. '
                f'Primary key fields include: {", ".join(f"`{f}`" for f in key_fields[:5])}. '
            )
            calc_fields = [f for f in fields if f.get('properties', {}).get('FieldClass', '').lower() == 'flowfield']
            if calc_fields:
                parts.append(f'Contains {len(calc_fields)} FlowField(s) that aggregate data from related tables. ')
            triggers = [p for p in procs if p['kind'] == 'trigger']
            if triggers:
                tnames = ', '.join(f'`{t["name"]}`' for t in triggers)
                parts.append(f'Business logic is enforced through triggers: {tnames}. ')

        elif obj_type == 'Codeunit':
            table_names = list({d['name'] for d in deps if d['kind'] == 'Table'})[:5]
            cu_names    = list({d['name'] for d in deps if d['kind'] == 'Codeunit'})[:3]
            parts.append(
                f'Codeunit **{name}** contains {len(procs)} procedures/triggers '
                f'implementing business logic. '
            )
            if table_names:
                parts.append(f'Operates on tables: {", ".join(f"`{t}`" for t in table_names)}. ')
            if cu_names:
                parts.append(f'Calls codeunits: {", ".join(f"`{c}`" for c in cu_names)}. ')
            has_post = any('post' in p['name'].lower() for p in procs)
            if has_post:
                parts.append('Appears to implement a **posting routine** — critical business process. ')

        elif obj_type == 'Report':
            dataset = analysis.get('report_dataset', [])
            dataitems = [d for d in dataset if d['kind'] == 'DataItem']
            columns   = [d for d in dataset if d['kind'] == 'Column']
            parts.append(f'Report **{name}** ')
            if dataitems:
                tables = ', '.join(f'`{d["name"]}`' for d in dataitems[:4])
                parts.append(f'reads data from: {tables}. ')
            if columns:
                parts.append(f'Outputs {len(columns)} columns. ')
            props = obj.get('properties', {})
            if 'PreviewMode' in props:
                parts.append(f'Preview mode: `{props["PreviewMode"]}`. ')

        elif obj_type in ('Page', 'Form'):
            props = obj.get('properties', {})
            src = props.get('SourceTable', '')
            ptype = props.get('PageType', '')
            parts.append(f'{obj_type} **{name}** ')
            if src:
                parts.append(f'is bound to table `{src}`. ')
            if ptype:
                parts.append(f'Page type: `{ptype}`. ')
            controls = obj.get('controls', [])
            if controls:
                parts.append(f'Contains {len(controls)} UI controls. ')

        elif obj_type == 'XMLport':
            props = obj.get('properties', {})
            direction = props.get('Direction', 'Import/Export')
            parts.append(f'XMLport **{name}** handles `{direction}` of XML data. ')

        if not parts:
            parts.append(f'{obj_type} **{name}** — see code sections below for details. ')

        deprecated = analysis.get('deprecated_hits', [])
        if deprecated:
            d_labels = ', '.join(f'`{d["pattern"]}`' for d in deprecated[:3])
            parts.append(f'\n\n> ⚠️ Contains deprecated calls: {d_labels} — **requires refactoring before migration**.')

        return ''.join(parts)

    def _generate_role_comments(self, obj: dict, analysis: dict) -> dict:
        """Generate migration comments tailored to three roles."""
        name     = obj['name']
        obj_type = obj['type']
        risk     = analysis.get('migration_risk', 'Medium')
        effort   = analysis.get('effort_hours', 0)
        deprecated = analysis.get('deprecated_hits', [])
        deps     = analysis.get('dependencies', [])
        procs    = analysis.get('procedures_detail', [])

        # ── Architect ──────────────────────────────────────────────────────────
        arch_parts = []
        if obj_type == 'Table':
            arch_parts.append(f'Review field structure for BLOB fields (must be converted to Media/MediaSet in BC). ')
            calc = [f for f in obj.get('fields', []) if f.get('properties', {}).get('FieldClass') == 'FlowField']
            if calc:
                arch_parts.append(f'{len(calc)} FlowFields — verify CalcFormula compatibility with AL. ')
            keys = obj.get('keys', [])
            if len(keys) > 3:
                arch_parts.append(f'{len(keys)} keys defined — evaluate if all are still needed (impact on performance). ')
        if obj_type in ('Form', 'Dataport'):
            arch_parts.append(f'**No direct BC equivalent.** Must be redesigned from scratch. Plan discovery session with business to define new UX/workflow. ')
        if obj_type == 'Codeunit':
            has_commit = any(d['pattern'] == 'COMMIT' for d in deprecated)
            if has_commit:
                arch_parts.append('Contains `COMMIT` — review transaction boundaries; BC is more strict about COMMIT inside event subscribers. ')
        dep_forms = [d for d in deps if d['kind'] == 'Form']
        if dep_forms:
            arch_parts.append(f'Calls {len(dep_forms)} Form object(s) — these targets must be migrated first or stubs provided. ')
        if not arch_parts:
            arch_parts.append(f'Standard migration path. Verify AL event model covers all triggers used here. ')

        # ── Developer ─────────────────────────────────────────────────────────
        dev_parts = []
        if deprecated:
            for d in deprecated:
                dev_parts.append(f'- `{d["pattern"]}`: {d["advice"]}')
        oem_fields = [f for f in obj.get('fields', []) if 'oem' in f.get('type', '').lower()]
        if oem_fields:
            dev_parts.append(f'- {len(oem_fields)} field(s) with OemCode/OemText type — rename to Code/Text in AL table extension.')
        if obj_type == 'Report':
            dev_parts.append('- Classic report layout must be rebuilt as RDLC (.rdlc) or Word layout; dataset structure documented below.')
        total_loc = sum(p['loc'] for p in procs)
        if total_loc > 200:
            dev_parts.append(f'- {total_loc} lines of C/AL — consider refactoring into smaller procedures during migration.')
        if not dev_parts:
            dev_parts.append('- No critical deprecated patterns detected. Standard AL rewrite applies.')

        # ── Project Manager ────────────────────────────────────────────────────
        risk_icon = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}.get(risk, '🟡')
        pm_parts = [
            f'**Migration risk:** {risk_icon} {risk}  ',
            f'**Estimated effort:** ~{effort}h  ',
        ]
        if obj_type in ('Form', 'Dataport'):
            pm_parts.append('**Action required:** Schedule redesign workshop with business stakeholders before sprint.  ')
        if deprecated:
            pm_parts.append(f'**Blockers:** {len(deprecated)} deprecated pattern(s) must be resolved by developer before UAT.  ')
        dep_objects = list({d["name"] for d in deps if d["kind"] in ("Form", "Codeunit", "Report")})[:4]
        if dep_objects:
            pm_parts.append(f'**Dependencies:** Relies on {", ".join(dep_objects)} — coordinate migration order.  ')

        return {
            'architect': ' '.join(arch_parts),
            'developer': '\n'.join(dev_parts),
            'pm':        '\n'.join(pm_parts),
        }


# ─────────────────────────────────────────────────────────────────────────────
# .TXT Parser
# ─────────────────────────────────────────────────────────────────────────────

class NavTxtParser:
    """Parses NAV .txt object exports. Supports NAV 2009 and 2013-2015."""

    OBJECT_HEADER_RE = re.compile(
        r'^OBJECT\s+(Table|Form|Report|Dataport|Codeunit|XMLport|MenuSuite|Page|Query)\s+(\d+)\s+(.*?)\s*$',
        re.IGNORECASE
    )
    PROPERTY_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_\-]*)\s*=\s*(.*?)\s*;?\s*$')

    def __init__(self, nav_version: str = 'auto'):
        self.nav_version = nav_version  # '2009' | '2013' | '2015' | 'auto'

    def parse_file(self, filepath: str, encoding: str = None) -> list:
        enc = encoding or detect_encoding(filepath)
        with open(filepath, 'r', encoding=enc, errors='replace') as f:
            content = f.read()
        print(f'  Encoding detected: {enc}')
        return self.parse_text(content)

    def parse_text(self, content: str) -> list:
        objects = []
        raw_blocks = re.split(r'(?=^OBJECT\s)', content, flags=re.MULTILINE)
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue
            obj = self._parse_object_block(block)
            if obj:
                objects.append(obj)
        return objects

    def _parse_object_block(self, block: str) -> dict | None:
        lines = block.splitlines()
        if not lines:
            return None
        m = self.OBJECT_HEADER_RE.match(lines[0])
        if not m:
            return None

        obj = {
            'type': m.group(1).capitalize(),
            'id': int(m.group(2)),
            'name': m.group(3).strip(),
            'modified_date': '',
            'version_list': '',
            'properties': {},
            'fields': [],
            'keys': [],
            'triggers': [],
            'procedures': [],
            'controls': [],
            'report_sections': [],   # NAV 2009 classic sections
            'request_form': [],      # NAV 2009 request form
            'raw_code': [],
        }

        self._parse_sections(lines[1:], obj)
        self._normalise_field_types(obj)
        return obj

    def _parse_sections(self, lines: list, obj: dict):
        section = None
        buffer  = []
        depth   = 0

        for line in lines:
            stripped = line.strip()
            upper    = stripped.upper().rstrip(':')

            if upper in SECTION_KEYWORDS and depth <= 1:
                self._flush_section(section, buffer, obj)
                section = upper
                buffer  = []
                depth   = 0
                continue

            depth += stripped.count('{') - stripped.count('}')
            if depth < 0:
                depth = 0
            if section:
                buffer.append(line)

        self._flush_section(section, buffer, obj)

    def _flush_section(self, section: str, buffer: list, obj: dict):
        if not section or not buffer:
            return
        if section == 'OBJECT-PROPERTIES':
            meta = self._parse_properties(buffer)
            obj['modified_date'] = meta.get('Date', '')
            obj['version_list']  = meta.get('Version List', meta.get('VersionList', ''))
        elif section == 'PROPERTIES':
            obj['properties'] = self._parse_properties(buffer)
        elif section == 'FIELDS':
            obj['fields'] = self._parse_fields(buffer)
        elif section == 'KEYS':
            obj['keys'] = self._parse_keys(buffer)
        elif section in ('CODE', 'TRIGGERS'):
            triggers, procs, raw = self._parse_code(buffer)
            obj['triggers'].extend(triggers)
            obj['procedures'].extend(procs)
            obj['raw_code'].extend(raw)
        elif section == 'CONTROLS':
            obj['controls'] = self._parse_controls(buffer)
        elif section == 'SECTIONS':
            obj['report_sections'] = self._parse_report_sections(buffer)
        elif section == 'REQUESTFORM':
            obj['request_form'] = self._parse_controls(buffer)  # same structure

    def _parse_properties(self, lines: list) -> dict:
        props = {}
        for line in lines:
            m = self.PROPERTY_RE.match(line)
            if m:
                props[m.group(1)] = m.group(2).strip().rstrip(';')
        return props

    def _parse_fields(self, lines: list) -> list:
        fields = []
        text = ' '.join(l.strip() for l in lines)
        for m in re.finditer(
            r'\{\s*(\d+)\s*;\s*([^;]*?)\s*;\s*([^;{]*?)\s*;\s*([^;{]*?)(?:\s*;[^}]*)?\s*\}',
            text
        ):
            no    = int(m.group(1))
            name  = m.group(3).strip()
            ftype = m.group(4).strip()
            if name:
                fields.append({
                    'no':         no,
                    'name':       name,
                    'type':       ftype,
                    'type_raw':   ftype,  # keep original for NAV 2009 OemCode detection
                    'properties': self._extract_field_props(m.group(0)),
                })
        return fields

    def _extract_field_props(self, field_text: str) -> dict:
        props = {}
        for key in ('TableRelation', 'CalcFormula', 'FieldClass', 'Editable',
                    'BlankZero', 'CaptionML', 'Description', 'InitValue'):
            m = re.search(rf'{key}\s*=\s*([^;}}]+)', field_text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().rstrip(';').strip()
                if val:
                    props[key] = val
        return props

    def _normalise_field_types(self, obj: dict):
        """NAV 2009: rename OemCode/OemText → Code/Text, flag the change."""
        for f in obj.get('fields', []):
            raw = f.get('type_raw', '')
            if re.search(r'\bOem(Code|Text)\b', raw, re.IGNORECASE):
                f['type'] = re.sub(r'\bOem(Code|Text)\b', r'\1', raw, flags=re.IGNORECASE)
                f['legacy_type'] = raw  # keep original for documentation

    def _parse_keys(self, lines: list) -> list:
        keys = []
        for line in lines:
            m = re.match(r'\{\s*([^;]*?)\s*;\s*([^;]*?)(?:\s*;\s*(.*?))?\s*\}', line.strip())
            if m:
                keys.append({
                    'enabled':    m.group(1).strip(),
                    'fields':     m.group(2).strip(),
                    'sum_fields': m.group(3).strip() if m.group(3) else '',
                })
        return keys

    def _parse_code(self, lines: list) -> tuple:
        triggers   = []
        procedures = []
        raw_lines  = list(lines)

        current_name  = None
        current_type  = None
        current_body  = []
        in_block      = False
        begin_depth   = 0

        for line in lines:
            stripped = line.strip()
            t_match  = re.match(r'^(ON\w+)\s*\(',      stripped, re.IGNORECASE)
            p_match  = re.match(r'^(LOCAL\s+)?PROCEDURE\s+([A-Za-z_@][A-Za-z0-9_@]*)\s*[\(@]',
                                stripped, re.IGNORECASE)
            if t_match or p_match:
                if current_name and current_body:
                    entry = {'name': current_name, 'body': '\n'.join(current_body)}
                    (triggers if current_type == 'trigger' else procedures).append(entry)
                current_name  = t_match.group(1) if t_match else p_match.group(2)
                current_type  = 'trigger' if t_match else 'procedure'
                current_body  = [line]
                begin_depth   = 0
                in_block      = True
            elif in_block:
                current_body.append(line)
                begin_depth += stripped.upper().count('BEGIN') - stripped.upper().count('END')
                if re.match(r'^END\s*[;.]?\s*$', stripped, re.IGNORECASE) and begin_depth <= 0:
                    in_block = False

        if current_name and current_body:
            entry = {'name': current_name, 'body': '\n'.join(current_body)}
            (triggers if current_type == 'trigger' else procedures).append(entry)

        return triggers, procedures, raw_lines

    def _parse_controls(self, lines: list) -> list:
        controls = []
        for line in lines:
            m = re.match(r'\{\s*(\d+)\s*;\s*(\d+)\s*;\s*([^;]*?)\s*;', line.strip())
            if m:
                controls.append({'id': m.group(1), 'parent': m.group(2), 'type': m.group(3).strip()})
        return controls

    def _parse_report_sections(self, lines: list) -> list:
        """NAV 2009: parse classic report SECTIONS (Header, Body, Footer groups)."""
        sections = []
        for line in lines:
            m = re.match(r'\{\s*(\d+)\s*;\s*\d+\s*;(\w+Section)\s*;([^;]*)', line.strip())
            if m:
                sections.append({'id': m.group(1), 'kind': m.group(2), 'name': m.group(3).strip()})
        return sections


# ─────────────────────────────────────────────────────────────────────────────
# .FOB Parser
# ─────────────────────────────────────────────────────────────────────────────

class NavFobParser:
    def parse_file(self, filepath: str) -> list:
        with open(filepath, 'rb') as f:
            data = f.read()
        return self._extract_objects(data)

    def _extract_objects(self, data: bytes) -> list:
        import zlib
        objects    = []
        txt_parser = NavTxtParser()
        size       = len(data)
        markers    = [b'\x78\x9c', b'\x78\xda', b'\x78\x01', b'\x78\x5e']

        positions = sorted({
            idx for marker in markers
            for idx in (lambda d=data, m=marker: [
                i for i in range(len(d)) if d[i:i+len(m)] == m
            ])()
        })

        for pos in positions:
            for end in range(min(pos + 100, size), size, 1024):
                try:
                    decompressed = zlib.decompress(data[pos:end])
                    text = decompressed.decode('utf-8', errors='replace')
                    if 'OBJECT' in text and any(t in text for t in OBJECT_TYPES.values()):
                        objects.extend(txt_parser.parse_text(text))
                        break
                except Exception:
                    continue

        seen, unique = set(), []
        for obj in objects:
            k = (obj['type'], obj['id'])
            if k not in seen:
                seen.add(k)
                unique.append(obj)

        if not unique:
            print('  [WARNING] FOB decompression yielded no objects. Use .txt export for best results.')
        return unique


# ─────────────────────────────────────────────────────────────────────────────
# Markdown Generator
# ─────────────────────────────────────────────────────────────────────────────

class MarkdownGenerator:

    BC_MIGRATION_NOTES = {
        'Form':      '⚠️ **BC Migration:** Forms are **removed** in Business Central. Must be fully redesigned as Pages.',
        'Dataport':  '⚠️ **BC Migration:** Dataports are **removed**. Replace with XMLport or Data Exchange Framework.',
        'MenuSuite': '⚠️ **BC Migration:** MenuSuites replaced by Role Center navigation model.',
        'Report':    'ℹ️ **BC Migration:** Reports require layout conversion to RDLC or Word. Classic layouts (NAV 2009) must be fully rebuilt.',
        'Codeunit':  'ℹ️ **BC Migration:** Codeunits migrate to AL with minimal structural changes. Review for deprecated function calls.',
        'Table':     'ℹ️ **BC Migration:** Tables migrate to AL. Check BLOB→Media, OemCode→Code, and obsolete field types.',
        'Page':      '✅ **BC Migration:** Pages have a direct AL equivalent.',
        'XMLport':   '✅ **BC Migration:** XMLports migrate to AL with minor syntax changes.',
        'Query':     '✅ **BC Migration:** Queries have a direct AL equivalent.',
    }

    def __init__(self, analyse: bool = True, nav_version: str = 'auto'):
        self.analyse     = analyse
        self.nav_version = nav_version
        self.analyser    = CodeAnalyser()

    def generate(self, objects: list, source_files: list) -> str:
        # Pre-compute analyses
        analyses = {}
        if self.analyse:
            print('  Analysing objects...', end='', flush=True)
            for obj in objects:
                analyses[(obj['type'], obj['id'])] = self.analyser.analyse_object(obj)
            print(f' done ({len(analyses)} objects)')

        lines = []
        lines += self._header(objects, source_files)
        lines += self._toc(objects)
        lines += self._summary_stats(objects, analyses)
        lines += self._migration_overview(objects, analyses)

        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        type_order = ['Table', 'Page', 'Codeunit', 'Report',
                      'XMLport', 'Query', 'Form', 'Dataport', 'MenuSuite']
        for type_name in type_order:
            if type_name in by_type:
                lines += self._type_section(
                    type_name,
                    sorted(by_type[type_name], key=lambda o: o['id']),
                    analyses
                )
        for type_name, objs in sorted(by_type.items()):
            if type_name not in type_order:
                lines += self._type_section(type_name,
                                            sorted(objs, key=lambda o: o['id']),
                                            analyses)
        return '\n'.join(lines)

    # ── Header & TOC ──────────────────────────────────────────────────────────

    def _header(self, objects, source_files):
        nav_v = self.nav_version if self.nav_version != 'auto' else '2009–2015'
        return [
            '# Dynamics NAV — Migration Documentation',
            '',
            f'> **Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  ',
            f'> **NAV Version:** {nav_v}  ',
            f'> **Source files:** {", ".join(source_files)}  ',
            f'> **Total objects:** {len(objects)}',
            '',
            '---', '',
        ]

    def _toc(self, objects):
        lines = ['## Table of Contents', '']
        lines += [
            '1. [Summary Statistics](#summary-statistics)',
            '2. [Migration Overview](#migration-overview)',
            '3. [Effort & Risk Matrix](#effort--risk-matrix)',
        ]
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)
        for i, type_name in enumerate(sorted(by_type.keys()), 4):
            lines.append(f'{i}. [{type_name}s ({len(by_type[type_name])})](#{type_name.lower()}s)')
        lines += ['', '---', '']
        return lines

    # ── Summary ───────────────────────────────────────────────────────────────

    def _summary_stats(self, objects, analyses):
        lines = ['## Summary Statistics', '']
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        complexity = {
            'Table': '🟡 Medium', 'Page': '🟢 Low', 'Codeunit': '🟡 Medium',
            'Report': '🟡 Medium', 'XMLport': '🟢 Low', 'Query': '🟢 Low',
            'Form': '🔴 High', 'Dataport': '🔴 High', 'MenuSuite': '🟡 Medium',
        }

        lines.append('| Object Type | Count | Migration Complexity | Est. Total Hours |')
        lines.append('|---|---|---|---|')
        grand_total = 0
        grand_hours = 0
        for type_name in sorted(by_type.keys()):
            objs  = by_type[type_name]
            count = len(objs)
            hours = sum(analyses.get((o['type'], o['id']), {}).get('effort_hours', 0)
                        for o in objs)
            grand_total += count
            grand_hours += hours
            comp = complexity.get(type_name, '🟡 Medium')
            lines.append(f'| {type_name} | {count} | {comp} | ~{hours}h |')
        lines.append(f'| **Total** | **{grand_total}** | | **~{grand_hours}h** |')
        lines += ['']

        # Quick facts
        tables = by_type.get('Table', [])
        if tables:
            total_fields = sum(len(t.get('fields', [])) for t in tables)
            oem_fields   = sum(1 for t in tables for f in t.get('fields', [])
                               if f.get('legacy_type'))
            lines.append(f'- **Tables:** {len(tables)} tables, {total_fields} total fields'
                         + (f', **{oem_fields} OemCode/OemText fields** to rename' if oem_fields else ''))
        codeunits = by_type.get('Codeunit', [])
        if codeunits:
            total_procs = sum(len(c.get('procedures', [])) for c in codeunits)
            lines.append(f'- **Codeunits:** {total_procs} procedures across {len(codeunits)} codeunits')
        if analyses:
            all_deprecated = [hit for a in analyses.values()
                              for hit in a.get('deprecated_hits', [])]
            if all_deprecated:
                lines.append(f'- ⚠️ **Deprecated patterns found:** {len(all_deprecated)} occurrences across all objects')

        lines += ['', '---', '']
        return lines

    def _migration_overview(self, objects, analyses):
        lines = ['## Migration Overview', '']
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        priority = [
            ('🔴 High Priority', ['Form', 'Dataport'],
             'No direct BC equivalent — must be fully redesigned.'),
            ('🟡 Medium Priority', ['Table', 'Codeunit', 'Report', 'MenuSuite'],
             'Require code review and partial refactoring.'),
            ('🟢 Low Priority', ['Page', 'XMLport', 'Query'],
             'Direct AL equivalents exist with minimal changes.'),
        ]
        for label, types, note in priority:
            relevant = [(t, by_type[t]) for t in types if t in by_type]
            if not relevant:
                continue
            lines.append(f'### {label}')
            lines.append(f'_{note}_')
            lines.append('')
            for type_name, objs in relevant:
                names = ', '.join(f'`{o["name"]}`' for o in objs[:5])
                more  = f' …and {len(objs)-5} more' if len(objs) > 5 else ''
                lines.append(f'- **{type_name}s ({len(objs)}):** {names}{more}')
            lines.append('')

        lines += ['---', '']

        # Effort & risk matrix
        lines += ['## Effort & Risk Matrix', '']
        lines.append('| Object | Type | Risk | Est. Hours | Deprecated Hits | Key Dependencies |')
        lines.append('|---|---|---|---|---|---|')
        rows = []
        for obj in objects:
            a = analyses.get((obj['type'], obj['id']), {})
            risk  = a.get('migration_risk', '—')
            icon  = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}.get(risk, '—')
            hours = a.get('effort_hours', '—')
            dep_c = len(a.get('deprecated_hits', []))
            deps  = '; '.join(f'{d["kind"]}:{d["name"]}' for d in a.get('dependencies', [])[:3])
            rows.append((hours if isinstance(hours, int) else 0, obj, icon, risk, hours, dep_c, deps))

        for _, obj, icon, risk, hours, dep_c, deps in sorted(rows, key=lambda x: -x[0]):
            lines.append(f'| {obj["name"]} | {obj["type"]} | {icon} {risk} | ~{hours}h | {dep_c} | {deps or "—"} |')
        lines += ['', '---', '']
        return lines

    # ── Per-type section ─────────────────────────────────────────────────────

    def _type_section(self, type_name, objects, analyses):
        lines = [f'## {type_name}s', '']
        note = self.BC_MIGRATION_NOTES.get(type_name, '')
        if note:
            lines.append(f'> {note}')
            lines.append('')
        for obj in objects:
            a = analyses.get((obj['type'], obj['id']), {})
            lines += self._object_section(obj, a)
        lines += ['---', '']
        return lines

    # ── Per-object section ────────────────────────────────────────────────────

    def _object_section(self, obj: dict, analysis: dict) -> list:
        lines = []
        type_name = obj['type']
        obj_id    = obj['id']
        name      = obj['name']
        risk      = analysis.get('migration_risk', '')
        risk_icon = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}.get(risk, '')
        effort    = analysis.get('effort_hours', '')
        modified  = obj.get('modified_date', '')
        version   = obj.get('version_list', '')

        # Object heading
        lines.append(f'### {type_name} {obj_id}: {name}')
        meta = []
        if modified: meta.append(f'Modified: `{modified}`')
        if version:  meta.append(f'Version: `{version}`')
        if risk:     meta.append(f'Risk: {risk_icon} {risk}')
        if effort:   meta.append(f'Est. effort: ~{effort}h')
        if meta:
            lines.append('  '.join(f'_{m}_' for m in meta))
        lines.append('')

        # Algorithm summary
        summary = analysis.get('algorithm_summary', '')
        if summary:
            lines.append('#### 📋 Algorithm Summary')
            lines.append('')
            lines.append(summary)
            lines.append('')

        # Role-specific migration comments
        comments = analysis.get('comments', {})
        if any(comments.values()):
            lines.append('#### 🚦 Migration Notes by Role')
            lines.append('')
            if comments.get('architect'):
                lines.append('<details>')
                lines.append('<summary>🏗️ Architect</summary>')
                lines.append('')
                lines.append(comments['architect'])
                lines.append('')
                lines.append('</details>')
                lines.append('')
            if comments.get('developer'):
                lines.append('<details>')
                lines.append('<summary>💻 Developer</summary>')
                lines.append('')
                lines.append(comments['developer'])
                lines.append('')
                lines.append('</details>')
                lines.append('')
            if comments.get('pm'):
                lines.append('<details>')
                lines.append('<summary>📋 Project Manager</summary>')
                lines.append('')
                lines.append(comments['pm'])
                lines.append('')
                lines.append('</details>')
                lines.append('')

        # Properties
        props = obj.get('properties', {})
        if props:
            shown = {k: v for k, v in props.items()
                     if k in ('Description','CaptionML','DataCaptionFields',
                               'LookupPageID','DrillDownPageID','TableType',
                               'SubType','RunObject','Permissions','SourceTable',
                               'PageType','DataItemTable') and v}
            if shown:
                lines.append('#### Properties')
                lines.append('')
                lines.append('| Property | Value |')
                lines.append('|---|---|')
                for k, v in shown.items():
                    lines.append(f'| {k} | `{v}` |')
                lines.append('')

        # Deprecated patterns
        deprecated = analysis.get('deprecated_hits', [])
        if deprecated:
            lines.append('#### ⚠️ Deprecated Patterns')
            lines.append('')
            lines.append('| Pattern | Migration Action |')
            lines.append('|---|---|')
            for d in deprecated:
                lines.append(f'| `{d["pattern"]}` | {d["advice"]} |')
            lines.append('')

        # Dependencies
        deps = analysis.get('dependencies', [])
        if deps:
            lines.append('#### 🔗 Dependencies')
            lines.append('')
            lines.append('| Type | Name | Operation |')
            lines.append('|---|---|---|')
            for d in deps:
                lines.append(f'| {d["kind"]} | `{d["name"]}` | {d["op"]} |')
            lines.append('')

        # Fields (Tables)
        fields = obj.get('fields', [])
        if fields:
            oem_count = sum(1 for f in fields if f.get('legacy_type'))
            label = f'**Fields** ({len(fields)} total'
            if oem_count:
                label += f', ⚠️ {oem_count} legacy OEM type(s)'
            label += '):'
            lines.append(label)
            lines.append('')
            lines.append('| No | Name | Type | Legacy Type | Properties |')
            lines.append('|---|---|---|---|---|')
            for f in fields:
                fprops = '; '.join(f'{k}={v}' for k, v in f.get('properties', {}).items()
                                   if k in ('TableRelation','CalcFormula','FieldClass','Editable','BlankZero'))
                legacy = f.get('legacy_type', '')
                lines.append(f'| {f["no"]} | `{f["name"]}` | {f["type"]} | '
                              f'{"⚠️ `"+legacy+"`" if legacy else "—"} | {fprops} |')
            lines.append('')

        # Keys (Tables)
        keys = obj.get('keys', [])
        if keys:
            lines.append('**Keys:**')
            lines.append('')
            lines.append('| Enabled | Key Fields | SumIndexFields |')
            lines.append('|---|---|---|')
            for k in keys:
                lines.append(f'| {k["enabled"]} | `{k["fields"]}` | {k["sum_fields"] or "—"} |')
            lines.append('')

        # Global variables
        global_vars = analysis.get('global_vars', [])
        if global_vars:
            lines.append('#### Global Variables')
            lines.append('')
            lines.append('| Name | Type | Description |')
            lines.append('|---|---|---|')
            for v in global_vars:
                lines.append(f'| `{v["name"]}` | {v["type"]} | {v.get("description","")} |')
            lines.append('')

        # Report dataset structure
        report_dataset = analysis.get('report_dataset', [])
        if report_dataset:
            lines.append('#### 📊 Report Dataset Structure')
            lines.append('')
            lines.append('_Use this structure when rebuilding the report in RDLC, Word Layout, SSRS or Power BI._')
            lines.append('')
            lines.append('| Kind | ID | Name / Column | Source / Table |')
            lines.append('|---|---|---|---|')
            for item in report_dataset:
                src = item.get('table_id', item.get('source', ''))
                lines.append(f'| {item["kind"]} | {item["id"]} | `{item["name"]}` | {src} |')
            lines.append('')

            # NAV 2009 classic sections
            sections_09 = obj.get('report_sections', [])
            if sections_09:
                lines.append('**Classic Report Sections (NAV 2009):**')
                lines.append('')
                lines.append('| Section ID | Kind | Name |')
                lines.append('|---|---|---|')
                for s in sections_09:
                    lines.append(f'| {s["id"]} | {s["kind"]} | {s["name"]} |')
                lines.append('')
                lines.append('> ℹ️ Classic layout sections must be rebuilt as RDLC or Word layout in BC.')
                lines.append('')

        # Request form (NAV 2009)
        req_form = obj.get('request_form', [])
        if req_form:
            lines.append('**Request Form Controls (NAV 2009)** — rebuild as RequestPage in BC:')
            lines.append('')
            lines.append('| ID | Parent | Type |')
            lines.append('|---|---|---|')
            for c in req_form[:20]:
                lines.append(f'| {c["id"]} | {c["parent"]} | {c["type"]} |')
            lines.append('')

        # Controls (Pages/Forms)
        controls = obj.get('controls', [])
        if controls:
            lines.append(f'**Controls** ({len(controls)} total):')
            lines.append('')
            lines.append('| ID | Parent | Type |')
            lines.append('|---|---|---|')
            for c in controls[:30]:
                lines.append(f'| {c["id"]} | {c["parent"]} | {c["type"]} |')
            if len(controls) > 30:
                lines.append(f'| … | … | _{len(controls)-30} more_ |')
            lines.append('')

        # Procedures with full detail
        proc_details = analysis.get('procedures_detail', [])
        if proc_details:
            lines.append(f'#### Procedures & Triggers ({len(proc_details)} total)')
            lines.append('')

            # Summary table
            lines.append('| Name | Kind | Params | Returns | LOC | Risk |')
            lines.append('|---|---|---|---|---|---|')
            for p in proc_details:
                params_str  = ', '.join(f'`{x["name"]}`:{x["type"]}({x["direction"]})' for x in p['params'][:3])
                ret_str     = f'`{p["return_type"]}`' if p['return_type'] else '—'
                dep_count   = len(p.get('deprecated', []))
                risk_p      = '⚠️' if dep_count else '✅'
                lines.append(f'| `{p["name"]}` | {p["kind"]} | {params_str or "—"} | {ret_str} | {p["loc"]} | {risk_p} |')
            lines.append('')

            # Expandable detail blocks
            for p in proc_details:
                lines.append('<details>')
                kind_icon = '🔔' if p['kind'] == 'trigger' else '⚙️'
                lines.append(f'<summary>{kind_icon} <code>{p["name"]}</code> — {p["summary"][:80]}</summary>')
                lines.append('')

                if p['params']:
                    lines.append('**Parameters:**')
                    lines.append('')
                    lines.append('| Name | Type | Direction |')
                    lines.append('|---|---|---|')
                    for param in p['params']:
                        lines.append(f'| `{param["name"]}` | {param["type"]} | {param["direction"]} |')
                    lines.append('')

                if p['return_type']:
                    lines.append(f'**Returns:** `{p["return_type"]}`')
                    lines.append('')

                if p['local_vars']:
                    lines.append('**Local Variables:**')
                    lines.append('')
                    lines.append('| Name | Type | Description |')
                    lines.append('|---|---|---|')
                    for v in p['local_vars']:
                        lines.append(f'| `{v["name"]}` | {v["type"]} | {v.get("description","")} |')
                    lines.append('')

                if p.get('deprecated'):
                    lines.append('**⚠️ Deprecated Patterns in this block:**')
                    for d in p['deprecated']:
                        lines.append(f'- `{d["pattern"]}`: {d["advice"]}')
                    lines.append('')

                lines.append('**C/AL Source:**')
                lines.append('')
                lines.append('```cal')
                body = p['body'].strip()
                lines.append(body[:3000] + ('…' if len(body) > 3000 else ''))
                lines.append('```')
                lines.append('')
                lines.append('</details>')
                lines.append('')

        lines.append('')
        return lines


# ─────────────────────────────────────────────────────────────────────────────
# Main CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cli = argparse.ArgumentParser(
        description='NAV Object Parser & Migration Intelligence Tool (NAV 2009–2015)'
    )
    cli.add_argument('--txt',         nargs='+',  help='.txt export file(s)')
    cli.add_argument('--fob',         nargs='+',  help='.fob export file(s)')
    cli.add_argument('--dir',                     help='Directory with .txt/.fob files')
    cli.add_argument('--output',      default='nav_documentation.md')
    cli.add_argument('--nav-version', default='auto',
                     choices=['auto','2009','2013','2015'],
                     help='NAV version — enables version-specific parsing (default: auto)')
    cli.add_argument('--encoding',    default=None,
                     help='Force file encoding (e.g. cp1252, utf-8). Default: auto-detect')
    cli.add_argument('--no-analyse',  action='store_true',
                     help='Skip static code analysis (faster, less detail)')
    args = cli.parse_args()

    txt_files = list(args.txt or [])
    fob_files = list(args.fob or [])

    if args.dir:
        d = Path(args.dir)
        txt_files += [str(p) for p in d.glob('*.txt')]
        fob_files += [str(p) for p in d.glob('*.fob')]

    if not txt_files and not fob_files:
        print('ERROR: Provide --txt, --fob, or --dir')
        cli.print_help()
        sys.exit(1)

    all_objects  = []
    source_files = []
    nav_ver      = getattr(args, 'nav_version', 'auto')
    txt_parser   = NavTxtParser(nav_version=nav_ver)
    fob_parser   = NavFobParser()

    for f in txt_files:
        if not os.path.exists(f):
            print(f'[SKIP] Not found: {f}')
            continue
        print(f'Parsing TXT: {f}')
        try:
            objs = txt_parser.parse_file(f, encoding=args.encoding)
            print(f'  → {len(objs)} objects')
            all_objects.extend(objs)
            source_files.append(os.path.basename(f))
        except Exception as e:
            print(f'  [ERROR] {e}')

    for f in fob_files:
        if not os.path.exists(f):
            print(f'[SKIP] Not found: {f}')
            continue
        print(f'Parsing FOB: {f}')
        try:
            objs = fob_parser.parse_file(f)
            print(f'  → {len(objs)} objects')
            all_objects.extend(objs)
            source_files.append(os.path.basename(f))
        except Exception as e:
            print(f'  [ERROR] {e}')

    if not all_objects:
        print('No objects parsed.')
        sys.exit(1)

    # Deduplicate — txt wins over fob
    seen, unique = {}, []
    for obj in all_objects:
        k = (obj['type'], obj['id'])
        if k not in seen:
            seen[k] = obj
            unique.append(obj)

    print(f'\nTotal unique objects: {len(unique)}')
    print('Generating documentation...')

    gen = MarkdownGenerator(
        analyse     = not args.no_analyse,
        nav_version = nav_ver,
    )
    md = gen.generate(unique, source_files or ['(unknown)'])

    with open(args.output, 'w', encoding='utf-8') as fout:
        fout.write(md)

    size = os.path.getsize(args.output)
    print(f'✅ Saved: {args.output}  ({size:,} bytes)')


if __name__ == '__main__':
    main()
