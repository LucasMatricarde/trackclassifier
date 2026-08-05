const LIMIAR_BLOCO = 0.75;
let itens = [];
let ativo = 0;

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

async function json(url, opcoes) {
  const resposta = await fetch(url, opcoes);
  if (!resposta.ok) throw new Error(`${url} respondeu ${resposta.status}`);
  return resposta.json();
}

function sparkline(curva) {
  if (!curva.length) return "";
  const maximo = Math.max(...curva) || 1;
  const pontos = curva
    .map((v, i) => `${(i / Math.max(curva.length - 1, 1)) * 100},${44 - (v / maximo) * 40}`)
    .join(" ");
  return `<svg class="sparkline" viewBox="0 0 100 44" preserveAspectRatio="none">
    <polyline points="${pontos}" fill="none" stroke="#5b8def" stroke-width="1.2"
      vector-effect="non-scaling-stroke" />
  </svg>`;
}

function minutos(segundos) {
  const m = Math.floor(segundos / 60);
  const s = Math.round(segundos % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function cardHtml(item, indice) {
  return `<div class="card ${indice === ativo ? "ativo" : ""}" data-sha1="${item.sha1}">
    <div class="cabecalho">
      <span class="nome">${esc(item.filename)}</span>
      <span class="meta">${Math.round(item.bpm)} BPM &middot; ${minutos(item.duration_s)}</span>
    </div>
    <div class="sugestao">
      <span class="rotulo" data-label="${item.label}">${item.label}</span>
      <span class="barra"><div style="width:${(item.confidence * 100).toFixed(0)}%"></div></span>
      <span class="confianca">confianca ${(item.confidence * 100).toFixed(0)}%
        &middot; escore ${item.score.toFixed(2)}</span>
    </div>
    ${sparkline(item.energy_curve)}
    <audio controls preload="none" src="/api/audio/${item.sha1}#t=${Math.floor(item.peak_offset_s)}"></audio>
    <div class="acoes">
      <button data-decidir="+1">+1</button>
      <button data-decidir="neutra">neutra</button>
      <button data-decidir="-1">-1</button>
      <button data-pular="1">pular</button>
    </div>
  </div>`;
}

function render(dados) {
  itens = dados.items;
  ativo = Math.min(ativo, Math.max(itens.length - 1, 0));

  const metricas = dados.metrics;
  document.getElementById("resumo").textContent = metricas
    ? `${itens.length} na fila · modelo com ${metricas.n_examples} exemplos, `
      + `acerto ${(metricas.accuracy * 100).toFixed(0)}%, `
      + `erro ordinal ${metricas.ordinal_mae.toFixed(2)}`
    : `${itens.length} na fila · modelo ainda nao treinado`;

  document.getElementById("aviso").innerHTML = dados.low_confidence_mode
    ? `<div class="aviso">Poucos exemplos rotulados. As confiancas estao reduzidas
       propositalmente ate o dataset crescer.</div>`
    : "";

  document.getElementById("fila").innerHTML = itens.length
    ? itens.map(cardHtml).join("")
    : `<p class="vazio">Nada na fila. Rode <code>dj scan</code> depois de baixar tracks novas.</p>`;
}

async function carregar() {
  render(await json("/api/queue"));
  const falhas = await json("/api/failures");
  document.getElementById("falhas").innerHTML = falhas.items.length
    ? falhas.items.map((f) => `<li>${esc(f.filename)} &mdash; ${esc(f.reason)}</li>`).join("")
    : `<li class="meta" style="color:#9aa0a6">Nenhuma.</li>`;
}

async function decidir(sha1, label) {
  await json("/api/decide", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sha1, label }),
  });
  await carregar();
}

document.addEventListener("click", async (evento) => {
  const alvo = evento.target;
  const card = alvo.closest?.(".card");

  if (alvo.dataset?.decidir && card) {
    await decidir(card.dataset.sha1, alvo.dataset.decidir);
  } else if (alvo.dataset?.pular && card) {
    ativo = Math.min(ativo + 1, itens.length - 1);
    render({ items: itens, metrics: null, low_confidence_mode: false });
    await carregar();
  } else if (alvo.id === "btn-bloco") {
    const resultado = await json("/api/bulk-approve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ min_confidence: LIMIAR_BLOCO }),
    });
    alert(`${resultado.moved} track(s) movida(s).`);
    await carregar();
  }
});

document.addEventListener("keydown", async (evento) => {
  if (!itens.length) return;
  const atalhos = { 1: "-1", 2: "neutra", 3: "+1" };

  if (atalhos[evento.key]) {
    evento.preventDefault();
    await decidir(itens[ativo].sha1, atalhos[evento.key]);
  } else if (evento.code === "Space") {
    evento.preventDefault();
    const player = document.querySelectorAll("audio")[ativo];
    if (player) player.paused ? player.play() : player.pause();
  }
});

carregar();
