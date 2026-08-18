import base64
import mimetypes
import traceback

from PyQt6.QtCore import QThread, pyqtSignal
from litellm import completion


class WorkerLitellm(QThread):
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
            with open(self.image_path, "rb") as image_file:
                image_b64 = base64.b64encode(image_file.read()).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(self.image_path)
            if not mime_type:
                mime_type = "image/png"
            image_url = f"data:{mime_type};base64,{image_b64}"

            response = completion(
                model=self.llm_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                api_key=self.llm_api_model,
            )
            self.finished.emit(response.choices[0].message.content)
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))
