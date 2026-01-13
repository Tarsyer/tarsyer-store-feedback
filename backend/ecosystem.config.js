// PM2 Ecosystem Configuration for Store Feedback System
// Deploy with: pm2 start ecosystem.config.js

module.exports = {
  apps: [
    {
      name: 'feedback-api',
      script: 'uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000',
      cwd: '/opt/store-feedback/backend',
      interpreter: 'none',
      env: {
        MONGO_URI: 'mongodb://localhost:27017',
        DB_NAME: 'store_feedback',
        UPLOAD_DIR: '/data/store-feedback/uploads',
        BASE_URL: 'https://store-feedback.tarsyer.com'
      },
      env_production: {
        NODE_ENV: 'production',
        MONGO_URI: 'mongodb://localhost:27017',
        DB_NAME: 'store_feedback',
        UPLOAD_DIR: '/data/store-feedback/uploads',
        BASE_URL: 'https://store-feedback.tarsyer.com'
      },
      instances: 2,
      exec_mode: 'cluster',
      watch: false,
      max_memory_restart: '500M',
      error_file: '/var/log/pm2/feedback-api-error.log',
      out_file: '/var/log/pm2/feedback-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'feedback-worker',
      script: 'worker.py',
      cwd: '/opt/store-feedback/backend',
      interpreter: 'python3',
      env: {
        MONGO_URI: 'mongodb://localhost:27017',
        DB_NAME: 'store_feedback',
        UPLOAD_DIR: '/data/store-feedback/uploads',
        WHISPER_CLI: '/home/ubuntu/whisper.cpp/build/bin/whisper-cli',
        WHISPER_MODEL: '/home/ubuntu/whisper.cpp/models/ggml-medium.bin',
        WHISPER_LANGUAGE: 'hi',
        QWEN_API_URL: 'https://kwen.tarsyer.com/v1/chat/completions',
        QWEN_API_KEY: 'Tarsyer-key-1',
        QWEN_TARGET_SERVER: 'BK',
        POLL_INTERVAL: '30',
        MAX_CONCURRENT: '2'
      },
      instances: 1,
      watch: false,
      max_memory_restart: '1G',
      error_file: '/var/log/pm2/feedback-worker-error.log',
      out_file: '/var/log/pm2/feedback-worker-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
