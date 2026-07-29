import traceback

from PyQt6.QtCore import QThread, pyqtSignal
from litellm import completion
from ollama import chat


class TextSummaryWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, observations, api_key, model_id, use_ollama, prompt):
        super().__init__()
        self.observations = observations
        self.api_key = api_key
        self.model_id = model_id
        self.use_ollama = use_ollama
        self.prompt = prompt

    def run(self):
        try:
            message = f"{self.prompt}\n\nHourly observations:\n{self.observations}"
            if self.use_ollama:
                response = chat(S,
                    model=self.model_id,
                    messages=[{"role": "user", "content": message}],
                )
                summary = response["message"]["content"]
            else:
                response = completion(
                    model=self.model_id,
                    messages=[{"role": "user", "content": message}],
                    api_key=self.api_key or None,
                )
                summary = response.choices[0].message.content
            self.finished.emit(summary)
        except Exception as exc:
            traceback.print_exc()
            self.error.emit(str(exc))
