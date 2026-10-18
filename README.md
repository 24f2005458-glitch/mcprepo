# MCP Server Test
##Start using

gunicorn server:app --worker-class uvicorn_worker.UvicornWorker --workers 1 --bind 0.0.0.0:$PORT

##Environment variable to be set
EXAM_EMAIL

