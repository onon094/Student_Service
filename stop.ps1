# 停止粤教服务后端
# uvicorn --reload 会启动「监控进程 + 工作进程」两个进程，
# 直接 Ctrl+C 经常只停掉其中一个，必须结束整棵进程树。

$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if (-not $conns) {
    Write-Host "  端口 8000 当前空闲，无需停止。"
    exit 0
}

foreach ($c in $conns) {
    $procId = $c.OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"

    if ($proc -and $proc.ParentProcessId) {
        $root = $proc.ParentProcessId
        Write-Host "  结束进程树 PID $root （连同子进程）"
        taskkill /F /T /PID $root 2>$null | Out-Null
    }
    else {
        Write-Host "  结束进程 PID $procId"
        taskkill /F /PID $procId 2>$null | Out-Null
    }
}

Start-Sleep -Seconds 2

$still = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "  端口仍被占用，PID: $($still.OwningProcess)"
    Write-Host "  请在任务管理器里手动结束该进程。"
}
else {
    Write-Host "  已彻底停止。现在可以双击 run.bat 重新启动。"
}

