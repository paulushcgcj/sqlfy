/**
 * sqlfy — app/app.js
 *
 * UI layer. All rendering, DOM manipulation, and event handling lives here.
 * Zero business logic — everything is imported from ../cli/core.js.
 *
 * NOTE: served via a local HTTP server (not file://) so ES module imports work.
 * Simplest way: `npx serve .` from the sqlfy/step2 folder, then open
 *   http://localhost:3000/app/
 */

import {
  applyMigrations,
  buildChunks,
  computeLayout,
  typeStr,
} from '../cli/core.js';

// ─────────────────────────────────────────────
// SAMPLE DATA
// ─────────────────────────────────────────────

const SAMPLES = [
  {
    filename: 'V1__create_core_tables.sql',
    sql: `-- Core user and product tables
CREATE TABLE app.users (
    user_id     NUMBER(10)      NOT NULL,
    username    VARCHAR2(50)    NOT NULL,
    email       VARCHAR2(100)   NOT NULL,
    status      VARCHAR2(20)    DEFAULT 'ACTIVE' NOT NULL,
    created_at  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE','INACTIVE','SUSPENDED'))
);
CREATE SEQUENCE app.seq_users START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE TABLE app.products (
    product_id  NUMBER(10)      NOT NULL,
    name        VARCHAR2(200)   NOT NULL,
    description CLOB,
    price       NUMBER(10,2)    NOT NULL,
    stock_qty   NUMBER(10)      DEFAULT 0 NOT NULL,
    category    VARCHAR2(50),
    CONSTRAINT pk_products PRIMARY KEY (product_id),
    CONSTRAINT ck_products_price CHECK (price >= 0)
);
CREATE SEQUENCE app.seq_products START WITH 1 INCREMENT BY 1 NOCACHE;
COMMENT ON TABLE app.users IS 'Core user accounts';
COMMENT ON COLUMN app.users.status IS 'Account lifecycle status';`,
  },
  {
    filename: 'V2__create_orders.sql',
    sql: `-- Order management
CREATE TABLE app.orders (
    order_id        NUMBER(10)      NOT NULL,
    user_id         NUMBER(10)      NOT NULL,
    total_amount    NUMBER(12,2)    NOT NULL,
    status          VARCHAR2(20)    DEFAULT 'PENDING' NOT NULL,
    shipping_addr   VARCHAR2(500),
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    completed_at    TIMESTAMP,
    CONSTRAINT pk_orders PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id)
        REFERENCES app.users(user_id) ON DELETE CASCADE,
    CONSTRAINT ck_orders_status CHECK (status IN ('PENDING','PROCESSING','SHIPPED','DELIVERED','CANCELLED'))
);
CREATE SEQUENCE app.seq_orders START WITH 1000 INCREMENT BY 1 NOCACHE;
CREATE TABLE app.order_items (
    item_id     NUMBER(10)   NOT NULL,
    order_id    NUMBER(10)   NOT NULL,
    product_id  NUMBER(10)   NOT NULL,
    quantity    NUMBER(5)    NOT NULL,
    unit_price  NUMBER(10,2) NOT NULL,
    CONSTRAINT pk_order_items PRIMARY KEY (item_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id)
        REFERENCES app.orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id)
        REFERENCES app.products(product_id),
    CONSTRAINT ck_items_qty CHECK (quantity > 0)
);
CREATE INDEX app.idx_orders_user   ON app.orders(user_id);
CREATE INDEX app.idx_orders_status ON app.orders(status, created_at);
CREATE INDEX app.idx_items_order   ON app.order_items(order_id);`,
  },
  {
    filename: 'V3__add_audit.sql',
    sql: `-- Audit trail
CREATE TABLE app.audit_log (
    log_id      NUMBER(15)      NOT NULL,
    table_name  VARCHAR2(100)   NOT NULL,
    record_id   NUMBER(15)      NOT NULL,
    action      VARCHAR2(10)    NOT NULL,
    changed_by  NUMBER(10),
    changed_at  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    old_values  CLOB,
    new_values  CLOB,
    CONSTRAINT pk_audit_log PRIMARY KEY (log_id),
    CONSTRAINT fk_audit_user FOREIGN KEY (changed_by)
        REFERENCES app.users(user_id),
    CONSTRAINT ck_audit_action CHECK (action IN ('INSERT','UPDATE','DELETE'))
);
CREATE SEQUENCE app.seq_audit START WITH 1 INCREMENT BY 1 CACHE 100;
ALTER TABLE app.users ADD (last_login TIMESTAMP, login_count NUMBER(10) DEFAULT 0);
ALTER TABLE app.products ADD CONSTRAINT uq_products_name UNIQUE (name);
CREATE INDEX app.idx_audit_table ON app.audit_log(table_name, record_id);
CREATE INDEX app.idx_audit_user  ON app.audit_log(changed_by, changed_at);`,
  },
];

