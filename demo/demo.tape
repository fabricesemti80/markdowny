# https://github.com/charmbracelet/vhs
# VHS configuration for terminal recording

Output demo.gif

Set FontSize 14
Set Width 900
Set Height 600
Set Theme "rose-pine-moon"
Set Padding 10

# Show help
Type "mdy --help"
Enter
Sleep 1s

# Clear screen
Hide
Type "clear"
Enter
Sleep 500ms
Show

# Convert to PDF
Type "mdy -i demo/demo.md -o demo/demo.pdf --pdf"
Enter
Sleep 2s

# Clear screen
Hide
Type "clear"
Enter
Sleep 500ms
Show

# Convert to DOCX
Type "mdy -i demo/demo.md -o demo/demo.docx --docx"
Enter
Sleep 2s
