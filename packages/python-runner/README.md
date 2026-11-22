# Run Python

Runs the Python that's written in Lasso's chat, on your Mac, and shows the result.

- **How to use it:**
  - **Run** on any Python code block in a chat reply: the block shows the run as it happens, then
    the output and how long it took; **Code** switches back.
    - A picture the code saves (`plt.savefig("chart.png")`) or a page it writes (an `.html` or `.svg`
      file, such as a plotly chart) shows in the block, the newest one if it makes several. Pages show
      walled in, the way Lasso shows any package's page (Lasso 0.29).
    - A missing library gets **Install numpy** (or whichever): it's installed in a private environment
      only Run Python uses (in its own data folder, never your Python), then the code runs again.
    - A run that fails gets **Fix it**: it sends the code and the error to the chat model, which answers
      with a fixed block you can run.
  - **/run** runs the Python in the last reply (its code blocks), or **/run** followed by your own
    code. The answer shows what it printed, its error if any, and the files it made.
  - Type **/run** on its own: the words after it are run as code, so "/run the code above" is answered
    with how to run it instead.
  - Chat knows about it: the package adds a few lines to the chat model's instructions, so it suggests
    **Run** rather than saying it can't run code, and saves charts to a file instead of opening a window.
  - A reply can have several files: a code block whose first line is `# helper.py` is saved as
    `helper.py`, so the block that runs can import it.
  - The Agent (and chat models that use tools) can run code with the `run_python` tool. Lasso shows
    you the code and asks before every run.
- **Sends:** nothing, except when you click **Install …**: `scripts/install.py` downloads that library
  from PyPI (it's the only script that may reach the internet, and it doesn't work in local-only mode).
  The code itself runs with `scripts/run.py` on your Mac in Lasso's sandbox, with no internet. The
  code can read Python itself and write only in `~/LassoWorkspace/python-runner/`, one folder per run.
  Each run stops after 20 seconds.
- **Needs:** `python3` (macOS asks to install it the first time, or get it from python.org). Code can
  use what that Python has installed, plus what you install with **Install …**.
- **Can't:** read input while it runs (`input()` gets nothing), open windows (turtle, tkinter,
  `plt.show()`), or reach the internet.
- **To remove the private environment:** remove Run Python (Settings › Packages); its data folder goes with it.
