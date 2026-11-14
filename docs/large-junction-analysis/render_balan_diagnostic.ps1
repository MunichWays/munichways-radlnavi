Add-Type -AssemblyName System.Drawing
$pilotData = Get-Content -Raw -Encoding utf8 (Join-Path $PSScriptRoot 'balan-chiemgau-review.json') | ConvertFrom-Json
$bitmap = New-Object System.Drawing.Bitmap(1000,800)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::White)
$font = New-Object System.Drawing.Font('Arial',12)
$smallFont = New-Object System.Drawing.Font('Arial',10)
function MapPoint($coordinate) {
    [System.Drawing.PointF]::new([single](60+($coordinate[0]-11.60320)*490000),[single](740-($coordinate[1]-48.10798)*650000))
}
function DrawPath($coordinates,$pen) {
    $points = [System.Drawing.PointF[]]@($coordinates | ForEach-Object { MapPoint $_ })
    if ($points.Length -ge 2) { $graphics.DrawLines($pen,$points) }
}
foreach ($way in $pilotData.osm.features) {
    $width = if ($way.properties.highway -in @('primary','secondary','tertiary')) {14} else {2}
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::LightGray,$width)
    DrawPath $way.geometry.coordinates $pen
    $pen.Dispose()
}
$polygonPoints = [System.Drawing.PointF[]]@($pilotData.polygon.geometry.coordinates[0] | ForEach-Object { MapPoint $_ })
$fill = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(35,130,75,180))
$graphics.FillPolygon($fill,$polygonPoints)
$polygonPen = New-Object System.Drawing.Pen([System.Drawing.Color]::Purple,2)
$graphics.DrawPolygon($polygonPen,$polygonPoints)
foreach ($way in $pilotData.osm.features) {
    if ($way.properties.crossing) {
        $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::DimGray,4)
        DrawPath $way.geometry.coordinates $pen
        $pen.Dispose()
    }
}
foreach ($route in $pilotData.routes) {
    $color = if ($route.id.EndsWith('left')) {[System.Drawing.Color]::Blue} else {[System.Drawing.Color]::DarkOrange}
    $routePen = New-Object System.Drawing.Pen($color,4)
    if ($route.id.EndsWith('straight')) { $routePen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash }
    DrawPath $route.geometry.coordinates $routePen
    $routePen.Dispose()
}
foreach ($marker in $pilotData.markers) {
    if ($marker.kind -eq 'traffic_signals') {
        $p=MapPoint $marker.location
        $graphics.FillEllipse([System.Drawing.Brushes]::Black,($p.X-4),($p.Y-4),8,8)
    }
}
foreach ($gate in $pilotData.gates) {
    $p=MapPoint $gate.location
    $graphics.FillEllipse([System.Drawing.Brushes]::White,($p.X-6),($p.Y-6),12,12)
    $graphics.DrawEllipse([System.Drawing.Pens]::Black,($p.X-6),($p.Y-6),12,12)
    $graphics.DrawString(($gate.id+' '+$gate.kind),$smallFont,[System.Drawing.Brushes]::Black,($p.X+8),($p.Y-10))
}
$graphics.DrawString('Balanstrasse / Chiemgaustrasse - Polygonentwurf v1',$font,[System.Drawing.Brushes]::Black,20,20)
$graphics.DrawString('Blau: links | orange gestrichelt: geradeaus | violett: Entwurf',$smallFont,[System.Drawing.Brushes]::Black,20,760)
$graphics.DrawString('N',$font,[System.Drawing.Brushes]::Black,950,40)
$graphics.Dispose()
$bitmap.Save((Join-Path $PSScriptRoot 'balan-chiemgau-diagnostic.png'),[System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
