const { app, BrowserWindow, Menu, clipboard, dialog, ipcMain, shell, screen } = require('electron');
const path = require('path');

function createWindow() {
  const area = screen.getPrimaryDisplay().workArea;
  const width = Math.min(Math.max(1100, area.width - 40), 1600);
  const height = Math.min(Math.max(760, area.height - 40), 1100);
  const win = new BrowserWindow({
    width,
    height,
    minWidth: 760,
    minHeight: 520,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.webContents.on('context-menu', (_event, params) => {
    const selected = String(params.selectionText || '').trim();
    const editable = Boolean(params.isEditable);
    const hasSelection = selected.length > 0;
    const hasLink = typeof params.linkURL === 'string' && params.linkURL.trim().length > 0;
    const menu = Menu.buildFromTemplate([
      { role: 'undo', enabled: editable },
      { role: 'redo', enabled: editable },
      { type: 'separator' },
      { role: 'cut', enabled: editable },
      { role: 'copy', enabled: editable || hasSelection },
      { role: 'paste', enabled: editable },
      { role: 'delete', enabled: editable },
      { role: 'selectAll', enabled: editable || hasSelection },
      { type: 'separator' },
      { label: 'Kopiuj jako zwykly tekst', enabled: hasSelection, click: () => win.webContents.copy() },
      { label: 'Otworz link', enabled: hasLink, click: () => shell.openExternal(params.linkURL) },
      { label: 'Kopiuj adres linku', enabled: hasLink, click: () => clipboard.writeText(params.linkURL) },
    ]);
    menu.popup({ window: win });
  });

  win.once('ready-to-show', () => {
    try {
      win.maximize();
    } catch {}
    win.show();
  });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  ipcMain.handle('open-external', async (_event, url) => {
    if (typeof url !== 'string') return false;
    const u = url.trim();
    if (!u) return false;
    await shell.openExternal(u);
    return true;
  });

  ipcMain.handle('pick-file', async (_event, options = {}) => {
    const win = BrowserWindow.getFocusedWindow();
    const filters = Array.isArray(options.filters) ? options.filters : [];
    const result = await dialog.showOpenDialog(win || undefined, {
      title: typeof options.title === 'string' ? options.title : 'Wybierz plik',
      properties: ['openFile'],
      filters,
      defaultPath: typeof options.defaultPath === 'string' ? options.defaultPath : undefined,
    });
    if (result.canceled || !Array.isArray(result.filePaths) || !result.filePaths.length) return '';
    return result.filePaths[0];
  });

  ipcMain.handle('pick-save-file', async (_event, options = {}) => {
    const win = BrowserWindow.getFocusedWindow();
    const filters = Array.isArray(options.filters) ? options.filters : [];
    const result = await dialog.showSaveDialog(win || undefined, {
      title: typeof options.title === 'string' ? options.title : 'Wybierz plik wynikowy',
      defaultPath: typeof options.defaultPath === 'string' ? options.defaultPath : undefined,
      filters,
    });
    if (result.canceled || typeof result.filePath !== 'string') return '';
    return result.filePath;
  });

  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
