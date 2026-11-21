# My notes

Lets Lasso's chat answer from a folder of your Markdown or text notes.

- **How to use it:** in chat, type **@My notes** and your question. Or just ask: Lasso looks here by
  itself when a message fits its "What's in it" line (filled in from your notes when you choose the
  folder, and editable on its page in Settings › Packages).
- **Sends:** nothing. It runs `scripts/search.py` on your Mac, in Lasso's sandbox, with no internet. It
  can read only the notes folder you choose. The matching passages go to your chat model; with a cloud
  model, Lasso asks you first.
- **Needs:** a notes folder, and Python 3 (`/usr/bin/python3`).
