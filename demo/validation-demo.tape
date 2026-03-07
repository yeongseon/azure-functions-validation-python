Output "docs/assets/validation-demo.gif"

Set Shell "bash"
Set FontSize 22
Set Width 1200
Set Height 900
Set Theme "Builtin Solarized Dark"
Set TypingSpeed 55ms
Set Padding 24

Hide
Type "python3 -m venv /tmp/validation-demo-venv"
Enter
Type "/tmp/validation-demo-venv/bin/pip install -q --upgrade pip"
Enter
Type "/tmp/validation-demo-venv/bin/pip install -q -e /workspace"
Enter
Type "clear"
Enter
Show

Type "cd /workspace"
Enter
Sleep 700ms

Type "/tmp/validation-demo-venv/bin/python demo/render_validation_output.py"
Enter
Sleep 3200ms
