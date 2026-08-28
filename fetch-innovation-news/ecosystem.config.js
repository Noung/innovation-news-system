// ====================================
// PM2 Ecosystem Configuration
// ====================================

module.exports = {
  apps: [
    // ====================================
    // Innovation News Admin API Server
    // ====================================
    {
      name: 'innovation-news-api',
      script: '/home/kittisak/.openclaw/workspace/fetch-innovation-news/api/server.js',
      cwd: '/home/kittisak/.openclaw/workspace/fetch-innovation-news/api',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PORT: 3001,
        PYTHON_BIN: '/usr/bin/python3',
        INNOVATION_NEWS_ENV_FILE: '/home/kittisak/.openclaw/workspace/.env',
        INNOVATION_NEWS_MAIN_SCRIPT: '/home/kittisak/.openclaw/workspace/scripts/fetch-innovation-news-mysql.py',
        INNOVATION_NEWS_FETCH_WORKDIR: '/home/kittisak/.openclaw/workspace/scripts',
        INNOVATION_NEWS_WORKSPACE_DIR: '/home/kittisak/.openclaw/workspace'
      },
      error_file: '/home/kittisak/.openclaw/workspace/logs/pm2-innovation-api-error.log',
      out_file: '/home/kittisak/.openclaw/workspace/logs/pm2-innovation-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true
    }
  ]
};
