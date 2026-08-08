<#
.SYNOPSIS
    Task runner cho VietJob Korea AI trên Windows.

.DESCRIPTION
    Máy phát triển không có `make`, nên script này đóng vai trò tương đương
    Makefile. `Makefile` ở gốc repo giữ nguyên các target trùng tên để môi
    trường Linux/CI dùng được cùng bộ lệnh.

.EXAMPLE
    .\make.ps1 help
    .\make.ps1 install
    .\make.ps1 api
    .\make.ps1 test
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Target = 'help',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

# Console mặc định của Windows dùng codepage 437/1252 nên tiếng Việt hiện thành
# ký tự rác. Ép UTF-8 cho cả output lẫn các tiến trình con.
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'

$RepoRoot = $PSScriptRoot
$ApiDir = Join-Path $RepoRoot 'apps\api'
$WebDir = Join-Path $RepoRoot 'apps\web'
$Venv = Join-Path $ApiDir '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "OK  $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "!   $Message" -ForegroundColor Yellow
}

function Assert-Venv {
    if (-not (Test-Path $VenvPython)) {
        throw "Chưa có virtualenv tại $Venv. Chạy: .\make.ps1 install"
    }
}

# Dừng ngay khi một bước thất bại, thay vì báo thành công nhầm.
function Invoke-Checked([scriptblock]$Block, [string]$What) {
    & $Block
    if ($LASTEXITCODE -ne 0) {
        throw "$What thất bại (exit code $LASTEXITCODE)"
    }
}

