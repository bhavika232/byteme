import boto3
import time

REGION = "us-east-2"
ec2    = boto3.client('ec2', region_name=REGION)

DOWNSIZE_MAP = {
    "t3.large":  "t3.medium",  "t3.medium": "t3.small",
    "t3.small":  "t3.micro",   "t3.micro":  "t3.micro",
    "t2.large":  "t2.medium",  "t2.medium": "t2.small",
    "t2.small":  "t2.micro",   "t2.micro":  "t2.micro",
    "m5.xlarge": "m5.large",   "m5.large":  "t3.large",
    "m4.xlarge": "m4.large",   "m4.large":  "t3.large",
    "c5.xlarge": "c5.large",   "c5.large":  "t3.large",
}

def get_all_instances():
    """Returns all EC2 instances in the region — works with any number."""
    try:
        response  = ec2.describe_instances()
        instances = []
        for res in response['Reservations']:
            for inst in res['Instances']:
                instances.append({
                    'instance_id':   inst['InstanceId'],
                    'state':         inst['State']['Name'],
                    'instance_type': inst['InstanceType'],
                })
        print(f"[ec2_actions] Found {len(instances)} instance(s)")
        return instances
    except Exception as e:
        print(f"get_all_instances error: {e}")
        return []

def get_ec2_status(instance_id=None):
    try:
        kwargs   = {'InstanceIds': [instance_id]} if instance_id else {}
        response = ec2.describe_instances(**kwargs)
        inst     = response['Reservations'][0]['Instances'][0]
        return {
            'instance_id':   inst['InstanceId'],
            'state':         inst['State']['Name'],
            'instance_type': inst['InstanceType'],
        }
    except Exception as e:
        print(f"get_ec2_status error: {e}")
        return {'state': 'unknown', 'instance_type': 'unknown'}

def stop_ec2(instance_id):
    response = ec2.stop_instances(InstanceIds=[instance_id])
    state    = response['StoppingInstances'][0]['CurrentState']['Name']
    print(f"Stopping {instance_id}: {state}")
    return state

def start_ec2(instance_id):
    response = ec2.start_instances(InstanceIds=[instance_id])
    state    = response['StartingInstances'][0]['CurrentState']['Name']
    print(f"Starting {instance_id}: {state}")
    return state

def wait_for_state(instance_id, target_state, timeout=120):
    print(f"Waiting for {instance_id} → '{target_state}'...")
    elapsed = 0
    while elapsed < timeout:
        if get_ec2_status(instance_id)['state'] == target_state:
            print(f"{instance_id} reached '{target_state}'")
            return True
        time.sleep(5)
        elapsed += 5
    print(f"Timeout waiting for '{target_state}'")
    return False

def downsize_instance(instance_id=None):
    """
    Downsize a specific instance, or auto-pick the best idle candidate.
    Fully dynamic — works with any number of instances in the account.
    """
    try:
        # Auto-select instance if none given
        if not instance_id:
            instances = get_all_instances()
            running   = [i for i in instances if i['state'] == 'running']
            stopped   = [i for i in instances if i['state'] == 'stopped']
            if running:
                instance_id = running[0]['instance_id']
            elif stopped:
                instance_id = stopped[0]['instance_id']
            else:
                return {'success': False, 'message': 'No instances found to optimize.'}

        current       = get_ec2_status(instance_id)
        current_type  = current['instance_type']
        current_state = current['state']
        target_type   = DOWNSIZE_MAP.get(current_type)

        if not target_type or target_type == current_type:
            return {
                'success':     False,
                'message':     f"{instance_id} is already at minimum type ({current_type}).",
                'old_type':    current_type,
                'new_type':    current_type,
                'instance_id': instance_id,
            }

        print(f"Downsizing {instance_id}: {current_type} → {target_type}")

        if current_state == 'running':
            stop_ec2(instance_id)
            if not wait_for_state(instance_id, 'stopped'):
                return {'success': False, 'message': f'Timed out stopping {instance_id}.'}

        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={'Value': target_type}
        )
        print(f"{instance_id} type changed to {target_type}")

        if current_state == 'running':
            start_ec2(instance_id)
            wait_for_state(instance_id, 'running')

        return {
            'success':     True,
            'message':     f"Downsized {instance_id}: {current_type} → {target_type}.",
            'old_type':    current_type,
            'new_type':    target_type,
            'instance_id': instance_id,
        }

    except Exception as e:
        print(f"downsize_instance error: {e}")
        return {'success': False, 'message': str(e)}

if __name__ == '__main__':
    print(get_all_instances())
