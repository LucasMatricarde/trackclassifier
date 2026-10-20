# Aba Biblioteca no React - plano de implementacao

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portar a aba Biblioteca do PySide6 para React/TS: tabela com busca, chips de classe, filtros, inspetor, reproducao e acoes de classificar, remover e revelar no Finder.

**Architecture:** A aba consome `/api/library/state`, contrato que ja existe, e escuta `states_changed` no WebSocket singleton. `library.ts` concentra filtro e ordenacao puros (testaveis sem DOM); `LibraryToolbar`, `LibraryTable` e `LibraryInspector` sao apresentacao; `LibraryTab` orquestra selecao, player e acoes. Nao ha endpoint novo: classificar usa `/api/review/decide` (o servidor ja chama `reclassify` fora da inbox) e remover usa `/api/review/remove`.

**Tech Stack:** React 19 + TypeScript + Vite; Playwright para unidade pura e E2E; FastAPI existente; Electron preload para revelar no Finder.

**Spec:** `docs/superpowers/specs/2026-10-19-aba-biblioteca-dashboard-design.md` e mockup `design/mockup/TrackClassifier Music Library Dashboard.png`.

## Global Constraints

- Nenhum endpoint novo no backend; `LibraryState` e `TrackRow` ja bastam.
- Filtro, busca e ordenacao sao no cliente, sobre as linhas de `library_state`; as contagens dos chips sao absolutas (nao encolhem com a busca).
- Nenhum `#RRGGBB` em `web/src/`; cor so por `var(--token)` de `tokens.css`.
- Codigo, comentarios e nomes de teste em portugues sem acentos (copy de tela pode ter acento, como no resto do React).
- Testes de UI usam fixture + rota mockada e WebSocket falso; nunca decidem, movem ou removem tracks reais. O unico teste com acervo real e o de playback, e ele so le e toca.
- Gate TS: `cd web && npm run build`. Gate E2E: `TC_WEB_URL=http://127.0.0.1:8765 npx playwright test`.
- Cada task termina com os testes da task verdes e um commit.

## Review Focus

1. **Biblioteca vazia** (nenhuma track rotulada): quatro chips em 0, tabela com EmptyState e inspetor vazio; nenhum crash e nenhuma request de capa.
2. **Linha sem capa, sem key ou sem artista**: placeholder de capa, `—` no KeyChip e titulo caindo para o nome do arquivo; nada de `<img>` quebrada.
3. **Acervo grande (~464 linhas)**: sem 464 canvases nem 464 requests simultaneas; capa com `loading="lazy"`, onda de linha em SVG leve.
4. **`states_changed` durante scan/decisao**: tabela e selecao atualizam; se a track selecionada sumiu, seleciona a primeira da lista filtrada.
5. **Falha de acao** (decide/remove 404 ou 500): banner de erro e selecao preservada; a linha nao some de forma otimista.
6. **Revelar no browser puro**: o botao nao aparece (nao ha preload), sem exception.

---

## Estrutura de arquivos

- `web/src/library.ts` - tipos de visao, `applyLibraryView`, formatacao de duracao e rotulos de classe.
- `web/src/hooks/useLibraryState.ts` - fetch inicial, WS, `reload`, `peaksReady` e `requestPeaks`.
- `web/src/components/LibraryTab.tsx` - orquestracao: selecao, player, acoes, estados de erro.
- `web/src/components/LibraryToolbar.tsx` - busca, chips, genero, key e ordenacao.
- `web/src/components/LibraryTable.tsx` - tabela, capa, mini-onda, key, classe, duracao.
- `web/src/components/LibraryInspector.tsx` - ficha tecnica, onda com seek e acoes.
- `web/src/components/LibraryTransport.tsx` - play/pause, tempo e volume.
- `web/src/components/ui/MiniWave.tsx` - SVG da `energy_curve` (sem request).
- `web/src/components/ui/ClassScale.tsx` - tres segmentos ordinais da classe.
- `web/src/components/ui/ClassChip.tsx` - chip de classe do inspetor.
- `web/src/styles/library.css` - layout e tabela.
- `web/tests/library-fixtures.ts` - fixture, `mockLibrary` e WebSocket falso.
- `web/tests/library-unit.spec.ts` - `applyLibraryView` puro.
- `web/tests/library.spec.ts` - UI e acoes.
- Modificam: `web/src/api/client.ts`, `web/src/api/types.ts` (nada novo de tipo, so conferir), `web/src/components/AppHeader.tsx`, `web/src/App.tsx`, `web/src/components/ui/CoverArt.tsx`, `shell/preload.js`, `shell/main.js`, `web/src/electron.d.ts`.

