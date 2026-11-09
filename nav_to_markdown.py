#!/usr/bin/env python3
"""
Dynamics NAV Object Parser & Migration Intelligence Tool
Supports: NAV 2009, NAV 2013-2015

Целевая платформа миграции: 1С (редакция уточняется)
Документация платформонезависима — описывает объекты NAV в терминах,
понятных архитектору и разработчику 1С.

Usage:
    python nav_to_markdown.py --txt objects.txt --output docs.md
    python nav_to_markdown.py --fob objects.fob --nav-version 2009 --output docs.md
    python nav_to_markdown.py --dir ./exports/ --output docs.md
    python nav_to_markdown.py --txt objects.txt --no-analyse --output docs.md
"""

import re
import sys
import os
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

SECTION_KEYWORDS = {
    "OBJECT", "OBJECT-PROPERTIES", "PROPERTIES",
    "FIELDS", "KEYS", "FIELDGROUPS",
    "CODE", "TRIGGERS",
    "CONTROLS", "ELEMENTS",
    "REQUESTPAGE", "REQUESTFORM",
    "LABELS", "DATASET",
    "SECTIONS",
    "QUERYCOLUMNS",
}

# ── 1С mapping ────────────────────────────────────────────────────────────────
# NAV object type → 1С analogue (universal, version-agnostic)
ONEC_MAPPING = {
    "Table": {
        "analogue":     "Справочник / Регистр сведений / Документ",
        "description":  "В зависимости от назначения таблицы: справочные данные → Справочник, "
                        "журнальные/операционные записи → Регистр сведений или Документ.",
        "action":       "Провести анализ назначения таблицы. Определить тип объекта 1С. "
                        "Перенести поля вручную с учётом типов данных 1С.",
        "risk":         "Medium",
    },
    "Form": {
        "analogue":     "Форма (управляемая)",
        "description":  "NAV Form — классический интерфейс (аналог Windows Forms). "
                        "В 1С — управляемые формы на основе объектов конфигурации.",
        "action":       "Перепроектировать как управляемую форму 1С. "
                        "Логику из Code-секции перенести в модуль формы.",
        "risk":         "High",
    },
    "Report": {
        "analogue":     "Отчёт (СКД или программный)",
        "description":  "В 1С отчёты строятся на основе Системы Компоновки Данных (СКД) "
                        "или программно через табличный документ.",
        "action":       "Воссоздать структуру выборки данных в СКД. "
                        "Макет оформления перенести в макет 1С (таблица/спредшит).",
        "risk":         "High",
    },
    "Dataport": {
        "analogue":     "Обработка загрузки/выгрузки данных",
        "description":  "NAV Dataport — инструмент импорта/экспорта. "
                        "В 1С аналог — внешняя обработка или регламентное задание с обменом данными.",
        "action":       "Создать обработку 1С с форматом файла по спецификации Dataport. "
                        "Рассмотреть использование планов обмена 1С для регулярного обмена.",
        "risk":         "High",
    },
    "Codeunit": {
        "analogue":     "Общий модуль",
        "description":  "Codeunit в NAV — библиотека процедур/функций без пользовательского интерфейса. "
                        "Прямой аналог в 1С — Общий модуль.",
        "action":       "Создать общий модуль 1С. Перенести логику процедур. "
                        "Учесть различия: в 1С нет статических методов, есть Сеанс/Глобальный контекст.",
        "risk":         "Medium",
    },
    "XMLport": {
        "analogue":     "XDTO-пакет / Обработка XML",
        "description":  "NAV XMLport — декларативный XML-обмен. "
                        "В 1С: XDTO для структурированного XML или объекты ЧтениеXML/ЗаписьXML.",
        "action":       "Создать XDTO-пакет по XSD-схеме NAV XMLport "
                        "или реализовать через встроенные средства работы с XML.",
        "risk":         "Medium",
    },
    "MenuSuite": {
        "analogue":     "Подсистема / Интерфейс",
        "description":  "NAV MenuSuite определяет навигационное меню. "
                        "В 1С навигация задаётся через Подсистемы конфигурации.",
        "action":       "Воссоздать структуру меню через подсистемы 1С. "
                        "Настроить видимость объектов по ролям.",
        "risk":         "Low",
    },
    "Page": {
        "analogue":     "Форма (управляемая)",
        "description":  "NAV Page — современный UI-объект (RoleTailored Client). "
                        "В 1С — управляемая форма, привязанная к объекту конфигурации.",
        "action":       "Создать управляемую форму 1С. "
                        "PageType=List → форма списка, PageType=Card → форма элемента.",
        "risk":         "Medium",
    },
    "Query": {
        "analogue":     "Запрос (объект конфигурации) / СКД",
        "description":  "NAV Query — именованный запрос к нескольким таблицам. "
                        "В 1С аналог — объект Запрос конфигурации или набор данных СКД.",
        "action":       "Реализовать как запрос 1С на языке запросов. "
                        "Если используется в отчёте — включить в СКД.",
        "risk":         "Low",
    },
}

# ── Поля: маппинг типов NAV → 1С ─────────────────────────────────────────────
FIELD_TYPE_MAPPING = {
    r'Code\s*\d*':        ('Строка',      'Тип Строка с фиксированной длиной'),
    r'OemCode\s*\d*':     ('Строка',      'Тип Строка (был OemCode — устаревший тип NAV 2009)'),
    r'Text\s*\d*':        ('Строка',      'Тип Строка'),
    r'OemText\s*\d*':     ('Строка',      'Тип Строка (был OemText — устаревший тип NAV 2009)'),
    r'Integer':           ('Число',       'Целое число; в 1С — Число(10,0)'),
    r'BigInteger':        ('Число',       'Большое целое; в 1С — Число(15,0)'),
    r'Decimal':           ('Число',       'Число с десятичной частью; в 1С — Число(15,2) или по требованиям'),
    r'Boolean':           ('Булево',      'Тип Булево'),
    r'Date':              ('Дата',        'Тип Дата (без времени)'),
    r'Time':              ('Дата',        'Только время; в 1С хранить как Дата или Строка'),
    r'DateTime':          ('Дата и время','Тип Дата (с временем)'),
    r'Option':            ('Перечисление','В 1С — Перечисление или значение из списка значений'),
    r'Blob':              ('ХранилищеЗначения', 'Двоичные данные; в 1С — ХранилищеЗначения'),
    r'GUID':              ('УникальныйИдентификатор', 'Тип УникальныйИдентификатор'),
    r'RecordID':          ('Строка',      'Ссылка на запись; в 1С использовать ссылочный тип'),
    r'DateFormula':       ('Строка',      'Формула даты NAV; в 1С нет прямого аналога — хранить как строку'),
    r'Duration':          ('Число',       'Длительность в мс; в 1С — Число или разница дат'),
}

