const { execFileSync } = require('child_process')
const path = require('path')
const fs = require('fs')

const root = path.resolve(__dirname, '..', '..')
const venvPython = process.platform === 'win32'
  ? path.join(root, '.venv', 'Scripts', 'python.exe')
  : path.join(root, '.venv', 'bin', 'python')
const python = process.env.YSS_PYTHON || (fs.existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3'))
const separator = process.platform === 'win32' ? ';' : ':'
const args = [
  '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', 'yc2ys-server',
  '--distpath', path.join(root, 'desktop', 'dist'),
  '--workpath', path.join(root, 'desktop', '.build'),
  '--specpath', path.join(root, 'desktop'),
  '--add-data', `${path.join(root, 'frontend', 'dist')}${separator}frontend_dist`,
  // Selenium exposes browser-specific classes through dynamic imports
  // (for example webdriver.ChromeOptions).  Collect the complete package so
  // those modules and Selenium Manager are available in the frozen server.
  '--collect-all', 'selenium',
  // Ship the platform-specific ffmpeg binary used for video creation.
  '--collect-all', 'imageio_ffmpeg',
  path.join(root, 'desktop', 'backend_launcher.py'),
]
execFileSync(python, args, { cwd: root, stdio: 'inherit' })
