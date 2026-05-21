$ErrorActionPreference = "Stop"

$OllamaHost = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { "http://localhost:11434" }
$Model = if ($env:DEEPSEEK_MODEL) { $env:DEEPSEEK_MODEL } else { "deepseek-coder:6.7b" }

Write-Host "Checking Ollama at $OllamaHost..."
Invoke-RestMethod -Method Get -Uri "$OllamaHost/api/tags" | Out-Null

Write-Host "Pulling $Model. This can take a while."
Invoke-RestMethod `
  -Method Post `
  -Uri "$OllamaHost/api/pull" `
  -ContentType "application/json" `
  -Body (@{ name = $Model; stream = $false } | ConvertTo-Json)

Write-Host "Ollama model ready: $Model"
