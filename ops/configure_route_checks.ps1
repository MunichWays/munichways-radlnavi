# Replace legacy uptime probes with daytime route requests. No min instances.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$project = 'munichways-radlnavi-prod'
$parent = "projects/$project/locations/europe-west3"
$schedule = '*/5 5-23 * * *'
$path = '/route/v1/bike/11.5755,48.1374;11.5583,48.1402?alternatives=false&steps=false&annotations=false&geometries=geojson&overview=false'
$targets = @{
    standard = 'https://api.radlnavi.munichways.de'
    direct = 'https://munichways-radlnavi-direct-api-melvpv5saa-ey.a.run.app'
    discovery = 'https://munichways-radlnavi-discovery-api-melvpv5saa-ey.a.run.app'
}
if (-not $Apply) {
    $targets.GetEnumerator() | ForEach-Object {
        [pscustomobject]@{variant=$_.Key; schedule=$schedule; timeZone='Europe/Berlin'; uri=$_.Value+$path}
    }
    return
}
& gcloud services enable cloudscheduler.googleapis.com "--project=$project" --quiet
if ($LASTEXITCODE -ne 0) { throw 'Could not enable Cloud Scheduler' }
$token = & gcloud auth print-access-token
if ($LASTEXITCODE -ne 0) { throw 'Could not authenticate' }
$headers = @{Authorization="Bearer $token"}
function Api($method, $uri, $body=$null) {
    $args = @{Method=$method; Uri=$uri; Headers=$headers; TimeoutSec=90}
    if ($null -ne $body) { $args.ContentType='application/json'; $args.Body=($body|ConvertTo-Json -Depth 30) }
    try { Invoke-RestMethod @args } catch {
        Write-Host "Failed: $method $uri"
        if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
        elseif ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host $reader.ReadToEnd()
        }
        throw
    }
}
$scheduler = "https://cloudscheduler.googleapis.com/v1/$parent/jobs"
$monitor = "https://monitoring.googleapis.com/v3/projects/$project"
$existing = @( (Api GET $scheduler).jobs )
foreach ($variant in @('standard','direct','discovery')) {
    $name = "$parent/jobs/radlnavi-route-check-$variant"
    $old = @($existing|Where-Object name -eq $name)
    if ($old.Count -gt 0 -and $old[0].state -ne 'ENABLED') { throw "Job is not enabled: $name" }
    $job = @{
        name=$name; description='Daytime routing availability / best-effort warmup; no minimum instances'
        schedule=$schedule; timeZone='Europe/Berlin'; attemptDeadline='60s'
        retryConfig=@{retryCount=0; maxRetryDuration='0s'}
        httpTarget=@{uri=$targets[$variant]+$path; httpMethod='GET'; headers=@{'User-Agent'='RadlNavi-Route-Check/1.0'}}
    }
    if ($old.Count -gt 0) {
        $null=Api PATCH "https://cloudscheduler.googleapis.com/v1/${name}?updateMask=description,schedule,timeZone,attemptDeadline,retryConfig,httpTarget" $job
    } else { $null=Api POST $scheduler $job }
    $v=Api GET "https://cloudscheduler.googleapis.com/v1/$name"
    if ($v.schedule -ne $schedule -or $v.timeZone -ne 'Europe/Berlin' -or [uri]::UnescapeDataString($v.httpTarget.uri) -ne $job.httpTarget.uri -or $v.state -ne 'ENABLED') { throw "Job verification failed: $name" }
    # Verify real route content before retiring working checks.
    $response=Invoke-RestMethod -Uri $job.httpTarget.uri -TimeoutSec 65
    if ($response.code -ne 'Ok' -or $response.routes.Count -lt 1) { throw "Invalid route: $variant" }
    $null=Api POST "https://cloudscheduler.googleapis.com/v1/${name}:run" @{}
    Write-Output "Verified route and scheduled job: $variant"
}
$policies=@((Api GET "$monitor/alertPolicies").alertPolicies)
$title='RadNavi - Zeitgesteuerte Routenpruefung fehlgeschlagen'
$latency=@($policies|Where-Object name -eq "projects/$project/alertPolicies/2737926620328278465")[0]
$policy=@{
    displayName=$title; combiner='OR'; enabled=$true
    notificationChannels=$latency.notificationChannels
    conditions=@(@{displayName='Scheduler route check error';conditionMatchedLog=@{
        filter='resource.type="cloud_scheduler_job" AND resource.labels.job_id=~"^radlnavi-route-check-(standard|direct|discovery)$" AND severity>=ERROR'
        labelExtractors=@{variant='EXTRACT(resource.labels.job_id)'}
    }})
    alertStrategy=@{notificationRateLimit=@{period='900s'};autoClose='1800s'}
    documentation=@{mimeType='text/markdown';content='Eine Routenpruefung ist fehlgeschlagen. Cloud Scheduler Ausfuehrungslogs pruefen. Pruefungen alle 5 Minuten, 05:00 bis 00:00 Europe/Berlin. Nachts keine aktiven Pruefungen. HTTP-Erfolg wird geprueft; fachliche Routeninhalte nur beim Einrichten.'}
}
$match=@($policies|Where-Object displayName -eq $title)
if ($match.Count -gt 1) { throw 'Duplicate route check alerts' }
if ($match.Count -eq 1) {
    $policy.name=$match[0].name
    $result=Api PATCH "https://monitoring.googleapis.com/v3/$($policy.name)" $policy
} else { $result=Api POST "$monitor/alertPolicies" $policy }
$verified=Api GET "https://monitoring.googleapis.com/v3/$($result.name)"
if ($verified.validity -or -not $verified.enabled) { throw 'Invalid replacement alert' }
# Uptime checks cannot be deleted while an alert policy references them,
# even if that policy is disabled. Retire only these two legacy policies.
foreach ($id in @('6249641800971351133','6249641800971353232')) {
    $name="projects/$project/alertPolicies/$id"
    if (@($policies|Where-Object name -eq $name).Count -gt 0) {
        $null=Api DELETE "https://monitoring.googleapis.com/v3/$name"
    }
}
$checks=@((Api GET "$monitor/uptimeCheckConfigs").uptimeCheckConfigs)
foreach ($check in $checks) {
    if ($check.name.Split('/')[-1] -in @('radlnavi-api-health-qorOHVXh5to','radlnavi-routing-smoke-test-KCxP5Tzmb6E')) {
        $null=Api DELETE "https://monitoring.googleapis.com/v3/$($check.name)"
    }
}
Write-Output 'Replacement alert verified; legacy uptime checks and their alerts removed.'
