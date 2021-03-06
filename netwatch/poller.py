from netwatch import models

from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, \
    NetMikoAuthenticationException
from datetime import datetime
import re
import time
from threading import Thread, enumerate


def ping(ip_address):
    import os, platform
    ping_str = "-n 1" if platform.system().lower() == "windows" else "-c 1"

    # Returns True if host responds to a ping request
    # Adding  '+ " -w 1"' to the ping command changes the timeout to
    # 1 second on Windows, so improves results time, but may not be
    # cross platform:
    return os.system("ping " + ping_str + " " + ip_address + " -w 1") == 0


def ssh_save_config_file(node, remediated=False):
    # DEPRECATED
    device_profile = build_device_profile(node)
    run_time = datetime.now().strftime('%Y%m%d-%H%M')

    try:
        net_connect = ConnectHandler(**device_profile)
        net_connect.enable()
        cfg_req_output = net_connect.send_command(node.connection_profile.config_command)
        net_connect.disconnect()
        if remediated:
            backup_file =\
                './configs/' + device_profile['ip'] + "-" + run_time + '-RMD' + '.cfg'
        else:
            backup_file =\
                './configs/' + device_profile['ip'] + "-" + run_time + '.cfg'

        logme('Saving config to "{}" ...'.format(backup_file))
        backup = open(backup_file, 'a')
        backup.write(cfg_req_output + "\n")
        backup.close()

        return cfg_req_output

    except NetMikoAuthenticationException as e:
        z = str(e)
        logme(z)
        return("Authentication failed.")
    except NetMikoTimeoutException as e:
        z = str(e)
        logme(z)
        logme("Device is unreachable.")
        return("Device is unreachable.")
    except Exception as e:
        z = str(e)
        logme("\nOops! A general error occurred, here's the message:")
        logme(z)


def ssh_return_config(node):
    device_profile = build_device_profile(node)

    try:
        logme('Connecting to device {0.node_name}'.format(node))
        net_connect = ConnectHandler(**device_profile)
        net_connect.enable()
        cfg_req_output = net_connect.send_command(node.connection_profile.config_command)
        net_connect.disconnect()

        logme('Got config for node: "{}"!'.format(node.node_name))

        return cfg_req_output

    except NetMikoAuthenticationException as e:
        z = str(e)
        logme(z)
        return("Authentication failed.")
    except NetMikoTimeoutException as e:
        z = str(e)
        logme(z)
        logme("Device is unreachable.")
        return("Device is unreachable.")
    except Exception as e:
        z = str(e)
        logme("\nOops! A general error occurred, here's the message:")
        logme(z)


def ssh_remediate_config(node, raw_remediation_config):
    device_profile = build_device_profile(node)

    try:
        net_connect = ConnectHandler(**device_profile)
        net_connect.enable()

        remediation_config = raw_remediation_config.split("\n")
        logme(net_connect.send_config_set(remediation_config))

        net_connect.exit_config_mode()
        # logme(net_connect.send_command("copy run start"))
        logme(net_connect.send_command("\n"))

        net_connect.disconnect()

    except NetMikoAuthenticationException as e:
        z = str(e)
        logme(z)
    except NetMikoTimeoutException as e:
        z = str(e)
        logme(z)
        logme("Device is unreachable.")
    except Exception as e:
        z = str(e)
        logme("\nOops! A general error occurred, here's the message:")
        logme(z)


def check_config_compliance(node, rule):
    compliant = False
    backup_again = False
    node_config = node.get_latest_config()
    noderule = models.get_noderule(node, rule)

    # NEED TO CHECK rule.regex Boolean and
    # rule.found_in_config Boolean
    # to see if it should be escaped and/or NOT found...

    # To RegEx escape Rule.config. use..
    #                  re.escape(rule.config)
    # or if not just rule.config

    if not rule.found_in_config:
        match = re.search(re.escape(rule.config),
                          node_config.config)  # Gets latest config!

        if match is None:
            logme("{0.rule_name} - Not Compliant!".format(rule))
            noderule.set_noderule_status(compliant)
            # Checks if NR is enabled for auto remediate and executes:
            if noderule.auto_remediate:
                ssh_remediate_config(node, rule.remediation_config)
                backup_again = True
                compliant = True
        else:
            logme("{0.rule_name} - Compliant!".format(rule))
            backup_again = False
            compliant = True
    else:
        match = re.search(re.escape(rule.config),
                          node_config.config)

        if match is None:
            logme("{0.rule_name} - Compliant!".format(rule))
            backup_again = False
            compliant = True
        else:
            logme("{0.rule_name} - Not Compliant!".format(rule))
            noderule.set_noderule_status(compliant)
            # Checks if NR is enabled for auto remediate and executes:
            if noderule.auto_remediate:
                ssh_remediate_config(node, rule.remediation_config)
                backup_again = True
                compliant = True

    noderule.set_noderule_status(compliant)

    return {"backup_again": backup_again}


