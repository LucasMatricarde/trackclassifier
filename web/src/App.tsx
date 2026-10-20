import { AppHeader } from "./components/AppHeader";
import { ReviewTab } from "./components/ReviewTab";

export default function App() {
  return (
    <div className="app">
      <AppHeader />
      <main className="app-main">
        <ReviewTab />
      </main>
    </div>
  );
}
