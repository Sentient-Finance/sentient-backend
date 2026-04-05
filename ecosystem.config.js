module.exports = {
  apps: [
    {
      name: 'web',
      script: '/home/moltbot/.pyenv/versions/3.14.0/bin/python3',
      args: '-m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8001',
      watch: ['apps', 'libs'],
      env: {
        PORT: '8001',
      },
    },
    {
      name: 'worker',
      script: 'celery',
      args: '-A apps.worker.celery_app worker --pool=prefork -l info -Q celery',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        POSTGRES_PORT: '5435',
      },
    },
    {
      name: 'worker-exec',
      script: 'celery',
      args: '-A apps.worker.celery_app worker --pool=prefork -l info -Q execution --concurrency=1',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        POSTGRES_PORT: '5435',
      },
    },
    {
      name: 'beat',
      script: 'celery',
      args: '-A apps.worker.celery_app beat -l info',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        POSTGRES_PORT: '5435',
      },
    },
  ],
};
