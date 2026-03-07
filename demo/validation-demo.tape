Output "docs/assets/validation-demo.gif"

Set Shell "bash"
Set FontSize 22
Set Width 1200
Set Height 900
Set Theme "Builtin Solarized Dark"
Set TypingSpeed 90ms
Set Padding 24

Type "cd /workspace"
Enter
Sleep 1400ms
Type "python3 -m venv /tmp/validation-demo-venv"
Enter
Sleep 2600ms
Type "source /tmp/validation-demo-venv/bin/activate"
Enter
Sleep 1200ms
Type "python -m pip install -q -e ."
Enter
Sleep 3200ms

Type "python demo/preview.py"
Enter
Sleep 4200ms