---

### Task 1: Aba visivel, estado e contagem

**Files:**
- Modify: `web/src/api/client.ts`
- Create: `web/src/hooks/useLibraryState.ts`
- Create: `web/src/components/LibraryTab.tsx`
- Create: `web/src/styles/library.css`
- Modify: `web/src/components/AppHeader.tsx`
- Modify: `web/src/App.tsx`
- Test: `web/tests/library-fixtures.ts`, `web/tests/library.spec.ts`

**Interfaces:**
- Consumes: `apiFetch`, `onWSMessage`, `WSMessage`, `LibraryState`.
- Produces:
  - `getLibraryState(): Promise<LibraryState>`
  - `useLibraryState(): { state: LibraryState | null; error: string | null; reload: () => Promise<void> }`
  - `LibraryTab` renderiza `data-testid="library-tab"` e `data-testid="library-count"` com o texto `${total} tracks classificadas`.
  - `Aba = "revisao" | "biblioteca" | "configuracao"`.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/tests/library-fixtures.ts`, exportar `FIXTURE_VAZIA` e um helper `mockLibrary(page, state)` que:
1. chama `page.addInitScript` substituindo `window.WebSocket` por uma classe com `readyState = 1`, `static OPEN = 1`, `onopen` disparado em `setTimeout(0)`, `send`/`close` no-op;
2. faz `page.route("**/api/library/state*", route => route.fulfill({ json: state }))`.

Em `web/tests/library.spec.ts`:

```ts
test("abre a Biblioteca e mostra o total", async ({ page }) => {
  await mockLibrary(page, FIXTURE_VAZIA);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-tab")).toBeVisible();
  await expect(page.getByTestId("library-count")).toHaveText("0 tracks classificadas");
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "abre a Biblioteca"`
Expected: FAIL porque o botao Biblioteca esta desabilitado e `library-tab` nao existe.

- [ ] **Step 3: Implementar o minimo**

`client.ts`: `export async function getLibraryState(): Promise<LibraryState> { return apiFetch<LibraryState>("/api/library/state"); }`.

`useLibraryState.ts`: estado inicial `null`, `error`; `reload` com `getLibraryState`; `useEffect` chama `reload` e assina `onWSMessage`, trocando o estado em `states_changed` e guardando `msg.message` em `error` para `type === "error"`.

`LibraryTab.tsx`: header com `h1` "Biblioteca" e subtitulo "Gerencie, visualize e classifique suas musicas."; `library-count` com `state?.total ?? 0`; `config-loading` enquanto `state === null && !error`; banner de erro se houver.

`AppHeader.tsx`: adicionar `"biblioteca"` ao union `Aba`; trocar o botao desabilitado por botao ativo com `aria-current` e `onClick={() => onAba("biblioteca")}`; manter Modelo desabilitado.

`App.tsx`: `aba === "biblioteca" ? <LibraryTab /> : ...`.

`library.css`: `.library-tab` com `display:flex; flex-direction:column; gap:var(--space-5); padding:var(--space-7); height:100%; overflow-y:auto`, `.library-header`, `.library-count`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "abre a Biblioteca"`
Expected: PASS.
Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/api/client.ts web/src/hooks/useLibraryState.ts web/src/components/LibraryTab.tsx web/src/components/AppHeader.tsx web/src/App.tsx web/src/styles/library.css web/tests/library-fixtures.ts web/tests/library.spec.ts
git commit -m "feat(web): aba Biblioteca com estado e contagem"
```

---

### Task 2: Filtro, ordenacao, toolbar e tabela

**Files:**
- Create: `web/src/library.ts`
- Create: `web/src/components/LibraryToolbar.tsx`
- Create: `web/src/components/LibraryTable.tsx`
- Create: `web/src/components/ui/MiniWave.tsx`
- Create: `web/src/components/ui/ClassScale.tsx`
- Modify: `web/src/components/ui/CoverArt.tsx`
- Modify: `web/src/components/LibraryTab.tsx`
- Modify: `web/src/styles/library.css`
- Test: `web/tests/library-unit.spec.ts`, `web/tests/library.spec.ts`, `web/tests/library-fixtures.ts`

**Interfaces:**
- Consumes: `TrackRow`, `LibraryState`, `CoverArt`, `KeyChip`, `scan`.
- Produces:
```ts
export type LibrarySortKey = "title" | "artist" | "genre" | "bpm" | "duration";
export type SortDirection = "asc" | "desc";
export interface LibraryView {
  query: string;
  label: string | null;   // null = todos; senao "-1" | "neutra" | "+1"
  genre: string | null;
  key: string | null;
  sort: LibrarySortKey;
  direction: SortDirection;
}
export const DEFAULT_LIBRARY_VIEW: LibraryView; // title asc
export function applyLibraryView(rows: readonly TrackRow[], view: LibraryView): TrackRow[];
export function formatDuration(seconds: number): string; // "m:ss"
export const CLASS_CHIPS: readonly { rotulo: string; valor: string | null; indice: number | null }[];
```
- `CLASS_CHIPS` na ordem `Todos`, `-1`, `neutra`, `+1`, com `indice` 0,1,2 para `class_counts` (ordem de `LABEL_ORDER`).
- `LibraryToolbar` props: `{ state: LibraryState; view: LibraryView; onChange: (patch: Partial<LibraryView>) => void; resultado: number }`.
- `LibraryTable` props: `{ rows: TrackRow[]; selectedSha1: string | null; onSelect: (sha1: string) => void; sort: LibrarySortKey; direction: SortDirection; onSort: (key: LibrarySortKey) => void }`.

- [ ] **Step 1: Escrever os testes puros que falham**

Em `web/tests/library-unit.spec.ts`, importar de `../src/library` e montar quatro `TrackRow` (um sem capa/key, um sem artista, titulos "Alpha", "beta", "Gamma"):

```ts
test("busca cobre titulo, artista, album e arquivo", () => {
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "BETA" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "album-x" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, query: "arquivo-y" })).toHaveLength(1);
});

