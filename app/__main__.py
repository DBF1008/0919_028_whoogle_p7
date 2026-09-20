from app.graceful import graceful
from app.routes import run_app

# Install SIGTERM/SIGINT handlers before serving so in-flight requests
# are drained on shutdown.
graceful.attach()

run_app()
