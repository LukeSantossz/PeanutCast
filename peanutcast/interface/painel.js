/* =====================================================================
   PeanutCast · o painel no navegador.

   Recebe do Python (peanutcast/painel.py) o pacote com histórico, clima,
   cenários, previsões e os números do modelo, e desenha. Não decide nada de
   modelo: a única conta feita aqui é a previsão enquanto um controle de clima
   desliza, com os coeficientes de previsao.parametros(), e a conferência no
   fim de iniciar() avisa no console se ela divergir das previsões do Python.

   O Streamlit chama a função exportada a cada rerun com os dados novos e o
   mesmo elemento; o estado da tela (cenário, município aberto, comparação)
   fica neste módulo e sobrevive aos reruns.
   ===================================================================== */

const CEN = ['Seco', 'Normal', 'Chuvoso'];
const COR = { Seco: '#D45A43', Normal: '#D6A26B', Chuvoso: '#86B06F' };
const PIN = ['#D6A26B', '#86B06F', '#E7D3A8', '#D45A43'];
const ROT = { chuva_critica_mm: 'Chuva', temp_max_critica_c: 'Máxima média', radiacao_critica_mj_m2: 'Radiação', dias_calor_critica: 'Dias acima de 35 °C' };
const CURTO = { chuva_critica_mm: 'Chuva', temp_max_critica_c: 'Máxima', radiacao_critica_mj_m2: 'Radiação', dias_calor_critica: 'Dias > 35 °C' };
const UN = { chuva_critica_mm: 'mm', temp_max_critica_c: '°C', radiacao_critica_mj_m2: 'MJ/m²', dias_calor_critica: 'dias' };
const DEC = { chuva_critica_mm: 0, temp_max_critica_c: 1, radiacao_critica_mj_m2: 1, dias_calor_critica: 0 };

const soma = a => a.reduce((x, y) => x + y, 0);
const mediana = a => { const s = [...a].sort((x, y) => x - y), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
const fmt = (v, d = 0) => v == null || Number.isNaN(v) ? '—' : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const sinal = v => (v >= 0 ? '+' : '−') + fmt(Math.abs(v));
const lin = (a, b, c, d) => v => c + (v - a) / (b - a) * (d - c);
const semAcento = s => s.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/\p{M}/gu, '');
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ---------- cores ---------- */
function rampa(hex) {
  const c = hex.map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));
  return t => { t = clamp(t, 0, 1); const x = t * (c.length - 1), i = Math.min(c.length - 2, Math.floor(x)), f = x - i;
    return '#' + c[i].map((v, j) => Math.round(v + (c[i + 1][j] - v) * f).toString(16).padStart(2, '0')).join(''); };
}
const R_REND = rampa(['#6B2A1D', '#A23E27', '#C9632F', '#DE9443', '#E6C066', '#C3C26B', '#8FAF62', '#5F9150', '#3B6E3C']);
const R_SECO = rampa(['#3A2E25', '#7A3A2A', '#B04A33', '#E06A4E']);
const R_CALOR = rampa(['#2F2620', '#6E4B2B', '#B7743A', '#D9973F', '#E06A4E']);
const R_CHUVA = rampa(['#7A3424', '#B4643B', '#9C8F5C', '#6F9B5B', '#4C7E45']);
const R_NEUTRA = rampa(['#2B221B', '#5C4A3A', '#8F7A63']);
const tinta = hex => { const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)); return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? '#14100C' : '#F2EADD'; };

/* ---------- o que depende dos dados (recalculado quando a versão muda) ---------- */
let D, M, COL, ANOS, ERRO, MUN, NOMES, TER, COM, NCEL;
let E0, E1, NDEG, P0, P1, NP, GEO, LON, LAT, KX;
const PASSO = 250;
const valida = h => h && h.ac != null && h.ac >= D.areaMin;
const temPrev = m => m.media != null && !!m.cenarios;

/* a mesma conta do previsao.prever: média + intercepto + Σ coef·(x − μ)/σ */
const contrib = c => COL.map((k, i) => M.coef[i] * (c[k] - M.mu[i]) / M.sd[i]);
const prever = (m, c) => m.media + M.b + soma(contrib(c));
const erroLocal = m => m.wf.length ? soma(m.wf.map(w => Math.abs(w.r - w.p))) / m.wf.length : null;

function tercos(m) {   // os terços de previsao.cenarios: de que cenário foi cada safra
  const ch = m.clima.chuva_critica_mm, idx = ANOS.map((_, i) => i).filter(i => ch[i] != null).sort((a, b) => ch[a] - ch[b]);
  const n = idx.length, base = Math.floor(n / 3), r = n % 3, classe = {}; let p = 0;
  CEN.forEach((c, g) => { const t = base + (g < r ? 1 : 0); idx.slice(p, p + t).forEach(i => classe[ANOS[i]] = c); p += t; });
  return classe;
}

function iniciar(dados) {
  D = dados; M = D.modelo; COL = D.colunas; ANOS = D.anos; ERRO = D.erro;
  MUN = Object.fromEntries(D.municipios.map(m => [m.nome, m]));
  NOMES = D.municipios.map(m => m.nome).sort((a, b) => a.localeCompare(b, 'pt-BR'));
  TER = Object.fromEntries(D.municipios.map(m => [m.nome, tercos(m)]));
  COM = D.municipios.filter(temPrev);
  NCEL = new Set(D.municipios.map(m => m.celula)).size;
  const todas = COM.flatMap(m => CEN.map(c => m.prev[c]));
  E0 = Math.floor(Math.min(...todas) / PASSO) * PASSO; E1 = Math.ceil(Math.max(...todas) / PASSO) * PASSO; NDEG = Math.max(1, (E1 - E0) / PASSO);
  const perdas = COM.map(m => m.prev.Seco - m.prev.Normal);
  P0 = Math.floor(Math.min(...perdas) / 25) * 25; P1 = Math.ceil(Math.max(...perdas) / 25) * 25; NP = Math.max(1, (P1 - P0) / 25);
  GEO = D.geo ? Object.fromEntries(Object.entries(D.geo).map(([k, v]) => [+k, v])) : null;
  if (GEO) {
    const pts = Object.values(GEO).flat(2);
    LON = [Math.min(...pts.map(p => p[0])), Math.max(...pts.map(p => p[0]))];
    LAT = [Math.min(...pts.map(p => p[1])), Math.max(...pts.map(p => p[1]))];
    KX = Math.cos((LAT[0] + LAT[1]) / 2 * Math.PI / 180);
  }
  for (const m of COM) for (const c of CEN)
    if (Math.abs(prever(m, m.cenarios[c]) - m.prev[c]) > 0.01) console.error('[PeanutCast] previsão no navegador diverge do Python', m.nome, c);
}
const corRend = v => R_REND((Math.min(NDEG - 1, Math.floor((v - E0) / PASSO)) + 0.5) / NDEG);
const corPerda = v => R_SECO(1 - (Math.min(NP - 1, Math.floor((v - P0) / 25)) + 0.5) / NP);

/* ---------- estado da tela ---------- */
const S = { vista: 'mapa', sel: null, cen: 'Normal', aj: null, camada: 'esperado', fav: new Set(), comp: [], quente: null, busca: '' };
let ROOT = null, AVISAR = () => {}, VERSAO = null, FAVS = null, PROJ = null;
const $ = s => ROOT.querySelector(s), $$ = s => [...ROOT.querySelectorAll(s)];
const clima = m => S.aj && S.aj.mun === m.nome && S.aj.cen === S.cen ? S.aj.v : m.cenarios[S.cen];
const ajustado = m => !!(S.aj && S.aj.mun === m.nome && S.aj.cen === S.cen);
const valorMapa = m => S.camada === 'esperado' ? prever(m, clima(m)) : m.prev.Seco - m.prev.Normal;
const corMapa = m => !temPrev(m) ? '#2B221B' : S.camada === 'esperado' ? corRend(valorMapa(m)) : corPerda(valorMapa(m));
const ordem = () => [...COM].sort((a, b) => valorMapa(b) - valorMapa(a));

const alvos = new WeakMap();
function contar(el, alvo) {
  const de = alvos.get(el) ?? alvo; alvos.set(el, alvo);
  if (de === alvo || matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = fmt(alvo); return; }
  const t0 = performance.now();
  const f = t => { if (alvos.get(el) !== alvo) return; const k = Math.min(1, (t - t0) / 600), e = 1 - (1 - k) ** 3; el.textContent = fmt(de + (alvo - de) * e); if (k < 1) requestAnimationFrame(f); };
  requestAnimationFrame(f);
}

