import { useEffect, useState } from "react";
import { getHealth, scan } from "./api/client";
import { AppHeader, type Aba } from "./components/AppHeader";
import { ConfigTab } from "./components/ConfigTab";
import { LibraryTab } from "./components/LibraryTab";
import { ModelTab } from "./components/ModelTab";
import { ReviewTab } from "./components/ReviewTab";
import { useModelState } from "./hooks/useModelState";

export default function App() {
  const [aba, setAba] = useState<Aba>("revisao");
  const [configurado, setConfigurado] = useState<boolean | null>(null);
  // O controle de treino mora aqui em cima: o header (ilha do modelo) e a
  // aba Modelo dividem UM estado de "treinando" e UM guard de clique --
  // dois gatilhos, um POST, zero segundo treino paralelo.
  const treino = useModelState();

  useEffect(() => {
    getHealth()
      // `?? true`: servidor antigo sem o campo configured nao pode cair no
      // setup -- la o formulario existe, mas o apply nao e o primeiro uso.
      .then((health) => setConfigurado(health.configured ?? true))
      // Erro de rede: mantem o comportamento anterior em vez de prender o
      // app no setup.
      .catch(() => setConfigurado(true));
  }, []);

  // Handler para navegação vinda do EmptyState do Modelo
  useEffect(() => {
    const handler = () => setAba("revisao");
    window.addEventListener("navegar-para-revisao", handler);
    return () => window.removeEventListener("navegar-para-revisao", handler);
  }, []);

  if (configurado === null) {
    return (
      <div className="app">
        <div className="config-loading">Carregando…</div>
      </div>
    );
  }

  if (!configurado) {
    return (
      <div className="app">
        <main className="app-main">
          <ConfigTab
            setup
            onSaved={() => {
              setConfigurado(true);
              // O scan de abertura do lifespan rodou sem servico; dispara
              // um agora para a fila nascer preenchida, como no primeiro
              // `dj scan`.
              void scan().catch(() => {});
            }}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <AppHeader aba={aba} onAba={setAba} treino={treino} />
      <main className="app-main">
        {aba === "revisao" ? (
          <ReviewTab />
        ) : aba === "biblioteca" ? (
          <LibraryTab />
        ) : aba === "modelo" ? (
          <ModelTab control={treino} />
        ) : (
          <ConfigTab />
        )}
      </main>
    </div>
  );
}
