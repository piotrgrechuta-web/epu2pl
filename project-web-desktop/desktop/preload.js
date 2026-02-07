const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('appInfo', {
  name: 'Translator Studio Desktop',
  version: '0.1.0',
});
