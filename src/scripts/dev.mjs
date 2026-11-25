import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const srcDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = join(srcDir, 'backend')
const frontendDir = join(srcDir, 'frontend')
const backendPython = process.platform === 'win32'
  ? join(backendDir, '.venv', 'Scripts', 'python.exe')
  : join(backendDir, '.venv', 'bin', 'python')
if (!existsSync(backendPython)) {
  const venvCommand = process.platform === 'win32'
    ? 'py -m venv .venv && .venv\\Scripts\\python.exe -m pip install -e ".[dev]"'
    : 'python -m venv .venv && .venv/bin/pip install -e ".[dev]"'

  console.error(`Backend virtual environment not found at ${backendPython}`)
  console.error(`Create it first from src/backend:\n  ${venvCommand}`)
  process.exit(1)
}

const backend = spawn(backendPython, ['-m', 'uvicorn', 'app.main:app', '--reload'], {
  cwd: backendDir,
  stdio: 'inherit',
})
// Node 20+ on Windows rejects spawning .cmd without shell; use cmd.exe instead.
const frontend = process.platform === 'win32'
  ? spawn('cmd.exe', ['/d', '/s', '/c', 'npm run dev'], {
    cwd: frontendDir,
    stdio: 'inherit',
  })
  : spawn('npm', ['run', 'dev'], {
    cwd: frontendDir,
    stdio: 'inherit',
  })

let shuttingDown = false

function stopProcess(child) {
  if (child.exitCode !== null || child.killed) return

  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    child.kill('SIGTERM')
  }
}

function shutdown(exitCode = 0) {
  if (shuttingDown) return
  shuttingDown = true
  stopProcess(backend)
  stopProcess(frontend)
  setTimeout(() => process.exit(exitCode), 250)
}

backend.on('exit', (code) => {
  if (!shuttingDown) shutdown(code ?? 1)
})
frontend.on('exit', (code) => {
  if (!shuttingDown) shutdown(code ?? 1)
})
process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))

console.log('Backend:  http://127.0.0.1:8000')
console.log('Frontend: http://localhost:5173')
console.log('Press Ctrl+C to stop both servers.')