test("filtra label, genero e key e ordena bpm", () => {
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, label: "+1" })).toHaveLength(1);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, genre: "House" })).toHaveLength(2);
  expect(applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, key: "6A" })).toHaveLength(1);
  const bpm = applyLibraryView(ROWS, { ...DEFAULT_LIBRARY_VIEW, sort: "bpm", direction: "asc" });
  expect(bpm.map((r) => r.bpm)).toEqual([120, 124, 128, 130]);
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library-unit.spec.ts`
Expected: FAIL porque `../src/library` nao existe.

- [ ] **Step 3: Implementar `library.ts`**

`applyLibraryView`:

1. `query` normalizada com `trim().toLocaleLowerCase("pt-BR")`; casa em `display_title`, `artist`, `album` e `filename`.
2. aplica `label`, `genre`, `key` por igualdade exata.
3. ordena por `sort`: `title` -> `display_title`, `artist` -> `artist ?? ""`, `genre` -> `genre ?? ""`, `bpm`/`duration` numericos.
4. desempate por `filename.toLocaleLowerCase("pt-BR")`; `direction === "desc"` inverte o resultado inteiro.
5. nao muta a entrada.

`formatDuration` igual ao `viewmodel.py`: `Math.floor(max(0,s))` -> `m:ss`.

- [ ] **Step 4: UI deterministica da tabela**

Em `library-fixtures.ts`, adicionar `FIXTURE_TRES` com uma track de cada classe (uma sem capa e sem key), `class_counts: [1,1,1]`, `genres: ["House","Techno"]`, `keys: ["6A","8A"]`, e `FIXTURE_VAZIA`.

Em `library.spec.ts`:

```ts
test("busca, chips e ordenacao filtram a tabela", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-row")).toHaveCount(3);

  await page.getByTestId("library-search").fill("alpha");
  await expect(page.getByTestId("library-row")).toHaveCount(1);
  await page.getByTestId("library-search").fill("");

  await page.getByTestId("library-chip-up").click();
  await expect(page.getByTestId("library-row")).toHaveCount(1);

  await page.getByTestId("library-chip-todos").click();
  await page.getByTestId("library-sort").selectOption("title:desc");
  await expect(page.getByTestId("library-row").first()).toContainText("Gamma");
});
```

Adicionar casos: `FIXTURE_VAZIA` mostra "Biblioteca vazia" e "Escanear"; linha sem capa mostra `.library-cover-empty`; linha sem key mostra `—`; busca sem resultado mostra "Nenhuma track encontrada." e o botao "Limpar busca".

- [ ] **Step 5: Implementar a UI**

`LibraryToolbar`: input `data-testid="library-search"` com placeholder `Buscar por titulo, artista, album ou arquivo`; quatro chips (`library-chip-todos`, `library-chip-down`, `library-chip-neutral`, `library-chip-up`) com `rotulo` e contagem absoluta de `state.class_counts[indice]`; chips desabilitados quando `state.total === 0`; selects `library-genre` (`Todos` + `state.genres`), `library-key` (`Todas` + `state.keys`) e `library-sort` com valores `title:asc`, `title:desc`, `artist:asc`, `artist:desc`, `bpm:asc`, `bpm:desc`, `duration:asc`, `duration:desc` e rotulos `Titulo · artista (A-Z)` etc.; `resultado` em `<span class="library-resultado">`.

`LibraryTable`: `<table data-testid="library-table">` com colunas `#`, `Capa`, `Titulo · artista`, `Onda`, `Genero`, `BPM`, `Key`, `Classe`, `Dur`. Cabecalhos de `Titulo`, `Genero`, `BPM`, `Key`, `Dur` chamam `onSort`; o `#` e a posicao em `rows` (`i + 1`). Cada linha `data-testid="library-row"`, `data-sha1`, `data-label`; classe selecionada `library-row-selected`.

