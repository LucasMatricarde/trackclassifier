import { useState } from "react";
import { AppHeader, type Aba } from "./components/AppHeader";
import { ConfigTab } from "./components/ConfigTab";
import { ReviewTab } from "./components/ReviewTab";

export default function App() {
  const [aba, setAba] = useState<Aba>("revisao");

  return (
    <div className="app">
      <AppHeader aba={aba} onAba={setAba} />
      <main className="app-main">
        {aba === "revisao" ? <ReviewTab /> : <ConfigTab />}
      </main>
    </div>
  );
}
