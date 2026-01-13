// PM2 Ecosystem Configuration
// Run with: pm2 start ecosystem.config.js
// Note: This loads environment variables from .env file

module.exports = {
  apps: [
    {
      name: 'feedback-api',
      script: 'backend/venv/bin/uvicorn',
      args: 'backend.app.main:app --host 0.0.0.0 --port 20525',
      interpreter: 'none',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env_file: '.env',
      error_file: './logs/api-error.log',
      out_file: './logs/api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'transcription-worker',
      script: 'backend/services/transcription_worker.py',
      interpreter: 'backend/venv/bin/python',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env_file: '.env',
      error_file: './logs/transcription-error.log',
      out_file: './logs/transcription-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'analysis-worker',
      script: 'backend/services/analysis_worker.py',
      interpreter: 'backend/venv/bin/python',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env_file: '.env',
      error_file: './logs/analysis-error.log',
      out_file: './logs/analysis-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