def logme(output):
    run_time = datetime.now().strftime('%Y%m%d-%H%M')
    log_file = './logs/POLLING-' + run_time + '.log'

    logger = open(log_file, 'a')
    logger.write(output + "\n")
    print(output)


def build_device_profile(node):
    device_profile = {'ip': node.ip_address,
                      'device_type': node.connection_profile.device_os,
                      'username': node.connection_profile.ssh_username,
                      'password': models.decrypt_creds(node.connection_profile.ssh_password),
                      'secret': models.decrypt_creds(node.connection_profile.ssh_enable),
                      'port': node.connection_profile.port_num}
    return device_profile


def poller_run(node):
    print("Started poller for {0.node_name}...".format(node))
    # run_time = datetime.now().strftime('%Y%m%d-%H%M')
    # log_file = './logs/POLLING-' + run_time + '.log'
    models.set_last_poll(datetime.now().strftime('%H:%M:%S'))

    if ping(node.ip_address):
        node.set_node_status(True)  # Also sets last_seen to now()

        if node.is_next_poll_now():  # True if next poll is before now(), this prevents rechecking a recently checked node
            node.set_next_poll_relative(15)  # Set next_poll to now()+15mins to allow for the rest to complete before running again
            logme("\n:::::::::::::" + node.ip_address + ":::::::::::::")
            backup_config = ssh_return_config(node)
            if (backup_config == "Device is unreachable.") or\
                    (backup_config == "Authentication failed."):
                # Stop current node and wait for poll setting timeout
                # Need to set node status to ERROR here, so can display on dash
                return
            node.create_config(backup_config + "\n")
            backup_again = False

            for rule in node.list_rules_for_node():
                check_compliance = check_config_compliance(node,
                                                           rule)
                # Only backs up config again once,
                # rather than after each rule is remediated:
                if check_compliance['backup_again']:
                    backup_again = True

            if backup_again:
                new_config = ssh_return_config(node)
                node.create_config(new_config + "\n")

            # Set next_poll to now()+24hrs...
            node.set_next_poll_relative(1440)
            # This also sets last_seen to now()...
            node.set_node_status(True)

    else:
        node.set_node_status(False)
        if node.is_next_poll_now(): #True if next poll is before now(), this prevents setting a recently checked node to a sooner poll time
            node.set_next_poll_relative(0) #Set next_poll to now()+0mins, will not be checked until upto 5mins anyway as the Celery task should run 5mins, if set to now()+5mins the next Celery job may be before it


def poller_service():
    models.set_setting("poller_status", "STARTED")
    print("Poller service started...")
    while True:
        while models.get_settings('pause_poller') == "True":
            models.set_setting("poller_status", "PAUSED")
            time.sleep(5)
        models.set_setting("poller_status", "RUNNING")
        for node in models.list_all_nodes():
            # Stop processing additional nodes if paused:
            if models.get_settings('pause_poller') == "True":
                models.set_setting("poller_status", "PAUSING")
                break
            print("Starting poller for {0.node_name}...".format(node))
            thread = Thread(target=poller_run,
                            args=(node,),
                            name='Poller-' + node.node_name)
            thread.start()
            # FOR DEBUG
            # Stops all threads running in parallel so prints can be seen:
            time.sleep(3)
        if models.get_settings('pause_poller') == "True":
                models.set_setting("poller_status", "PAUSED")
        else:
            models.set_setting("poller_status", "STARTED")

        # Sleep the poller until number of mins in settings, checking if paused
        # every second
        poll_interval = models.get_settings('poll_interval_mins')
        for check in range(1, (int(poll_interval) * 60)):
            time.sleep(1)
            if models.get_settings('pause_poller') == "True":
                break


def poller_init():
    print("Initialising Poller...")
    thread = Thread(target=poller_service,
                    name='Poller_Service_Thread',
                    daemon=True)
    thread.start()


def get_active_pollers():
    threads = enumerate()
    poller_threads = 0

    for thread in threads:
        if "Thread" not in thread.name:
            poller_threads += 1
    return poller_threads


if __name__ == '__main__':
    print("Poller is no longer stand-alone!")
