Option Explicit

Dim shell, fso, baseDir, pythonExe, scriptFile, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = "C:\venvs\performance_inspection\Scripts\pythonw.exe"
scriptFile = fso.BuildPath(baseDir, "main.py")

If Not fso.FileExists(pythonExe) Then
    MsgBox "pythonw.exe not found:" & vbCrLf & pythonExe, vbCritical, "Launch error"
    WScript.Quit 1
End If

If Not fso.FileExists(scriptFile) Then
    MsgBox "Program file not found:" & vbCrLf & scriptFile, vbCritical, "Launch error"
    WScript.Quit 1
End If

shell.CurrentDirectory = baseDir
command = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & scriptFile & Chr(34)
shell.Run command, 0, False