/* ---------- geografia ---------- */
function projetor(w, h, pad, padDir = pad) {
  const dx = (LON[1] - LON[0]) * KX, dy = LAT[1] - LAT[0], s = Math.min((w - pad - padDir) / dx, (h - 2 * pad) / dy);
  const ox = pad + (w - pad - padDir - dx * s) / 2, oy = (h - dy * s) / 2;
  const f = ([x, y]) => [ox + (x - LON[0]) * KX * s, oy + (LAT[1] - y) * s]; f.s = s; return f;
}
const caminho = (a, P) => a.map(r => 'M' + r.map(p => P(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('');
const grau = (v, h) => `${Math.abs(Math.trunc(v))}°${Math.abs(v % 1) > 0.01 ? '30′' : '00′'} ${h}`;

function legendaHorizontal(esp = true) {
  const n = esp ? NDEG : NP, a = esp ? E0 : P0, p = esp ? PASSO : 25, txt = v => esp ? fmt(v) : sinal(v);
  const cor = i => esp ? corRend(a + i * p + 1) : corPerda(a + i * p + 1);
  return `<div class="degraus h">` + Array.from({ length: n }, (_, i) => `<i style="background:${cor(i)}"></i>`).join('') +
    [0, Math.round(n / 2), n].map(k => `<span style="left:${k / n * 100}%">${txt(a + k * p)}</span>`).join('') + `</div>`;
}

/* =====================================================================
   CAPA da tela de entrada: o mapa da região no cenário normal
   ===================================================================== */
function capa(raiz) {
  let el = raiz.querySelector('.capa');
  if (!el) { el = document.createElement('div'); el.className = 'pc capa'; raiz.appendChild(el); }
  if (!GEO) { el.remove(); return; }
  const W = 900, H = 600, P = projetor(W, H, 10);
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${D.municipios.map(m => `<path d="${caminho(GEO[m.codigo], P)}" fill="${temPrev(m) ? corRend(m.prev.Normal) : '#2B221B'}" stroke="#14100C" stroke-width="1"/>`).join('')}</svg>
    <div class="leg"><p class="nota">Rendimento esperado na safra ${D.proxima}, cenário normal, nos ${D.municipios.length} municípios das microrregiões de Marília, Tupã e Adamantina. IBGE/SIDRA-PAM ${ANOS[0]}–${ANOS.at(-1)} e NASA POWER.</p>${legendaHorizontal()}</div>`;
}

/* =====================================================================
   ESTRUTURA do espaço de trabalho
   ===================================================================== */
const MOLDE = `
  <header class="topo">
    <div class="marca">Peanut<i>Cast</i> <span class="rot" style="margin-left:10px;font-stretch:100%">Amendoim · Alta Paulista</span></div>
    <nav>
      <button data-vista="mapa" aria-current="true">Mapa</button>
      <button data-vista="comparar">Comparar<b data-n-comp hidden></b></button>
      <button data-vista="metodo">Método</button>
    </nav>
    <div class="usu"><span data-usuario></span><button class="btn" data-sair>Sair</button></div>
  </header>
  <aside class="esq">
    <div class="busca"><input data-busca placeholder="Buscar município" aria-label="Buscar município"></div>
    <div class="esq-cab"><span class="rot" data-lista-tit></span><span class="rot">kg/ha</span></div>
    <div class="lista" data-lista></div>
  </aside>
  <section class="mapa" data-mapa>
    <svg data-mapa-svg role="img" aria-label="Mapa dos municípios"></svg>
    <div class="legenda" data-legenda></div>
    <div class="escala-km" data-escala></div>
    <div class="dica" data-dica hidden></div>
    <div class="bandeja" data-bandeja hidden></div>
  </section>
  <aside class="dir" data-dir></aside>
  <section class="sobre" data-sobre hidden></section>
  <footer class="base">
    <div class="safra"><span class="rot">Safra</span><b data-safra></b></div>
    <div>
      <div class="rot" style="margin-bottom:5px">Cenário climático · chuva de dez a fev, mediana da região</div>
      <div class="trilha" data-trilha></div>
    </div>
    <div>
      <div class="rot" style="margin-bottom:5px">O mapa mostra</div>
      <div class="camadas" data-camadas>
        <button class="btn on" data-c="esperado">Rendimento esperado</button>
        <button class="btn" data-c="seco">Perda no ano seco</button>
      </div>
    </div>
    <div class="modelo" data-modelo></div>
  </footer>`;

function montar(raiz) {
  let el = raiz.querySelector('.app');
  if (el) return el;
  el = document.createElement('div'); el.className = 'pc app'; el.innerHTML = MOLDE; raiz.appendChild(el);
  ROOT = el;
  $$('.topo nav button').forEach(b => b.onclick = () => irPara(b.dataset.vista));
  // Quem entrar depois na mesma aba não herda o município aberto nem a comparação.
  $('[data-sair]').onclick = () => {
    Object.assign(S, { vista: 'mapa', sel: null, cen: 'Normal', aj: null, camada: 'esperado', comp: [], busca: '' });
    FAVS = null; AVISAR('sair', true);
  };
  $('[data-busca]').oninput = e => { S.busca = e.target.value; lista(); };
  $('[data-busca]').onkeydown = e => { if (e.key === 'Enter') { const b = $('[data-lista] .it'); if (b) { selecionar(b.dataset.n); e.target.value = ''; S.busca = ''; lista(); } } };
  return el;
}

/* =====================================================================
   BARRA INFERIOR: cenário e camada
   ===================================================================== */
function base() {
  $('[data-safra]').textContent = D.proxima;
  const t = $('[data-trilha]');
  if (t.dataset.versao !== VERSAO) {
    t.dataset.versao = VERSAO;
    const mm = c => mediana(COM.map(m => m.cenarios[c].chuva_critica_mm));
    t.innerHTML = `<span class="ind"></span>` + CEN.map(c => `<button data-cen="${c}"><b><i style="background:${COR[c]}"></i>${c}</b><span>${fmt(mm(c))} mm</span></button>`).join('');
    t.querySelectorAll('button').forEach(b => b.onclick = () => mudarCenario(b.dataset.cen));
  }
  t.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.cen === S.cen));
  const ind = t.querySelector('.ind'); ind.style.transform = `translateX(${CEN.indexOf(S.cen) * 100}%)`; ind.style.background = COR[S.cen];
  $$('[data-camadas] button').forEach(b => { b.classList.toggle('on', b.dataset.c === S.camada); b.onclick = () => { S.camada = b.dataset.c; render(); }; });
  $('[data-modelo]').innerHTML = `Modelo <b>${esc(M.nome)}</b>, clima de dez a fev<br>Erro típico <b>± ${fmt(ERRO)} kg/ha</b> · simula cenário, não prevê o tempo`;
}
function mudarCenario(c) { S.cen = c; S.aj = null; render(); }

/* =====================================================================
   LISTA LATERAL
   ===================================================================== */
function lista() {
  $('[data-lista-tit]').textContent = S.camada === 'esperado' ? `Ranking · ${S.cen.toLowerCase()}` : 'Perda no ano seco';
  const q = semAcento(S.busca), filtra = m => !q || semAcento(m.nome).includes(q);
  const ord = ordem(), pos = Object.fromEntries(ord.map((m, i) => [m.nome, i + 1]));
  const item = m => { const v = valorMapa(m), c = corMapa(m);
    return `<button class="it ${S.sel === m.nome ? 'sel' : ''} ${S.quente === m.nome ? 'quente' : ''}" data-n="${esc(m.nome)}"><span class="n">${pos[m.nome]}</span><span class="nm">${esc(m.nome)}${S.fav.has(m.nome) ? '<em>★</em>' : ''}</span><span class="chip" style="background:${c};color:${tinta(c)}">${S.camada === 'esperado' ? fmt(v) : sinal(v)}</span></button>`; };
  const favs = ord.filter(m => S.fav.has(m.nome) && filtra(m)), todos = ord.filter(filtra);
  const semHist = D.municipios.filter(m => !temPrev(m) && filtra(m));
  $('[data-lista]').innerHTML = (favs.length && !q ? `<div class="rot grupo-t">Meus municípios</div>${favs.map(item).join('')}<div class="rot grupo-t">Todos</div>` : '') +
    todos.map(item).join('') +
    semHist.map(m => `<button class="it" data-n="${esc(m.nome)}"><span class="n">—</span><span class="nm">${esc(m.nome)}</span><span class="nota">sem histórico</span></button>`).join('') +
    (!todos.length && !semHist.length ? `<p class="nota" style="padding:8px">Nenhum município com esse nome.</p>` : '');
  $$('[data-lista] .it').forEach(b => {
    b.onclick = () => selecionar(b.dataset.n);
    b.onmouseenter = () => quente(b.dataset.n); b.onmouseleave = () => quente(null);
  });
}
function quente(n) { S.quente = n; $$('.mun').forEach(p => p.classList.toggle('apagado', !!n && p.dataset.n !== n && p.dataset.n !== S.sel)); }

/* =====================================================================
   MAPA
   ===================================================================== */
function mapa(forcar) {
  const box = $('[data-mapa]'), svg = $('[data-mapa-svg]'), W = box.clientWidth, H = box.clientHeight;
  if (!GEO) {
    svg.innerHTML = ''; $('[data-legenda]').hidden = true; $('[data-escala]').innerHTML = '';
    if (!box.querySelector('.sem-mapa')) box.insertAdjacentHTML('beforeend', `<div class="sem-mapa"><p class="nota">O contorno dos municípios não foi baixado nesta máquina.<br>Rode <code>python scripts/coletar.py</code>. A lista, a ficha e a comparação funcionam sem ele.</p></div>`);
    bandeja(); return;
  }
  if (!W || !H) return;
  if (forcar || !PROJ || svg.dataset.w != W || svg.dataset.h != H) {
    svg.dataset.w = W; svg.dataset.h = H; svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const estreito = W < 600, P = PROJ = projetor(W, estreito ? H - 60 : H, estreito ? 16 : Math.max(36, Math.min(W, H) * 0.06), W > 700 ? 120 : 16);
    let g = '';
    for (let lon = Math.ceil(LON[0] * 2) / 2; lon <= LON[1]; lon += 0.5) { const x = P([lon, 0])[0]; g += `<line class="grat" x1="${x}" x2="${x}" y1="0" y2="${H}"/><text class="grat-t" x="${x + 4}" y="14">${grau(lon, 'O')}</text>`; }
    for (let lat = Math.ceil(LAT[0] * 2) / 2; lat <= LAT[1]; lat += 0.5) { const y = P([LON[0], lat])[1]; g += `<line class="grat" x1="0" x2="${W}" y1="${y}" y2="${y}"/><text class="grat-t" x="6" y="${y - 4}">${grau(lat, 'S')}</text>`; }
    g += D.municipios.filter(m => GEO[m.codigo]).map(m => `<path class="mun" data-n="${esc(m.nome)}" d="${caminho(GEO[m.codigo], P)}"/>`).join('');
    g += D.municipios.filter(m => m.centro).map(m => { const [x, y] = P(m.centro); return `<text class="m-nome" data-n="${esc(m.nome)}" x="${x}" y="${y}">${esc(m.nome)}</text><text class="m-val" data-n="${esc(m.nome)}" x="${x}" y="${y + 12}"></text>`; }).join('');
    svg.innerHTML = g;
    $('[data-escala]').innerHTML = `<i style="width:${P.s * 20 / 111.32}px"></i>20 km`;
    svg.querySelectorAll('.mun').forEach(p => {
      const n = p.dataset.n;
      p.onclick = () => selecionar(n);
      p.onmousemove = e => dica(n, e);
      p.onmouseenter = () => { const c = MUN[n].celula; svg.querySelectorAll('.mun').forEach(q => q.classList.toggle('par', q !== p && MUN[q.dataset.n].celula === c)); };
      p.onmouseleave = () => { $('[data-dica]').hidden = true; svg.querySelectorAll('.par').forEach(q => q.classList.remove('par')); };
    });
  }
  const pequeno = W < 560;
  svg.querySelectorAll('.mun').forEach(p => { const m = MUN[p.dataset.n]; p.style.fill = corMapa(m); p.classList.toggle('sel', m.nome === S.sel); });
  const ps = svg.querySelector('.mun.sel'); if (ps) svg.insertBefore(ps, svg.querySelector('.m-nome'));
  svg.querySelectorAll('.m-val').forEach(t => { const m = MUN[t.dataset.n]; t.textContent = !temPrev(m) || pequeno ? '' : S.camada === 'esperado' ? fmt(valorMapa(m)) : sinal(valorMapa(m)); });
  svg.querySelectorAll('.m-nome').forEach(t => t.style.fontSize = pequeno ? '9px' : '11px');
  rotulos(svg); legenda(); bandeja();
}

/* Rótulos sem colisão: o selecionado primeiro, depois os maiores polígonos.
   O que não cabe some, e aparece no passar do mouse. */
function rotulos(svg) {
  const caixas = [], area = n => { const p = svg.querySelector(`.mun[data-n="${n}"]`); if (!p) return 0; const b = p.getBBox(); return b.width * b.height; };
  const ns = D.municipios.filter(m => m.centro).map(m => m.nome).sort((a, b) => (b === S.sel) - (a === S.sel) || area(b) - area(a));
  for (const n of ns) {
    const ts = [...svg.querySelectorAll(`[data-n="${n}"].m-nome, [data-n="${n}"].m-val`)];
    ts.forEach(t => t.style.display = '');
    const bs = ts.filter(t => t.textContent).map(t => t.getBBox());
    if (!bs.length) continue;
    const b = { x0: Math.min(...bs.map(c => c.x)) - 2, y0: Math.min(...bs.map(c => c.y)) - 1, x1: Math.max(...bs.map(c => c.x + c.width)) + 2, y1: Math.max(...bs.map(c => c.y + c.height)) + 1 };
    if (caixas.some(c => !(b.x1 < c.x0 || b.x0 > c.x1 || b.y1 < c.y0 || b.y0 > c.y1))) ts.forEach(t => t.style.display = 'none'); else caixas.push(b);
  }
}
function dica(n, e) {
  const m = MUN[n], el = $('[data-dica]'), r = $('[data-mapa]').getBoundingClientRect();
  if (!temPrev(m)) el.innerHTML = `<h4>${esc(n)}</h4><div class="nota">Sem safra recente com ${D.areaMin} ha colhidos: não há base para prever.</div>`;
  else {
    const v = prever(m, clima(m));
    el.innerHTML = `<h4>${esc(n)}</h4><div class="v">${fmt(v)} kg/ha <span class="nota">· cenário ${S.cen.toLowerCase()}${ajustado(m) ? ' ajustado' : ''}</span></div>` +
      `<div class="cs">${CEN.map(c => { const k = corRend(m.prev[c]); return `<span style="background:${k};color:${tinta(k)}">${c[0]} ${fmt(m.prev[c])}</span>`; }).join('')}</div>` +
      `<div class="nota" style="margin-top:6px">Tracejados: mesma célula de clima da NASA POWER</div>`;
  }
  const x = e.clientX - r.left, y = e.clientY - r.top;
  el.style.left = (x > r.width - 240 ? x - 250 : x) + 'px'; el.style.top = clamp(y, 60, r.height - 60) + 'px'; el.hidden = false;
}
function legenda() {
  const el = $('[data-legenda]'); el.hidden = false;
  if ($('[data-mapa]').clientWidth < 600) { el.innerHTML = legendaHorizontal(S.camada === 'esperado'); return; }
  const esp = S.camada === 'esperado', n = esp ? NDEG : NP, a = esp ? E0 : P0, p = esp ? PASSO : 25;
  const cor = i => esp ? corRend(a + i * p + 1) : corPerda(a + i * p + 1), txt = v => esp ? fmt(v) : sinal(v), pulo = n > 8 ? 2 : 1;
  el.innerHTML = `<span class="rot">kg/ha</span><div class="degraus">` +
    Array.from({ length: n }, (_, i) => `<i style="background:${cor(n - 1 - i)}"></i>`).join('') +
    Array.from({ length: n + 1 }, (_, k) => k % pulo ? '' : `<span style="bottom:${k * 15}px">${txt(a + k * p)}</span>`).join('') + `</div>`;
}
function bandeja() {
  const el = $('[data-bandeja]'), nc = $('[data-n-comp]');
  nc.hidden = !S.comp.length; nc.textContent = S.comp.length;
  if (!S.comp.length || S.vista !== 'mapa') { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<span class="rot" style="margin-right:4px">Comparar</span>` + S.comp.map((n, i) => `<span class="pin"><i style="background:${PIN[i]}"></i>${esc(n)}<button data-n="${esc(n)}" aria-label="Tirar ${esc(n)}">×</button></span>`).join('') +
    `<button class="ir" ${S.comp.length < 2 ? 'disabled' : ''}>${S.comp.length < 2 ? 'Escolha mais um' : 'Comparar →'}</button>`;
  el.querySelectorAll('.pin button').forEach(b => b.onclick = () => alternarComp(b.dataset.n));
  el.querySelector('.ir').onclick = () => S.comp.length > 1 && irPara('comparar');
}
function alternarComp(n) { const i = S.comp.indexOf(n); if (i >= 0) S.comp.splice(i, 1); else if (S.comp.length < 4) S.comp.push(n); render(); }
function alternarFav(n) { S.fav.has(n) ? S.fav.delete(n) : S.fav.add(n); AVISAR('favorito', n); render(); }

/* =====================================================================
   PAINEL DIREITO: boletim da região, ou a ficha do município
   ===================================================================== */
function selecionar(n) { S.sel = n; S.aj = null; $('[data-dir]').dataset.chave = ''; $('[data-dir]').scrollTop = 0; if (S.vista !== 'mapa') irPara('mapa'); else render(); }

function painel() {
  const el = $('[data-dir]');
  if (!S.sel || !MUN[S.sel]) return regiaoResumo(el);
  const m = MUN[S.sel];
  if (!temPrev(m)) {
    el.dataset.chave = '';
    el.innerHTML = `<div class="sec"><div class="f-cab"><div class="f-nome">${esc(m.nome)}</div><button class="fechar" data-fechar-ficha aria-label="Fechar">×</button></div><p class="nota" style="margin-top:14px">O IBGE não registra safra de amendoim com pelo menos ${D.areaMin} ha colhidos aqui nos anos recentes, então não há base para prever.</p></div>`;
    el.querySelector('[data-fechar-ficha]').onclick = () => selecionar(null); return;
  }
  ficha(el, m);
}

const celulaTxt = m => { const ns = COM.filter(x => x.celula === m.celula).map(x => x.nome); return ns.length > 2 ? `${ns[0]}, ${ns[1]} e +${ns.length - 2}` : ns.join(' e '); };

function regiaoResumo(el) {
  el.dataset.chave = '';
  if (!COM.length) { el.innerHTML = `<div class="sec"><p class="nota">Nenhum município tem histórico suficiente para prever.</p></div>`; return; }
  const vs = COM.map(m => ({ m, v: prever(m, clima(m)) })).sort((a, b) => b.v - a.v);
  const perdas = [...COM].sort((a, b) => (b.prev.Seco - b.prev.Normal) - (a.prev.Seco - a.prev.Normal));
  const W = 360, H = 96, lo = Math.floor((vs.at(-1).v - 200) / 500) * 500, hi = Math.ceil((vs[0].v + 200) / 500) * 500, X = lin(lo, hi, 18, W - 18);
  const pil = []; let g = '';
  for (let k = lo; k <= hi; k += 500) g += `<line x1="${X(k)}" x2="${X(k)}" y1="6" y2="${H - 20}" stroke="rgba(242,234,221,.07)"/><text x="${X(k)}" y="${H - 6}" text-anchor="middle">${fmt(k)}</text>`;
  [...vs].reverse().forEach(({ m, v }) => { const x = X(v); let nivel = 0; while (pil.some(p => p.n === nivel && Math.abs(p.x - x) < 11)) nivel++; pil.push({ x, n: nivel });
    g += `<circle class="pt-reg" data-n="${esc(m.nome)}" cx="${x}" cy="${H - 30 - nivel * 11}" r="5" fill="${corRend(v)}" stroke="#1C1611" stroke-width="1.2" style="cursor:pointer"><title>${esc(m.nome)}: ${fmt(v)} kg/ha</title></circle>`; });
  const larg = X(lo + 2 * ERRO) - X(lo);
  g += `<g transform="translate(${X(lo) + 4},10)"><line x1="0" x2="${larg}" y1="0" y2="0" stroke="#BDAC97"/><line x1="0" x2="0" y1="-3" y2="3" stroke="#BDAC97"/><line x1="${larg}" x2="${larg}" y1="-3" y2="3" stroke="#BDAC97"/><text x="${larg / 2}" y="13" text-anchor="middle" style="fill:#BDAC97">largura da faixa de erro</text></g>`;
  const perda = m => sinal(m.prev.Seco - m.prev.Normal);
  el.innerHTML = `
    <div class="sec">
      <span class="rot">Boletim da região · safra ${D.proxima}</span>
      <div class="f-nome" style="margin-top:8px">Alta Paulista</div>
      <div class="f-meta">${D.municipios.length} municípios · cenário ${S.cen.toLowerCase()}</div>
      <p class="nota" style="margin-top:14px;color:var(--txt-2)">Clique num município no mapa ou na lista para ver a previsão, o porquê e simular o clima.</p>
    </div>
    <div class="sec">
      <h3><span class="rot">Os ${COM.length} no mesmo eixo, kg/ha</span></h3>
      <svg viewBox="0 0 ${W} ${H}" style="width:100%">${g}</svg>
      <p class="nota" style="margin-top:8px">Boa parte dos municípios cabe numa única faixa de erro: entre vizinhos de ranking, o histórico pesa mais que a diferença prevista.</p>
    </div>
    <div class="sec">
      <h3><span class="rot">Destaques no cenário ${S.cen.toLowerCase()}</span></h3>
      <div class="stats" style="grid-template-columns:1fr 1fr">
        <div><span class="rot">Maior rendimento</span><div class="x">${fmt(vs[0].v)}</div><small>${esc(vs[0].m.nome)}</small></div>
        <div><span class="rot">Menor rendimento</span><div class="x">${fmt(vs.at(-1).v)}</div><small>${esc(vs.at(-1).m.nome)}</small></div>
        <div><span class="rot">Menor perda no seco</span><div class="x">${perda(perdas[0])}</div><small>${esc(celulaTxt(perdas[0]))}</small></div>
        <div><span class="rot">Maior perda no seco</span><div class="x">${perda(perdas.at(-1))}</div><small>${esc(celulaTxt(perdas.at(-1)))}</small></div>
      </div>
      <p class="nota" style="margin-top:10px">A perda no ano seco depende só do clima, e a NASA POWER dá ${NCEL} séries de clima para os ${D.municipios.length} municípios: quem divide a célula perde igual.</p>
    </div>`;
  el.querySelectorAll('.pt-reg').forEach(c => { c.onclick = () => selecionar(c.dataset.n); c.onmouseenter = () => quente(c.dataset.n); c.onmouseleave = () => quente(null); });
}

function ficha(el, m) {
  const chave = m.nome + '|' + S.cen + '|' + VERSAO;
  if (el.dataset.chave !== chave) {
    el.dataset.chave = chave;
    const viz = D.municipios.filter(x => x.celula === m.celula && x !== m).length;
    el.innerHTML = `
      <div class="sec">
        <div class="f-cab">
          <div><div class="f-nome">${esc(m.nome)}</div><div class="f-meta">IBGE ${m.codigo} · célula de clima ${m.celula + 1}${viz ? ` com ${viz} vizinho${viz > 1 ? 's' : ''}` : ''}</div></div>
          <button class="fechar" data-fechar-ficha aria-label="Fechar">×</button>
        </div>
        <div class="f-acoes"><button class="btn" data-fav></button><button class="btn" data-comp></button></div>
        <div class="f-num"><span class="v" data-f-v></span><span class="u">kg/ha</span></div>
        <div class="f-sub" data-f-sub></div>
        <div class="reg" data-f-reg><div class="ax"></div><div class="fx"></div><div class="ag"></div></div>
        <div class="reg-leg"><span>piso <b data-f-lo></b></span><span>teto <b data-f-hi></b></span></div>
        <p class="nota" style="margin-top:8px">Piso e teto: ± ${fmt(ERRO)} kg/ha, o erro médio do modelo em safras que ele não tinha visto. Não é intervalo de confiança.</p>
      </div>
      <div class="sec">
        <h3><span class="rot">Nos três cenários</span></h3>
        <div class="cen-chips" data-f-cen></div>
        <div class="stats" data-f-stats style="margin-top:10px"></div>
      </div>
      <div class="sec">
        <h3><span class="rot">Por que esse número</span></h3>
        <table class="porque" data-f-porque></table>
        <div class="vars" data-f-vars></div>
      </div>
      <div class="sec">
        <h3><span class="rot">Simular o clima de dez a fev</span><button class="reset" data-f-reset>Voltar ao cenário</button></h3>
        <div data-f-sl></div>
        <p class="nota" style="margin-top:8px">Os traços no trilho são os cenários seco, normal e chuvoso. Os limites são o mínimo e o máximo que ${esc(m.nome)} já teve desde ${ANOS[0]}: fora deles o modelo estaria chutando.</p>
      </div>
      <div class="sec">
        <h3><span class="rot">Safras desde ${ANOS[0]}</span><button class="link" data-f-bol>Abrir boletim →</button></h3>
        <div class="spark" data-f-spark></div>
      </div>`;
    el.querySelector('[data-fechar-ficha]').onclick = () => selecionar(null);
    el.querySelector('[data-f-bol]').onclick = () => irPara('boletim');
    el.querySelector('[data-f-reset]').onclick = () => { S.aj = null; el.dataset.chave = ''; render(); };
    const c0 = clima(m);
    el.querySelector('[data-f-sl]').innerHTML = COL.map((k, i) => { const [a, b] = m.lim[k], d = DEC[k], P = v => `calc(${b > a ? (v - a) / (b - a) : 0.5} * (100% - 14px) + 7px)`;
      return `<div class="sl" data-k="${k}"><div class="sl-top"><label for="sl${i}">${ROT[k]}</label><output></output></div>
        <div class="sl-trilho">${CEN.map(c => `<span class="mk" style="left:${P(m.cenarios[c][k])};background:${COR[c]}"></span>`).join('')}<input id="sl${i}" type="range" min="${a}" max="${b}" step="${d ? 0.1 : 1}" value="${(+c0[k]).toFixed(d)}"></div>
        <div class="sl-pe"><span>${fmt(a, d)}</span><span>efeito <b class="ef"></b> kg/ha</span><span>${fmt(b, d)}</span></div></div>`; }).join('');
    el.querySelectorAll('[data-f-sl] input').forEach(inp => inp.oninput = () => {
      if (!ajustado(m)) S.aj = { mun: m.nome, cen: S.cen, v: { ...m.cenarios[S.cen] } };
      S.aj.v[inp.closest('.sl').dataset.k] = +inp.value;
      fichaViva(m); mapa(); lista();
    });
  }
  const f = S.fav.has(m.nome), noc = S.comp.includes(m.nome), bf = el.querySelector('[data-fav]'), bc = el.querySelector('[data-comp]');
  bf.textContent = f ? '★ Nos meus municípios' : '☆ Guardar'; bf.classList.toggle('on', f); bf.onclick = () => alternarFav(m.nome);
  bc.textContent = noc ? '✓ Na comparação' : '+ Comparar'; bc.classList.toggle('on', noc);
  bc.disabled = !noc && S.comp.length >= 4; bc.onclick = () => alternarComp(m.nome);
  fichaViva(m);
}

function fichaViva(m) {
  const c = clima(m), cs = contrib(c), v = prever(m, c), q = s => $('[data-dir]').querySelector(s);
  contar(q('[data-f-v]'), v);
  q('[data-f-sub]').innerHTML = `Safra ${D.proxima} · cenário <b style="color:${COR[S.cen]}">${S.cen.toLowerCase()}</b>${ajustado(m) ? ' <b>ajustado</b>' : ''}`;
  const X = lin(1000, 6500, 0, 100), r = q('[data-f-reg]');
  if (!r.dataset.ok) { r.dataset.ok = 1; r.insertAdjacentHTML('beforeend', [2000, 3000, 4000, 5000, 6000].map(k => `<span class="tk" style="left:${X(k)}%">${fmt(k)}</span>`).join('')); }
  r.querySelector('.fx').style.left = clamp(X(v - ERRO), 0, 100) + '%'; r.querySelector('.fx').style.width = (clamp(X(v + ERRO), 0, 100) - clamp(X(v - ERRO), 0, 100)) + '%';
  r.querySelector('.ag').style.left = clamp(X(v), 0, 100) + '%';
  q('[data-f-lo]').textContent = fmt(v - ERRO); q('[data-f-hi]').textContent = fmt(v + ERRO);

  q('[data-f-cen]').innerHTML = CEN.map(k => { const x = k === S.cen ? v : m.prev[k], cr = corRend(x);
    return `<button class="cen-chip" data-cen="${k}" aria-pressed="${k === S.cen}" style="background:${cr};color:${tinta(cr)}"><span class="k"><i style="background:${COR[k]}"></i>${k}</span><div class="x">${fmt(x)}</div></button>`; }).join('');
  q('[data-f-cen]').querySelectorAll('button').forEach(b => b.onclick = () => mudarCenario(b.dataset.cen));
  const ord = COM.map(x => ({ n: x.nome, v: prever(x, clima(x)) })).sort((a, b) => b.v - a.v);
  const perdas = [...COM].sort((a, b) => (b.prev.Seco - b.prev.Normal) - (a.prev.Seco - a.prev.Normal));
  q('[data-f-stats]').innerHTML =
    `<div><span class="rot">Posição</span><div class="x">${ord.findIndex(o => o.n === m.nome) + 1}º</div><small>de ${ord.length}</small></div>` +
    `<div><span class="rot">Ano seco</span><div class="x">${sinal(m.prev.Seco - m.prev.Normal)}</div><small>${perdas.indexOf(m) + 1}º menor perda</small></div>` +
    `<div><span class="rot">Erro aqui</span><div class="x">${m.wf.length ? '±' + fmt(erroLocal(m)) : '—'}</div><small>${m.wf.length} safras</small></div>`;

  const cl = soma(cs), passos = [[`Média ${m.anosMedia[0]}–${m.anosMedia.at(-1)}`, m.media, m.media, fmt(m.media), '#8B7A69'],
    ['Tendência de alta', m.media, m.media + M.b, sinal(M.b), '#BDAC97'],
    ['Clima do cenário' + (ajustado(m) ? '*' : ''), m.media + M.b, v, sinal(cl), cl >= 0 ? '#86B06F' : '#D45A43']];
  const todos = passos.flatMap(p => [p[1], p[2]]), XP = lin(Math.min(...todos) - 40, Math.max(...todos) + 40, 0, 100);
  q('[data-f-porque]').innerHTML = passos.map(([rot, de, ate, t, cor], i) => `<tr><td>${rot}</td><td><div class="bar"><i style="left:${XP(Math.min(de, ate))}%;width:${i ? Math.max(1, Math.abs(XP(ate) - XP(de))) : 0.8}%;background:${cor}"></i></div></td><td>${t}</td></tr>`).join('') +
    `<tr class="tot"><td>Previsão</td><td><div class="bar"><i style="left:${XP(v)}%;width:1.2%;background:var(--amendoim);height:14px;top:-2px"></i></div></td><td>${fmt(v)}</td></tr>`;
  q('[data-f-vars]').innerHTML = COL.map((k, i) => `<span>${CURTO[k]} <b>${sinal(cs[i])}</b></span>`).join('') + `<span>todo o clima <b>${sinal(cl)}</b> · erro típico <b>±${fmt(ERRO)}</b></span>`;

  q('[data-f-sl]').querySelectorAll('.sl').forEach((d, i) => { const k = d.dataset.k; d.querySelector('output').innerHTML = `${fmt(c[k], DEC[k])} <small>${UN[k]}</small>`; d.querySelector('.ef').textContent = sinal(cs[i]); });
  q('[data-f-reset]').disabled = !ajustado(m);
  spark(m, v);
}

function spark(m, v) {
  const W = 360, H = 120, X = lin(ANOS[0], D.proxima, 30, W - 8), Y = lin(0, 7000, H - 16, 6);
  let g = '';
  for (let k = 0; k <= 6000; k += 3000) g += `<line x1="30" x2="${W - 8}" y1="${Y(k)}" y2="${Y(k)}" stroke="rgba(242,234,221,${k ? .07 : .2})"/><text x="24" y="${Y(k) + 3}" text-anchor="end">${k / 1000}k</text>`;
  [ANOS[0], 2010, 2020, D.proxima].filter(a => a >= ANOS[0]).forEach(a => g += `<text x="${X(a)}" y="${H - 2}" text-anchor="middle">${a}</text>`);
  let d = '', ant = false;
  ANOS.forEach((a, i) => { const h = m.hist[i]; if (!h) { ant = false; return; } d += (ant ? 'L' : 'M') + X(a).toFixed(1) + ',' + Y(h.r).toFixed(1); ant = true; });
  g += `<path d="${d}" fill="none" stroke="#BDAC97" stroke-width="1.3"/>`;
  ANOS.forEach((a, i) => { const h = m.hist[i]; if (h) g += `<circle cx="${X(a)}" cy="${Y(h.r)}" r="2.6" fill="${valida(h) ? (COR[TER[m.nome][a]] || '#8B7A69') : '#1C1611'}" stroke="${valida(h) ? 'none' : '#8B7A69'}"/>`; });
  g += `<rect x="${X(D.proxima) - 4}" y="${Y(v + ERRO)}" width="8" height="${Y(v - ERRO) - Y(v + ERRO)}" rx="2" fill="rgba(242,234,221,.14)"/><circle cx="${X(D.proxima)}" cy="${Y(v)}" r="4.5" fill="#D6A26B"/>`;
  $('[data-dir]').querySelector('[data-f-spark]').innerHTML = `<svg viewBox="0 0 ${W} ${H}">${g}</svg><p class="nota" style="margin-top:6px">Cada ponto tem a cor do clima que a safra teve: <span style="color:${COR.Seco}">seco</span>, <span style="color:${COR.Normal}">normal</span> ou <span style="color:${COR.Chuvoso}">chuvoso</span>. Vazado: menos de ${D.areaMin} ha, fora do modelo.</p>`;
}

/* =====================================================================
   CAMADAS SOBRE O MAPA: comparar, boletim, método
   ===================================================================== */
function irPara(v) {
  S.vista = v; $('[data-sobre]').scrollTop = 0;
  $$('.topo nav button').forEach(b => b.setAttribute('aria-current', b.dataset.vista === (v === 'boletim' ? 'mapa' : v)));
  render();
}
function sobre() {
  const el = $('[data-sobre]');
  if (S.vista === 'mapa') { el.hidden = true; return; }
  el.hidden = false;
  if (S.vista === 'comparar') comparar(el);
  if (S.vista === 'boletim') boletim(el);
  if (S.vista === 'metodo') metodo(el);
}
const cab = (t, sub) => `<div class="sobre-cab"><div><span class="rot">${sub}</span><h2>${t}</h2></div><button class="fechar" data-fechar aria-label="Voltar ao mapa">×</button></div>`;
const ligarFechar = el => el.querySelectorAll('[data-fechar]').forEach(b => b.onclick = () => irPara('mapa'));

function comparar(el) {
  const sel = S.comp.map(n => MUN[n]).filter(m => m && temPrev(m));
  if (sel.length < 2) {
    const favs = [...S.fav].filter(n => MUN[n] && temPrev(MUN[n]));
    el.innerHTML = `<div class="sobre-in">${cab('Comparar municípios', 'Cenário ' + S.cen.toLowerCase())}<div class="cartao" style="text-align:center;padding:48px 20px"><p style="margin:0 0 6px;font-size:16px">Escolha de 2 a 4 municípios.</p><p class="nota">No mapa, abra um município e use <b style="color:var(--txt)">+ Comparar</b>. Eles ficam na bandeja embaixo do mapa.</p>${favs.length > 1 ? `<button class="btn" data-cmp-fav style="margin-top:16px">Comparar os meus municípios</button>` : ''}</div></div>`;
    ligarFechar(el); const b = el.querySelector('[data-cmp-fav]'); if (b) b.onclick = () => { S.comp = favs.slice(0, 4); render(); };
    return;
  }
  const vs = sel.map(m => prever(m, clima(m))), W = 1176, rh = 46, ml = 150, H = sel.length * rh + 30;
  const lo = Math.floor((Math.min(...vs) - ERRO - 250) / 500) * 500, hi = Math.ceil((Math.max(...vs) + ERRO + 250) / 500) * 500, X = lin(lo, hi, ml, W - 24);
  let g = '';
  for (let k = lo; k <= hi; k += 250) g += `<line x1="${X(k)}" x2="${X(k)}" y1="0" y2="${sel.length * rh}" stroke="rgba(242,234,221,${k % 1000 ? .04 : .1})"/>` + (k % 500 ? '' : `<text x="${X(k)}" y="${H - 6}" text-anchor="middle">${fmt(k)}</text>`);
  sel.forEach((m, i) => { const y = i * rh + rh / 2, v = vs[i];
    g += `<text x="0" y="${y + 5}" style="font-family:var(--sans);font-size:15px;font-weight:600;fill:#F2EADD">${esc(m.nome)}</text>` +
      `<rect x="${X(v - ERRO)}" y="${y - 11}" width="${X(v + ERRO) - X(v - ERRO)}" height="22" rx="4" fill="rgba(242,234,221,.08)" stroke="rgba(242,234,221,.18)"/>` +
      CEN.map(c => c === S.cen ? '' : `<line x1="${X(m.prev[c])}" x2="${X(m.prev[c])}" y1="${y - 7}" y2="${y + 7}" stroke="${COR[c]}" stroke-width="2"/>`).join('') +
      `<circle cx="${X(v)}" cy="${y}" r="7" fill="${PIN[i]}" stroke="#14100C" stroke-width="2"/><text x="${X(v)}" y="${y - 15}" text-anchor="middle" style="fill:#F2EADD;font-size:11px">${fmt(v)}</text>`; });
  const dif = Math.max(...vs) - Math.min(...vs);
  const H2 = 230, X2 = lin(ANOS[0], D.proxima, 40, W - 10), Y2 = lin(0, 7000, H2 - 22, 8);
  let g2 = '';
  for (let k = 0; k <= 6000; k += 2000) g2 += `<line x1="40" x2="${W - 10}" y1="${Y2(k)}" y2="${Y2(k)}" stroke="rgba(242,234,221,${k ? .06 : .2})"/><text x="34" y="${Y2(k) + 3}" text-anchor="end">${fmt(k)}</text>`;
  for (let a = Math.ceil(ANOS[0] / 5) * 5; a < D.proxima; a += 5) g2 += `<text x="${X2(a)}" y="${H2 - 4}" text-anchor="middle">${a}</text>`;
  g2 += `<text x="${X2(D.proxima)}" y="${H2 - 4}" text-anchor="middle" style="fill:#F2EADD">${D.proxima}</text>`;
  sel.forEach((m, i) => { let d = '', ant = false;
    ANOS.forEach((a, j) => { const h = m.hist[j]; if (!valida(h)) { ant = false; return; } d += (ant ? 'L' : 'M') + X2(a).toFixed(1) + ',' + Y2(h.r).toFixed(1); ant = true; });
    const x = X2(D.proxima) + (i - 1.5) * 5;
    g2 += `<path d="${d}" fill="none" stroke="${PIN[i]}" stroke-width="1.8" stroke-opacity=".9"/><line x1="${x}" x2="${x}" y1="${Y2(vs[i] + ERRO)}" y2="${Y2(vs[i] - ERRO)}" stroke="${PIN[i]}" stroke-opacity=".35" stroke-width="3"/><circle cx="${x}" cy="${Y2(vs[i])}" r="4.5" fill="${PIN[i]}"/>`; });
  const melhor = (f, max = true) => { const xs = sel.map(f); const a = max ? Math.max(...xs) : Math.min(...xs); return xs.map(x => x === a && new Set(xs).size > 1); };
  const mPerda = melhor(m => m.prev.Seco - m.prev.Normal), mErro = melhor(m => erroLocal(m) ?? Infinity, false);
  el.innerHTML = `<div class="sobre-in">${cab('Comparar municípios', 'Mesmo cenário para todos: ' + S.cen.toLowerCase())}
    <div class="cartao"><span class="rot">Previsão e faixa de erro, kg/ha</span><svg viewBox="0 0 ${W} ${H}" style="width:100%;margin-top:14px">${g}</svg>
      <p class="nota" style="margin-top:10px;color:var(--txt-2)">${dif < ERRO ? `Do maior ao menor são <b style="color:var(--txt)">${fmt(dif)} kg/ha</b>, menos que o erro típico de ± ${fmt(ERRO)}. As faixas se cruzam: pelo número sozinho estes municípios empatam, e o histórico e a perda no ano seco decidem.` : `Do maior ao menor são <b style="color:var(--txt)">${fmt(dif)} kg/ha</b>, mais que o erro típico de ± ${fmt(ERRO)}.`} Traços: os outros dois cenários.</p></div>
    <div class="cols" style="grid-template-columns:repeat(${sel.length},1fr);margin-top:12px">${sel.map((m, i) => { const v = vs[i];
      return `<div class="cartao col"><h4><i style="background:${PIN[i]}"></i>${esc(m.nome)}</h4><div class="big">${fmt(v)}</div><span class="nota">kg/ha · faixa ${fmt(v - ERRO)}–${fmt(v + ERRO)}${ajustado(m) ? ' · clima ajustado' : ''}</span>
        <div class="cen-chips" style="margin-top:14px">${CEN.map(c => { const k = corRend(m.prev[c]); return `<div class="cen-chip" style="background:${k};color:${tinta(k)};${c === S.cen ? 'border-color:#F2EADD' : ''}"><span class="k">${c}</span><div class="x" style="font-size:13px">${fmt(m.prev[c])}</div></div>`; }).join('')}</div>
        <dl><dt>Perda no ano seco</dt><dd style="${mPerda[i] ? 'color:var(--chuvoso)' : ''}">${sinal(m.prev.Seco - m.prev.Normal)}</dd><dt>Média ${m.anosMedia[0]}–${m.anosMedia.at(-1)}</dt><dd>${fmt(m.media)}</dd><dt>Erro do modelo aqui</dt><dd style="${mErro[i] ? 'color:var(--chuvoso)' : ''}">${m.wf.length ? '± ' + fmt(erroLocal(m)) : '—'}</dd><dt>Safras usadas</dt><dd>${m.hist.filter(valida).length}</dd><dt>Célula de clima</dt><dd>${m.celula + 1}</dd></dl>
        <div style="display:flex;gap:6px;margin-top:14px"><button class="btn" data-abrir="${esc(m.nome)}">Abrir no mapa</button><button class="btn" data-tirar="${esc(m.nome)}">Tirar</button></div></div>`; }).join('')}</div>
    <div class="cartao" style="margin-top:12px"><span class="rot">Rendimento por safra, só safras com ${D.areaMin} ha ou mais</span><svg viewBox="0 0 ${W} ${H2}" style="width:100%;margin-top:12px">${g2}</svg></div>
    <p class="nota" style="margin-top:12px">Em verde, o melhor da linha. Municípios na mesma célula de clima recebem o mesmo cenário: o que os separa é o histórico.</p></div>`;
  ligarFechar(el);
  el.querySelectorAll('[data-abrir]').forEach(b => b.onclick = () => selecionar(b.dataset.abrir));
  el.querySelectorAll('[data-tirar]').forEach(b => b.onclick = () => alternarComp(b.dataset.tirar));
}

/* Boletim das safras: um meteograma por ano, à maneira do meteoblue. */
function boletim(el) {
  const m = MUN[S.sel]; if (!m) { irPara('mapa'); return; }
  const v = temPrev(m) ? prever(m, clima(m)) : null, anos = [...ANOS, D.proxima], ter = TER[m.nome];
  const W = 1176, lab = 150, cw = (W - lab) / anos.length, H = 200, X = a => lab + (anos.indexOf(a) + 0.5) * cw, Y = lin(0, 7000, H - 8, 10);
  let g = '';
  for (let k = 0; k <= 7000; k += 1000) g += `<line x1="${lab}" x2="${W}" y1="${Y(k)}" y2="${Y(k)}" stroke="rgba(242,234,221,${k ? .05 : .2})"/>` + (k % 2000 ? '' : `<text x="${lab - 8}" y="${Y(k) + 3}" text-anchor="end">${fmt(k)}</text>`);
  g += `<text x="0" y="${Y(3500)}" style="font-family:var(--sans);font-size:12px;fill:#BDAC97">Rendimento, kg/ha</text>`;
  if (v != null) g += `<rect x="${X(D.proxima) - cw * 0.35}" y="${Y(v + ERRO)}" width="${cw * 0.7}" height="${Y(v - ERRO) - Y(v + ERRO)}" rx="3" fill="rgba(242,234,221,.12)"/>`;
  m.wf.forEach(w => g += `<line x1="${X(w.a)}" x2="${X(w.a)}" y1="${Y(w.p)}" y2="${Y(w.r)}" stroke="rgba(214,162,107,.5)"/><line x1="${X(w.a) - cw * .3}" x2="${X(w.a) + cw * .3}" y1="${Y(w.p)}" y2="${Y(w.p)}" stroke="#D6A26B" stroke-width="2"/>`);
  let d = '', ant = false;
  ANOS.forEach((a, i) => { const h = m.hist[i]; if (!h) { ant = false; return; } d += (ant ? 'L' : 'M') + X(a) + ',' + Y(h.r); ant = true; });
  g += `<path d="${d}" fill="none" stroke="#F2EADD" stroke-width="1.6"/>`;
  ANOS.forEach((a, i) => { const h = m.hist[i]; if (h) { const c = corRend(clamp(h.r, E0, E1 - 1)); g += `<circle cx="${X(a)}" cy="${Y(h.r)}" r="4.2" fill="${valida(h) ? c : '#14100C'}" stroke="${valida(h) ? '#14100C' : c}" stroke-width="1.4"><title>${a}: ${fmt(h.r)} kg/ha</title></circle>`; } });
  if (v != null) g += `<circle cx="${X(D.proxima)}" cy="${Y(v)}" r="6" fill="${COR[S.cen]}" stroke="#14100C" stroke-width="2"/>`;

  const cel = (txt, cor) => `<td style="background:${cor};color:${tinta(cor)}">${txt}</td>`;
  const vazio = '<td style="background:transparent;color:var(--txt-3)">·</td>';
  const cAtual = v != null ? clima(m) : null;
  const linhaClima = (k, R) => { const xs = m.clima[k].filter(x => x != null), a = Math.min(...xs), b = Math.max(...xs), t = x => b > a ? (x - a) / (b - a) : 0.5, d = k === 'temp_max_critica_c' ? 1 : 0;
    return `<tr><td class="r">${ROT[k]} <span class="nota">${UN[k]}</span></td>${ANOS.map((_, i) => { const x = m.clima[k][i]; return x == null ? vazio : cel(fmt(x, d), R(t(x))); }).join('')}${cAtual ? cel(fmt(cAtual[k], d), R(t(cAtual[k]))) : vazio}</tr>`; };
  const tab = `<table class="mg"><colgroup><col style="width:${lab / W * 100}%">${anos.map(() => '<col>').join('')}</colgroup>
    <thead><tr><th></th>${anos.map(a => `<th style="${a === D.proxima ? 'color:var(--txt)' : ''}">${String(a).slice(2)}</th>`).join('')}</tr></thead><tbody>
    <tr><td class="r">Cenário do ano</td>${ANOS.map(a => ter[a] ? `<td style="background:${COR[ter[a]]};color:#14100C;font-weight:600">${ter[a][0]}</td>` : vazio).join('')}${v != null ? `<td style="background:${COR[S.cen]};color:#14100C;font-weight:600;outline:1px solid #F2EADD">${S.cen[0]}</td>` : vazio}</tr>
    ${linhaClima('chuva_critica_mm', R_CHUVA)}${linhaClima('temp_max_critica_c', R_CALOR)}${linhaClima('dias_calor_critica', R_CALOR)}${linhaClima('radiacao_critica_mj_m2', R_NEUTRA)}
    <tr><td class="r">Área colhida <span class="nota">ha</span></td>${ANOS.map((a, i) => { const h = m.hist[i]; return !h || h.ac == null ? vazio : `<td style="background:${valida(h) ? '#33281F' : 'transparent'};color:${valida(h) ? 'var(--txt)' : 'var(--seco)'}">${h.ac >= 1000 ? fmt(h.ac / 1000, 1) + 'k' : fmt(h.ac)}</td>`; }).join('')}${vazio}</tr>
    <tr><td class="r">Erro do modelo <span class="nota">kg/ha</span></td>${ANOS.map(a => { const w = m.wf.find(x => x.a === a); if (!w) return vazio; const e = w.p - w.r, k = clamp(Math.abs(e) / 1500, 0, 1); return `<td style="background:${R_SECO(k)};color:${tinta(R_SECO(k))}">${e > 0 ? '+' : '−'}${fmt(Math.abs(e) / 1000, 1)}k</td>`; }).join('')}${vazio}</tr>
    </tbody></table>`;
  el.innerHTML = `<div class="sobre-in">${cab(esc(m.nome) + ': boletim das safras', `${ANOS[0]} a ${ANOS.at(-1)}${v != null ? ` e a previsão de ${D.proxima}` : ''}`)}
    <div class="cartao"><div class="rolar"><div><svg viewBox="0 0 ${W} ${H}" style="width:100%">${g}</svg>${tab}</div></div>
    <p class="nota" style="margin-top:14px">Cada coluna é uma safra; o clima é o de dezembro a fevereiro, floração e enchimento da vagem. "Cenário do ano" diz em que terço da chuva a safra caiu, a mesma régua que define os cenários. Traços amendoim no gráfico: o que o modelo teria previsto sem ver a safra; a linha "Erro do modelo" é essa diferença (+ previu acima). Área em vermelho: menos de ${D.areaMin} ha, fora do modelo.${v != null ? ` A última coluna é o cenário ${S.cen.toLowerCase()}${ajustado(m) ? ', com o seu ajuste' : ''}.` : ''}</p></div></div>`;
  ligarFechar(el);
}

function metodo(el) {
  const V = D.validacao, T = D.teste;
  const P = V ? V.previsores : {}, kP = Object.keys(P);
  const pv = kP.find(k => k.startsWith(M.nome) && k.includes('fase crítica'));
  const rv = T ? T.regua : kP.slice(0, 4).find(k => Math.abs(P[k].ganho_sobre_baseline) < 1e-9);
  const TM = T ? T.metricas : {}, kT = Object.keys(TM), pt = kT.find(k => k.includes('(principal)'));
  const anosT = T && pt ? Object.keys(T.mae_por_ano[pt]) : [];
  const W = 1176;
  let cartaoTeste = '', cartaoVal = '', grafTeste = '';
  if (T && pt && TM[rv]) {
    cartaoTeste = `<div class="cartao"><span class="rot">Teste ${anosT[0]}–${anosT.at(-1)}, aberto uma única vez</span><div class="big">${sinal(TM[pt].ganho_sobre_regua)} <small>kg/ha de erro a menos</small></div><p>O modelo com clima errou <b style="color:var(--txt)">${fmt(TM[pt].mae)}</b> kg/ha; o melhor palpite sem clima, <b style="color:var(--txt)">${fmt(TM[rv].mae)}</b>. Quase todo o ganho veio de 2024, o ano da quebra.</p></div>`;
    const H = 230, mx = Math.ceil(Math.max(...anosT.flatMap(a => [T.mae_por_ano[pt][a], T.mae_por_ano[rv][a]])) / 600) * 600, Y = lin(0, mx, H - 24, 18), cw = (W - 50) / anosT.length;
    let g = '';
    for (let k = 0; k <= mx; k += 600) g += `<line x1="50" x2="${W}" y1="${Y(k)}" y2="${Y(k)}" stroke="rgba(242,234,221,${k ? .06 : .2})"/><text x="42" y="${Y(k) + 3}" text-anchor="end">${fmt(k)}</text>`;
    anosT.forEach((a, j) => { const x = 50 + j * cw + cw / 2;
      [[rv, '#5C4A3A', -46], [pt, '#D6A26B', 6]].forEach(([k, c, dx]) => { const v = T.mae_por_ano[k][a];
        g += `<rect x="${x + dx}" y="${Y(v)}" width="40" height="${Y(0) - Y(v)}" rx="3" fill="${c}"/><text x="${x + dx + 20}" y="${Y(v) - 6}" text-anchor="middle" style="fill:#F2EADD;font-size:11px">${fmt(v)}</text>`; });
      g += `<text x="${x}" y="${H - 4}" text-anchor="middle" style="fill:#F2EADD;font-size:12px">${a}</text>`; });
    grafTeste = `<div class="cartao" style="margin-top:12px"><span class="rot">Erro médio por safra do teste, kg/ha</span><svg viewBox="0 0 ${W} ${H}" style="width:100%;margin-top:12px">${g}</svg><p class="nota" style="margin-top:8px"><span style="color:#D6A26B">■</span> ${esc(M.nome)}, o modelo do painel · <span style="color:#8B7A69">■</span> ${esc(rv)}, a régua sem clima. Em 2024 a seca derrubou a safra e todos os palpites erraram muito.</p></div>`;
  } else {
    cartaoTeste = `<div class="cartao"><span class="rot">Teste final</span><p style="margin-top:10px">O teste de 2023 a 2025 ainda não foi aberto nesta máquina. Rode <code>python scripts/avaliar_teste.py --abrir-teste</code>.</p></div>`;
  }
  if (V && pv && rv && P[rv]) {
    cartaoVal = `<div class="cartao"><span class="rot">Validação ${V.anos[0]}–${V.anos[1]}, ano a ano</span><div class="big" style="color:var(--txt-2)">${sinal(P[pv].ganho_sobre_baseline)} <small>kg/ha de erro a menos</small></div><p>${fmt(P[pv].mae)} contra ${fmt(P[rv].mae)}. Dentro do ruído: o erro varia ± ${fmt(P[pv].mae_desvio_entre_anos)} de um ano para outro. Conclusão honesta: o clima municipal agregado acrescenta pouco, e ajuda mais no ano ruim.</p></div>`;
  } else {
    cartaoVal = `<div class="cartao"><span class="rot">Validação</span><p style="margin-top:10px">A comparação entre modelos ainda não rodou nesta máquina. Rode <code>python scripts/comparar.py</code> (cerca de 40 segundos).</p></div>`;
  }
  const fs = COL.map((c, i) => ({ c, k: M.coef[i], sd: M.sd[i] })).sort((a, b) => a.k - b.k);
  const rh = 40, H2 = fs.length * rh, lim = Math.ceil(Math.max(...fs.map(f => Math.abs(f.k))) / 10) * 10 + 10, X = lin(-lim, lim, 180, 760);
  let g2 = `<line x1="${X(0)}" x2="${X(0)}" y1="0" y2="${H2}" stroke="rgba(242,234,221,.25)"/>`;
  fs.forEach((f, i) => { const y = i * rh + rh / 2;
    g2 += `<text x="0" y="${y + 4}" style="font-family:var(--sans);font-size:14px;fill:#F2EADD">${ROT[f.c]}</text><rect x="${Math.min(X(0), X(f.k))}" y="${y - 7}" width="${Math.abs(X(f.k) - X(0))}" height="14" rx="3" fill="${f.k < 0 ? '#D45A43' : '#86B06F'}"/>` +
      `<text x="${X(f.k) + (f.k < 0 ? -8 : 8)}" y="${y + 4}" text-anchor="${f.k < 0 ? 'end' : 'start'}" style="fill:#F2EADD;font-size:11px">${sinal(f.k)}</text><text x="800" y="${y + 4}">uma variação típica = ${fmt(f.sd, DEC[f.c] || 1)} ${UN[f.c]}</text>`; });
  const tr = (k, cols) => `<tr class="${k === pv || k === pt ? 'dest' : ''}"><td>${esc(k)}</td>${cols.map(c => `<td>${c}</td>`).join('')}</tr>`;
  const tabelas = (V ? `<table class="tab"><thead><tr><th>Validação ${V.anos.join('–')}</th><th>Erro médio</th><th>Variação entre anos</th><th>RMSE</th><th>R²</th><th>Ganho sobre a régua</th></tr></thead><tbody>${kP.slice().sort((a, b) => P[a].mae - P[b].mae).map(k => tr(k, [fmt(P[k].mae), fmt(P[k].mae_desvio_entre_anos), fmt(P[k].rmse), fmt(P[k].r2, 2), sinal(P[k].ganho_sobre_baseline)])).join('')}</tbody></table>` : '') +
    (T ? `<table class="tab" style="margin-top:24px"><thead><tr><th>Teste ${anosT.join(', ')}</th><th>Erro médio</th><th>RMSE</th><th>Ganho sobre a régua</th>${anosT.map(a => `<th>${a}</th>`).join('')}</tr></thead><tbody>${kT.slice().sort((a, b) => TM[a].mae - TM[b].mae).map(k => tr(k, [fmt(TM[k].mae), fmt(TM[k].rmse), sinal(TM[k].ganho_sobre_regua), ...anosT.map(a => fmt(T.mae_por_ano[k][a]))])).join('')}</tbody></table>` : '');
  el.innerHTML = `<div class="sobre-in">${cab('Como o número é feito', 'Método · para validar antes de recomendar')}
    <div class="tese">${cartaoTeste}${cartaoVal}</div>${grafTeste}
    <div class="cartao" style="margin-top:12px"><span class="rot">Quanto cada variável move a previsão, em kg/ha</span><div class="rolar"><svg viewBox="0 0 ${W} ${H2}" style="width:100%;margin-top:14px">${g2}</svg></div><p class="nota" style="margin-top:8px">${esc(M.nome)}, com o clima de dezembro a fevereiro. Cada barra é quanto a previsão muda quando a variável sobe uma variação típica (um desvio-padrão), com as outras paradas. Calor e radiação na floração puxam o rendimento para baixo; a chuva puxa para cima. A faixa de erro (± ${fmt(ERRO)}) é ${fmt(ERRO / Math.max(...fs.map(f => Math.abs(f.k))))} vezes a maior barra.</p></div>
    ${tabelas ? `<details class="cartao" style="margin-top:12px"><summary>Todas as métricas da validação e do teste</summary><div class="rolar" style="margin-top:14px">${tabelas}</div></details>` : ''}</div>`;
  ligarFechar(el);
}

/* =====================================================================
   ORQUESTRAÇÃO
   ===================================================================== */
function render(forcar) {
  if (!ROOT || !ROOT.isConnected) return;
  base(); lista(); mapa(forcar); painel(); sobre(); bandeja();
}

let ouvindo = false;
function ouvirJanela() {
  if (ouvindo) return; ouvindo = true;
  let rz;
  addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => render(true), 120); });
  addEventListener('keydown', e => {
    if (!ROOT || !ROOT.isConnected) return;
    const alvo = e.composedPath()[0];   // dentro do shadow DOM, e.target é o componente inteiro
    if (alvo && alvo.matches && alvo.matches('input, textarea, select')) { if (e.key === 'Escape') alvo.blur(); return; }
    if (e.key === 'Escape') { if (S.vista !== 'mapa') irPara('mapa'); else if (S.sel) selecionar(null); }
    if (['1', '2', '3'].includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) mudarCenario(CEN[+e.key - 1]);
  });
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  if (!data || !data.municipios) return;
  AVISAR = setTriggerValue;
  const nova = data.versao !== VERSAO;
  if (nova) { iniciar(data); VERSAO = data.versao; PROJ = null; }
  if (data.modo === 'capa') { capa(parentElement); return; }

  // Favoritos: o arquivo do servidor manda quando muda; entre um clique e a
  // gravação, vale o que a tela já mostrou.
  const favs = JSON.stringify(data.favoritos || []);
  if (favs !== FAVS) { S.fav = new Set(data.favoritos || []); FAVS = favs; }
  if (S.sel && !MUN[S.sel]) S.sel = null;
  S.comp = S.comp.filter(n => MUN[n]);

  ROOT = montar(parentElement);
  ROOT.querySelector('[data-usuario]').textContent = data.usuario || '';
  ouvirJanela();
  // O primeiro desenho espera o layout: sem largura, o mapa não tem onde caber.
  requestAnimationFrame(() => render(nova));
}
