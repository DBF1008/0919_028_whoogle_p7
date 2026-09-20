from app.routes import run_app
from app.shutdown import shutdown_manager

# Handle SIGTERM/SIGINT gracefully: stop accepting new connections, wait for
# in-flight requests to finish (with a timeout), then exit
shutdown_manager.install_signal_handlers()

run_app()
