# One-time prerequisites only. Does not create jobs or change minimum instances.
param(
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$Region = 'europe-west3',
    [string]$ApiService = 'munichways-radlnavi-discovery-api',
    [string]$RoutingService = 'munichways-radlnavi-discovery-routing'
)
$ErrorActionPreference = 'Stop'
function Invoke-Gcloud([string[]]$Arguments) {
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed: $($Arguments[0])" }
}
$accountId = 'radlnavi-discovery-scheduler'
$account = "$accountId@$Project.iam.gserviceaccount.com"
$buildAccount = "radlnavi-build@$Project.iam.gserviceaccount.com"
Invoke-Gcloud -Arguments @('services','enable','cloudscheduler.googleapis.com',"--project=$Project")
# List instead of interpreting a failing describe (403 must not mean missing).
$accounts = & gcloud iam service-accounts list "--project=$Project" "--filter=email:$account" '--format=value(email)'
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Scheduler service account' }
if ($account -notin @($accounts)) {
    Invoke-Gcloud -Arguments @('iam','service-accounts','create',$accountId,"--project=$Project",'--display-name=Discovery scheduled scaling')
}
# This identity can update only the two Discovery services, not Standard/Direct.
foreach ($service in @($ApiService, $RoutingService)) {
    Invoke-Gcloud -Arguments @('run','services','add-iam-policy-binding',$service,"--project=$Project","--region=$Region","--member=serviceAccount:$account",'--role=roles/run.developer')
}
foreach ($runtimeAccount in @('radlnavi-api', 'radlnavi-routing')) {
    Invoke-Gcloud -Arguments @('iam','service-accounts','add-iam-policy-binding',"$runtimeAccount@$Project.iam.gserviceaccount.com","--project=$Project","--member=serviceAccount:$account",'--role=roles/iam.serviceAccountUser')
}
Invoke-Gcloud -Arguments @('projects','add-iam-policy-binding',$Project,"--member=serviceAccount:$buildAccount",'--role=roles/cloudscheduler.admin','--condition=None')
Invoke-Gcloud -Arguments @('iam','service-accounts','add-iam-policy-binding',$account,"--project=$Project","--member=serviceAccount:$buildAccount",'--role=roles/iam.serviceAccountUser')
Write-Output 'Discovery Scheduler prerequisites ready. Next run Deploy discovery routing.'
