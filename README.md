# EC2 to NC2 migration with IP preservation
This is a PowerShell script and a Python script for use when migrating EC2 instances to Nutanix Cloud Clusters. The PowerShell script is executed via Amazon Systems Manager and saves the instance details in DynamoDB prior to migration. After migration the Python script is used take the data from DynamoDB and restore the original IP addreses. 
