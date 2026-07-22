from PyQt6.QtCore import QThread, pyqtSignal
from ollama import chat


class Worker_Local(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, image_path, LLM_API_MODEL, LLM_MODEL_ID, prompt):
        super().__init__()
        self.image_path = image_path
        self.LLM_API_MODEL = LLM_API_MODEL
        self.LLM_MODEL_ID = LLM_MODEL_ID
        self.prompt = prompt

    def run(self):
        try:
            response = chat(
                model=self.LLM_MODEL_ID,
                messages=[{"role": "user", "content": self.prompt, "images": [self.image_path]}],
            )
            self.finished.emit(response["message"]["content"])
        except Exception as e:
            self.error.emit(str(e))
