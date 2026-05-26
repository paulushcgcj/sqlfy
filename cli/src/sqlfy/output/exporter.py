"""
sqlfy.exporter
==============
Self-contained HTML schema documentation generator.

Produces a single .html file with no external dependencies that contains:
  - Searchable, filterable table list with column details
  - Inline SVG ERD (relationship diagram)
  - Insights summary panel (errors/warnings from InsightsEngine)
  - Migration history timeline
  - Full-text search across tables and columns
  - Dark/light mode toggle

The output is a single file you can open in any browser, email, or
commit to your repo as living documentation.

Usage
-----
    from cli.exporter import Exporter

    state   = SchemaStateBuilder.from_graph(reconstruct(files))
    report  = InsightsEngine.analyse(state)
    grapher = Grapher()
    svg     = Grapher.to_dot(state)   # we use our own inline SVG builder

    html = Exporter.to_html(state, report)
    Path('schema_docs.html').write_text(html)
"""

from __future__ import annotations

import json
import html as html_mod
from ..domain.schema_state import SchemaState, TableState
from ..analysis.insights import InsightsReport, Finding
from .grapher import Grapher


def _e(s: object) -> str:
    """HTML-escape a value."""
    return html_mod.escape(str(s or ''))


class Exporter:

    @staticmethod
    def to_html(
        state:  SchemaState,
        report: InsightsReport | None = None,
        title:  str = '',
    ) -> str:
        doc_title  = title or f'Schema Documentation — V{state.version}'
        stats      = state.stats
        mermaid    = Grapher.to_mermaid(state, title=doc_title)
        tables_json = json.dumps(Exporter._tables_for_js(state), ensure_ascii=False)
        findings_json = json.dumps(
            [f.to_dict() for f in (report.findings if report else [])],
            ensure_ascii=False
        )

        errors   = len(report.errors())   if report else 0
        warnings = len(report.warnings()) if report else 0
        infos    = len(report.infos())    if report else 0
        health   = '✓ Healthy' if (errors == 0 and warnings == 0) else (
                   f'✖ {errors} error{"s" if errors != 1 else ""}' if errors else
                   f'⚠ {warnings} warning{"s" if warnings != 1 else ""}')
        health_cls = 'healthy' if errors == 0 and warnings == 0 else (
                     'errored' if errors else 'warned')

        migration_rows = ''.join(
            f'<tr><td class="ver">V{_e(m.version)}</td>'
            f'<td class="desc">{_e(m.description)}</td></tr>'
            for m in state.migration_history
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{_e(doc_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {{
  --bg:   #f8f7ff; --bg2: #ffffff; --bg3: #f3f0ff;
  --txt:  #111827; --txt2: #4b5563; --txt3: #9ca3af;
  --brd:  rgba(0,0,0,.12); --brd2: rgba(0,0,0,.06);
  --acc:  #7c3aed; --acc2: rgba(124,58,237,.10);
  --err:  #dc2626; --warn: #d97706; --ok: #059669;
  --fk:   #0891b2;
}}
[data-theme=dark] {{
  --bg:  #0f172a; --bg2: #1e2235; --bg3: #1a1040;
  --txt: #f1f5f9; --txt2: #94a3b8; --txt3: #64748b;
  --brd: rgba(255,255,255,.10); --brd2: rgba(255,255,255,.05);
}}
*,::before,::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',system-ui,sans-serif;font-size:13px;background:var(--bg);color:var(--txt);line-height:1.5}}
a{{color:var(--acc);text-decoration:none}}
/* ── Layout ── */
.shell{{display:flex;height:100vh;overflow:hidden}}
.sidebar{{width:240px;flex-shrink:0;background:var(--bg2);border-right:1px solid var(--brd);display:flex;flex-direction:column;overflow:hidden}}
.main{{flex:1;overflow:auto}}
/* ── Topbar ── */
.topbar{{padding:14px 16px;border-bottom:1px solid var(--brd);background:var(--bg2)}}
.logo{{display:flex;align-items:center;gap:8px;margin-bottom:4px}}
.logo-dot{{width:18px;height:18px;border-radius:50%;background:var(--acc);opacity:.8}}
.logo-name{{font-weight:600;font-size:15px;color:var(--acc)}}
.logo-ver{{font-size:11px;color:var(--txt3)}}
.health{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:4px;margin-top:4px}}
.healthy{{background:rgba(5,150,105,.1);color:var(--ok)}}
.errored{{background:rgba(220,38,38,.1);color:var(--err)}}
.warned {{background:rgba(217,119,6,.1); color:var(--warn)}}
/* ── Search ── */
.search-wrap{{padding:10px 12px;border-bottom:1px solid var(--brd)}}
.search{{width:100%;padding:6px 10px;border:1px solid var(--brd);border-radius:6px;background:var(--bg);color:var(--txt);font-size:12px;outline:none}}
.search:focus{{border-color:var(--acc)}}
/* ── Nav ── */
.nav{{flex:1;overflow-y:auto;padding:8px 0}}
.nav-sect{{font-size:10px;color:var(--txt3);padding:10px 12px 4px;text-transform:uppercase;letter-spacing:.08em}}
.nav-item{{display:block;padding:6px 14px;cursor:pointer;font-size:12px;color:var(--txt2);border-left:2px solid transparent;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.nav-item:hover{{color:var(--txt);background:var(--brd2)}}
.nav-item.active{{color:var(--acc);border-left-color:var(--acc);background:var(--acc2)}}
.nav-item .badge{{float:right;font-size:10px;color:var(--txt3)}}
/* ── Theme toggle ── */
.theme-btn{{margin:10px 12px;padding:5px 10px;border:1px solid var(--brd);border-radius:6px;background:none;color:var(--txt2);cursor:pointer;font-size:11px;width:calc(100% - 24px)}}
/* ── Main content ── */
.content{{padding:24px 32px;max-width:1100px}}
/* ── Section ── */
.section{{margin-bottom:40px;scroll-margin-top:20px}}
.section-title{{font-size:18px;font-weight:600;margin-bottom:6px;color:var(--txt)}}
.section-sub{{font-size:13px;color:var(--txt2);margin-bottom:16px}}
/* ── Stats grid ── */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:24px}}
.stat{{background:var(--bg2);border:1px solid var(--brd);border-radius:8px;padding:14px 16px}}
.stat-val{{font-size:24px;font-weight:700;color:var(--acc)}}
.stat-lbl{{font-size:11px;color:var(--txt3);margin-top:2px}}
/* ── Table card ── */
.table-card{{background:var(--bg2);border:1px solid var(--brd);border-radius:10px;margin-bottom:20px;overflow:hidden;display:none}}
.table-card.visible{{display:block}}
.tc-head{{padding:14px 18px;border-bottom:1px solid var(--brd);display:flex;align-items:center;gap:10px}}
.tc-name{{font-weight:600;font-size:15px}}
.tc-schema{{font-size:11px;color:var(--txt3)}}
.tc-comment{{font-size:12px;color:var(--txt2);font-style:italic;margin-top:2px}}
.tc-meta{{margin-left:auto;font-size:11px;color:var(--txt3)}}
/* ── Column table ── */
.col-tbl{{width:100%;border-collapse:collapse;font-size:12px}}
.col-tbl th{{padding:7px 16px;text-align:left;font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--brd);background:var(--bg3)}}
.col-tbl td{{padding:7px 16px;border-bottom:1px solid var(--brd2)}}
.col-tbl tr:last-child td{{border-bottom:none}}
.col-tbl tr:hover td{{background:var(--brd2)}}
.type{{color:#0891b2;font-family:monospace}}
.badge-pk{{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(124,58,237,.12);color:var(--acc);border:1px solid rgba(124,58,237,.2)}}
.badge-fk{{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(8,145,178,.10);color:#0891b2;border:1px solid rgba(8,145,178,.2)}}
.badge-uq{{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(5,150,105,.10);color:#059669;border:1px solid rgba(5,150,105,.2)}}
.badge-nn{{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(220,38,38,.08);color:var(--err);border:1px solid rgba(220,38,38,.2)}}
.cmt{{font-size:11px;color:var(--txt3);font-style:italic}}
/* ── Index table ── */
.idx-tbl{{width:100%;border-collapse:collapse;font-size:12px;border-top:1px solid var(--brd)}}
.idx-tbl td{{padding:5px 16px;border-bottom:1px solid var(--brd2)}}
.idx-tbl tr:last-child td{{border-bottom:none}}
/* ── Relationships ── */
.rel-list{{display:flex;flex-direction:column;gap:6px}}
.rel-row{{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg2);border:1px solid var(--brd);border-radius:6px;font-size:12px}}
.rel-from{{font-weight:500}}
.rel-arrow{{color:var(--warn);font-size:16px}}
.rel-to{{color:var(--fk)}}
.rel-od{{font-size:10px;color:var(--txt3);margin-left:auto}}
/* ── Insights ── */
.ins-grid{{display:flex;flex-direction:column;gap:8px}}
.ins-row{{display:flex;gap:10px;padding:10px 14px;border-radius:8px;border:1px solid var(--brd);font-size:12px}}
.ins-row.error{{border-left:3px solid var(--err);background:rgba(220,38,38,.04)}}
.ins-row.warning{{border-left:3px solid var(--warn);background:rgba(217,119,6,.04)}}
.ins-row.info{{border-left:3px solid #60a5fa;background:rgba(96,165,250,.04)}}
.ins-code{{font-family:monospace;font-size:11px;padding:1px 6px;background:var(--brd2);border-radius:3px;white-space:nowrap}}
.ins-msg{{flex:1}}
.ins-fix{{font-size:11px;color:var(--txt3);margin-top:3px}}
/* ── Migration timeline ── */
.mig-tbl{{width:100%;border-collapse:collapse;font-size:12px}}
.mig-tbl td{{padding:7px 16px;border-bottom:1px solid var(--brd2)}}
.mig-tbl tr:last-child td{{border-bottom:none}}
.ver{{font-family:monospace;color:var(--acc);font-weight:500;width:80px}}
/* ── ERD ── */
.mermaid-wrap{{background:var(--bg2);border:1px solid var(--brd);border-radius:10px;padding:20px;overflow:auto}}
.mermaid{{min-width:400px}}
/* ── Footer ── */
.footer{{padding:20px 0;color:var(--txt3);font-size:11px;border-top:1px solid var(--brd);margin-top:40px}}
</style>
</head>
<body data-theme="light">

<div class="shell">
<!-- ── Sidebar ── -->
<div class="sidebar">
  <div class="topbar">
    <div class="logo">
      <div class="logo-dot"></div>
      <span class="logo-name">sqlfy</span>
      <span class="logo-ver">V{_e(state.version)}</span>
    </div>
    <span class="health {health_cls}">{_e(health)}</span>
  </div>

  <div class="search-wrap">
    <input class="search" type="search" placeholder="Search tables…" id="searchInput"
           oninput="filterTables(this.value)"/>
  </div>

  <nav class="nav" id="nav">
    <div class="nav-sect">Overview</div>
    <div class="nav-item active" onclick="showSection('overview', this)">
      Summary <span class="badge">{stats['table_count']} tables</span>
    </div>
    <div class="nav-item" onclick="showSection('erd', this)">
      ERD Diagram
    </div>
    {f'<div class="nav-item" onclick="showSection(&apos;insights&apos;, this)">Insights <span class="badge">{errors+warnings+infos}</span></div>' if report else ''}
    <div class="nav-item" onclick="showSection('history', this)">Migration History</div>

    <div class="nav-sect">Tables ({stats['table_count']})</div>
    {''.join(
      f'<div class="nav-item table-nav" data-target="tbl-{_e(t.full_name.replace(".", "-"))}" '
      f'onclick="scrollToTable(&apos;{_e(t.full_name)}&apos;, this)">'
      f'{_e(t.name)} <span class="badge">{len(t.columns)}c</span></div>'
      for t in state.tables.values()
    )}
  </nav>

  <button class="theme-btn" onclick="toggleTheme()">☀ Toggle theme</button>
</div>

<!-- ── Main ── -->
<div class="main">
<div class="content">

<!-- Overview -->
<div class="section" id="section-overview">
  <div class="section-title">{_e(doc_title)}</div>
  <div class="section-sub">
    Generated {_e(state.generated_at)} · Fingerprint <code>{_e(state.fingerprint)}</code> · Dialect {_e(state.dialect)}
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-val">{stats['table_count']}</div><div class="stat-lbl">Tables</div></div>
    <div class="stat"><div class="stat-val">{stats['column_count']}</div><div class="stat-lbl">Columns</div></div>
    <div class="stat"><div class="stat-val">{stats['relationship_count']}</div><div class="stat-lbl">Relationships</div></div>
    <div class="stat"><div class="stat-val">{stats['index_count']}</div><div class="stat-lbl">Indexes</div></div>
    <div class="stat"><div class="stat-val">{stats['migration_count']}</div><div class="stat-lbl">Migrations</div></div>
    <div class="stat"><div class="stat-val">{stats.get('tables_without_pk', 0)}</div><div class="stat-lbl">Missing PK</div></div>
  </div>
</div>

<!-- Table cards (always rendered, shown/hidden via JS) -->
<div id="tables-section">
{''.join(Exporter._table_card(t, state) for t in state.tables.values())}
</div>

<!-- ERD -->
<div class="section" id="section-erd" style="display:none">
  <div class="section-title">ERD Diagram</div>
  <div class="section-sub">Entity–relationship diagram — rendered from Mermaid</div>
  <div class="mermaid-wrap">
    <div class="mermaid">
{_e(mermaid)}
    </div>
  </div>
</div>

<!-- Insights -->
{Exporter._insights_section(report) if report else ''}

<!-- Relationships -->
<div class="section" id="section-rels" style="display:none">
  <div class="section-title">Relationships</div>
  <div class="rel-list">
    {''.join(
      f'<div class="rel-row">'
      f'<span class="rel-from">{_e(r.from_table)}</span>'
      f'<span class="rel-arrow">──FK──▶</span>'
      f'<span class="rel-to">{_e(r.to_table)}</span>'
      f'<span style="font-size:11px;color:var(--txt3)">{_e(", ".join(r.from_columns))} → {_e(", ".join(r.to_columns))}</span>'
      f'{"<span class=rel-od>ON DELETE " + _e(r.on_delete) + "</span>" if r.on_delete else ""}'
      f'</div>'
      for r in state.relationships
    ) or '<div style="color:var(--txt3);padding:8px">No FK relationships.</div>'}
  </div>
</div>

<!-- Migration history -->
<div class="section" id="section-history" style="display:none">
  <div class="section-title">Migration History</div>
  <table class="mig-tbl">
    {migration_rows or '<tr><td>No migrations recorded.</td></tr>'}
  </table>
</div>

<div class="footer">
  Generated by sqlfy · V{_e(state.version)} · {_e(state.generated_at)}
</div>
</div><!-- /content -->
</div><!-- /main -->
</div><!-- /shell -->

<script>
const TABLES = {tables_json};
const FINDINGS = {findings_json};

// ── Mermaid ──────────────────────────────────────────────────────
mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});

// ── Theme ────────────────────────────────────────────────────────
function toggleTheme() {{
  const el = document.body;
  el.dataset.theme = el.dataset.theme === 'dark' ? 'light' : 'dark';
}}

// ── Section navigation ───────────────────────────────────────────
let activeNavItem = document.querySelector('.nav-item.active');

function showSection(id, navEl) {{
  // Hide all sections except overview stats + table cards
  ['erd','insights','history','rels'].forEach(s => {{
    const el = document.getElementById('section-' + s);
    if (el) el.style.display = 'none';
  }});
  document.getElementById('section-overview').style.display = '';
  document.getElementById('tables-section').style.display = 'none';

  if (id === 'overview') {{
    document.getElementById('tables-section').style.display = '';
    filterTables(document.getElementById('searchInput').value);
  }} else {{
    const sec = document.getElementById('section-' + id);
    if (sec) sec.style.display = '';
  }}

  if (activeNavItem) activeNavItem.classList.remove('active');
  if (navEl) {{ navEl.classList.add('active'); activeNavItem = navEl; }}
}}

// ── Table search ─────────────────────────────────────────────────
function filterTables(q) {{
  const query = (q || '').toLowerCase().trim();
  document.querySelectorAll('.table-card').forEach(card => {{
    const match = !query ||
      card.dataset.name.toLowerCase().includes(query) ||
      card.dataset.cols.toLowerCase().includes(query);
    card.classList.toggle('visible', match);
  }});
  document.querySelectorAll('.table-nav').forEach(nav => {{
    const tgt = nav.dataset.target || '';
    const card = document.getElementById(tgt);
    nav.style.display = card && card.classList.contains('visible') ? '' : 'none';
  }});
}}

function scrollToTable(fullName, navEl) {{
  showSection('overview', navEl);
  document.getElementById('tables-section').style.display = '';
  // show all cards, then scroll
  document.querySelectorAll('.table-card').forEach(c => c.classList.add('visible'));
  const id = 'tbl-' + fullName.replace('.', '-');
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

// ── Init ─────────────────────────────────────────────────────────
document.querySelectorAll('.table-card').forEach(c => c.classList.add('visible'));
</script>
</body>
</html>"""

    @staticmethod
    def _table_card(t: TableState, state: SchemaState) -> str:
        rels_out = [r for r in state.relationships if r.from_table == t.full_name]
        rels_in  = [r for r in state.relationships if r.to_table   == t.full_name]
        col_names = ' '.join(c.name for c in t.columns)
        card_id   = f'tbl-{t.full_name.replace(".", "-")}'

        col_rows = ''
        for col in t.columns:
            badges = ''
            if col.is_pk:     badges += '<span class="badge-pk">PK</span> '
            if col.is_fk:     badges += '<span class="badge-fk">FK</span> '
            if col.is_unique: badges += '<span class="badge-uq">UQ</span> '
            if not col.nullable: badges += '<span class="badge-nn">NN</span>'
            cmt = f'<div class="cmt">{_e(col.comment)}</div>' if col.comment else ''
            col_rows += (
                f'<tr>'
                f'<td>{_e(col.name)}</td>'
                f'<td class="type">{_e(col.data_type)}</td>'
                f'<td>{badges}</td>'
                f'<td>{_e(col.default) if col.default else ""}</td>'
                f'<td>{cmt}</td>'
                f'</tr>'
            )

        idx_rows = ''
        for idx in t.indexes:
            uq = '<span class="badge-uq">UNIQUE</span>' if idx.unique else ''
            idx_rows += (
                f'<tr>'
                f'<td>{_e(idx.name)}</td>'
                f'<td>{_e(", ".join(idx.columns))}</td>'
                f'<td>{uq}</td>'
                f'<td style="color:var(--txt3)">[V{_e(idx.created_in)}]</td>'
                f'</tr>'
            )

        rel_rows = ''
        for r in rels_out:
            od = f' <span style="color:var(--txt3)">ON DELETE {_e(r.on_delete)}</span>' if r.on_delete else ''
            rel_rows += (
                f'<tr><td>▶</td>'
                f'<td>{_e(r.constraint_name or "")}</td>'
                f'<td><code>{_e(", ".join(r.from_columns))}</code> → '
                f'<a href="#" onclick="scrollToTable(&apos;{_e(r.to_table)}&apos;,null);return false">'
                f'{_e(r.to_table)}</a>.<code>{_e(", ".join(r.to_columns))}</code>{od}</td>'
                f'</tr>'
            )
        for r in rels_in:
            rel_rows += (
                f'<tr><td>◀</td>'
                f'<td>{_e(r.constraint_name or "")}</td>'
                f'<td><a href="#" onclick="scrollToTable(&apos;{_e(r.from_table)}&apos;,null);return false">'
                f'{_e(r.from_table)}</a>.<code>{_e(", ".join(r.from_columns))}</code> → '
                f'<code>{_e(", ".join(r.to_columns))}</code></td>'
                f'</tr>'
            )

        comment_html = f'<div class="tc-comment">{_e(t.comment)}</div>' if t.comment else ''
        mod_html     = f' · modified V{_e(", ".join(t.modified_in))}' if t.modified_in else ''

        return f"""
<div class="table-card" id="{card_id}" data-name="{_e(t.full_name)}" data-cols="{_e(col_names)}">
  <div class="tc-head">
    <div>
      <span class="tc-name">{_e(t.full_name)}</span>
      <span class="tc-schema">schema: {_e(t.schema or 'default')}</span>
      {comment_html}
    </div>
    <div class="tc-meta">
      {len(t.columns)} cols · created V{_e(t.created_in)}{mod_html}
    </div>
  </div>
  <table class="col-tbl">
    <thead><tr>
      <th>Column</th><th>Type</th><th>Flags</th><th>Default</th><th>Comment</th>
    </tr></thead>
    <tbody>{col_rows}</tbody>
  </table>
  {f'<table class="idx-tbl"><tbody>{idx_rows}</tbody></table>' if idx_rows else ''}
  {f'<table class="idx-tbl"><tbody>{rel_rows}</tbody></table>' if rel_rows else ''}
</div>"""

    @staticmethod
    def _insights_section(report: InsightsReport) -> str:
        if not report or not report.findings:
            return ''

        rows = ''
        for f in report.findings:
            table_tag  = f' · <code>{_e(f.table)}</code>' if f.table else ''
            column_tag = f'.<code>{_e(f.column)}</code>' if f.column else ''
            fix_html   = f'<div class="ins-fix">↳ {_e(f.fix)}</div>' if f.fix else ''
            rows += f"""
<div class="ins-row {_e(f.severity)}">
  <div><span class="ins-code">{_e(f.code)}</span></div>
  <div class="ins-msg">
    <span>{_e(f.message)}{table_tag}{column_tag}</span>
    {fix_html}
  </div>
</div>"""

        e  = sum(1 for f in report.findings if f.severity == 'error')
        w  = sum(1 for f in report.findings if f.severity == 'warning')
        i  = sum(1 for f in report.findings if f.severity == 'info')
        return f"""
<div class="section" id="section-insights" style="display:none">
  <div class="section-title">Schema Insights</div>
  <div class="section-sub">{e} errors · {w} warnings · {i} info</div>
  <div class="ins-grid">{rows}</div>
</div>"""

    @staticmethod
    def _tables_for_js(state: SchemaState) -> list[dict]:
        return [
            {'full': t.full_name, 'name': t.name,
             'cols': [c.name for c in t.columns]}
            for t in state.tables.values()
        ]