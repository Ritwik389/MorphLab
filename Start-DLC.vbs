Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c .\venv\Scripts\python.exe run.py --execution-provider cuda", 0, False
