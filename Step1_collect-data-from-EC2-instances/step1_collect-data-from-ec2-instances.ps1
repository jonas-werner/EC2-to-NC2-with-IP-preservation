######################################################################################################
#     _______________        __              _   ___________                   __        ________ 
#    / ____/ ____/__ \      / /_____        / | / / ____/__ \      ____ ____  / /_      /  _/ __ \
#   / __/ / /    __/ /_____/ __/ __ \______/  |/ / /    __/ /_____/ __ `/ _ \/ __/_____ / // /_/ /
#  / /___/ /___ / __/_____/ /_/ /_/ /_____/ /|  / /___ / __/_____/ /_/ /  __/ /_/_____// // ____/ 
# /_____/\____//____/     \__/\____/     /_/ |_/\____//____/     \__, /\___/\__/     /___/_/      
#                                                            /____/                            
######################################################################################################


# Check if AWS CLI is installed and install if not present
try {
    $awsVersion = & "aws.exe" --version
} catch {
    Write-Host "AWS CLI not present. Starting install"
}

if (-not ($awsVersion)) {
    # Define download URL and file paths
    $cliUrl = "https://awscli.amazonaws.com/AWSCLIV2.msi"
    $installerPath = "$env:TEMP\AWSCLIV2.msi"

    # Download the AWS CLI MSI installer
    Write-Host "Downloading AWS CLI installer..."
    Invoke-WebRequest -Uri $cliUrl -OutFile $installerPath

    # Install the AWS CLI silently
    Write-Host "Installing AWS CLI..."
    Start-Process msiexec.exe -ArgumentList "/i `"$installerPath`" /quiet /norestart" -Wait

    # Add AWS CLI installation path to the current PowerShell session's PATH
    $awsCliPath = "C:\Program Files\Amazon\AWSCLIV2"
    if (-not ($env:PATH -contains $awsCliPath)) {
        $env:PATH += ";$awsCliPath"
    }

    # Verify installation by calling AWS CLI
    Write-Host "Verifying AWS CLI installation..."
    $awsVersion = & "$awsCliPath\aws.exe" --version

    if ($awsVersion) {
        Write-Host "AWS CLI installed successfully: $awsVersion"
    } else {
        Write-Host "AWS CLI installation failed!"
    } 

    # Clean up installer file
    Remove-Item $installerPath -Force
}


# Collect instance metadata
$instanceId = Invoke-RestMethod -Uri http://169.254.169.254/latest/meta-data/instance-id
$privateIp = Invoke-RestMethod -Uri http://169.254.169.254/latest/meta-data/local-ipv4

$instanceNameUri = "http://169.254.169.254/latest/meta-data/tags/instance/Name"
try {
    $instanceName = Invoke-RestMethod -Uri $instanceNameUri
} catch {
    $instanceName = "NoNameTag"  # Fallback if instance tag is not available
}

# Define DynamoDB table name and AWS region
$dynamoTableName = "ec2-to-nc2-ip-preservation"
$awsRegion = "ap-northeast-1"


# Create a PowerShell hash table representing the JSON object for DynamoDB
$item = @{
    "InstanceId"   = @{ "S" = $instanceId }
    "InstanceName" = @{ "S" = $instanceName }
    "PrivateIp"    = @{ "S" = $privateIp }
}

# Convert the hash table to JSON
$jsonPayload = $item | ConvertTo-Json -Compress

# Output the JSON to a text file
$outputFile = "$env:TEMP\dynamodb_item.json"
$jsonPayload | Out-File -FilePath $outputFile -Encoding ascii

# Store the instance name and private IP as a key-value pair in DynamoDB using AWS CLI
aws dynamodb put-item --table-name $dynamoTableName --item file://$outputFile --region $awsRegion