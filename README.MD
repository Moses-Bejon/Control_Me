# Control Me: AI-Powered Distraction Avoidance

Control Me is a Python application that monitors your screen activity on a configurable timer and uses AI to help you stay focused. Built with PyQt6 for a single-window interface and integrating with various AI models, it provides real-time feedback to help you avoid distractions and maintain productivity.

## Features

* **Live Activity Monitoring:** Captures your screen on a configurable interval to track what you're doing.
* **AI-Powered Analysis:** Uses AI to identify productive vs. unproductive behavior in real-time.
* **Single Live Window:** Shows current activity status and feedback in one place.
* **Configurable AI Models:** Supports multiple AI models via configurable API keys and model IDs.
* **Flexible Configuration:** Manage settings, including API keys and model selection, through a dedicated settings tab.
* **Local Model Support:** Optionally analyze activity using a local Ollama model.
* **Hourly Activity Summary:** Tracks your activity throughout the day and generates hourly summaries to help you reflect on your focus patterns.

### Shell Script (Linux/MacOS)

1. **Make the `Control_Me` script executable:**

    ```sh
    chmod +x Control_Me.sh
    ```

2. **Run the `Control_Me` script through the terminal:**

    ```sh
    Control_Me.sh
    ```

These steps will ensure that the `Installer.sh` script is executable, the necessary environment variables are set, and the `Control_Me` script can be run from any terminal session.

### Pacman makepkg (Arch)

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

### From Source Code (All platforms)

1. **Install Dependencies:**

   # Bash (Linux/MacOS):
   ```bash
   pip install -r requirements.txt
   ```
   
   # Windows PowerShell (Windows):
      ```
      py -m pip install -r requirements.txt
      ```
   
2. **Configure Environment:** 
   Create a `.env` file in the project's root directory and add your API keys and settings:

   ```
   LLM_API_KEY=YOUR_API_KEY  # Your API key for the LLM
   LLM_MODEL_ID=gemini/gemini-3.1-flash-lite  # Default model ID
   CAPTURE_INTERVAL_SECONDS=120  # How often to capture the screen
   OLLAMA=0  # Set to 1 to enable local Ollama inference
   ACTIVITY_DATA_DIRECTORY=~/.control_me/activity  # Location for activity text files and SQLite database
   ```

3. **Run the Application:**

   ```bash
   python main.py
   ```
   
   # Windows PowerShell (Windows):
      ```
      py main.py
      ```

## Usage

1. Provide your API keys and configure settings in the `.env` file or the application's settings tab.
2. Run the application. It will monitor your screen on the interval you configured.
3. View real-time feedback on your current activity and whether it's productive or distracting.
4. Review hourly summaries to understand your focus patterns throughout the day.


## Configuration Details

The application uses a `.env` file to store configuration details.  Essential settings include:

*   `LLM_API_KEY`: Your API key for the chosen LLM service.
*   `LLM_MODEL_ID`: The model ID to use. Defaults to `gemini/gemini-3.1.flash-lite`.
*   `CAPTURE_INTERVAL_SECONDS`: How often to capture the screen. Defaults to `60`.
*   `OLLAMA`: Set to `1` to enable local LLM inference using Ollama. Requires Ollama to be running and configured.
*   `ACTIVITY_DATA_DIRECTORY`: Where hourly text files and `activity_memory.db` are stored. Defaults to `~/.control_me/activity`.

## Activity Memory

Each screenshot observation is logged for the current clock hour. At the start of each new hour, the application generates a natural-language summary of your activities to help you understand your productivity patterns. The `hourly_summaries` table in SQLite contains `date`, `hour_start`, `hour_end`, and `summary`, allowing you to track your focus over time. Historical data is retained for reflection and analysis.

## Environment Variable Overrides

These are used to ovrride hard-coded defaults.  Mainly for use with the systemd implementation:

*   `SCRLLM_SYSTEMD_UNIT`: If set to any value, the script presumes execution from a systemd enviornment.  The systemd unit defaults to `%n`.
*   `SCRLLM_ENV_FILE`: Override the `.env` location, systemd unit defaults to `%h/.control_me/env`

## License

This project is licensed under the MIT License.  See the `LICENSE` file for details.


## Acknowledgments

*   **PyQt6:** For the user interface.
*   **python-dotenv:** For environment variable management.
*   **litellm:** For AI model integration.
*   **ollama:** For local LLM inference (optional).


This revised description is clearer, more concise, and better organized for readability.  It also provides more specific guidance for setup and usage.
