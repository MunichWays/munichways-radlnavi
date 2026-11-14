param([string]$BatchDirectory = 'review-batch-01-images')
# Render the same drawing commands as the SVGs, without installing image libraries.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$outputDirectory = Join-Path $PSScriptRoot $BatchDirectory
$reviewDirectory = Join-Path $PSScriptRoot 'kreuzungspruefung'
$drawingFiles = @(Get-ChildItem -LiteralPath $outputDirectory -Filter '*.drawing.json')
if (Test-Path -LiteralPath $reviewDirectory) {
    $drawingFiles += @(Get-ChildItem -LiteralPath $reviewDirectory -Recurse -Filter '*.drawing.json')
}
foreach ($file in $drawingFiles) {
    $commands = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $bitmap = [System.Drawing.Bitmap]::new(1200, 1100)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
        $graphics.Clear([System.Drawing.Color]::White)
        foreach ($command in $commands) {
            if ($command.kind -eq 'clip') {
                $graphics.SetClip([System.Drawing.Rectangle]::new($command.x,$command.y,$command.width,$command.height))
                continue
            }
            if ($command.kind -eq 'unclip') { $graphics.ResetClip(); continue }
            $color = [System.Drawing.ColorTranslator]::FromHtml($command.color)
            $brush = [System.Drawing.SolidBrush]::new($color)
            try {
                if ($command.kind -eq 'text') {
                    $font = [System.Drawing.Font]::new('Arial', [single]$command.size, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
                    try { $graphics.DrawString($command.text,$font,$brush,[single]$command.x,[single]$command.y) }
                    finally { $font.Dispose() }
                } elseif ($command.kind -eq 'circle') {
                    $pen = [System.Drawing.Pen]::new($color,2)
                    $fill = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($command.fill))
                    try {
                        $r = [single]$command.radius
                        $graphics.FillEllipse($fill,[single]($command.x-$r),[single]($command.y-$r),2*$r,2*$r)
                        $graphics.DrawEllipse($pen,[single]($command.x-$r),[single]($command.y-$r),2*$r,2*$r)
                    } finally { $pen.Dispose(); $fill.Dispose() }
                } else {
                    $points = [System.Drawing.PointF[]]@($command.points | ForEach-Object { [System.Drawing.PointF]::new([single]$_[0],[single]$_[1]) })
                    $pen = [System.Drawing.Pen]::new($color,[single]$command.width)
                    try {
                        if ($command.kind -eq 'polygon') {
                            $fill = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($command.fill))
                            try { $graphics.FillPolygon($fill,$points) } finally { $fill.Dispose() }
                            $graphics.DrawPolygon($pen,$points)
                        } elseif ($points.Length -ge 2) { $graphics.DrawLines($pen,$points) }
                    } finally { $pen.Dispose() }
                }
            } finally { $brush.Dispose() }
        }
        $target = Join-Path $file.DirectoryName ($file.Name.Replace('.drawing.json','.png'))
        $bitmap.Save($target,[System.Drawing.Imaging.ImageFormat]::Png)
        Write-Output $target
    } finally { $graphics.Dispose(); $bitmap.Dispose() }
}

# A contact sheet for quickly comparing the complete batch, with full-size files alongside it.
$reviewData = Get-Content -LiteralPath (Join-Path $outputDirectory 'review-data.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$expectedFiles = @($reviewData.sites | ForEach-Object { 'K{0:00}-{1}.png' -f $_.number,$_.id })
$files = @(Get-ChildItem -LiteralPath $reviewDirectory -Recurse -Filter 'K*.png' | Where-Object { $_.Name -in $expectedFiles } | Sort-Object Name)
$sheet = [System.Drawing.Bitmap]::new(1200, [int](550 * [Math]::Ceiling($files.Count / 2)))
$canvas = [System.Drawing.Graphics]::FromImage($sheet)
try {
    $canvas.Clear([System.Drawing.Color]::White)
    $canvas.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    for ($i=0; $i -lt $files.Count; $i++) {
        $image = [System.Drawing.Image]::FromFile($files[$i].FullName)
        try { $canvas.DrawImage($image,[int](($i % 2)*600),[int]([Math]::Floor($i/2)*550),600,550) }
        finally { $image.Dispose() }
    }
    $sheet.Save((Join-Path $outputDirectory 'overview.png'),[System.Drawing.Imaging.ImageFormat]::Png)
} finally { $canvas.Dispose(); $sheet.Dispose() }
