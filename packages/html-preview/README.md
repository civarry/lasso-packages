# Preview HTML

Shows the HTML and SVG that chat writes as a live page, right in the code block, the way chat apps
show artifacts.

- **How to use it:** click **Preview** on an `html` or `svg` code block in a chat reply. The page
  runs in the block (its JavaScript works: charts, small tools, games); **Open larger** shows it in
  its own window, and **Code** switches back.
  - Chat knows about it: the package adds a few lines to the chat model's instructions, so when you
    ask for a chart, a diagram or a small tool it answers with one self-contained html block.
- **Sends:** nothing. `scripts/preview.sh` saves the block as a file in `~/LassoWorkspace/html-preview/`
  and Lasso shows it walled in: no internet except scripts and styles from cdnjs.cloudflare.com (none
  at all in local-only mode), no other files, no popups, nothing kept between pages. A web link opens
  in your browser when you click it.
- **Needs:** Lasso 0.29 or newer. Nothing else.
- **Can't:** load files the page names besides itself (put CSS and JavaScript inline), or reach any
  other site. The window's **Open in Browser** shows it without those limits.
