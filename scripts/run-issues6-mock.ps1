$body = @{
action = "swap"
reason = "manual swap test"
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
} | ConvertTo-Json -Depth 6

$res = Invoke-RestMethod -Method Post `
-Uri "http://localhost:8000/api/v1/vaults/0x130372e8c9d1a9cedcbc489b77922b1c9e8e6b8d/action/execute" `
-ContentType "application/json" `
-Body $body

$res
$executionId = $res.execution_id
