# Prompt Enhancer — VHS Demo Tape
# Renders a terminal demo showing pe enhance → pe benchmark → pe install

Output "docs/demo.gif"
Set Framerate 24
Set PlaybackSpeed 0.8

# Window setup
Set Width 90
Set Height 30
Set FontFamily "JetBrains Mono"
Set FontSize 14
Set Theme "Dracula"

# Start
Hide
Type "pe enhance 'a senior Rust developer who prefers functional programming and zero-cost abstractions'"
Sleep 500ms
Enter
Sleep 5s

# Show the output scrolling
Show
Sleep 2s

# Clear and show benchmark
Hide
Ctrl+L
Type "pe benchmark --enhance 'a Go backend dev who prefers simplicity'"
Sleep 500ms
Enter
Sleep 8s

# Show benchmark result
Show
Sleep 3s

# Clear and show install
Hide
Ctrl+L
Type "pe install 'a security reviewer who focuses on injection vulnerabilities' --agent claude --dry-run"
Sleep 500ms
Enter
Sleep 5s

# Show install result
Show
Sleep 2s

# Show store stats
Hide
Ctrl+L
Type "pe store stats"
Sleep 500ms
Enter
Sleep 2s

Show
Sleep 2s
