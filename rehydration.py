import json
import boto3
import time
from collections import Counter

asg = "xxxxxxxxx"
Arn = "arn:aws:sns:us-east-1:xxxxxxxx:xxxxxxxx"
queue_url = "https://sqs.us-east-1.amazonaws.com/xxxxxxxxx/lambda_queue.fifo"
ec2 = boto3.resource('ec2')

def lambda_handler(event,context):
    asg_client = boto3.client('autoscaling')
    sns_client = boto3.client('sns')
    sqs_client = boto3.client('sqs')

    sns_response = sns_client.publish (
        TargetArn=Arn,
        Subject='Rehydration of test instance',
        Message='Rehydration of servers started for test Instances!'
    )
    return(sns_response)

    asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])
    initial_ids = []
    for i in asg_response['AutoScalingGroups']:
        for k in i['Instances']:
            initial_ids.append(k['InstanceId'])
    for i in asg_response['AutoScalingGroups']:
        orig_maxsize = i['MaxSize']
        orig_desired = i['DesiredCapacity']
    print('original details about autoscaling original DesiredCount is', orig_desired,'original MaxSize is', orig_maxsize)

    new_desired = orig_desired*2
    new_maxsize = orig_maxsize*2

    double_size = asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg,
        MaxSize=new_maxsize,
        DesiredCapacity=new_desired,
    )

    print(double_size)
    print('update of autoscaling started New DesiredCount is',new_desired,'New MaxSize is',new_maxsize)

    def count_inservice():
        life_cycle = []
        asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])
        for i in asg_response['AutoScalingGroups']:
            for k in i['Instances']:
                life_cycle.append(k['LifecycleState'])
        ct= Counter(life_cycle)
        n = ct['InService']
        return(n)

    count = count_inservice()
    while count < new_desired:
        count = count_inservice()
        print(asg, 'nodes InService equals', count, 'waiting for it to reach', new_desired)
        time.sleep(100)

    print('Instances currently in service: ', count_inservice())
    print('reverting asg size, maxsize to', orig_maxsize, 'desired', orig_desired)

    Half_size = asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg,
        MaxSize=orig_maxsize,
        DesiredCapacity=orig_desired,
    )
    print('Rehydration of servers are done')

    #sends notification with newely created Ip-address
    paginator = asg_client.get_paginator('describe_auto_scaling_groups')
    groups = paginator.paginate(PaginationConfig={'PageSize': 100})
    ips = []
    filtered_asgs = groups.search('AutoScalingGroups[] | [?contains(Tags[?Key==`Name`].Value, `nameofthetag`)]'.format('Application', 'CCP'))
    for asgroup in filtered_asgs:
        instance_ids = [i for i in asgroup['Instances']]
        running_instances = ec2.instances.filter(Filters=[ {'Name':'tag:Name','Values':['testing']} ])
        for instance in running_instances:
            print(instance.public_dns_name)
            ips.append(instance.public_dns_name)
    message = {"Newely updated Ip addresses are": ips}
    print(message)
    sns_response = sns_client.publish (
        TargetArn=Arn,
        Subject='Ip address of Rehydrated Instances',
        Message=json.dumps({'default': json.dumps(message)}),
        MessageStructure='json'
    )
    return(sns_response)

    response = sqs_client.send_message(
        QueueUrl = queue_url,
        MessageBody = 'Rehydration of servers are done!',
        MessageGroupId = 'sqs-queue-testing',
        MessageDeduplicationId = 'xxxxxxx'
    )
    print('sent message to sqs service, MessageId:', response['MessageId'])