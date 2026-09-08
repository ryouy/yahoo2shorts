const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs')

const PORT = Number(process.env.YSS_PORT || 18180)
const APP_URL = `http://127.0.0.1:${PORT}`
let backend = null
let backendReady = false

function backendLogPath() {
  return path.join(app.getPath('userData'), 'backend.log')
}

function logBackend(message) {
  fs.appendFileSync(backendLogPath(), `[${new Date().toISOString()}] ${message}\n`)
}

function projectRoot() {
  return path.resolve(__dirname, '..', '..')
}

function pythonCommand() {
  if (process.env.YSS_PYTHON) return process.env.YSS_PYTHON
  const root = projectRoot()
  const candidates = process.platform === 'win32'
    ? [path.join(root, '.venv', 'Scripts', 'python.exe'), 'python']
    : [path.join(root, '.venv', 'bin', 'python'), 'python3']
  return candidates.find(candidate => candidate.includes(path.sep) ? fs.existsSync(candidate) : true)
}

function backendCommand() {
  if (!app.isPackaged) {
    return {
      command: pythonCommand(),
      args: ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(PORT)],
      cwd: projectRoot(),
    }
  }
  const filename = process.platform === 'win32' ? 'yc2ys-server.exe' : 'yc2ys-server'
  return {
    command: path.join(process.resourcesPath, 'server', filename),
    args: [],
    cwd: process.resourcesPath,
  }
}

function healthCheck() {
  return new Promise(resolve => {
    const request = http.get(`${APP_URL}/api/health`, response => {
      response.resume()
      resolve(response.statusCode === 200)
    })
    request.on('error', () => resolve(false))
    request.setTimeout(700, () => { request.destroy(); resolve(false) })
  })
}

async function waitForBackend() {
  // A one-file PyInstaller server extracts its bundled Python runtime on first
  // launch. On slower disks this can take well over ten seconds.
  for (let attempt = 0; attempt < 180; attempt += 1) {
    if (await healthCheck()) return true
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  return false
}

async function startBackend() {
  const spec = backendCommand()
  logBackend(`Starting: ${spec.command} ${spec.args.join(' ')}`)
  const log = fs.openSync(backendLogPath(), 'a')
  backend = spawn(spec.command, spec.args, {
    cwd: spec.cwd,
    env: { ...process.env, YSS_HOST: '127.0.0.1', YSS_PORT: String(PORT), YSS_DATA_DIR: path.join(app.getPath('userData'), 'data') },
    stdio: ['ignore', log, log],
    windowsHide: true,
  })
  backend.on('error', error => logBackend(`Spawn error: ${error.stack || error.message}`))
  backend.on('exit', (code, signal) => logBackend(`Server exited: code=${code} signal=${signal}`))
  return waitForBackend()
}

function stopBackend() {
  if (backend && !backend.killed) backend.kill()
  backend = null
}

function createWindow() {
  const existing = BrowserWindow.getAllWindows()[0]
  if (existing) { existing.focus(); return existing }
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: '#ffffff',
    title: 'yc2ys',
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(APP_URL)) { event.preventDefault(); shell.openExternal(url) }
  })
  window.loadURL(APP_URL)
}

app.whenReady().then(async () => {
  const ready = await startBackend()
  if (!ready) {
    dialog.showErrorBox('yc2ys を起動できません', `ローカルサーバーを起動できませんでした。\nログ: ${backendLogPath()}`)
    app.quit()
    return
  }
  backendReady = true
  createWindow()
})

app.on('before-quit', stopBackend)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (backendReady && BrowserWindow.getAllWindows().length === 0) createWindow() })
