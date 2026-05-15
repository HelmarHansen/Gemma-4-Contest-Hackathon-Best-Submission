
import _mock_ollama  # patches requests.post before main imports
import uvicorn
import main as app_module
uvicorn.run(app_module.app, host='127.0.0.1', port=8765, log_level='warning')
