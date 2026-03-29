import boto3
import time

EC2_INSTANCE_ID = "i-0c46dfa3a28a086d0"
REGION          = "us-east-2"

ec2 = boto3.client('ec2', region_name=REGION)

# Downsize map — what each instance type downsizes to
DOWNSIZE_MAP = {
    "t3.large":   "t3.medium",
    "t3.medium":  "t3.small",
    "t3.small":   "t3.micro",
    "t3.micro":   "t3.micro",   # already smallest
    "m5.xlarge":  "m5.large",
    "m5.large":   "m5.medium",  # Note: m5.medium doesn't exist, maps to t3.large
    "m4.xlarge":  "m4.large",
    "m4.large":   "t3.large",
    "c5.xlarge":  "c5.large",
    "c5.large":   "t3.large",
}

def get_ec2_status():
    try:
        response = ec2.describe_instances(InstanceIds=[EC2_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        state    = instance['State']['Name']
        itype    = instance['InstanceType']
        print(f"EC2 status: {state}, type: {itype}")
        return {"state": state, "instance_type": itype}
    except Exception as e:
        print(f"get_ec2_status error: {e}")
        return {"state": "unknown", "instance_type": "unknown"}

def stop_ec2():
    try:
        response = ec2.stop_instances(InstanceIds=[EC2_INSTANCE_ID])
        state    = response['StoppingInstances'][0]['CurrentState']['Name']
        print(f"EC2 instance {EC2_INSTANCE_ID} stopping: {state}")
        return state
    except Exception as e:
        print(f"stop_ec2 error: {e}")
        raise

def start_ec2():
    try:
        response = ec2.start_instances(InstanceIds=[EC2_INSTANCE_ID])
        state    = response['StartingInstances'][0]['CurrentState']['Name']
        print(f"EC2 instance {EC2_INSTANCE_ID} starting: {state}")
        return state
    except Exception as e:
        print(f"start_ec2 error: {e}")
        raise

def wait_for_state(target_state, timeout=120):
    """Poll EC2 until instance reaches target_state or timeout."""
    print(f"Waiting for instance to reach '{target_state}'...")
    elapsed = 0
    while elapsed < timeout:
        status = get_ec2_status()
        if status["state"] == target_state:
            print(f"Instance is now '{target_state}'")
            return True
        time.sleep(5)
        elapsed += 5
    print(f"Timeout waiting for '{target_state}'")
    return False

def downsize_instance():
    """
    Stop instance → change to smaller type → restart.
    Returns a dict with old_type, new_type, status.
    """
    try:
        # 1. Get current type and state
        current = get_ec2_status()
        current_type  = current["instance_type"]
        current_state = current["state"]

        target_type = DOWNSIZE_MAP.get(current_type)
        if not target_type or target_type == current_type:
            return {
                "success": False,
                "message": f"Instance is already at minimum type ({current_type}). No downsize possible.",
                "old_type": current_type,
                "new_type": current_type
            }

        print(f"Downsizing {EC2_INSTANCE_ID}: {current_type} → {target_type}")

        # 2. Stop instance if running
        if current_state == "running":
            stop_ec2()
            stopped = wait_for_state("stopped", timeout=120)
            if not stopped:
                return {"success": False, "message": "Timed out waiting for instance to stop."}

        # 3. Modify instance type
        ec2.modify_instance_attribute(
            InstanceId=EC2_INSTANCE_ID,
            InstanceType={"Value": target_type}
        )
        print(f"Instance type changed to {target_type}")

        # 4. Restart if it was running before
        if current_state == "running":
            start_ec2()
            wait_for_state("running", timeout=120)

        return {
            "success":   True,
            "message":   f"Successfully downsized from {current_type} to {target_type}.",
            "old_type":  current_type,
            "new_type":  target_type,
            "instance_id": EC2_INSTANCE_ID
        }

    except Exception as e:
        print(f"downsize_instance error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    print(get_ec2_status())