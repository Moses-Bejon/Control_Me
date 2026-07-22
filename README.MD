# Screenshot LLM: AI-Powered Screenshot Analysis

Screenshot LLM is a Python application that captures the screen on a configurable timer and writes a description of what is visible. Built with PyQt6 for a single-window interface and integrating with various AI models, it turns the live desktop into a continuously updated caption feed.

## Features

* **Timed Screen Capture:** Captures the screen on a configurable interval without watching a screenshots folder.
* **Single Live Window:** Shows the latest description in one place.
* **Configurable AI Models:** Supports multiple AI models via configurable API keys and model IDs.
* **Flexible Configuration:** Manage settings, including API keys and model selection, through a dedicated settings tab.
* **Local Model Support:** Optionally analyze screenshots using a local Ollama model.


## Getting Started

**Pre-built Executable:**

For a quick start, download the pre-built executable:

[Download](https://drive.google.com/file/d/1RTobs3usu4oucYrTiEIHWD84KjNASXWw/view?usp=sharing)

1. Extract the downloaded zip file.
2. Run `Screenshot_LLM.exe`.


## Installation Instructions for Linux Users

### Shell Script

1. **Make the `Screenshot_LLM` script executable:**

    ```sh
    chmod +x Screenshot_LLM.sh
    ```

2. **Run the `Screenshot_LLM` script through the terminal:**

    ```sh
    Screenshot_LLM.sh
    ```

These steps will ensure that the `Installer.sh` script is executable, the necessary environment variables are set, and the `Screenshot_LLM` script can be run from any terminal session.

### Pacman makepkg

1. **Clone repo & navigate to *PKGBUILD***

   ```sh
   cd package/archlinux
   ```

2. **Build and install package**

   ```sh
   makepkg --syncdeps --install
   ```

This builds and installs the package. The **Control Me** desktop entry launches the application directly. Alternatively, its user service can be started manually or enabled on login:

- Manual start: `systemctl --user start control-me.service`
- Start and enable on login: `systemctl --user enable --now control-me.service`

**From Source Code:**

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment:** Create a `.env` file in the project's root directory and add your API keys and settings:

   ```
   LLM_API_KEY=YOUR_API_KEY  # Your API key for the LLM
   LLM_MODEL_ID=gemini/gemini-3.1.flash-lite  # Default model ID
   CAPTURE_INTERVAL_SECONDS=60  # How often to capture the screen
   OLLAMA=0  # Set to 1 to enable local Ollama inference
   ```

3. **Run the Application:**

   ```bash
   python main.py
   ```

## Usage

1. Provide your API keys and configure settings in the `.env` file or the application's settings tab.
2. Run the application. It will capture the live screen on the interval you configured.
3. Each new capture is described directly in the same window.


## Configuration Details

The application uses a `.env` file to store configuration details.  Essential settings include:

*   `LLM_API_KEY`: Your API key for the chosen LLM service.
*   `LLM_MODEL_ID`: The model ID to use. Defaults to `gemini/gemini-3.1.flash-lite`.
*   `CAPTURE_INTERVAL_SECONDS`: How often to capture the screen. Defaults to `60`.
*   `OLLAMA`: Set to `1` to enable local LLM inference using Ollama. Requires Ollama to be running and configured.

## Environment Variable Overrides

These are used to ovrride hard-coded defaults.  Mainly for use with the systemd implementation:

*   `SCRLLM_SYSTEMD_UNIT`: If set to any value, the script presumes execution from a systemd enviornment.  The systemd unit defaults to `%n`.
*   `SCRLLM_ENV_FILE`: Override the `.env` location, systemd unit defaults to `%h/.screenshot_llm/env`

## License

This project is licensed under the MIT License.  See the `LICENSE` file for details.


## Acknowledgments

*   **PyQt6:** For the user interface.
*   **python-dotenv:** For environment variable management.
*   **litellm:** For AI model integration.
*   **ollama:** For local LLM inference (optional).


This revised description is clearer, more concise, and better organized for readability.  It also provides more specific guidance for setup and usage.
