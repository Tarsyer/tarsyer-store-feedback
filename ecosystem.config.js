// PM2 Ecosystem Configuration
// Run with: pm2 start ecosystem.config.js
// Note: Environment variables are loaded from .env by python-dotenv in the scripts
// Using uv-created virtualenv at ~/new

const path = require('path');
const os = require('os');

const homeDir = os.homedir();
const venvPath = path.join(homeDir, 'new');

module.exports = {
  apps: [
    {
      name: 'feedback-api',
      script: path.join(venvPath, 'bin/uvicorn'),
      args: 'backend.app.main:app --host 0.0.0.0 --port 20525',
      interpreter: 'none',
      cwd: __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: path.join(__dirname, 'logs/api-error.log'),
      out_file: path.join(__dirname, 'logs/api-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10
    },
    {
      name: 'transcription-worker',
      script: path.join(__dirname, 'backend/services/transcription_worker.py'),
      interpreter: path.join(venvPath, 'bin/python'),
      cwd: __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      error_file: path.join(__dirname, 'logs/transcription-error.log'),
      out_file: path.join(__dirname, 'logs/transcription-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10
    },
    {
      name: 'analysis-worker',
      script: path.join(__dirname, 'backend/services/analysis_worker.py'),
      interpreter: path.join(venvPath, 'bin/python'),
      cwd: __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      error_file: path.join(__dirname, 'logs/analysis-error.log'),
      out_file: path.join(__dirname, 'logs/analysis-out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10
    }
  ]
};
