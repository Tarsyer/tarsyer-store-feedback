// PM2 Ecosystem Configuration
// Run with: pm2 start ecosystem.config.js

module.exports = {
  apps: [
    {
      name: 'feedback-api',
      script: 'uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      interpreter: 'none',
      env: {
        MONGO_URI: 'mongodb://localhost:27017',
        DB_NAME: 'store_feedback',
        UPLOAD_DIR: '/data/uploads',
        BASE_URL: 'https://store-feedback.tarsyer.com'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M'
    },
    {
      name: 'transcription-worker',
      script: 'services/transcription_worker.py',
      cwd: './backend',
      interpreter: 'python3',
      env: {
        API_BASE_URL: 'http://localhost:8000',
        UPLOAD_DIR: '/data/uploads',
        WHISPER_CLI: '/opt/whisper.cpp/build/bin/whisper-cli',
        WHISPER_MODEL: '/opt/whisper.cpp/models/ggml-medium.bin',
        WHISPER_LANG: 'hi',
        POLL_INTERVAL: '10'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G'
    },
    {
      name: 'analysis-worker',
      script: 'services/analysis_worker.py',
      cwd: './backend',
      interpreter: 'python3',
      env: {
        API_BASE_URL: 'http://localhost:8000',
        QWEN_API_URL: 'https://kwen.tarsyer.com/v1/chat/completions',
        QWEN_API_KEY: 'Tarsyer-key-1',
        QWEN_TARGET_SERVER: 'BK',
        POLL_INTERVAL: '10',
        MAX_TOKENS: '1024'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M'
    }
  ]
};