# ── Deprecated C/AL паттерны ──────────────────────────────────────────────────
DEPRECATED_PATTERNS = [
    (r'\bFORM\s*\.\s*RUN\b',        'FORM.RUN',         'Объект Form удалён. В 1С: ОткрытьФорму()'),
    (r'\bFORM\s*\.\s*OPEN\b',       'FORM.OPEN',        'Объект Form удалён. В 1С: ОткрытьФорму()'),
    (r'\bDATAPORT\s*\.\s*RUN\b',    'DATAPORT.RUN',     'Dataport удалён. Перенести в обработку 1С'),
    (r'\bCREATEFORM\b',             'CREATEFORM',       'Удалён. Аналог 1С: ОткрытьФорму()'),
    (r'\bSKIPLINE\b',               'SKIPLINE',         'Удалён. Переработать цикл'),
    (r'\bOEMCODE\b',                'OemCode тип',      'Переименовать в Code / Строка (1С)'),
    (r'\bOEMTEXT\b',                'OemText тип',      'Переименовать в Text / Строка (1С)'),
    (r'\bLOCKTABLE\b',              'LOCKTABLE',        'В 1С: блокировка через УправляемаяБлокировка или ЗаблокироватьДанныеДляРедактирования'),
    (r'\bCOMMIT\b',                 'COMMIT',           'В 1С транзакции управляются иначе: НачатьТранзакцию / ЗафиксироватьТранзакцию'),
    (r'\bERROR\s*\(',               'ERROR()',          'В 1С: ВызватьИсключение или Сообщить()'),
    (r'\bMESSAGE\s*\(',             'MESSAGE()',        'В 1С: Сообщить() или ПоказатьПредупреждение()'),
    (r'\bGLOBALLANGUAGE\b',        'GLOBALLANGUAGE',   'В 1С язык определяется параметрами сеанса'),
    (r'\bCALCFIELDS\b',             'CALCFIELDS',       'В 1С вычисляемые поля реализуются через запросы или реквизиты с формулой'),
    (r'\bFILTERGROUP\b',            'FILTERGROUP',      'В 1С: фильтры через Отбор объекта СписокЗначений или запрос'),
    (r'\bSETCURRENTKEY\b',          'SETCURRENTKEY',    'В 1С порядок записей задаётся в запросе (УПОРЯДОЧИТЬ ПО)'),
]

TABLE_ACCESS_RE  = re.compile(
    r'(\w[\w\s"]*?)\s*\.(FIND|GET|INSERT|MODIFY|DELETE|MODIFYALL|DELETEALL|FINDFIRST|FINDSET)',
    re.IGNORECASE)
