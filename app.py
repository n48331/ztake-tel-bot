import importlib.util
import pathlib

# Load the Flask app object from render-webhook-bot.py (hyphenated filename)
module_path = pathlib.Path(__file__).with_name("render-webhook-bot.py")
spec = importlib.util.spec_from_file_location("render_webhook_bot", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Expose as app for Gunicorn (app:app)
app = module.app
