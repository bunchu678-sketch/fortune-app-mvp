"""Print a Windows Task Scheduler XML draft. Never registers or runs a task.

The draft runs a FRESH disposable synthetic demo each invocation. It is not a
production backup job. A deployment adapter, identity, ACLs and real schedule
must be reviewed separately before any registration.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from research.home_backup_storage import BackupSchedule


def draft(python,node,start,*,schedule):
    schedule=BackupSchedule.coerce(schedule)
    if len(schedule.times)!=4 or schedule.pull_delay.total_seconds()%60:
        raise ValueError('Four explicit generation times and whole-minute pull delay required')
    moment=datetime.fromisoformat(start)
    if moment.utcoffset()!=timedelta(hours=9):
        raise ValueError('Explicit JST start (+09:00) required; no deployment default')
    for value in (python,node):
        if not Path(value).is_absolute() or any(c in value for c in '\r\n"'):
            raise ValueError('Absolute existing runtime path required')
    ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
    ET.register_namespace('',ns)
    def add(parent,name,value=None,**attributes):
        child=ET.SubElement(parent,'{'+ns+'}'+name,attributes)
        if value is not None: child.text=value
        return child
    root=ET.Element('{'+ns+'}Task',version='1.4')
    registration=add(root,'RegistrationInfo')
    add(registration,'Description','DRAFT ONLY: fresh synthetic demo, no production backup or task registration')
    triggers=add(root,'Triggers')
    for generation_time in schedule.times:
        boundary=datetime.combine(moment.date(),generation_time,moment.tzinfo)+schedule.pull_delay
        if boundary<moment: boundary+=timedelta(days=1)
        daily=add(triggers,'CalendarTrigger'); add(daily,'StartBoundary',boundary.isoformat())
        add(daily,'Enabled','true'); add(add(daily,'ScheduleByDay'),'DaysInterval','1')
    boot=add(triggers,'BootTrigger'); add(boot,'Enabled','true'); add(boot,'Delay','PT2M')
    principals=add(root,'Principals'); principal=add(principals,'Principal',id='SyntheticOnly')
    add(principal,'UserId','DRAFT-IDENTITY-REQUIRES-REVIEW')
    add(principal,'LogonType','S4U'); add(principal,'RunLevel','LeastPrivilege')
    settings=add(root,'Settings')
    for name,value in [('MultipleInstancesPolicy','IgnoreNew'),('DisallowStartIfOnBatteries','false'),
                       ('StopIfGoingOnBatteries','false'),('StartWhenAvailable','true'),
                       ('RunOnlyIfNetworkAvailable','false'),('Enabled','true'),
                       ('WakeToRun','true'),('ExecutionTimeLimit','PT30M')]: add(settings,name,value)
    restart=add(settings,'RestartOnFailure'); add(restart,'Interval','PT10M'); add(restart,'Count','3')
    actions=add(root,'Actions',Context='SyntheticOnly'); action=add(actions,'Exec')
    add(action,'Command',python)
    demo=Path(__file__).with_name('home_backup_demo.py')
    times=','.join(value.isoformat(timespec='minutes') for value in schedule.times)
    delay=int(schedule.pull_delay.total_seconds()/60)
    add(action,'Arguments',f'-B "{demo}" --node "{node}" --generation-times-jst "{times}" --pull-delay-minutes {delay}')
    add(action,'WorkingDirectory',str(demo.parents[1]))
    return ET.tostring(root,encoding='unicode',xml_declaration=True)


def configured_draft(python,node,start,*,schedule,config,approval,user_id,logon_type='InteractiveToken'):
    """Real adapter action, disabled pending separate registration approval."""
    for path in (config,approval):
        if not Path(path).is_absolute() or any(c in str(path) for c in '\r\n"'):
            raise ValueError('Explicit private configuration and approval paths required')
    if not user_id or logon_type not in ('InteractiveToken','Password'):
        raise ValueError('Explicit Windows identity and reviewed logon mode required')
    ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    root=ET.fromstring(draft(python,node,start,schedule=schedule))
    root.find('t:RegistrationInfo/t:Description',ns).text='DISABLED DRAFT: explicit-grant backup adapter; registration not performed'
    root.find('t:Settings/t:Enabled',ns).text='false'
    root.find('t:Principals/t:Principal/t:UserId',ns).text=user_id
    root.find('t:Principals/t:Principal/t:LogonType',ns).text=logon_type
    entry=Path(__file__).resolve().parents[1]/'adapters'/'backup_client.py'
    root.find('t:Actions/t:Exec/t:Arguments',ns).text=f'-B "{entry}" --config "{config}" --approval "{approval}" --catch-up'
    if logon_type=='InteractiveToken':
        trigger=ET.SubElement(root.find('t:Triggers',ns),'{'+ns['t']+'}LogonTrigger')
        ET.SubElement(trigger,'{'+ns['t']+'}Enabled').text='true'
        ET.SubElement(trigger,'{'+ns['t']+'}UserId').text=user_id
    return ET.tostring(root,encoding='unicode',xml_declaration=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',required=True); parser.add_argument('--node',required=True)
    parser.add_argument('--start-jst',required=True)
    parser.add_argument('--generation-times-jst',required=True)
    parser.add_argument('--pull-delay-minutes',required=True,type=int)
    args=parser.parse_args()
    print(draft(args.python,args.node,args.start_jst,
                schedule=BackupSchedule.parse(args.generation_times_jst,args.pull_delay_minutes)))
