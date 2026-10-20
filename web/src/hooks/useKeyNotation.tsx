import { createContext, useContext, useState, type ReactNode } from "react";

type KeyNotation = "camelot" | "classic";

interface KeyNotationContextType {
  notation: KeyNotation;
  setNotation: (n: KeyNotation) => void;
}

const KeyNotationContext = createContext<KeyNotationContextType>({
  notation: "camelot",
  setNotation: () => {},
});

const STORAGE_KEY = "trackclassifier-key-notation";

export function KeyNotationProvider({ children }: { children: ReactNode }) {
  const [notation, setNotationState] = useState<KeyNotation>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "classic" ? "classic" : "camelot";
  });

  const setNotation = (n: KeyNotation) => {
    setNotationState(n);
    localStorage.setItem(STORAGE_KEY, n);
  };

  return (
    <KeyNotationContext.Provider value={{ notation, setNotation }}>
      {children}
    </KeyNotationContext.Provider>
  );
}

export function useKeyNotation() {
  return useContext(KeyNotationContext);
}