`CoverArt`: adicionar prop opcional `loading?: "lazy" | "eager"` (default `"eager"`) e repassar ao `<img>`; a tabela passa `"lazy"` e envolve num `.library-cover` com `.library-cover-empty` de fundo.

`MiniWave`: SVG `viewBox="0 0 120 26"`, `preserveAspectRatio="none"`, uma `polyline` com 40 pontos amostrados de `energy_curve` normalizada; `aria-hidden`; sem request.

`ClassScale`: tres `<span class="class-scale-seg">`; o indice ativo recebe `class-scale-down|neutral|up` e os demais ficam muted; `aria-label` com o rotulo.

`LibraryTab`: aplica `applyLibraryView(state.rows, view)`; se `state.total === 0`, renderiza `EmptyState` "Biblioteca vazia" / "Nenhuma track classificada ainda." / "Escanear" com `scan`; se filtrou para zero, renderiza "Nenhuma track encontrada." + "Limpar busca".

- [ ] **Step 6: Rodar e ver passar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library-unit.spec.ts tests/library.spec.ts`
Expected: PASS.
Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/library.ts web/src/components/LibraryToolbar.tsx web/src/components/LibraryTable.tsx web/src/components/ui/MiniWave.tsx web/src/components/ui/ClassScale.tsx web/src/components/ui/CoverArt.tsx web/src/components/LibraryTab.tsx web/src/styles/library.css web/tests/library-fixtures.ts web/tests/library-unit.spec.ts web/tests/library.spec.ts
git commit -m "feat(web): tabela e filtros da Biblioteca"
```

---

### Task 3: Inspetor com ficha tecnica e selecao

**Files:**
- Create: `web/src/components/LibraryInspector.tsx`
- Create: `web/src/components/ui/ClassChip.tsx`
- Modify: `web/src/components/LibraryTab.tsx`
- Modify: `web/src/styles/library.css`
- Test: `web/tests/library.spec.ts`

