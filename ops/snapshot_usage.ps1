# Aggregate retained request logs; never persist URLs, coordinates or IPs.
$ErrorActionPreference='Stop'
$plan=Get-Content "$PSScriptRoot/usage-plan.json" -Raw|ConvertFrom-Json
$token=gcloud auth print-access-token
if($LASTEXITCODE -ne 0){throw 'Authentication failed'}
$headers=@{Authorization="Bearer $token"}
$end=[DateTimeOffset]::UtcNow
$start=$end.AddDays(-30)
$filters=@($plan.metrics|Where-Object {$_.name -like '*_usage'}|ForEach-Object {'('+$_.filter+')'})
$filter='(' + ($filters -join ' OR ') + ') AND timestamp>="'+$start.ToString('o')+'" AND timestamp<"'+$end.ToString('o')+'"'
$days=@{}
$counts=@{standard=0;direct=0;discovery=0}
$zone=[TimeZoneInfo]::FindSystemTimeZoneById('W. Europe Standard Time')
$page=$null
do {
    $body=@{resourceNames=@('projects/munichways-radlnavi-prod');filter=$filter;pageSize=1000;orderBy='timestamp asc'}
    if($page){$body.pageToken=$page}
    $r=Invoke-RestMethod -Method Post -Uri 'https://logging.googleapis.com/v2/entries:list' -Headers $headers -ContentType 'application/json' -Body ($body|ConvertTo-Json) -TimeoutSec 90
    foreach($entry in $r.entries){
        $service=$entry.resource.labels.service_name
        $variant=if($service -eq 'munichways-radlnavi-api'){'standard'}elseif($service -eq 'munichways-radlnavi-direct-api'){'direct'}else{'discovery'}
        $day=[TimeZoneInfo]::ConvertTime([DateTimeOffset]::Parse($entry.timestamp),$zone).ToString('yyyy-MM-dd')
        if(-not $days.ContainsKey($day)){$days[$day]=@{standard=0;direct=0;discovery=0}}
        $days[$day][$variant]++
        $counts[$variant]++
    }
    $page=$r.nextPageToken
}while($page)
$snapshot=@{start=$start.ToString('o');end=$end.ToString('o');counts=$counts;days=@($days.Keys|Sort-Object|ForEach-Object {@{day=$_;counts=$days[$_]}})}
$snapshot|ConvertTo-Json -Depth 8|Set-Content "$PSScriptRoot/usage-history.json" -Encoding UTF8
$counts|ConvertTo-Json
Write-Output 'Aggregated history saved; no individual request data persisted.'
