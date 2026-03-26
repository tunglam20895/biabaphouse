# setup_scheduler.ps1
# Tạo Task Scheduler chạy pipeline tự động mỗi ngày lúc 7:00
# Cách chạy: chuột phải → "Run with PowerShell"

$PythonPath  = (Get-Command python).Source
$ScriptPath  = "G:\TIKTOK\run_pipeline.py"
$WorkDir     = "G:\TIKTOK"
$TaskName    = "TikTok_Affiliate_Pipeline"
$TriggerTime = "07:00"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --auto" `
    -WorkingDirectory $WorkDir

$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 30)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName   $TaskName `
    -Action     $Action `
    -Trigger    $Trigger `
    -Settings   $Settings `
    -Principal  $Principal `
    -Description "TikTok Affiliate pipeline - chạy mỗi ngày lúc $TriggerTime"

Write-Host ""
Write-Host "✅ Task Scheduler đã được tạo!" -ForegroundColor Green
Write-Host "   Tên task : $TaskName"
Write-Host "   Chạy lúc : $TriggerTime mỗi ngày"
Write-Host ""
Write-Host "⚠️  Nhớ đóng Microsoft Edge hoàn toàn trước $TriggerTime" -ForegroundColor Yellow
Write-Host "   (Selenium cần độc quyền truy cập Edge profile)"
Write-Host ""
Read-Host "Nhấn Enter để thoát"