**Interfaces:**
- Consumes: `TrackRow`, `CoverArt`, `KeyChip`.
- Produces: `LibraryInspector({ track }: { track: TrackRow | null })`; `ClassChip({ label }: { label: string | null })`.
- `LibraryTab` mantem `selectedSha1`; apos filtrar, se a selecao nao esta em `rows`, seleciona `rows[0]?.sha1 ?? null`.

- [ ] **Step 1: Escrever o teste que falha**

```ts
test("seleciona a primeira linha e mostra a ficha tecnica", async ({ page }) => {
  await mockLibrary(page, FIXTURE_TRES);
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  await expect(page.getByTestId("library-inspector-title")).toHaveText("Alpha");
  await expect(page.getByTestId("library-inspector-bpm")).toHaveText("128");
  await page.getByTestId("library-row").nth(1).click();
  await expect(page.getByTestId("library-inspector-title")).toHaveText("Beta");
});
```

Adicionar: `FIXTURE_VAZIA` mostra `library-inspector-empty` com "Nenhuma track selecionada"; a linha sem key mostra `—` no inspetor; a linha sem capa mostra `.library-inspector-cover-empty`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "ficha tecnica"`
Expected: FAIL.

- [ ] **Step 3: Implementar**

`LibraryInspector`: capa 120 via `CoverArt` (com placeholder `.library-inspector-cover-empty`), titulo (`library-inspector-title`), artista, ficha em pares rotulo/valor: `Genero`, `BPM` (arredondado, mono), `Key` (`KeyChip`), `Duracao` (`formatDuration`), `Classe atual` (`ClassChip`). Nao renderizar `Confianca` (na Biblioteca e sempre `None`).

`ClassChip`: usa as cores `--color-class-lento|neutro|animada` por rotulo; texto `-1`, `neutra`, `+1`; vazio vira `—`.

`LibraryTab`: seleciona a primeira linha por default; `onSelect` atualiza `selectedSha1`; a tabela recebe `selectedSha1`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "ficha tecnica"`
Expected: PASS.
Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/LibraryInspector.tsx web/src/components/ui/ClassChip.tsx web/src/components/LibraryTab.tsx web/src/styles/library.css web/tests/library.spec.ts
git commit -m "feat(web): inspetor da Biblioteca com ficha tecnica"
```

---

### Task 4: Reproducao, onda com seek e transporte

**Files:**
- Modify: `web/src/hooks/useLibraryState.ts`
- Create: `web/src/components/LibraryTransport.tsx`
- Modify: `web/src/components/LibraryInspector.tsx`
- Modify: `web/src/components/LibraryTab.tsx`
- Modify: `web/src/styles/library.css`
- Test: `web/tests/library.spec.ts`

**Interfaces:**
- `useLibraryState` passa a devolver `peaksReady: Set<string>` e `requestPeaks: (sha1: string) => void`.
- `LibraryTab` usa `useAudioPlayer`; ao trocar a selecao, `player.load(sha1, duration_s * 1000)` e `player.seek(peak_offset_s * 1000)`, sem autoplay.
- `LibraryTransport` props: `{ isPlaying; positionMs; durationMs; onToggle; onSeek; onVolumeChange; enabled }`; renderiza `data-testid="library-player"`, botao `library-play`, tempo `library-time` no formato `m:ss / m:ss`, `<input type="range">` de seek e `VolumeRail`.
- `LibraryInspector` props adicionais: `{ progress: number; peaksReady: boolean; onSeek: (fraction: number) => void; onToggle: () => void; isPlaying: boolean }`; usa `WaveformCanvas` com `height={120}`, sem `ruler`, e um botao de play.

- [ ] **Step 1: Escrever o teste que falha**

```ts
test("toca a track selecionada", async ({ page }) => {
  test.skip(process.env.TC_LIBRARY_PLAYBACK !== "1", "precisa de acervo real");
  await page.goto("/");
  await page.getByRole("button", { name: "Biblioteca" }).click();
  const primeira = page.getByTestId("library-row").first();
  test.skip((await primeira.count()) === 0, "biblioteca vazia");
  await primeira.click();
  const tempo = page.getByTestId("library-time");
  const antes = await tempo.textContent();
  await page.getByTestId("library-play").click();
  await expect.poll(() => tempo.textContent(), { timeout: 10000 }).not.toBe(antes);
  await page.getByTestId("library-play").click();
});
```

O teste fica atras de `TC_LIBRARY_PLAYBACK=1` porque depende de arquivo real e de audio no Chromium; a suite padrao nao deve ficar flaky.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 TC_LIBRARY_PLAYBACK=1 npx playwright test tests/library.spec.ts -g "toca a track"`
Expected: FAIL porque nao ha transporte.

