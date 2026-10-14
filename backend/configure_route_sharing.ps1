param(
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$Region = 'europe-west3',
    [string]$Service = 'munichways-radlnavi-api',
    [string]$Bucket,
    [string]$ServiceAccount,
    [string]$PublicBaseUrl = 'https://radlnavi.munichways.de'
)
$ErrorActionPreference = 'Stop'
if (!$Bucket) { $Bucket = "$Project-shared-routes" }
if (!$ServiceAccount) { $ServiceAccount = "radlnavi-api@$Project.iam.gserviceaccount.com" }
function Invoke-Gcloud([string[]]$Arguments) {
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed: $($Arguments[0])" }
}
& gcloud storage buckets describe "gs://$Bucket" --project=$Project --format='value(name)' 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-Gcloud -Arguments @('storage','buckets','create',"gs://$Bucket","--project=$Project","--location=$Region",'--uniform-bucket-level-access','--public-access-prevention')
}
Invoke-Gcloud -Arguments @('storage','buckets','update',"gs://$Bucket","--project=$Project",'--public-access-prevention',"--lifecycle-file=$PSScriptRoot/shared-routes-lifecycle.json")
Invoke-Gcloud -Arguments @('storage','buckets','add-iam-policy-binding',"gs://$Bucket","--project=$Project","--member=serviceAccount:$ServiceAccount",'--role=roles/storage.objectUser')
Invoke-Gcloud -Arguments @('run','services','update',$Service,"--project=$Project","--region=$Region","--update-env-vars=SHARED_ROUTES_BUCKET=$Bucket,SHARE_PUBLIC_BASE_URL=$PublicBaseUrl")