CODEUNIT_CALL_RE = re.compile(r'CODEUNIT\s*\.\s*RUN\s*\(\s*CODEUNIT\s*::\s*"?([^")]+)"?', re.IGNORECASE)
PAGE_CALL_RE     = re.compile(r'PAGE\s*\.\s*RUN\s*\(\s*PAGE\s*::\s*"?([^")]+)"?', re.IGNORECASE)
REPORT_CALL_RE   = re.compile(r'REPORT\s*\.\s*RUN\s*\(\s*REPORT\s*::\s*"?([^")]+)"?', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Encoding detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_encoding(filepath: str) -> str:
    try:
        import chardet
        with open(filepath, 'rb') as f:
            raw = f.read(65536)
        r = chardet.detect(raw)
        if r and r.get('confidence', 0) > 0.75:
            return r['encoding']
    except ImportError:
        pass
    for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'cp1252', 'cp850', 'cp437', 'latin-1'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return 'latin-1'


# ─────────────────────────────────────────────────────────────────────────────
# Field type mapper NAV → 1С
# ─────────────────────────────────────────────────────────────────────────────

def map_field_type(nav_type: str) -> tuple[str, str]:
    """Returns (1С type, comment)."""
    for pattern, (onec_type, comment) in FIELD_TYPE_MAPPING.items():
        if re.match(pattern, nav_type.strip(), re.IGNORECASE):
            return onec_type, comment
    return '?', f'Нет прямого аналога для типа NAV «{nav_type}» — требует ручного анализа'


# ─────────────────────────────────────────────────────────────────────────────
# Static Code Analyser
# ─────────────────────────────────────────────────────────────────────────────

class CodeAnalyser:

    def analyse_object(self, obj: dict) -> dict:
        all_code = '\n'.join(obj.get('raw_code', []))
        result = {
            'global_vars':       self._extract_vars(all_code),
            'deprecated_hits':   self._find_deprecated(all_code),
            'dependencies':      self._find_dependencies(all_code),
            'procedures_detail': self._analyse_procedures(obj),
            'report_dataset':    self._extract_report_dataset(obj) if obj['type'] == 'Report' else [],
            'effort_hours':      0,
            'migration_risk':    'Low',
            'algorithm_summary': '',
            'onec_notes':        {},
        }
        result['effort_hours']      = self._estimate_effort(obj, result)
        result['migration_risk']    = self._assess_risk(obj, result)
        result['algorithm_summary'] = self._summarise_algorithm(obj, result, all_code)
        result['onec_notes']        = self._generate_onec_notes(obj, result)
        return result

    # ── Variables ─────────────────────────────────────────────────────────────

    def _extract_vars(self, code: str) -> list:
        vars_ = []
        in_var = False
        for line in code.splitlines():
            s = line.strip()
            if re.match(r'^VAR\s*$', s, re.IGNORECASE):
                in_var = True
                continue
            if in_var:
                if re.match(r'^(BEGIN|PROCEDURE|LOCAL|ON\w)', s, re.IGNORECASE):
                    in_var = False
                    continue
                m = re.match(r'^([A-Za-z_@][A-Za-z0-9_@\s]*?)\s*:\s*([^;]+?)\s*;', s)
                if m:
                    nav_type = m.group(2).strip()
                    onec_type, type_comment = map_field_type(nav_type)
                    vars_.append({
                        'name':         m.group(1).strip(),
                        'nav_type':     nav_type,
                        'onec_type':    onec_type,
                        'type_comment': type_comment,
                        'description':  self._infer_var_desc(m.group(1).strip(), nav_type),
                    })
        return vars_

    def _infer_var_desc(self, name: str, vtype: str) -> str:
        if 'Record' in vtype:
            t = re.sub(r'Record\s*', '', vtype, flags=re.IGNORECASE).strip().strip('"')
            return f'Буфер записи таблицы «{t}»'
        if 'Codeunit' in vtype:
            return f'Ссылка на codeunit {vtype}'
        if name.lower() in ('i', 'j', 'k', 'counter', 'cnt'):
            return 'Счётчик цикла'
        if re.search(r'text|code', vtype, re.IGNORECASE):
            return 'Строковая переменная'
        if 'Boolean' in vtype:
            return 'Флаг / признак'
        if re.search(r'Decimal|Integer', vtype, re.IGNORECASE):
            return 'Числовая переменная'
        return ''

    # ── Parameters ────────────────────────────────────────────────────────────

    def _parse_signature(self, header: str) -> tuple[list, str]:
        params = []
        m_paren = re.search(r'\(([^)]*)\)', header)
        if m_paren:
            for token in re.split(r';', m_paren.group(1)):
                token = token.strip()
                if not token:
                    continue
                is_var = token.upper().startswith('VAR ')
                clean  = re.sub(r'^VAR\s+', '', token, flags=re.IGNORECASE)
                pm = re.match(r'([A-Za-z_@][A-Za-z0-9_@]*)\s*:\s*(.+)', clean)
                if pm:
                    nav_t = pm.group(2).strip()
                    onec_t, _ = map_field_type(nav_t)
                    params.append({
                        'name':      pm.group(1).strip(),
                        'nav_type':  nav_t,
                        'onec_type': onec_t,
                        'direction': 'Вх/Вых (VAR)' if is_var else 'Вх',
                    })
        ret = ''
        m_ret = re.search(
            r'\)\s*:\s*(Text\s*(?:\[\d+\])?|Code\s*(?:\[\d+\])?|Integer|Decimal|Boolean|'
            r'Date|Time|DateTime|Option|Record\s+\S+|[A-Za-z][A-Za-z0-9]*)\s*$',
            header, re.IGNORECASE)
        if m_ret:
            ret = m_ret.group(1).strip()
        return params, ret

    def _analyse_procedures(self, obj: dict) -> list:
        details = []
        for blocks, kind in [(obj.get('triggers', []), 'trigger'),
                              (obj.get('procedures', []), 'procedure')]:
            for block in blocks:
                body       = block['body']
                first_line = body.splitlines()[0] if body.splitlines() else ''
                params, ret = self._parse_signature(first_line)
                local_vars  = self._extract_vars(body)
                deprecated  = self._find_deprecated(body)
                deps        = self._find_dependencies(body)
                loc = sum(1 for l in body.splitlines()
                          if l.strip() and not l.strip().startswith('//'))
                onec_ret, _ = map_field_type(ret) if ret else ('', '')
                details.append({
                    'name':       block['name'],
                    'kind':       kind,
                    'params':     params,
                    'return_nav': ret,
                    'return_1c':  onec_ret,
                    'local_vars': local_vars,
                    'deprecated': deprecated,
                    'dependencies': deps,
                    'loc':        loc,
                    'body':       body,
                    'summary':    self._summarise_proc(block['name'], body, params, ret),
                })
        return details

    # ── Deprecated ────────────────────────────────────────────────────────────

    def _find_deprecated(self, code: str) -> list:
        hits = []
        for pat, label, advice in DEPRECATED_PATTERNS:
            if re.search(pat, code, re.IGNORECASE):
                hits.append({'pattern': label, 'advice': advice})
        return hits

    # ── Dependencies ──────────────────────────────────────────────────────────

    def _find_dependencies(self, code: str) -> list:
        deps = []
        seen = set()
        for m in TABLE_ACCESS_RE.finditer(code):
            n = m.group(1).strip()
            k = ('Table', n)
            if k not in seen:
                seen.add(k)
                deps.append({'kind': 'Table', 'name': n, 'op': m.group(2)})
        for regex, kind in [(CODEUNIT_CALL_RE, 'Codeunit'),
                             (PAGE_CALL_RE,    'Page'),
                             (REPORT_CALL_RE,  'Report')]:
            for m in regex.finditer(code):
                n = m.group(1).strip()
                k = (kind, n)
                if k not in seen:
                    seen.add(k)
                    deps.append({'kind': kind, 'name': n, 'op': 'RUN'})
        return deps

    # ── Report dataset ────────────────────────────────────────────────────────

    def _extract_report_dataset(self, obj: dict) -> list:
        dataset  = []
        all_text = '\n'.join(obj.get('raw_code', []))
        for line in all_text.splitlines():
            m = re.search(
                r'\{\s*(\d+)\s*;\s*\d+\s*;DataItem;\s*([^;]+)\s*;.*?DataItemTable\s*=\s*Table(\d+)',
                line, re.IGNORECASE)
            if m:
                dataset.append({'kind': 'DataItem', 'id': m.group(1),
                                 'name': m.group(2).strip(), 'source': f'Table {m.group(3)}'})
                continue
            mc = re.search(
                r'\{\s*(\d+)\s*;\s*\d+\s*;Column\s*;\s*([^;]+)\s*;.*?SourceExpr\s*=\s*([^;}]+)',
                line, re.IGNORECASE)
            if mc:
                dataset.append({'kind': 'Column', 'id': mc.group(1),
                                 'name': mc.group(2).strip(), 'source': mc.group(3).strip()})
        return dataset

    # ── Effort & risk ─────────────────────────────────────────────────────────

    def _estimate_effort(self, obj: dict, a: dict) -> int:
        base = {'Table': 3, 'Page': 4, 'Codeunit': 5, 'Report': 8,
                'Form': 10, 'Dataport': 12, 'XMLport': 4, 'Query': 2, 'MenuSuite': 3}
        h  = base.get(obj['type'], 4)
        h += sum(p['loc'] for p in a.get('procedures_detail', [])) // 40
        h += len(a.get('deprecated_hits', [])) * 2
        h += len(obj.get('fields', [])) // 15
        return max(1, h)

    def _assess_risk(self, obj: dict, a: dict) -> str:
        dep  = len(a.get('deprecated_hits', []))
        eff  = a.get('effort_hours', 0)
        typ  = obj['type']
        if typ in ('Form', 'Dataport') or dep >= 3 or eff >= 20:
            return 'Высокий'
        if dep >= 1 or eff >= 8 or typ in ('Report', 'Codeunit', 'Page'):
            return 'Средний'
        return 'Низкий'

    # ── Algorithm summary ─────────────────────────────────────────────────────

    def _summarise_proc(self, name: str, body: str, params: list, ret: str) -> str:
        actions = []
        if re.findall(r'\w+\.(FIND|GET|FINDFIRST|FINDSET)', body, re.IGNORECASE):
            actions.append('читает данные из таблиц')
        if re.findall(r'\w+\.(INSERT|MODIFY|DELETE|MODIFYALL|DELETEALL)', body, re.IGNORECASE):
            actions.append('изменяет/удаляет записи')
        if re.search(r'\bCOMMIT\b', body, re.IGNORECASE):
            actions.append('фиксирует транзакцию')
        if re.search(r'\bREPEAT\b|\bWHILE\b', body, re.IGNORECASE):
            actions.append('итерирует по набору данных')
        if re.search(r'\bERROR\b', body, re.IGNORECASE):
            actions.append('генерирует ошибку при нарушении условий')
        if not actions:
            loc = sum(1 for l in body.splitlines() if l.strip())
            return f'Процедура «{name}» — {loc} строк C/AL логики.'
        direction = ''
        if params:
            in_p  = [p for p in params if 'Вых' not in p['direction']]
            out_p = [p for p in params if 'Вых' in p['direction']]
            if in_p:
                direction += f'Принимает {", ".join(p["name"] for p in in_p[:3])}. '
            if out_p:
                direction += f'Возвращает по ссылке: {", ".join(p["name"] for p in out_p[:2])}. '
        if ret:
            direction += f'Возвращаемый тип: `{ret}`. '
        return f'{direction}Процедура {"; ".join(actions)}.'

    def _summarise_algorithm(self, obj: dict, a: dict, all_code: str) -> str:
        name  = obj['name']
        typ   = obj['type']
        procs = a.get('procedures_detail', [])
        deps  = a.get('dependencies', [])
        parts = []

        if typ == 'Table':
            fields = obj.get('fields', [])
            pk     = [f['name'] for f in fields[:5]]
            calc   = [f for f in fields if f.get('properties', {}).get('FieldClass', '').lower() == 'flowfield']
            parts.append(f'Таблица **{name}** содержит {len(fields)} полей. '
                         f'Ключевые поля: {", ".join(f"`{f}`" for f in pk)}. ')
            if calc:
                parts.append(f'Содержит {len(calc)} вычисляемых поля (FlowField) — агрегируют данные из связанных таблиц. ')
            trg = [p for p in procs if p['kind'] == 'trigger']
            if trg:
                trg_names = ", ".join(f'`{t["name"]}`' for t in trg)
                parts.append(f'Бизнес-логика реализована в триггерах: {trg_names}. ')

        elif typ == 'Codeunit':
            tables = list({d['name'] for d in deps if d['kind'] == 'Table'})[:5]
            cus    = list({d['name'] for d in deps if d['kind'] == 'Codeunit'})[:3]
            parts.append(f'Codeunit **{name}** содержит {len(procs)} процедур/триггеров. ')
            if tables:
                tbl_names = ", ".join(f'`{t}`' for t in tables)
                parts.append(f'Работает с таблицами: {tbl_names}. ')
            if cus:
                cu_names2 = ', '.join(f'`{c}`' for c in cus)
                parts.append(f'Вызывает codeunit-ы: {cu_names2}. ')
            if any('post' in p['name'].lower() for p in procs):
                parts.append('По характеру — **процедура проведения документа** (критический бизнес-процесс). ')

        elif typ == 'Report':
            ds  = a.get('report_dataset', [])
            di  = [d for d in ds if d['kind'] == 'DataItem']
            col = [d for d in ds if d['kind'] == 'Column']
            parts.append(f'Отчёт **{name}** ')
            if di:
                di_names = ", ".join(f'`{d["name"]}`' for d in di[:4])
                parts.append(f'выбирает данные из: {di_names}. ')
            if col:
                parts.append(f'Выводит {len(col)} колонок. ')

        elif typ in ('Page', 'Form'):
            props = obj.get('properties', {})
            src   = props.get('SourceTable', '')
            ptype = props.get('PageType', '')
            parts.append(f'{typ} **{name}** ')
            if src:
                parts.append(f'привязан к таблице `{src}`. ')
            if ptype:
                parts.append(f'Тип: `{ptype}`. ')
            parts.append(f'Содержит {len(obj.get("controls", []))} элементов управления. ')

        else:
            parts.append(f'{typ} **{name}** — см. секции кода ниже. ')

        depr = a.get('deprecated_hits', [])
        if depr:
            labels = ', '.join(f'`{d["pattern"]}`' for d in depr[:3])
            parts.append(f'\n\n> ⚠️ Содержит устаревшие вызовы: {labels} — **требует переработки при миграции**.')

        return ''.join(parts)

    # ── 1С-specific migration notes ───────────────────────────────────────────

    def _generate_onec_notes(self, obj: dict, a: dict) -> dict:
        typ      = obj['type']
        name     = obj['name']
        risk     = a.get('migration_risk', 'Средний')
        effort   = a.get('effort_hours', 0)
        depr     = a.get('deprecated_hits', [])
        deps     = a.get('dependencies', [])
        procs    = a.get('procedures_detail', [])
        mapping  = ONEC_MAPPING.get(typ, {})

        risk_icon = {'Высокий': '🔴', 'Средний': '🟡', 'Низкий': '🟢'}.get(risk, '🟡')

        # ── Архитектор ────────────────────────────────────────────────────────
        arch = []
        arch.append(f'**Аналог в 1С:** {mapping.get("analogue","?")}')
        arch.append(mapping.get('description', ''))
        if typ == 'Table':
            fields  = obj.get('fields', [])
            blob_f  = [f for f in fields if 'blob' in f.get('type','').lower()]
            calc_f  = [f for f in fields if f.get('properties',{}).get('FieldClass','').lower()=='flowfield']
            oem_f   = [f for f in fields if f.get('legacy_type')]
            if blob_f:
                arch.append(f'⚠️ {len(blob_f)} BLOB-поле(й) — в 1С использовать ХранилищеЗначения или хранение файлов.')
            if calc_f:
                arch.append(f'{len(calc_f)} FlowField(ов) — реализовать через виртуальные реквизиты или запросы в 1С.')
            if oem_f:
                arch.append(f'{len(oem_f)} полей с устаревшим типом OemCode/OemText — переименовать в Строка.')
            keys = obj.get('keys', [])
            if len(keys) > 3:
                arch.append(f'{len(keys)} индексов — оценить необходимость каждого, в 1С индексирование устроено иначе.')
        if typ == 'Codeunit':
            has_commit = any(d['pattern'] == 'COMMIT' for d in depr)
            if has_commit:
                arch.append('Содержит COMMIT — в 1С управление транзакциями через НачатьТранзакцию/ЗафиксироватьТранзакцию. Проверить границы транзакций.')
        if typ == 'Report':
            arch.append('В 1С рекомендуется реализовать через СКД (Система компоновки данных). '
                        'Структура DataItems → наборы данных СКД. '
                        'Классический макет NAV 2009 → макет СКД или табличный документ.')
        if typ == 'Form':
            arch.append('Требуется полный редизайн. Провести встречу с бизнесом для определения нового UX в 1С.')
        dep_forms = [d for d in deps if d['kind'] in ('Form', 'Dataport')]
        if dep_forms:
            arch.append(f'Зависит от {len(dep_forms)} объектов Form/Dataport — они тоже требуют редизайна. Согласовать порядок миграции.')

        # ── Разработчик ───────────────────────────────────────────────────────
        dev = [f'**Действие:** {mapping.get("action","?")}', '']
        if depr:
            dev.append('**Устаревшие вызовы (требуют замены):**')
            for d in depr:
                dev.append(f'- `{d["pattern"]}` → {d["advice"]}')
            dev.append('')
        # Field type issues
        problem_fields = []
        for f in obj.get('fields', []):
            onec_t, comment = map_field_type(f.get('type',''))
            if onec_t == '?':
                problem_fields.append(f['name'])
        if problem_fields:
            dev.append(f'**Поля без прямого аналога в 1С** (требуют ручного анализа): '
                       + ', '.join(f'`{n}`' for n in problem_fields[:5]))
            dev.append('')
        total_loc = sum(p['loc'] for p in procs)
        if total_loc > 150:
            dev.append(f'**Объём кода:** {total_loc} строк C/AL — рассмотреть декомпозицию на модули при переносе в 1С.')
        if typ == 'Report':
            dev.append('**Отчёт:** структура данных задокументирована ниже. '
                       'Реализовать наборы данных в СКД, параметры → параметры СКД.')

        # ── Проект-менеджер ───────────────────────────────────────────────────
        pm = [
            f'**Риск миграции:** {risk_icon} {risk}',
            f'**Оценка трудозатрат:** ~{effort}ч',
            f'**Аналог в 1С:** {mapping.get("analogue","?")}',
        ]
        if typ in ('Form', 'Dataport', 'Report'):
            pm.append('**⚠️ Требует встречи с бизнесом** для подтверждения функциональных требований перед началом разработки.')
        if depr:
            pm.append(f'**Блокеры:** {len(depr)} устаревших вызовов — разработчик должен проработать до UAT.')
        linked = list({d["name"] for d in deps if d["kind"] in ("Codeunit","Form","Report")})[:4]
        if linked:
            pm.append(f'**Зависимости:** {", ".join(linked)} — согласовать очерёдность миграции.')

        return {
            'architect': '\n\n'.join(arch),
            'developer': '\n'.join(dev),
            'pm':        '\n\n'.join(pm),
        }


# ─────────────────────────────────────────────────────────────────────────────
# .TXT Parser
# ─────────────────────────────────────────────────────────────────────────────

class NavTxtParser:

    OBJECT_HEADER_RE = re.compile(
        r'^OBJECT\s+(Table|Form|Report|Dataport|Codeunit|XMLport|MenuSuite|Page|Query)\s+(\d+)\s+(.*?)\s*$',
        re.IGNORECASE)
    PROPERTY_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_\-]*)\s*=\s*(.*?)\s*;?\s*$')

    def __init__(self, nav_version: str = 'auto'):
        self.nav_version = nav_version

    def parse_file(self, filepath: str, encoding: str = None) -> list:
        enc = encoding or detect_encoding(filepath)
        with open(filepath, 'r', encoding=enc, errors='replace') as f:
            content = f.read()
        print(f'  Кодировка: {enc}')
        return self.parse_text(content)

    def parse_text(self, content: str) -> list:
        objects = []
        for block in re.split(r'(?=^OBJECT\s)', content, flags=re.MULTILINE):
            block = block.strip()
            if block:
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
            'type': m.group(1).capitalize(), 'id': int(m.group(2)),
            'name': m.group(3).strip(),
            'modified_date': '', 'version_list': '',
            'properties': {}, 'fields': [], 'keys': [],
            'triggers': [], 'procedures': [], 'controls': [],
            'report_sections': [], 'request_form': [], 'raw_code': [],
        }
        self._parse_sections(lines[1:], obj)
        self._normalise_field_types(obj)
        return obj

    def _parse_sections(self, lines: list, obj: dict):
        section, buffer, depth = None, [], 0
        for line in lines:
            stripped = line.strip()
            upper    = stripped.upper().rstrip(':')
            if upper in SECTION_KEYWORDS and depth <= 1:
                self._flush_section(section, buffer, obj)
                section, buffer, depth = upper, [], 0
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
            t, p, r = self._parse_code(buffer)
            obj['triggers'].extend(t)
            obj['procedures'].extend(p)
            obj['raw_code'].extend(r)
        elif section == 'CONTROLS':
            obj['controls'] = self._parse_controls(buffer)
        elif section == 'SECTIONS':
            obj['report_sections'] = self._parse_report_sections(buffer)
        elif section == 'REQUESTFORM':
            obj['request_form'] = self._parse_controls(buffer)

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
            text):
            name  = m.group(3).strip()
            ftype = m.group(4).strip()
            if name:
                onec_t, type_comment = map_field_type(ftype)
                fields.append({
                    'no': int(m.group(1)), 'name': name,
                    'type': ftype, 'type_raw': ftype,
                    'onec_type': onec_t, 'type_comment': type_comment,
                    'properties': self._extract_field_props(m.group(0)),
                })
        return fields

    def _extract_field_props(self, text: str) -> dict:
        props = {}
        for key in ('TableRelation','CalcFormula','FieldClass','Editable',
                    'BlankZero','CaptionML','Description','InitValue'):
            mm = re.search(rf'{key}\s*=\s*([^;}}]+)', text, re.IGNORECASE)
            if mm:
                v = mm.group(1).strip().rstrip(';').strip()
                if v:
                    props[key] = v
        return props

    def _normalise_field_types(self, obj: dict):
        for f in obj.get('fields', []):
            raw = f.get('type_raw', '')
            if re.search(r'\bOem(Code|Text)\b', raw, re.IGNORECASE):
                f['type']        = re.sub(r'\bOem(Code|Text)\b', r'\1', raw, flags=re.IGNORECASE)
                f['legacy_type'] = raw

    def _parse_keys(self, lines: list) -> list:
        keys = []
        for line in lines:
            m = re.match(r'\{\s*([^;]*?)\s*;\s*([^;]*?)(?:\s*;\s*(.*?))?\s*\}', line.strip())
            if m:
                keys.append({'enabled': m.group(1).strip(), 'fields': m.group(2).strip(),
                             'sum_fields': (m.group(3) or '').strip()})
        return keys

    def _parse_code(self, lines: list) -> tuple:
        triggers, procedures, raw = [], [], list(lines)
        cur_name, cur_type, cur_body, in_block, depth = None, None, [], False, 0
        for line in lines:
            s = line.strip()
            tm = re.match(r'^(ON\w+)\s*\(', s, re.IGNORECASE)
            pm = re.match(r'^(LOCAL\s+)?PROCEDURE\s+([A-Za-z_@][A-Za-z0-9_@]*)\s*[\(@]',
                          s, re.IGNORECASE)
            if tm or pm:
                if cur_name and cur_body:
                    e = {'name': cur_name, 'body': '\n'.join(cur_body)}
                    (triggers if cur_type == 'trigger' else procedures).append(e)
                cur_name  = tm.group(1) if tm else pm.group(2)
                cur_type  = 'trigger' if tm else 'procedure'
                cur_body  = [line]
                depth     = 0
                in_block  = True
            elif in_block:
                cur_body.append(line)
                depth += s.upper().count('BEGIN') - s.upper().count('END')
                if re.match(r'^END\s*[;.]?\s*$', s, re.IGNORECASE) and depth <= 0:
                    in_block = False
        if cur_name and cur_body:
            e = {'name': cur_name, 'body': '\n'.join(cur_body)}
            (triggers if cur_type == 'trigger' else procedures).append(e)
        return triggers, procedures, raw

    def _parse_controls(self, lines: list) -> list:
        controls = []
        for line in lines:
            m = re.match(r'\{\s*(\d+)\s*;\s*(\d+)\s*;\s*([^;]*?)\s*;', line.strip())
            if m:
                controls.append({'id': m.group(1), 'parent': m.group(2), 'type': m.group(3).strip()})
        return controls

    def _parse_report_sections(self, lines: list) -> list:
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
        objects, txt_parser, size = [], NavTxtParser(), len(data)
        markers  = [b'\x78\x9c', b'\x78\xda', b'\x78\x01', b'\x78\x5e']
        positions = sorted({i for marker in markers
                            for i in range(len(data))
                            if data[i:i+len(marker)] == marker})
        for pos in positions:
            for end in range(min(pos+100, size), size, 1024):
                try:
                    text = zlib.decompress(data[pos:end]).decode('utf-8', errors='replace')
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
            print('  [ПРЕДУПРЕЖДЕНИЕ] FOB: объекты не извлечены. Используйте .txt формат.')
        return unique