- [ ] **Step 3: Implementar**

`useLibraryState`:

```ts
const [peaksReady, setPeaksReady] = useState<Set<string>>(new Set());
const [peaksRequested, setPeaksRequested] = useState<Set<string>>(new Set());
```

`requestPeaks(sha1)` so dispara se a track nao tem `peaks_path`, nao esta em `peaksReady` nem em `peaksRequested`; chama `computePeaks(sha1)` e remove de `peaksRequested` no erro. Em `peaks_ready`, adiciona em `peaksReady` e remove de `peaksRequested`.

`LibraryTab`: player; efeito de selecao carrega e posiciona no `peak_offset_s`; efeito chama `requestPeaks` da selecionada; handlers `toggle`, `seekFraction`, `setVolume`.

`LibraryInspector`: `WaveformCanvas` com `track`, `progress`, `onSeek`, `peaksReady`, `height={120}` (sem `ruler`); botao de play/pause; tempo ao lado.

`LibraryTransport`: barra fixa no fim da aba, com play, tempo, range de seek e volume.

`library.css`: `.library-player`, `.library-wave`, `.library-play`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 TC_LIBRARY_PLAYBACK=1 npx playwright test tests/library.spec.ts -g "toca a track"`
Expected: PASS (com acervo real).
Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/hooks/useLibraryState.ts web/src/components/LibraryTransport.tsx web/src/components/LibraryInspector.tsx web/src/components/LibraryTab.tsx web/src/styles/library.css web/tests/library.spec.ts
git commit -m "feat(web): reproducao e onda da Biblioteca"
```

---

### Task 5: Acoes de classificar, remover e revelar

**Files:**
- Modify: `web/src/components/LibraryInspector.tsx`
- Modify: `web/src/components/LibraryTab.tsx`
- Modify: `shell/preload.js`
- Modify: `shell/main.js`
- Modify: `web/src/electron.d.ts`
- Test: `web/tests/library.spec.ts`

**Interfaces:**
- `LibraryInspector` ganha `onClassify(label: number)`, `onRemove()`, `onReveal()`, `canReveal: boolean`, `error: string | null`.
- `LibraryTab.classify` chama `decide(sha1, label)` e `reload`; `remove` chama `remove(sha1)`, limpa a selecao e `reload`; ambos capturam excecao em `library-error`.
- `window.trackclassifier.revealItem(caminho: string): Promise<boolean>`.
- IPC `trackclassifier:reveal-item` usa `shell.showItemInFolder(caminho)`.

- [ ] **Step 1: Escrever os testes que falham**

Com `mockLibrary(page, FIXTURE_TRES)`, interceptar as acoes:

```ts
let decideBody: any = null;
await page.route("**/api/review/decide*", async (route) => {
  decideBody = route.request().postDataJSON();
  await route.fulfill({ json: { ok: true } });
});
await page.goto("/");
await page.getByRole("button", { name: "Biblioteca" }).click();
await page.getByTestId("library-class-up").click();
await expect.poll(() => decideBody).toEqual({ sha1: "sha-alpha", label: 1 });
```

