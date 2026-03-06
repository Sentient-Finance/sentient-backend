$ErrorActionPreference = "Stop"

$body = @{
action = "swap"
reason = "manual swap test 2"
metadata = @{ source = "api" }
swap = @{
tokenIn = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
tokenOut = "0x4200000000000000000000000000000000000006"
amountIn = "50000"
amountOutMinimum = "1"
currentPrice = "0"
router = "0x2626664c2603336E57B271c5C0b26F421741e481"
fee = 500
}
} | ConvertTo-Json -Depth 8

$uri = "http://localhost:8000/api/v1/vaults/0x130372e8c9d1a9cedcbc489b77922b1c9e8e6b8d/action/execute"
$res = Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body $body
$executionId = $res.execution_id
Write-Host "Created execution_id=$executionId status=$($res.status)"

$statusUri = "http://localhost:8000/api/v1/executions/$executionId"
for ($i=1; $i -le 15; $i++) {
Start-Sleep -Seconds 1
$st = Invoke-RestMethod -Method Get -Uri $statusUri
Write-Host "[$i] status=$($st.status) tx_hash=$($st.tx_hash)"
if ($st.status -in @("confirmed","failed","dead_letter")) { break }
}

Invoke-RestMethod -Method Get -Uri $statusUri | ConvertTo-Json -Depth 10