// ─────────────────────────────────────────────
// APPLICATION STATE
// ─────────────────────────────────────────────

let files     = SAMPLES.map(s => ({ ...s }));
let graph     = null;
let chunks    = null;
let selTable  = null;
let selChunk  = null;

// ─────────────────────────────────────────────
// UTILITY
// ─────────────────────────────────────────────

function escH(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById('pane-migrations').style.display = tab === 'migrations' ? '' : 'none';
  document.getElementById('pane-graph').style.display      = tab === 'graph' ? 'flex' : 'none';
  document.getElementById('pane-llm').style.display        = tab === 'llm'   ? 'flex' : 'none';
  if (tab === 'graph') renderGraph();
  if (tab === 'llm')   renderLLM();
}

// ─────────────────────────────────────────────
// RENDER: MIGRATIONS TAB
// ─────────────────────────────────────────────

function renderMigrations() {
  const pane = document.getElementById('pane-migrations');
  pane.innerHTML = '';

  files.forEach((file, i) => {
    const block = document.createElement('div');
    block.className = 'file-block';
    block.innerHTML = `
      <div class="file-hdr">
        <span style="color:var(--accent);font-size:11px">V</span>
        <input value="${escH(file.filename)}" data-i="${i}" data-f="filename" />
        <button class="rm" data-rm="${i}">×</button>
      </div>
      <textarea class="sql-area" rows="10" data-i="${i}" data-f="sql">${escH(file.sql)}</textarea>
    `;
    pane.appendChild(block);
  });

  const addBtn = document.createElement('button');
  addBtn.className = 'add-btn';
  addBtn.textContent = '+ Add Migration File';
  addBtn.addEventListener('click', () => {
    files.push({ filename: `V${files.length + 1}__new_migration.sql`, sql: '-- Add your SQL here\n' });
    renderMigrations();
  });
  pane.appendChild(addBtn);

  pane.querySelectorAll('input[data-f],textarea[data-f]').forEach(el => {
    el.addEventListener('input', () => { files[parseInt(el.dataset.i)][el.dataset.f] = el.value; });
  });
  pane.querySelectorAll('[data-rm]').forEach(btn => {
    btn.addEventListener('click', () => { files.splice(parseInt(btn.dataset.rm), 1); renderMigrations(); });
  });
}

// ─────────────────────────────────────────────
// RENDER: SCHEMA GRAPH TAB
// ─────────────────────────────────────────────

