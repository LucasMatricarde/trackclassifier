/**
 * Ponte minima entre a janela e o processo principal.
 *
 * A janela continua sem Node (contextIsolation + sandbox): o unico poder
 * exposto e abrir o seletor nativo de pasta. O resto do contrato segue
 * sendo HTTP/WS com o backend. Sem este preload, a tela de Configuracao
 * depende de digitar caminho absoluto -- inviavel no primeiro uso.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("trackclassifier", {
  selectFolder: (atual) =>
    ipcRenderer.invoke("trackclassifier:select-folder", atual),
});