switch ($Target.ToLower()) {

    'help' {
        Write-Host @'
VietJob Korea AI — các lệnh có sẵn

  Cài đặt
    install        Cài dependency cho cả backend và frontend
    env            Tạo .env từ .env.example (không ghi đè file đã có)

  Chạy
    api            Khởi động backend FastAPI (http://127.0.0.1:8000)
    web            Khởi động frontend Vite   (http://localhost:5173)
    worker         Khởi động background worker

  Database
    db-setup       In hướng dẫn tạo database MySQL
    db-check       Kiểm tra kết nối MySQL và charset
    migrate        Áp dụng toàn bộ migration
    migration      Sinh migration mới:  .\make.ps1 migration "mo ta thay doi"
    db-downgrade   Lùi lại một migration

  Kiểm tra chất lượng
    test           Chạy toàn bộ test (backend + frontend)
    test-api       Chỉ test backend
    test-web       Chỉ test frontend
    lint           Lint cả hai
    format         Tự động format cả hai
    typecheck      mypy + tsc
    check          lint + typecheck + test  (chạy trước khi commit)

  Khác
    build          Build frontend cho production
    clean          Xoá cache và file build
'@
    }

    'install' {
        Write-Step 'Backend: virtualenv + dependency'
        if (-not (Test-Path $VenvPython)) {
            python -m venv $Venv
        }
        Invoke-Checked { & $VenvPython -m pip install --upgrade pip --quiet } 'Nâng cấp pip'
        Invoke-Checked {
            & $VenvPython -m pip install -r (Join-Path $ApiDir 'requirements-dev.txt') --quiet
        } 'Cài dependency backend'
        Write-Ok 'Backend sẵn sàng'

        Write-Step 'Frontend: npm install'
        Push-Location $RepoRoot
        try { Invoke-Checked { npm install } 'npm install' } finally { Pop-Location }
        Write-Ok 'Frontend sẵn sàng'

        & $PSCommandPath env
    }

    'env' {
        $envFile = Join-Path $RepoRoot '.env'
        if (Test-Path $envFile) {
            Write-Warn '.env đã tồn tại — không ghi đè.'
        }
        else {
            Copy-Item (Join-Path $RepoRoot '.env.example') $envFile
            Write-Ok 'Đã tạo .env từ .env.example'
            Write-Warn 'Hãy mở .env và điền mật khẩu MySQL vào DATABASE_URL và TEST_DATABASE_URL.'
        }
    }

    'db-setup' {
        $mysql = Get-ChildItem 'C:\Program Files\MySQL' -Recurse -Filter 'mysql.exe' `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        $exe = if ($mysql) { $mysql.FullName } else { 'mysql' }
        $local = Join-Path $RepoRoot 'scripts\mysql_setup.local.sql'
        $script = if (Test-Path $local) { 'scripts\mysql_setup.local.sql' } else { 'scripts\mysql_setup.sql' }

        if (-not (Test-Path $local)) {
            Write-Warn 'Chưa có scripts\mysql_setup.local.sql.'
            Write-Host '  Mở scripts\mysql_setup.sql, thay CHANGE_ME_STRONG_PASSWORD bằng mật khẩu'
            Write-Host '  bạn tự chọn, lưu thành mysql_setup.local.sql (file này đã được gitignore),'
            Write-Host '  rồi điền cùng mật khẩu đó vào .env.'
            Write-Host ''
        }

        # Dùng `-e "source ..."` chứ không dùng `< file`: PowerShell không hỗ trợ
        # toán tử `<` (báo "reserved for future use"), nên lệnh redirect quen
        # thuộc của MySQL sẽ lỗi cú pháp trước khi chạy tới.
        $forward = $script -replace '\\', '/'
        Write-Host @"
Chạy lệnh sau, MySQL sẽ hỏi mật khẩu root của bạn:

   & "$exe" -u root -p -e "source $forward"

Sau đó kiểm tra:

   .\make.ps1 db-check

"@
    }

    'api' {
        Assert-Venv
        Push-Location $ApiDir
        try {
            & $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
        }
        finally { Pop-Location }
    }

    'web' {
        Push-Location $WebDir
        try { npm run dev } finally { Pop-Location }
    }

    'worker' {
        Assert-Venv
        Push-Location $ApiDir
        try { & $VenvPython -m app.workers.run } finally { Pop-Location }
    }

    'db-check' {
        Assert-Venv
        Push-Location $ApiDir
        try {
            & $VenvPython -m app.cli.dbcheck
            if ($LASTEXITCODE -ne 0) { throw 'Kiểm tra database thất bại' }
        }
        finally { Pop-Location }
    }

    'migrate' {
        Assert-Venv
        Push-Location $ApiDir
        try { Invoke-Checked { & $VenvPython -m alembic upgrade head } 'Migration' }
        finally { Pop-Location }
        Write-Ok 'Database đã ở phiên bản mới nhất'
    }

    'migration' {
        Assert-Venv
        $message = if ($Rest) { $Rest -join ' ' } else { throw 'Cần mô tả: .\make.ps1 migration "mo ta"' }
        Push-Location $ApiDir
        try {
            Invoke-Checked {
                & $VenvPython -m alembic revision --autogenerate -m $message
            } 'Sinh migration'
        }
        finally { Pop-Location }
        Write-Warn 'Hãy ĐỌC LẠI file migration vừa sinh trước khi chạy migrate.'
    }

    'db-downgrade' {
        Assert-Venv
        Push-Location $ApiDir
        try { Invoke-Checked { & $VenvPython -m alembic downgrade -1 } 'Downgrade' }
        finally { Pop-Location }
    }

    'test-api' {
        Assert-Venv
        Push-Location $ApiDir
        try { Invoke-Checked { & $VenvPython -m pytest } 'Test backend' }
        finally { Pop-Location }
    }

    'test-web' {
        Push-Location $WebDir
        try { Invoke-Checked { npm run test } 'Test frontend' } finally { Pop-Location }
    }

    'test' {
        & $PSCommandPath test-api
        & $PSCommandPath test-web
        Write-Ok 'Toàn bộ test đã chạy xong'
    }

    'lint' {
        Assert-Venv
        Write-Step 'Backend: ruff'
        Push-Location $ApiDir
        try {
            Invoke-Checked { & $VenvPython -m ruff check . } 'ruff check'
            Invoke-Checked { & $VenvPython -m ruff format --check . } 'ruff format --check'
        }
        finally { Pop-Location }

        Write-Step 'Frontend: eslint'
        Push-Location $WebDir
        try { Invoke-Checked { npm run lint } 'eslint' } finally { Pop-Location }
        Write-Ok 'Lint sạch'
    }

    'format' {
        Assert-Venv
        Push-Location $ApiDir
        try {
            & $VenvPython -m ruff check --fix .
            & $VenvPython -m ruff format .
        }
        finally { Pop-Location }

        Push-Location $RepoRoot
        try { npm run format } finally { Pop-Location }
        Write-Ok 'Đã format xong'
    }

    'typecheck' {
        Assert-Venv
        Write-Step 'Backend: mypy'
        Push-Location $ApiDir
        try { Invoke-Checked { & $VenvPython -m mypy app tests } 'mypy' } finally { Pop-Location }

        Write-Step 'Frontend: tsc'
        Push-Location $WebDir
        try { Invoke-Checked { npm run typecheck } 'tsc' } finally { Pop-Location }
        Write-Ok 'Type check sạch'
    }

    'check' {
        & $PSCommandPath lint
        & $PSCommandPath typecheck
        & $PSCommandPath test
        Write-Ok 'Tất cả kiểm tra đã qua — sẵn sàng commit'
    }

    'build' {
        Push-Location $WebDir
        try { Invoke-Checked { npm run build } 'Build frontend' } finally { Pop-Location }
    }

    'clean' {
        $patterns = @(
            "$ApiDir\.pytest_cache", "$ApiDir\.mypy_cache", "$ApiDir\.ruff_cache",
            "$ApiDir\htmlcov", "$WebDir\dist", "$WebDir\coverage"
        )
        foreach ($p in $patterns) {
            if (Test-Path $p) { Remove-Item -Recurse -Force $p }
        }
        Get-ChildItem $ApiDir -Recurse -Directory -Filter '__pycache__' `
            -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        Write-Ok 'Đã dọn cache và file build'
    }

    default {
        Write-Warn "Không có target '$Target'."
        & $PSCommandPath help
        exit 1
    }
}
