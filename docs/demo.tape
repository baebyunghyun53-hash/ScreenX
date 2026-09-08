# VHS tape script — records a demo GIF of `market-rank update --market-cap 100`
# Docs: https://github.com/charmbracelet/vhs
#
# Run with:
#   vhs demo.tape
#
# Produces: demo.gif

Output demo.gif

Set Shell "bash"
Set Width 1400
Set Height 700
Set FontSize 13
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 60ms

# --- Hidden setup: fakes the prompt and clears real path/history before recording ---
Hide
Type "export PS1='~/market-rank $ '"
Enter
Type "cd ~"
Enter
Type "clear"
Enter
Show

# --- Visible recording starts here ---
Type "market-rank update --market-cap 100"
Sleep 500ms
Enter

# Adjust this to roughly how long the real command takes.
# If you want a faster/shorter demo instead of the real 100-symbol run,
# swap the command above for something like:
#   market-rank update --market-cap 100 --max-symbols 15
Sleep 15s

Sleep 2s
