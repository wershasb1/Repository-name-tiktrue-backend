# Move test_*.py files to tests/unit
Get-ChildItem -Path . -Filter "test_*.py" | ForEach-Object {
    Move-Item -Path $_.FullName -Destination "tests/unit/" -Force
    Write-Host "Moved $($_.Name) to tests/unit/"
}

# Move demo_*.py files to tests/demo
Get-ChildItem -Path . -Filter "demo_*.py" | ForEach-Object {
    Move-Item -Path $_.FullName -Destination "tests/demo/" -Force
    Write-Host "Moved $($_.Name) to tests/demo/"
}

# Move integration_test_suite.py to tests/integration
if (Test-Path "integration_test_suite.py") {
    Move-Item -Path "integration_test_suite.py" -Destination "tests/integration/" -Force
    Write-Host "Moved integration_test_suite.py to tests/integration/"
}