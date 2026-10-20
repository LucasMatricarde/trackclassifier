/**
 * Ponte minima entre a janela e o processo principal.
 *
 * A janela continua sem Node (contextIsolation + sandbox): o unico poder
 * exposto e abrir o seletor nativo de pasta e revelar arquivos no gerenciador.
 * O resto do contrato segue sendo HTTP/WS com o backend.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("trackclassifier", {
  selectFolder: (atual) =>
    ipcRenderer.invoke("trackclassifier:select-folder", atual),
  revealItem: (caminho) =>
    ipcRenderer.invoke("trackclassifier:reveal-item", caminho),
});