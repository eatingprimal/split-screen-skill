# Split screen skill for Claude

Makes the split screen "talking to yourself" video: you play both sides of a conversation, one take on each half
of the frame, and Claude lines the two takes up into one clip with a clean seam down the middle.

You film the two takes. Claude finds each line, lines up the conversation, blends the seam, and hands back a
finished 1080x1920 clip.

## What you need

- Claude Code (the Claude desktop app's Code tab, or the `claude` command line tool)
- Python 3.9 or newer
- ffmpeg 7 or newer (on a Mac: `brew install ffmpeg`)

Everything runs on your own computer. Your footage is not uploaded anywhere.

## Install

1. Download this repository (green **Code** button, then **Download ZIP**) and unzip it.
2. Rename the folder to `split-screen` and move it into your Claude skills folder:
   - for every project: `~/.claude/skills/split-screen`
   - or for one project only: `<your project>/.claude/skills/split-screen`
3. Install the two Python packages:

   ```bash
   pip install numpy faster-whisper
   ```

4. Start a new Claude session.

## Use

Film your two takes (the filming rules are below), put both files somewhere Claude can reach, and say something like:

> Make a split screen from these two takes. left.mov is the left side, right.mov is the right side.
> The conversation goes: right side "I've got the better one", left side "No, I've got the better one", ...

Claude walks through it from there and shows you the result.

## Filming rules (the edit cannot fix these)

1. Phone on a tripod. Do not touch it between the two takes.
2. Pick a midline in the background, like a door frame, and never cross it.
3. Film both takes back to back, same spot, same light.
4. Pause at the end of every line and before every reply.
5. While listening, stay fairly still: nod, look over, hold the product.
6. A different shirt for each side helps.

## Using it without Claude

`split_screen.py` works on its own. Copy `example_plan.json`, fill in your two files and the rough time window of
each line, then run:

```bash
python split_screen.py plan.json
```

`python transcribe.py take.mov` prints every word with its time, which makes the windows easy to find. The top of
`split_screen.py` explains every setting.