# ─────────────────────────────────────────────────────────────────────────────
# Markdown Generator
# ─────────────────────────────────────────────────────────────────────────────

class MarkdownGenerator:

    def __init__(self, analyse: bool = True, nav_version: str = 'auto'):
        self.analyse     = analyse
        self.nav_version = nav_version
        self.analyser    = CodeAnalyser()

    def generate(self, objects: list, source_files: list) -> str:
        analyses = {}
        if self.analyse:
            print('  Анализ объектов...', end='', flush=True)
            for obj in objects:
                analyses[(obj['type'], obj['id'])] = self.analyser.analyse_object(obj)
            print(f' готово ({len(analyses)} объектов)')

        lines = []
        lines += self._header(objects, source_files)
        lines += self._toc(objects)
        lines += self._summary_stats(objects, analyses)
        lines += self._migration_overview(objects, analyses)
        lines += self._onec_mapping_reference()

        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        for type_name in ['Table','Page','Codeunit','Report','XMLport',
                          'Query','Form','Dataport','MenuSuite']:
            if type_name in by_type:
                lines += self._type_section(
                    type_name,
                    sorted(by_type[type_name], key=lambda o: o['id']),
                    analyses)
        for t, objs in sorted(by_type.items()):
            if t not in ['Table','Page','Codeunit','Report','XMLport',
                         'Query','Form','Dataport','MenuSuite']:
                lines += self._type_section(t, sorted(objs, key=lambda o: o['id']), analyses)
        return '\n'.join(lines)

    # ── Шапка ─────────────────────────────────────────────────────────────────

    def _header(self, objects, source_files):
        nav_v = self.nav_version if self.nav_version != 'auto' else '2009–2015'
        return [
            '# Dynamics NAV — Документация для миграции на 1С',
            '',
            f'> **Сформировано:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  ',
            f'> **Версия NAV:** {nav_v}  ',
            f'> **Целевая платформа:** 1С (редакция уточняется)  ',
            f'> **Исходные файлы:** {", ".join(source_files)}  ',
            f'> **Всего объектов:** {len(objects)}',
            '',
            '> 📌 **Примечание:** Аналоги 1С указаны в общем виде, независимо от конкретной '
            'редакции (УП2, БП3, УТ11 и др.). При выборе редакции — уточнить маппинг '
            'под конкретную конфигурацию.',
            '',
            '---', '',
        ]

    def _toc(self, objects):
        lines = ['## Содержание', '']
        lines += [
            '1. [Сводная статистика](#сводная-статистика)',
            '2. [Обзор миграции](#обзор-миграции)',
            '3. [Матрица рисков и трудозатрат](#матрица-рисков-и-трудозатрат)',
            '4. [Справочник соответствий NAV → 1С](#справочник-соответствий-nav--1с)',
        ]
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)
        for i, t in enumerate(sorted(by_type.keys()), 5):
            lines.append(f'{i}. [{t}s ({len(by_type[t])})](#{t.lower()}s)')
        lines += ['', '---', '']
        return lines

    # ── Статистика ────────────────────────────────────────────────────────────

    def _summary_stats(self, objects, analyses):
        lines = ['## Сводная статистика', '']
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        risk_map = {'Table':'🟡','Page':'🟡','Codeunit':'🟡','Report':'🔴',
                    'Form':'🔴','Dataport':'🔴','XMLport':'🟡','Query':'🟢','MenuSuite':'🟢'}

        lines.append('| Тип объекта | Кол-во | Аналог в 1С | Сложность | Оценка (ч) |')
        lines.append('|---|---|---|---|---|')
        grand_h = 0
        for t in sorted(by_type.keys()):
            objs  = by_type[t]
            hours = sum(analyses.get((o['type'],o['id']),{}).get('effort_hours',0) for o in objs)
            grand_h += hours
            icon  = risk_map.get(t, '🟡')
            onec  = ONEC_MAPPING.get(t, {}).get('analogue', '?')
            lines.append(f'| {t} | {len(objs)} | {onec} | {icon} | ~{hours}ч |')
        lines.append(f'| **Итого** | **{len(objects)}** | | | **~{grand_h}ч** |')
        lines.append('')

        tables = by_type.get('Table', [])
        if tables:
            tf  = sum(len(t.get('fields',[])) for t in tables)
            oem = sum(1 for t in tables for f in t.get('fields',[]) if f.get('legacy_type'))
            lines.append(f'- **Таблицы:** {len(tables)} таблиц, {tf} полей'
                         + (f', ⚠️ {oem} полей с устаревшим типом OemCode/OemText' if oem else ''))
        cus = by_type.get('Codeunit', [])
        if cus:
            tp = sum(len(c.get('procedures',[])) for c in cus)
            lines.append(f'- **Codeunit-ы:** {tp} процедур в {len(cus)} объектах')
        if analyses:
            total_depr = sum(len(a.get('deprecated_hits',[])) for a in analyses.values())
            if total_depr:
                lines.append(f'- ⚠️ **Устаревших вызовов C/AL:** {total_depr} — требуют замены при переносе')
        lines += ['', '---', '']
        return lines

    def _migration_overview(self, objects, analyses):
        lines = ['## Обзор миграции', '']
        by_type = defaultdict(list)
        for obj in objects:
            by_type[obj['type']].append(obj)

        groups = [
            ('🔴 Высокий приоритет', ['Form','Dataport','Report'],
             'Нет прямого аналога или требуется полный редизайн.'),
            ('🟡 Средний приоритет', ['Table','Codeunit','Page','XMLport','MenuSuite'],
             'Есть аналоги в 1С, требуется анализ и адаптация.'),
            ('🟢 Низкий приоритет', ['Query'],
             'Прямые аналоги в 1С, минимальные изменения.'),
        ]
        for label, types, note in groups:
            relevant = [(t, by_type[t]) for t in types if t in by_type]
            if not relevant:
                continue
            lines.append(f'### {label}')
            lines.append(f'_{note}_')
            lines.append('')
            for t, objs in relevant:
                onec  = ONEC_MAPPING.get(t, {}).get('analogue', '?')
                names = ', '.join(f'`{o["name"]}`' for o in objs[:5])
                more  = f' …ещё {len(objs)-5}' if len(objs) > 5 else ''
                lines.append(f'- **{t} ({len(objs)}) → {onec}:** {names}{more}')
            lines.append('')

        lines += ['---', '']

        # Матрица рисков
        lines += ['## Матрица рисков и трудозатрат', '']
        lines.append('| Объект | Тип | Аналог 1С | Риск | Часы | Устар. | Зависимости |')
        lines.append('|---|---|---|---|---|---|---|')
        rows = []
        for obj in objects:
            a    = analyses.get((obj['type'], obj['id']), {})
            risk = a.get('migration_risk', '—')
            icon = {'Высокий':'🔴','Средний':'🟡','Низкий':'🟢'}.get(risk,'—')
            h    = a.get('effort_hours','—')
            dc   = len(a.get('deprecated_hits',[]))
            deps = '; '.join(f'{d["kind"]}:{d["name"]}' for d in a.get('dependencies',[])[:3])
            onec = ONEC_MAPPING.get(obj['type'],{}).get('analogue','?')
            rows.append((h if isinstance(h,int) else 0, obj, icon, risk, h, dc, deps, onec))
        for _, obj, icon, risk, h, dc, deps, onec in sorted(rows, key=lambda x:-x[0]):
            lines.append(f'| {obj["name"]} | {obj["type"]} | {onec} | {icon} {risk} | ~{h}ч | {dc} | {deps or "—"} |')
        lines += ['', '---', '']
        return lines

    # ── Справочник NAV → 1С ───────────────────────────────────────────────────

    def _onec_mapping_reference(self):
        lines = ['## Справочник соответствий NAV → 1С', '',
                 '_Общий маппинг, не зависящий от конкретной редакции 1С. '
                 'При выборе редакции уточнить под конкретную конфигурацию._',
                 '']
        lines.append('| Тип NAV | Аналог в 1С | Описание | Действие | Риск |')
        lines.append('|---|---|---|---|---|')
        for t, m in ONEC_MAPPING.items():
            icon = {'High':'🔴','Medium':'🟡','Low':'🟢'}.get(m.get('risk','Medium'),'🟡')
            desc = m['description'].replace('\n',' ')[:80]
            act  = m['action'].replace('\n',' ')[:80]
            lines.append(f'| {t} | {m["analogue"]} | {desc} | {act} | {icon} |')
        lines.append('')

        # Типы полей
        lines += ['### Соответствие типов данных полей', '']
        lines.append('| Тип NAV | Тип 1С | Примечание |')
        lines.append('|---|---|---|')
        for pat, (onec_t, comment) in FIELD_TYPE_MAPPING.items():
            nav_t = re.sub(r'\\[sd\+*?]+|\(.*?\)|\[.*?\]|\\b', '', pat).strip()
            lines.append(f'| {nav_t} | {onec_t} | {comment} |')
        lines += ['', '---', '']
        return lines

    # ── Секция по типу ────────────────────────────────────────────────────────

    def _type_section(self, type_name, objects, analyses):
        mapping = ONEC_MAPPING.get(type_name, {})
        lines   = [f'## {type_name}s', '']
        if mapping:
            lines.append(f'> **Аналог в 1С:** {mapping.get("analogue","?")}  ')
            lines.append(f'> {mapping.get("description","")}')
            lines.append('')
        for obj in objects:
            a = analyses.get((obj['type'], obj['id']), {})
            lines += self._object_section(obj, a)
        lines += ['---', '']
        return lines

    # ── Секция одного объекта ─────────────────────────────────────────────────

    def _object_section(self, obj: dict, a: dict) -> list:
        lines     = []
        type_name = obj['type']
        risk      = a.get('migration_risk','')
        icon      = {'Высокий':'🔴','Средний':'🟡','Низкий':'🟢'}.get(risk,'')
        effort    = a.get('effort_hours','')
        onec      = ONEC_MAPPING.get(type_name,{}).get('analogue','?')

        lines.append(f'### {type_name} {obj["id"]}: {obj["name"]}')
        meta = []
        if obj.get('modified_date'): meta.append(f'Изменено: `{obj["modified_date"]}`')
        if obj.get('version_list'):  meta.append(f'Версия: `{obj["version_list"]}`')
        if risk:    meta.append(f'Риск: {icon} {risk}')
        if effort:  meta.append(f'Оценка: ~{effort}ч')
        meta.append(f'1С-аналог: **{onec}**')
        if meta:
            lines.append('  '.join(f'_{m}_' for m in meta))
        lines.append('')

        # Описание алгоритма
        summary = a.get('algorithm_summary','')
        if summary:
            lines += ['#### 📋 Описание алгоритма', '', summary, '']

        # Заметки для ролей
        notes = a.get('onec_notes', {})
        if any(notes.values()):
            lines += ['#### 🚦 Заметки по миграции на 1С', '']
            for role, icon_r, key in [
                ('🏗️ Архитектор', '', 'architect'),
                ('💻 Разработчик', '', 'developer'),
                ('📋 Проект-менеджер', '', 'pm'),
            ]:
                if notes.get(key):
                    lines.append('<details>')
                    lines.append(f'<summary>{role}</summary>')
                    lines.append('')
                    lines.append(notes[key])
                    lines.append('')
                    lines.append('</details>')
                    lines.append('')

        # Свойства
        props = obj.get('properties', {})
        shown = {k:v for k,v in props.items()
                 if k in ('Description','CaptionML','DataCaptionFields','LookupPageID',
                           'DrillDownPageID','TableType','SubType','RunObject',
                           'Permissions','SourceTable','PageType') and v}
        if shown:
            lines += ['#### Свойства', '',
                      '| Свойство | Значение |', '|---|---|']
            for k,v in shown.items():
                lines.append(f'| {k} | `{v}` |')
            lines.append('')

        # Устаревшие вызовы
        depr = a.get('deprecated_hits', [])
        if depr:
            lines += ['#### ⚠️ Устаревшие вызовы C/AL', '',
                      '| Паттерн | Действие при миграции на 1С |', '|---|---|']
            for d in depr:
                lines.append(f'| `{d["pattern"]}` | {d["advice"]} |')
            lines.append('')

        # Зависимости
        deps = a.get('dependencies', [])
        if deps:
            lines += ['#### 🔗 Зависимости', '',
                      '| Тип | Имя | Операция |', '|---|---|---|']
            for d in deps:
                lines.append(f'| {d["kind"]} | `{d["name"]}` | {d["op"]} |')
            lines.append('')

        # Поля (Tables)
        fields = obj.get('fields', [])
        if fields:
            oem_c = sum(1 for f in fields if f.get('legacy_type'))
            lbl   = f'**Поля** ({len(fields)} всего{f", ⚠️ {oem_c} с устаревшим типом" if oem_c else ""}):'
            lines += [lbl, '',
                      '| № | Имя поля | Тип NAV | Тип 1С | Устар. | Свойства |',
                      '|---|---|---|---|---|---|']
            for f in fields:
                fprops = '; '.join(f'{k}={v}' for k,v in f.get('properties',{}).items()
                                   if k in ('TableRelation','CalcFormula','FieldClass','Editable'))
                legacy = f.get('legacy_type','')
                lines.append(
                    f'| {f["no"]} | `{f["name"]}` | {f["type"]} | {f.get("onec_type","?")} | '
                    f'{"⚠️ `"+legacy+"`" if legacy else "—"} | {fprops or "—"} |'
                )
            lines.append('')

        # Ключи
        keys = obj.get('keys', [])
        if keys:
            lines += ['**Ключи / Индексы:**', '',
                      '| Активен | Поля | SumIndex |', '|---|---|---|']
            for k in keys:
                lines.append(f'| {k["enabled"]} | `{k["fields"]}` | {k["sum_fields"] or "—"} |')
            lines.append('')

        # Глобальные переменные
        gv = a.get('global_vars', [])
        if gv:
            lines += ['#### Глобальные переменные', '',
                      '| Имя | Тип NAV | Тип 1С | Описание |', '|---|---|---|---|']
            for v in gv:
                lines.append(f'| `{v["name"]}` | {v["nav_type"]} | {v["onec_type"]} | {v.get("description","")} |')
            lines.append('')

        # Структура данных отчёта
        ds = a.get('report_dataset', [])
        if ds:
            lines += ['#### 📊 Структура данных отчёта (для СКД 1С)', '',
                      '_Используется при воссоздании отчёта в СКД или программным способом._',
                      '',
                      '| Вид | ID | Имя / Колонка | Источник |', '|---|---|---|---|']
            for item in ds:
                lines.append(f'| {item["kind"]} | {item["id"]} | `{item["name"]}` | {item["source"]} |')
            lines.append('')
            lines.append('> **1С СКД:** DataItem → Набор данных (Запрос). Column → Поле набора данных.')
            lines.append('')

        # NAV 2009: классические секции отчёта
        sec09 = obj.get('report_sections', [])
        if sec09:
            lines += ['**Классические секции отчёта (NAV 2009):**', '',
                      '| ID | Вид | Имя |', '|---|---|---|']
            for s in sec09:
                lines.append(f'| {s["id"]} | {s["kind"]} | {s["name"]} |')
            lines.append('')
            lines.append('> В 1С воссоздать как макет СКД или табличный документ.')
            lines.append('')

        # RequestForm (NAV 2009)
        rf = obj.get('request_form', [])
        if rf:
            lines += ['**RequestForm (NAV 2009)** — в 1С: параметры СКД или форма отчёта:', '',
                      '| ID | Родитель | Тип |', '|---|---|---|']
            for c in rf[:20]:
                lines.append(f'| {c["id"]} | {c["parent"]} | {c["type"]} |')
            lines.append('')

        # Элементы управления
        controls = obj.get('controls', [])
        if controls:
            lines.append(f'**Элементы управления** ({len(controls)} всего):')
            lines.append('')
            lines.append('| ID | Родитель | Тип |')
            lines.append('|---|---|---|')
            for c in controls[:30]:
                lines.append(f'| {c["id"]} | {c["parent"]} | {c["type"]} |')
            if len(controls) > 30:
                lines.append(f'| … | … | _{len(controls)-30} ещё_ |')
            lines.append('')

        # Процедуры и триггеры
        procs = a.get('procedures_detail', [])
        if procs:
            lines += [f'#### Процедуры и триггеры ({len(procs)} всего)', '',
                      '| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |',
                      '|---|---|---|---|---|---|---|']
            for p in procs:
                params_s = ', '.join(f'`{x["name"]}`:{x["onec_type"]}({x["direction"]})' for x in p['params'][:2])
                dep_flag = '⚠️' if p.get('deprecated') else '✅'
                lines.append(
                    f'| `{p["name"]}` | {p["kind"]} | {params_s or "—"} | '
                    f'`{p["return_nav"] or "—"}` | {p["return_1c"] or "—"} | {p["loc"]} | {dep_flag} |'
                )
            lines.append('')

            for p in procs:
                lines.append('<details>')
                icon_p = '🔔' if p['kind'] == 'trigger' else '⚙️'
                lines.append(f'<summary>{icon_p} <code>{p["name"]}</code> — {p["summary"][:90]}</summary>')
                lines.append('')
                if p['params']:
                    lines += ['**Параметры:**', '',
                               '| Имя | Тип NAV | Тип 1С | Направление |', '|---|---|---|---|']
                    for pr in p['params']:
                        lines.append(f'| `{pr["name"]}` | {pr["nav_type"]} | {pr["onec_type"]} | {pr["direction"]} |')
                    lines.append('')
                if p['return_nav']:
                    lines.append(f'**Возвращаемый тип NAV:** `{p["return_nav"]}` → **1С:** {p["return_1c"]}')
                    lines.append('')
                if p['local_vars']:
                    lines += ['**Локальные переменные:**', '',
                               '| Имя | Тип NAV | Тип 1С | Описание |', '|---|---|---|---|']
                    for v in p['local_vars']:
                        lines.append(f'| `{v["name"]}` | {v["nav_type"]} | {v["onec_type"]} | {v.get("description","")} |')
                    lines.append('')
                if p.get('deprecated'):
                    lines.append('**⚠️ Устаревшие вызовы в этом блоке:**')
                    for d in p['deprecated']:
                        lines.append(f'- `{d["pattern"]}` → {d["advice"]}')
                    lines.append('')
                lines += ['**Код C/AL:**', '', '```cal',
                           p['body'].strip()[:3000] + ('…' if len(p['body']) > 3000 else ''),
                           '```', '', '</details>', '']

        lines.append('')
        return lines


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cli = argparse.ArgumentParser(
        description='NAV Object Parser → Документация для миграции на 1С (NAV 2009–2015)'
    )
    cli.add_argument('--txt',         nargs='+')
    cli.add_argument('--fob',         nargs='+')
    cli.add_argument('--dir')
    cli.add_argument('--output',      default='nav_documentation.md')
    cli.add_argument('--nav-version', default='auto',
                     choices=['auto','2009','2013','2015'])
    cli.add_argument('--encoding',    default=None)
    cli.add_argument('--no-analyse',  action='store_true')
    args = cli.parse_args()

    txt_files = list(args.txt or [])
    fob_files = list(args.fob or [])
    if args.dir:
        d = Path(args.dir)
        txt_files += [str(p) for p in d.glob('*.txt')]
        fob_files += [str(p) for p in d.glob('*.fob')]
    if not txt_files and not fob_files:
        print('ОШИБКА: укажите --txt, --fob или --dir')
        cli.print_help()
        sys.exit(1)

    nav_ver    = getattr(args, 'nav_version', 'auto')
    txt_parser = NavTxtParser(nav_version=nav_ver)
    fob_parser = NavFobParser()
    all_objs   = []
    sources    = []

    for f in txt_files:
        if not os.path.exists(f):
            print(f'[ПРОПУСК] {f}')
            continue
        print(f'Парсинг TXT: {f}')
        try:
            objs = txt_parser.parse_file(f, encoding=args.encoding)
            print(f'  → {len(objs)} объектов')
            all_objs.extend(objs)
            sources.append(os.path.basename(f))
        except Exception as e:
            print(f'  [ОШИБКА] {e}')

    for f in fob_files:
        if not os.path.exists(f):
            print(f'[ПРОПУСК] {f}')
            continue
        print(f'Парсинг FOB: {f}')
        try:
            objs = fob_parser.parse_file(f)
            print(f'  → {len(objs)} объектов')
            all_objs.extend(objs)
            sources.append(os.path.basename(f))
        except Exception as e:
            print(f'  [ОШИБКА] {e}')

    if not all_objs:
        print('Объекты не найдены.')
        sys.exit(1)

    seen, unique = {}, []
    for obj in all_objs:
        k = (obj['type'], obj['id'])
        if k not in seen:
            seen[k] = obj
            unique.append(obj)

    print(f'\nУникальных объектов: {len(unique)}')
    print('Формирование документации...')

    gen = MarkdownGenerator(analyse=not args.no_analyse, nav_version=nav_ver)
    md  = gen.generate(unique, sources or ['(неизвестно)'])

    with open(args.output, 'w', encoding='utf-8') as fout:
        fout.write(md)

    print(f'✅ Готово: {args.output}  ({os.path.getsize(args.output):,} байт)')


if __name__ == '__main__':
    main()