
 = [System.Environment]::GetFolderPath('Desktop')
 = New-Object -ComObject WScript.Shell
Get-ChildItem -Path  -Filter *.lnk | ForEach-Object {
     = .CreateShortcut(.FullName)
    if (.TargetPath -match 'Work center' -or .Name -match 'BahonIQ') {
        .IconLocation = 'C:\Users\user\Desktop\Work center\assets\icon.ico'
        .Save()
        Write-Output ('Updated: ' + .Name)
    }
}
