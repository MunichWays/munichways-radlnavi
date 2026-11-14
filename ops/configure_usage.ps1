# Creates low-cardinality route counters and a separate usage dashboard.
param([switch]$Apply)
$ErrorActionPreference='Stop'
python "$PSScriptRoot/usage_dashboard.py"
if ($LASTEXITCODE -ne 0) { throw 'Cannot generate usage plan' }
$plan=Get-Content "$PSScriptRoot/usage-plan.json" -Raw|ConvertFrom-Json
if (-not $Apply) { $plan.metrics|Select-Object name,filter; return }
$token=gcloud auth print-access-token
if ($LASTEXITCODE -ne 0) { throw 'Authentication failed' }
$headers=@{Authorization="Bearer $token"}
function Api($method,$uri,$body=$null) {
    $params=@{Method=$method;Uri=$uri;Headers=$headers;TimeoutSec=90}
    if($null -ne $body){$params.ContentType='application/json';$params.Body=[Text.Encoding]::UTF8.GetBytes(($body|ConvertTo-Json -Depth 40))}
    try { Invoke-RestMethod @params } catch {
        Write-Host "Failed: $method $uri"
        if($_.ErrorDetails.Message){Write-Host $_.ErrorDetails.Message}
        throw
    }
}
$project='munichways-radlnavi-prod'
$logging="https://logging.googleapis.com/v2/projects/$project"
$existing=@((Api GET "$logging/metrics").metrics)
foreach($metric in $plan.metrics){
    $match=@($existing|Where-Object name -eq $metric.name)
    if($match.Count -gt 0){$null=Api PUT "$logging/metrics/$($metric.name)" $metric}
    else{$null=Api POST "$logging/metrics" $metric}
    $v=Api GET "$logging/metrics/$($metric.name)"
    if($v.filter -ne $metric.filter){throw "Metric verification failed: $($metric.name)"}
    Write-Output "Verified metric: $($metric.name)"
}
$base="https://monitoring.googleapis.com/v1/projects/$project/dashboards"
$existing=@((Api GET $base).dashboards)
$match=@($existing|Where-Object displayName -eq $plan.dashboard.displayName)
if($match.Count -gt 1){throw 'Duplicate usage dashboards'}
if($match.Count -eq 1){
    $old=Api GET "https://monitoring.googleapis.com/v1/$($match[0].name)"
    $plan.dashboard|Add-Member name $old.name
    $plan.dashboard|Add-Member etag $old.etag
    $result=Api PATCH "https://monitoring.googleapis.com/v1/$($old.name)" $plan.dashboard
}else{$result=Api POST $base $plan.dashboard}
$v=Api GET "https://monitoring.googleapis.com/v1/$($result.name)"
if($v.gridLayout.widgets.Count -ne $plan.dashboard.gridLayout.widgets.Count){throw 'Dashboard verification failed'}
Write-Output "Verified dashboard: https://console.cloud.google.com/monitoring/dashboards/builder/$($result.name.Split('/')[-1])?project=$project"
