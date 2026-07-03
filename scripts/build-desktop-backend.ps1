param(
    [string]$Python = ".\venv310\Scripts\python.exe",
    [string]$SampleSourceData = "",
    [string]$SampleBookName = "优化设计",
    [switch]$SkipSampleDataPrepare,
    [switch]$RequireSampleData
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDist = Join-Path $projectRoot "frontend\dist"
$sampleData = Join-Path $projectRoot "desktop\sample_data"
Set-Location $projectRoot

function Invoke-CheckedCommand {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Host $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipSampleDataPrepare) {
    if (-not $SampleSourceData) { $SampleSourceData = Join-Path $projectRoot "kaoyan-assistant\data" }
    if (Test-Path -LiteralPath $SampleSourceData) {
        & (Join-Path $projectRoot "scripts\prepare-desktop-sample-data.ps1") -SourceData $SampleSourceData -TargetData $sampleData -BookName $SampleBookName
    } elseif ($RequireSampleData) {
        throw "Sample source data not found: $SampleSourceData"
    } else {
        Write-Warning "Sample source data not found: $SampleSourceData. The desktop package will not include bundled demo data/models."
    }
}

Invoke-CheckedCommand "[1/3] Building frontend assets..." {
    Push-Location (Join-Path $projectRoot "frontend")
    try {
        npm.cmd run build
    } finally {
        Pop-Location
    }
}

Invoke-CheckedCommand "[2/3] Checking PyInstaller..." {
    & $Python -m PyInstaller --version
}

Invoke-CheckedCommand "[3/3] Building backend executable..." {
    & $Python -m PyInstaller `
      --noconfirm `
      --clean `
      --name backend_server `
      --distpath build\backend `
      --workpath build\pyinstaller `
      --specpath build\pyinstaller `
      --paths $projectRoot `
      --hidden-import backend.main `
      --hidden-import langchain_chroma `
      --hidden-import chromadb `
      --hidden-import sentence_transformers `
      --hidden-import huggingface_hub `
      --collect-submodules backend `
      --collect-submodules graph `
      --collect-submodules ingestion `
      --collect-submodules knowledge `
      --collect-submodules memory `
      --collect-submodules utils `
      --collect-data chromadb `
      --collect-data sentence_transformers `
      --collect-data transformers `
      --exclude-module agents `
      --exclude-module paddle `
      --exclude-module paddleocr `
      --exclude-module paddlex `
      --exclude-module cv2 `
      --exclude-module mineru `
      --exclude-module mineru_vl_utils `
      --exclude-module marker_pdf `
      --exclude-module marker `
      --exclude-module surya `
      --exclude-module nougat `
      --exclude-module doclayout_yolo `
      --exclude-module modelscope `
      --exclude-module albumentations `
      --exclude-module skimage `
      --exclude-module gradio `
      --exclude-module gradio_client `
      --exclude-module plotly `
      --exclude-module coverage `
      --exclude-module hypothesis `
      --exclude-module pytest_cov `
      --exclude-module notebook `
      --exclude-module jupyter `
      --exclude-module jupyterlab `
      --exclude-module sphinx `
      --exclude-module mkdocs `
      --exclude-module ultralytics `
      --exclude-module torchvision `
      --exclude-module datasets `
      --exclude-module timm `
      --exclude-module av `
      --exclude-module boto3 `
      --exclude-module botocore `
      --exclude-module s3transfer `
      --exclude-module pandas `
      --exclude-module polars `
      --exclude-module pyarrow `
      --exclude-module matplotlib `
      --exclude-module IPython `
      --exclude-module jedi `
      --exclude-module pytest `
      --exclude-module nltk `
      --exclude-module sklearn `
      --exclude-module lightning `
      --exclude-module onnxruntime `
      --exclude-module tkinter `
      --exclude-module _tkinter `
      --add-data "${frontendDist};frontend\dist" `
      --add-data "${sampleData};sample_data" `
      desktop\backend_server.py
}

Write-Host "Backend executable ready: build\backend\backend_server\backend_server.exe"
Write-Host "Next: cd desktop; npm install; npm run dist"
