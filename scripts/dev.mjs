import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

const children = new Set()
let stopping = false

function start(name, command, args) {
  const child = spawn(command, args, {
    stdio: 'inherit',
    env: process.env,
    shell: process.platform === 'win32',
    detached: process.platform !== 'win32',
  })
  children.add(child)
  child.on('exit', (code) => {
    children.delete(child)
    if (!stopping) {
      console.log(`[dev] ${name} 已退出 (code=${code})，正在停止另一个进程…`)
      stop('SIGTERM')
    }
  })
  return child
}

function stop(signal) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    try {
      if (process.platform === 'win32') {
        child.kill('SIGTERM')
      } else {
        process.kill(-child.pid, signal || 'SIGINT')
      }
    } catch {
      // already gone
    }
  }
  setTimeout(() => {
    for (const child of children) {
      try {
        if (process.platform !== 'win32') process.kill(-child.pid, 'SIGKILL')
        else child.kill('SIGKILL')
      } catch {
        // already gone
      }
    }
    process.exit(0)
  }, 1200)
}

process.on('SIGINT', () => stop('SIGINT'))
process.on('SIGTERM', () => stop('SIGTERM'))

const python = existsSync(join(process.cwd(), '.venv', 'bin', 'python'))
  ? join(process.cwd(), '.venv', 'bin', 'python')
  : (process.platform === 'win32' ? 'python' : 'python3')

start('backend', python, ['115-server.py'])
start('frontend', 'pnpm', ['--dir', 'frontend', 'dev'])
