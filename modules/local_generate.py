from PyQt6.QtCore import QThread, pyqtSignal
from ollama import chat


class WorkerLocal(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        image_path: str,
        llm_api_model: str | None,
        llm_model_id: str,
        prompt: str,
    ) -> None:
        super().__init__()
        self.image_path = image_path
        self.llm_api_model = llm_api_model
        self.llm_model_id = llm_model_id
        self.prompt = prompt

    def run(self) -> None:
        try:
            response = chat(
                model=self.llm_model_id,
                messages=[{"role": "user", "content": self.prompt, "images": [self.image_path]}],
            )
            self.finished.emit(response["message"]["content"])
        except Exception as e:
            self.error.emit(str(e))
