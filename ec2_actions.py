import boto3

EC2_INSTANCE_ID = "i-0c46dfa3a28a086d0"  # replace with your actual instance ID
REGION = "us-east-2"

ec2 = boto3.client('ec2', region_name=REGION)

def stop_ec2():
    response = ec2.stop_instances(InstanceIds=[EC2_INSTANCE_ID])
    state = response['StoppingInstances'][0]['CurrentState']['Name']
    print(f"EC2 instance {EC2_INSTANCE_ID} is now: {state}")
    return state

def start_ec2():
    response = ec2.start_instances(InstanceIds=[EC2_INSTANCE_ID])
    state = response['StoppingInstances'][0]['CurrentState']['Name']
    print(f"EC2 instance {EC2_INSTANCE_ID} is now: {state}")
    return state

def get_ec2_status():
    response = ec2.describe_instances(InstanceIds=[EC2_INSTANCE_ID])
    state = response['Reservations'][0]['Instances'][0]['State']['Name']
    print(f"EC2 status: {state}")
    return state

if __name__ == "__main__":
    get_ec2_status()