Para remover, mockar `**/api/review/remove*`, clicar em `library-remove`, conferir que o texto vira `Confirmar remocao`, clicar de novo e conferir o body `{ sha1: "sha-alpha" }`. Para revelar no browser, `expect(page.getByTestId("library-reveal")).toHaveCount(0)`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "classifica"`
Expected: FAIL.

- [ ] **Step 3: Implementar as acoes**

`LibraryInspector`: bloco "Acoes rapidas" com tres botoes (`library-class-down|neutral|up`) e `Kbd` 1/2/3; bloco "Acoes de arquivo" com play, revelar (so se `canReveal`) e remover (danger). Remover tem dois estados: `Remover` -> `Confirmar remocao`; um timeout de 4 s volta ao primeiro texto (evita confirmacao eterna).

`LibraryTab`:

```ts
const classify = async (label: number) => {
  if (!selected) return;
  setErro(null);
  try {
    await decide(selected.sha1, label);
    await library.reload();
  } catch (e) {
    setErro(String(e));
  }
};
```

`remove` so age depois do segundo clique do inspetor, limpa `selectedSha1` e recarrega.

`canReveal = typeof window.trackclassifier?.revealItem === "function"`.

`preload.js`: adicionar `revealItem: (caminho) => ipcRenderer.invoke("trackclassifier:reveal-item", caminho)`.

`main.js`: importar `shell` de Electron; `ipcMain.handle("trackclassifier:reveal-item", (_e, caminho) => { if (typeof caminho !== "string" || !caminho) return false; shell.showItemInFolder(caminho); return true; })`.

`electron.d.ts`: adicionar `revealItem: (caminho: string) => Promise<boolean>`.

`main.js` smoke: exigir `selectFolder` **e** `revealItem` na ponte; no ramo `estado.review`, clicar na aba Biblioteca via `document.querySelectorAll(".app-tab")`, esperar `[data-testid='library-tab']` por 10 s e so entao imprimir `SMOKE OK`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd web && TC_WEB_URL=http://127.0.0.1:8765 npx playwright test tests/library.spec.ts -g "classifica|remove|revela"`
Expected: PASS.
Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/LibraryInspector.tsx web/src/components/LibraryTab.tsx shell/preload.js shell/main.js web/src/electron.d.ts web/tests/library.spec.ts
git commit -m "feat(web): acoes da Biblioteca e revelar no Finder"
```

---

### Task 6: Gates finais e empacotamento

**Files:**
- Modify: `docs/superpowers/plans/2026-10-20-aba-biblioteca-react.md` (checkboxes)
- Test: suite completa

- [ ] **Step 1: Rodar todos os gates**

```bash
cd web && npm run build
TC_WEB_URL=http://127.0.0.1:8765 npx playwright test
cd .. && uv run pytest -q
uv run ruff check .
```

Expected: TS build limpo, Playwright verde (os specs de playback so rodam com `TC_LIBRARY_PLAYBACK=1`), pytest verde, ruff limpo.

- [ ] **Step 2: Reempacotar e rodar os dois smokes**

```bash
cd web && npm run build
cd .. && uv run --extra build pyinstaller packaging/trackclassifier.spec --noconfirm
cd shell && npm run pack
cd ..
while lsof -tiTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; do sleep 0.2; done
HOME=/tmp/tc-pkg-home ./shell/out/mac-arm64/TrackClassifier.app/Contents/MacOS/TrackClassifier --smoke
while lsof -tiTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; do sleep 0.2; done
HOME=/tmp/tc-pkg-home-empty ./shell/out/mac-arm64/TrackClassifier.app/Contents/MacOS/TrackClassifier --smoke
```

Expected: `SMOKE OK` nos dois; o configurado tambem abre a Biblioteca; porta 8765 livre no fim.

- [ ] **Step 3: Commit final**

```bash
git add docs/superpowers/plans/2026-10-20-aba-biblioteca-react.md
git commit -m "docs: fecha o plano da Biblioteca no React"
```

---

## Fora de escopo

- View "Cards", seletor de colunas,checkbox de multipla selecao e "Adicionar a fila de revisao" (o servico nao desrotula).
- Filtro de BPM por faixa.
- Ondas coloridas por banda em todas as linhas: a tabela usa `MiniWave` mono; o inspetor usa `WaveformCanvas` com buckets quando existirem.
- Abas Informacoes/Analise/Arquivo do inspetor, play circular sobre a capa e menu `⋮`.
- Atualizacao in-app no shell; o release continua Qt ate Biblioteca e Modelo fecharem.
