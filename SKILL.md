---
name: split-screen
description: Build a split screen "talking to yourself" video from two takes of the same person, one on each half of the frame. Use when the user wants a split screen, clone, or two-of-me conversation video, or sends two takes filmed from a locked tripod and asks to line them up as a conversation.
---

# Split screen conversation video

One person plays both sides of a conversation. They film one take standing on the left half of the frame and one
take on the right half, with the phone locked on a tripod. `split_screen.py` (in this folder) joins the two takes
down a soft vertical seam and lines up the conversation: the side that is talking plays at real speed and is the
only audio, and the listening side plays its own footage from between its lines.

## Before the user films: tell them the rules the edit cannot fix

1. Phone on a tripod or a surface that cannot move. Do not touch it between the two takes. Any shift breaks the seam.
2. Pick a physical midline in the background (a door frame works) and never let any part of the body cross it.
3. Film both takes back to back, in the same spot, in the same light.
4. Leave a pause at the end of every line, and start every reply with a pause. It should feel like having the
   conversation in your head.
5. While "listening", stay fairly still: nod, look over at the other side, hold the product. Big movements look
   jumpy once the conversation is lined up.
6. A different shirt for each side helps the viewer tell the two characters apart.

## Workflow

1. **Get the two takes** and ask which one is the left side and which is the right. Ask for the script, or the
   order the lines should play in. Never guess the line order: if it is unclear, ask.
2. **Find each line.** Run `python transcribe.py <take>` on both takes. It prints every word with its time.
   If a line was said more than once, ask the user which take of the line they want, or pick the cleanest one
   and say which you picked.
3. **Write the plan.** Copy `example_plan.json`. For each line, in conversation order, give the side (`"L"` or
   `"R"`) and a rough window in seconds, in that side's own take, that contains the line. Leave about half a
   second of slack on both ends; the script finds the voice and trims tight to it.
4. **Check the plan before rendering:** `python split_screen.py plan.json --pieces`. This prints the cut plan
   without rendering. Confirm each line has one tight piece and the total length looks right. A line that comes
   back in several pieces usually means the window caught a false start or a second take: tighten the window.
5. **Render:** `python split_screen.py plan.json`. It writes the video and a frame sheet image next to it.
6. **Look at the frame sheet yourself before showing the user anything.** One row per line: first, middle and
   last frame. Check that the seam is invisible (no doubled background edges, no ghosting), that nobody crosses
   it, and that the listening side looks natural. Then send the video.

## Settings worth knowing

- **`seam_x`**: where the seam sits on a 1080-wide frame. 540 is the centre. Move it if the user's midline is
  off-centre. Put it on a plain stretch of background, not on an edge.
- **`feather`**: how wide the soft blend is. 48 is a good start. Too narrow shows a hard line; too wide makes
  things near the seam go see-through.
- **`mode`**: `"1x"` (default) keeps the listening side at real speed, and it jumps into its next line. `"fit"`
  speeds up or slows down the listening side so it never jumps. Use `1x` unless the user asks otherwise; large
  speed changes in `fit` look unnatural. If unsure, render both and let the user pick.
- **`gap`**: the pause kept after each line before the reply. 0.15 seconds feels like a quick back and forth.
  Raise it for a slower conversation.
- **`cut`**: advanced. If word endings are getting clipped or background noise is being kept as speech, see the
  comment above `CUT_DEFAULTS` in `split_screen.py`.

## Practical advice

- A full-length split screen video is a lot of filming and lining up. A common approach is to use the split
  screen only for the opening few seconds, then cut to each character alone. This tool renders the split screen
  clip; the rest of the video can be joined after it in any editor.
- Output is 1080x1920, 30 fps, with audio levelled, ready to post or to drop into an editor for captions and text.

## Setup (once)

- Python 3.9 or newer, with `pip install numpy faster-whisper`
- ffmpeg version 7 or newer, on the PATH (macOS: `brew install ffmpeg`)
- Everything runs on the user's own computer. No footage is uploaded anywhere.
