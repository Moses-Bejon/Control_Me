import base64
import mimetypes
import traceback

from PyQt6.QtCore import QThread, pyqtSignal
from litellm import completion


class Worker_litellm(QThread):
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
            with open(self.image_path, "rb") as image_file:
                image_b64 = base64.b64encode(image_file.read()).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(self.image_path)
            if not mime_type:
                mime_type = "image/png"
            image_url = f"data:{mime_type};base64,{image_b64}"

            response = completion(
                model=self.LLM_MODEL_ID,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                api_key=self.LLM_API_MODEL if self.LLM_API_MODEL is not None else None,
            )
            self.finished.emit(response.choices[0].message.content)
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))
