export {};

declare global {
  interface Window {
    /**
     * Ponte exposta pelo preload do Electron (shell/preload.js). No browser
     * puro ela nao existe -- por isso os campos caem para texto.
     */
    trackclassifier?: {
      selectFolder: (atual: string) => Promise<string | null>;
    };
  }
}