function renderGraph() {
  const pane = document.getElementById('pane-graph');
  pane.innerHTML = '';
  const { tables, edges } = graph;

  // Sidebar
  const sb = document.createElement('div'); sb.className = 'sidebar';
  const tlist = document.createElement('div');
  const ssect = document.createElement('div'); ssect.className = 'sbar-sect';
  ssect.textContent = `Tables (${tables.size})`; tlist.appendChild(ssect);

  for (const [key, t] of tables) {
    const out = edges.filter(e => e.fromTable === key).length;
    const inn = edges.filter(e => e.toTable   === key).length;
    const btn = document.createElement('button');
    btn.className = 'sbar-item' + (key === selTable ? ' active' : '');
    btn.innerHTML = `${escH(t.name)}<div class="sub">${t.columns.length} cols · ${out + inn} rels · V${t.createdIn}</div>`;
    btn.addEventListener('click', () => { selTable = key; renderGraph(); });
    tlist.appendChild(btn);
  }

  if (graph.seqs.size > 0) {
    const ssect2 = document.createElement('div'); ssect2.className = 'sbar-sect';
    ssect2.textContent = `Sequences (${graph.seqs.size})`; tlist.appendChild(ssect2);
    for (const [, s] of graph.seqs) {
      const d = document.createElement('div'); d.className = 'sbar-item'; d.style.cursor = 'default';
      d.innerHTML = `${escH(s.name)}<div class="sub">START ${s.startWith} INC ${s.incrementBy}</div>`;
      tlist.appendChild(d);
    }
  }
  sb.appendChild(tlist); pane.appendChild(sb);

  // Main area
  const main = document.createElement('div'); main.className = 'main';
  const pos = computeLayout(tables, edges);
  const BW = 130, BH = 48, SVW = 580, SVH = 240;

  // ERD SVG
  const erdWrap = document.createElement('div'); erdWrap.className = 'erd-wrap';
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${SVW} ${SVH}`); svg.style.height = '240px';

  const defs = document.createElementNS(svgNS, 'defs');
  const marker = document.createElementNS(svgNS, 'marker');
  marker.setAttribute('id', 'arr'); marker.setAttribute('markerWidth', '8'); marker.setAttribute('markerHeight', '8');
  marker.setAttribute('refX', '6'); marker.setAttribute('refY', '3'); marker.setAttribute('orient', 'auto');
  const poly = document.createElementNS(svgNS, 'polygon');
  poly.setAttribute('points', '0 0, 6 3, 0 6'); poly.setAttribute('fill', '#d97706');
  marker.appendChild(poly); defs.appendChild(marker); svg.appendChild(defs);

  for (const e of edges) {
    const fp = pos.get(e.fromTable), tp = pos.get(e.toTable); if (!fp || !tp) continue;
    const [x1, y1, x2, y2] = [fp.x, fp.y + BH / 2, tp.x, tp.y - BH / 2];
    const mid = (y1 + y2) / 2;
    const path = document.createElementNS(svgNS, 'path');
    path.setAttribute('d', `M ${x1} ${y1} C ${x1} ${mid} ${x2} ${mid} ${x2} ${y2}`);
    path.setAttribute('stroke', '#d97706'); path.setAttribute('stroke-width', '1.2');
    path.setAttribute('fill', 'none'); path.setAttribute('opacity', '0.6');
    path.setAttribute('marker-end', 'url(#arr)');
    svg.appendChild(path);
  }

  const isDark = window.matchMedia('(prefers-color-scheme:dark)').matches;
  for (const [key, t] of tables) {
    const p = pos.get(key); if (!p) continue;
    const isSel = key === selTable;
    const g = document.createElementNS(svgNS, 'g'); g.style.cursor = 'pointer';
    g.addEventListener('click', () => { selTable = key; renderGraph(); });
    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('x', p.x - BW / 2); rect.setAttribute('y', p.y - BH / 2);
    rect.setAttribute('width', BW); rect.setAttribute('height', BH); rect.setAttribute('rx', '5');
    rect.setAttribute('fill',   isSel ? (isDark ? '#3c2f6b' : '#ede9fe') : (isDark ? '#1e2235' : '#f8f7ff'));
    rect.setAttribute('stroke', isSel ? '#7c3aed' : (isDark ? '#2d3748' : '#d1d5db'));
    rect.setAttribute('stroke-width', isSel ? '1.8' : '0.8');
    g.appendChild(rect);
    const t1 = document.createElementNS(svgNS, 'text');
    t1.setAttribute('x', p.x); t1.setAttribute('y', p.y - 4); t1.setAttribute('text-anchor', 'middle');
    t1.setAttribute('font-size', '11'); t1.setAttribute('font-weight', '500');
    t1.setAttribute('fill', isSel ? '#7c3aed' : (isDark ? '#e2e8f0' : '#111827'));
    t1.textContent = t.name; g.appendChild(t1);
    const t2 = document.createElementNS(svgNS, 'text');
    t2.setAttribute('x', p.x); t2.setAttribute('y', p.y + 11); t2.setAttribute('text-anchor', 'middle');
    t2.setAttribute('font-size', '9'); t2.setAttribute('fill', isDark ? '#64748b' : '#9ca3af');
    t2.textContent = `${t.columns.length} cols · V${t.createdIn}`; g.appendChild(t2);
    svg.appendChild(g);
  }
  erdWrap.appendChild(svg); main.appendChild(erdWrap);

  // Table detail panel
  if (selTable && tables.get(selTable)) {
    const t   = tables.get(selTable);
    const pk  = t.constraints.find(c => c.type === 'primary_key');
    const uqs = t.constraints.filter(c => c.type === 'unique');
    const cks = t.constraints.filter(c => c.type === 'check');
    const outE = edges.filter(e => e.fromTable === selTable);
    const inE  = edges.filter(e => e.toTable   === selTable);
    const detail = document.createElement('div');

    const hdr = document.createElement('div'); hdr.className = 'tbl-hdr';
    hdr.innerHTML = `
      <div class="tbl-name">${escH(t.full)}</div>
      <div class="tbl-meta">V${t.createdIn}${t.modifiedIn.length ? ` · modified V${t.modifiedIn.join(', ')}` : ''} · ${t.columns.length} columns${t.indexes.length ? ` · ${t.indexes.length} indexes` : ''}</div>
      ${t.comments['__table__'] ? `<div class="tbl-comment">${escH(t.comments['__table__'])}</div>` : ''}
    `;
    detail.appendChild(hdr);

    const colSect = document.createElement('div'); colSect.className = 'sect';
    colSect.innerHTML = `<div class="sect-title">Columns</div><div class="col-row col-head"><span>Column</span><span>Type</span><span>Flags</span><span>Default</span><span>Comment</span></div>`;
    for (const col of t.columns) {
      const row = document.createElement('div'); row.className = 'col-row';
      const badges = [];
      if (pk?.columns.includes(col.name))                badges.push('<span class="badge pk">PK</span>');
      if (!col.nullable)                                 badges.push('<span class="badge nn">NN</span>');
      if (uqs.some(u => u.columns.includes(col.name)))   badges.push('<span class="badge uq">UQ</span>');
      if (outE.some(e => e.fromCols.includes(col.name))) badges.push('<span class="badge fk">FK</span>');
      row.innerHTML = `<span>${escH(col.name)}</span><span class="col-type">${escH(typeStr(col))}</span><span>${badges.join('')}</span><span class="col-def">${col.default ? escH(col.default) : '—'}</span><span class="col-comment">${t.comments[col.name] ? escH(t.comments[col.name]) : ''}</span>`;
      colSect.appendChild(row);
    }
    detail.appendChild(colSect);

    if (outE.length || inE.length) {
      const relSect = document.createElement('div'); relSect.className = 'sect';
      relSect.innerHTML = '<div class="sect-title">Relationships</div><div class="rel-grid"></div>';
      const rg = relSect.querySelector('.rel-grid');
      if (outE.length) {
        const d = document.createElement('div');
        d.innerHTML = '<div style="font-size:10px;color:var(--color-text-tertiary);margin-bottom:6px">REFERENCES ▶</div>';
        for (const e of outE) {
          const c = document.createElement('div'); c.className = 'rel-card';
          c.innerHTML = `<div class="rl">${escH(e.fromCols.join(','))} → ${escH(e.toTable)}</div><div class="rm2">${e.constraintName ? escH(e.constraintName) : ''}${e.onDelete ? ` · ON DELETE ${e.onDelete}` : ''}</div>`;
          d.appendChild(c);
        }
        rg.appendChild(d);
      }
      if (inE.length) {
        const d = document.createElement('div');
        d.innerHTML = '<div style="font-size:10px;color:var(--color-text-tertiary);margin-bottom:6px">◀ REFERENCED BY</div>';
        for (const e of inE) {
          const c = document.createElement('div'); c.className = 'rel-card in';
          c.innerHTML = `<div class="rl">${escH(e.fromTable)}</div><div class="rm2">${escH(e.fromCols.join(','))} → ${escH(e.toCols.join(','))}</div>`;
          d.appendChild(c);
        }
        rg.appendChild(d);
      }
      detail.appendChild(relSect);
    }

    if (t.indexes.length) {
      const idxSect = document.createElement('div'); idxSect.className = 'sect';
      idxSect.innerHTML = '<div class="sect-title">Indexes</div>';
      for (const idx of t.indexes) {
        const row = document.createElement('div'); row.className = 'idx-row';
        row.innerHTML = `<span>${escH(idx.name)}</span><span style="color:var(--color-text-tertiary)">(${escH(idx.columns.join(', '))})</span>${idx.unique ? '<span class="badge uq">UNIQUE</span>' : ''}<span style="color:var(--color-text-tertiary);font-size:10px;margin-left:auto">V${idx.createdIn}</span>`;
        idxSect.appendChild(row);
      }
      detail.appendChild(idxSect);
    }

    if (cks.length) {
      const ckSect = document.createElement('div'); ckSect.className = 'sect';
      ckSect.innerHTML = '<div class="sect-title">Check Constraints</div>';
      for (const ck of cks) {
        const row = document.createElement('div');
        row.style.cssText = 'padding:4px 0;font-size:11.5px;border-bottom:0.5px solid var(--color-border-tertiary)';
        row.innerHTML = `<span style="color:var(--color-text-secondary)">${ck.name || 'unnamed'}: </span><span style="color:#d97706">CHECK (${escH(ck.checkExpr)})</span>`;
        ckSect.appendChild(row);
      }
      detail.appendChild(ckSect);
    }
    main.appendChild(detail);
  } else {
    const nd = document.createElement('div'); nd.className = 'no-data';
    nd.textContent = 'Select a table to view details'; main.appendChild(nd);
  }

  pane.appendChild(main);
}

// ─────────────────────────────────────────────
// RENDER: LLM CHUNKS TAB
// ─────────────────────────────────────────────

function renderLLM() {
  const pane = document.getElementById('pane-llm');
  pane.innerHTML = '';

  const sb = document.createElement('div'); sb.className = 'sidebar';
  const expBtn = document.createElement('button');
  expBtn.className = 'export-btn'; expBtn.textContent = '⬇ Export all JSON';
  expBtn.addEventListener('click', () => {
    const json = JSON.stringify(chunks.map(c => ({ id: c.id, type: c.type, title: c.title, content: c.content, metadata: c.meta })), null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'schema_vector_chunks.json'; a.click();
    URL.revokeObjectURL(url);
  });
  sb.appendChild(expBtn);

  const ssect = document.createElement('div'); ssect.className = 'sbar-sect';
  ssect.textContent = `Chunks (${chunks.length})`; sb.appendChild(ssect);

  for (const chunk of chunks) {
    const btn = document.createElement('button');
    btn.className = 'sbar-item' + (chunk.id === selChunk?.id ? ' active' : '');
    btn.innerHTML = `${escH(chunk.title)}<div class="sub">${chunk.type} · ${chunk.content.length} chars</div>`;
    btn.addEventListener('click', () => { selChunk = chunk; renderLLM(); });
    sb.appendChild(btn);
  }
  pane.appendChild(sb);

  const main = document.createElement('div'); main.className = 'main';
  if (selChunk) {
    const hdr = document.createElement('div'); hdr.className = 'chunk-hdr';
    hdr.innerHTML = `<span style="font-size:14px;font-weight:500">${escH(selChunk.title)}</span><span class="chunk-type-badge">${selChunk.type}</span><button class="copy-btn" id="copy-btn">Copy content</button>`;
    main.appendChild(hdr);

    const inner = document.createElement('div'); inner.style.cssText = 'padding:14px 20px';
    inner.innerHTML = `
      <div class="chunk-hint">💡 ${escH(selChunk.hint)}</div>
      <div class="chunk-content">${escH(selChunk.content)}</div>
      <div style="font-size:10px;color:var(--color-text-tertiary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">Metadata</div>
      <div class="chunk-meta">${escH(JSON.stringify(selChunk.meta, null, 2))}</div>
    `;
    main.appendChild(inner);

    hdr.querySelector('#copy-btn').addEventListener('click', function () {
      navigator.clipboard.writeText(selChunk.content);
      this.textContent = 'Copied!'; this.className = 'copy-btn ok';
      setTimeout(() => { this.textContent = 'Copy content'; this.className = 'copy-btn'; }, 1800);
    });
  } else {
    const nd = document.createElement('div'); nd.className = 'no-data';
    nd.textContent = 'Select a chunk to view'; main.appendChild(nd);
  }
  pane.appendChild(main);
}

// ─────────────────────────────────────────────
// EVENT WIRING + BOOTSTRAP
// ─────────────────────────────────────────────

document.getElementById('tabbar').addEventListener('click', e => {
  const btn = e.target.closest('.tab');
  if (!btn || btn.classList.contains('disabled')) return;
  showTab(btn.dataset.tab);
});

document.getElementById('parse-btn').addEventListener('click', () => {
  const errBar = document.getElementById('err-bar');
  try {
    graph    = applyMigrations(files);
    chunks   = buildChunks(graph);
    selTable = [...graph.tables.keys()][0];
    selChunk = chunks[0];
    document.getElementById('tab-graph').classList.remove('disabled');
    document.getElementById('tab-llm').classList.remove('disabled');
    errBar.style.display = 'none';
    showTab('graph');
  } catch (err) {
    errBar.textContent = '⚠ Parse error: ' + err.message;
    errBar.style.display = '';
    console.error(err);
  }
});

renderMigrations();