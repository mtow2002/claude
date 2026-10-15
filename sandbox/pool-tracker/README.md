# Pool Water Log

A small web page for logging home pool water test readings. It runs entirely in your browser. There is no server, no install, and no account.

This folder is also a practice project for learning git and GitHub. The second half of this file explains the git terms you will see while reviewing it.

## How to open the page

1. Download or clone this repository to your computer.
2. Open the `sandbox/pool-tracker` folder.
3. Double click `index.html`. It opens in your default web browser.

That is all. Chrome, Edge, Firefox, and Safari all work.

## How to use it

1. **Add a reading.** Pick the date, type the numbers you tested, and click **Save reading**. You can leave a box blank if you did not test that item that day.
2. **Read the table.** The newest reading is at the top. A cell turns **blue** when the value is below its target range and **red** when it is above. Hover over a colored cell to see the target.
3. **Change the targets.** Open **Target range settings** at the bottom of the page, edit any min or max, and click **Save ranges**. The table recolors right away. **Reset to defaults** puts the starting values back.
4. **Export.** Click **Export CSV** to download every reading as a spreadsheet file you can open in Excel or Google Sheets.

### Where your data is kept

Readings and settings are saved in your browser's `localStorage`. This is a small storage area each browser keeps for each page. Some things to know:

1. The data stays on this computer, in this browser only. Another browser or another device will not see it.
2. Clearing your browser history or site data can erase it. Export a CSV now and then as a backup.
3. Private or incognito windows usually throw the data away when you close them.

## Default target ranges

**The defaults are general guidance only. Adjust them for your own pool.** The right numbers depend on your sanitizer (for example, a saltwater pool or regular chlorine), your pool surface, your local water, and your test kit. Your pool professional or your equipment manual is a better source than these defaults.

| Reading | Default min | Default max | Unit |
|---|---|---|---|
| Free chlorine | 1 | 4 | ppm |
| pH | 7.2 | 7.8 | |
| Total alkalinity | 80 | 120 | ppm |
| Cyanuric acid | 30 | 50 | ppm |
| Calcium hardness | 200 | 400 | ppm |
| Water temperature | 78 | 86 | °F |

One example of why you may need to adjust: the free chlorine you need goes up as cyanuric acid (stabilizer) goes up. A fixed free chlorine range cannot capture that, so set it to match your stabilizer level.

The water temperature range is a comfort range for swimming, not a water chemistry target.

## How the files are organized

| File | What it does |
|---|---|
| `index.html` | The page itself. It holds the layout (HTML), the styling (CSS), and the code that saves readings, draws the table, and exports the CSV (JavaScript). |
| `ranges.js` | The range check logic on its own: the list of readings, the default ranges, and the function that decides if a value is low, high, or ok. The page loads this file. |
| `test-ranges.js` | Automated tests for `ranges.js`. |
| `README.md` | This file. |

The range check lives in its own file for one reason: it can be tested without a browser. Keeping the "decide if a number is in range" logic apart from the "draw the page" code is a common habit. It makes each part easier to check.

### Running the tests

You need [Node.js](https://nodejs.org) installed. Then, in a terminal, from this folder:

```
node test-ranges.js
```

You should see each test marked `ok` and a final line like `9 passed, 0 failed`. If a test breaks, it prints `FAIL` with the reason, and the command exits with an error code.

## Git and GitHub terms, for beginners

Git is a tool that records the history of a folder of files. GitHub is a website that stores that history online so you and others can see it, review it, and work on it together.

### Commit

A **commit** is a saved snapshot of your files at one moment, plus a short message saying what changed and why. Think of it as a save point in a game. Each commit remembers who made it and when. You can always go back and see exactly what the files looked like at any commit.

Good commit messages say *why*, not only *what*. "Add CSV export so readings can be backed up" is more useful later than "update file."

### Branch

A **branch** is a separate line of work. The main line of a project usually lives on a branch called `main`. When you start something new, you make a new branch. Your commits go there, and `main` stays untouched until you decide the work is ready.

This lets you experiment safely. If the idea does not work out, you delete the branch and `main` never knew about it.

This pool tracker was committed on its own branch, not on `main`.

### Diff

A **diff** shows the difference between two versions of files. Lines that were added are usually shown in green with a `+` at the start. Lines that were removed are shown in red with a `-` at the start. Lines without a mark are unchanged context.

Reading the diff is how you review a change. You do not need to read every file from top to bottom. You only read what changed.

### Pull request

A **pull request** (often shortened to "PR") is a request on GitHub to merge one branch into another, usually into `main`. It shows the diff, lets people leave comments on specific lines, and records the discussion. Once everyone is happy, someone clicks **Merge**, and the branch's commits become part of `main`.

The name means "please pull my changes into the main project."

### How they fit together

1. Make a **branch** for the new work.
2. Make one or more **commits** on that branch.
3. Look at the **diff** to see what changed.
4. Open a **pull request** so the change can be reviewed.
5. **Merge** the pull request into `main` when it looks right.

For this project, steps 1 and 2 are done. Step 3 is your review. Steps 4 and 5 are yours to try.
