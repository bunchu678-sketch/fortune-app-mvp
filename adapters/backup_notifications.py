"""Existing mail transport adapter. Queued, provider accepted and delivered differ."""
from datetime import datetime,timezone
from adapters.backup_runtime import ExecutionGrant
from research.home_backup_storage import JobState,ProcessLock,canonical,digest,LabFailure
from mail_delivery import TextMail,DisabledMailTransport


class BackupNotifications:
    def __init__(self,workspace,transport=None):
        self.lab=workspace;self.transport=transport or DisabledMailTransport()
        self.role='vps-state' if workspace.config['role']=='vps' else 'pc-state'
        self.state=JobState(workspace,self.role)
        with self.state.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS alert_delivery (revision TEXT PRIMARY KEY, status TEXT NOT NULL, at TEXT NOT NULL)')

    def dispatch(self,*,recipient):
        ExecutionGrant(self.lab.config,self.lab.grant.approval,'notify')
        with ProcessLock(self.lab,self.role):
            return self._dispatch(recipient)

    def _dispatch(self,recipient):
        accepted=0
        for row in self.state.rows('SELECT * FROM outbox ORDER BY code'):
            revision=digest(canonical(row))
            if self.state.rows('SELECT revision FROM alert_delivery WHERE revision=?',(revision,)):continue
            # Fixed codes/counts only; no backup content, credential or raw error.
            message=TextMail(recipient,'Backup requires attention',
                             'Event: '+row['code']+'\nOccurrences: '+str(row['occurrences']))
            try:self.transport.send(message)
            except Exception:
                self.state.event(datetime.now(timezone.utc),'notification_failed')
                raise LabFailure('notification_not_accepted') from None
            with self.state.db() as db:
                db.execute("INSERT INTO alert_delivery VALUES (?,'provider_accepted',?)",(revision,datetime.now(timezone.utc).isoformat()))
            accepted+=1
        return {'provider_accepted':accepted,'delivered_confirmed':False}
