#########################################################################################################################
#     _______________        __              _   ___________                       __                        ________ 
#    / ____/ ____/__ \      / /_____        / | / / ____/__ \      ________  _____/ /_____  ________        /  _/ __ \
#   / __/ / /    __/ /_____/ __/ __ \______/  |/ / /    __/ /_____/ ___/ _ \/ ___/ __/ __ \/ ___/ _ \______ / // /_/ /
#  / /___/ /___ / __/_____/ /_/ /_/ /_____/ /|  / /___ / __/_____/ /  /  __(__  ) /_/ /_/ / /  /  __/_____// // ____/ 
# /_____/\____//____/     \__/\____/     /_/ |_/\____//____/    /_/   \___/____/\__/\____/_/   \___/     /___/_/                                                                                                                          
#########################################################################################################################


import boto3
import os
import time
import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Prism Central credentials from environment variables
prism_central_url = "https://10.101.3.89:9440/api/nutanix/v3"
username = os.getenv("PRISM_CENTRAL_USERNAME")
password = os.getenv("PRISM_CENTRAL_PASSWORD")

# Subnet name to search for
subnet_name = "TKY-VPC-A_Subnet1"

# Initialize DynamoDB client using AWS credentials
botoClient = boto3.setup_default_session(region_name='ap-northeast-1')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ec2-to-nc2-ip-preservation')  # Replace with your table name

# Function to retrieve VMs from Prism Central based on VM name
def get_vm_by_name(vm_name):
    url = f"{prism_central_url}/vms/list"
    headers = {"Content-Type": "application/json"}
    payload = {
        "kind": "vm",
        "sort_attribute": "name",
        "sort_order": "ASCENDING"
    }

    response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
   
    if response.status_code == 200:
        vms = response.json().get("entities", [])
        if len(vms) > 0:
            for entry in vms:
                if entry["status"]["name"] == vm_name:
                    print("Found VM: %s" % vm_name)
                    return entry  # Assuming VM names are unique, return the first match
        else:
            print(f"No VM found with name: {vm_name}")
            return None
    else:
        print(f"Error fetching VMs: {response.text}")
        return None


def pause():
    programPause = input("Press the <ENTER> key to continue...")


# Function to retrieve subnet UUID by subnet name
def get_subnet_uuid_by_name(subnet_name):
    url = f"{prism_central_url}/subnets/list"
    headers = {"Content-Type": "application/json"}
    payload = {
        "kind": "subnet",
        "filter": f"name=={subnet_name}"
    }

    response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
   
    if response.status_code == 200:
        subnets = response.json().get("entities", [])
        if len(subnets) > 0:
            return subnets[0]["metadata"]["uuid"]
        else:
            print(f"No subnet found with name: {subnet_name}")
            return None
    else:
        print(f"Error fetching subnets: {response.text}")
        return None

# Function to delete all NICs from a VM
def remove_all_nics(vm_uuid):
    url = f"{prism_central_url}/vms/{vm_uuid}"
    headers = {"Content-Type": "application/json"}
   
    # Fetch current VM spec
    vm_response = requests.get(url, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
    if vm_response.status_code != 200:
        print(f"Error fetching VM details: {vm_response.text}")
        return False
   
    vm_spec = vm_response.json()
    # print("VM SPEC: %s" % vm_spec)
    vm_spec["spec"]["resources"]["nic_list"] = []  # Clear NIC list
    del vm_spec["status"] # Remove the status section or the PC API will get angry when we update the VM entry later
    # vm_spec = {
    #     "spec": {
    #         "resources": {
    #             "nic_list": []
    #         }
    #     }
    # }
   
    # Update VM to remove NICs
    update_response = requests.put(url, json=vm_spec, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
    if update_response.status_code == 202:
        print(f"All NICs removed from VM {vm_uuid}")
        return True
    else:
        print(f"Error removing NICs: {update_response.text}")
        return False

# Function to add a new NIC with a static IP to a VM
def add_nic_to_vm(vm_uuid, subnet_uuid, static_ip):
    url = f"{prism_central_url}/vms/{vm_uuid}?use_categories_mapping=true"
    headers = {"Content-Type": "application/json"}
   
    # Fetch current VM spec
    vm_response = requests.get(url, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
    if vm_response.status_code != 200:
        print(f"Error fetching VM details: {vm_response.text}")
        return False
   
    vm_spec = vm_response.json()
   
    # Add new NIC with static IP
    new_nic = {
        "subnet_reference": {
            "kind": "subnet",
            "uuid": subnet_uuid  # Subnet UUID for "VPC A - Subnet 1"
        },
        "ip_endpoint_list": [
            {
                "ip": static_ip
            }
        ]
    }

   

    vm_spec["spec"]["resources"]["nic_list"].append(new_nic)
    # vm_spec["spec"]["use_categories_mapping"] = True
    # vm_spec["spec"]["resources"].update["use_categories_mapping"] = True
    del vm_spec["status"] # Remove the status section or the PC API will get angry when we update the VM entry later

   
    # Update VM to add the new NIC
    update_response = requests.put(url, json=vm_spec, headers=headers, auth=HTTPBasicAuth(username, password), verify=False)
    if update_response.status_code == 202:
        print(f"New NIC with IP {static_ip} added to VM {vm_uuid}")
        return True
    else:
        print(f"Error adding NIC: {update_response.text}")
        return False

# Main function to orchestrate the process
def main():
    # Retrieve all items from the DynamoDB table
    response = table.scan()
    items = response.get("Items", [])
   
    if not items:
        print("No items found in DynamoDB.")
        return

    pause()

   
    # Retrieve subnet UUID dynamically
    subnet_uuid = get_subnet_uuid_by_name(subnet_name)
    if not subnet_uuid:
        print(f"Failed to retrieve subnet UUID for {subnet_name}. Exiting.")
        return

    # Iterate over each entry in the DynamoDB table
    for item in items:
        # print("Item is %s" % item)
        instance_name = item["InstanceName"]
        static_ip = item["PrivateIp"]
       
        # Fetch VM from Prism Central by instance name
        entry = get_vm_by_name(instance_name)
       
        if entry:
            vm_uuid = entry["metadata"]["uuid"]
           
            # Remove existing NICs
            if remove_all_nics(vm_uuid):
                # Add new NIC with static IP on the retrieved subnet
                time.sleep(10) 
                add_nic_to_vm(vm_uuid, subnet_uuid, static_ip)

            # add_nic_to_vm(vm_uuid, subnet_uuid, static_ip)

if __name__ == "__main__":
    main()
