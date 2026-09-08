# VHS tape script — records a demo GIF of `market-rank top --limit 25`
# Docs: https://github.com/charmbracelet/vhs
#
# Requires a snapshot to already exist (run `market-rank update ...` first
# in this same environment so `top` has data to show).
#
# Run with:
#   vhs demo-top.tape
#
# Produces: demo-top.gif

Output demo-top.gif

Set Shell "bash"
Set Width 1400
Set Height 700
Set FontSize 13
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 60ms

# --- Hidden setup: fakes home/prompt and clears real path/history before recording ---
Hide
Type "export PS1='~/market-rank $ '"
Enter
Type "cd ~"
Enter
Type "clear"
Enter
Show

# --- Visible recording starts here ---
Type "market-rank top --limit 25"
Sleep 500ms
Enter

Sleep 4s
