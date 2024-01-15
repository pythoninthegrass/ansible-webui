from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group

from crontab import CronTab

from aw.model.base import BareModel, BaseModel


class JobError(BareModel):
    field_list = ['short', 'med', 'logfile']

    short = models.CharField(max_length=100)
    med = models.TextField(max_length=1024, null=True)
    logfile = models.FilePathField()

    def __str__(self) -> str:
        return f"Job error {self.created}: '{self.short}'"


class JobWarning(JobError):
    def __str__(self) -> str:
        return f"Job warning {self.created}: '{self.short}'"


class JobPermission(BaseModel):
    field_list = ['name', 'permission', 'users', 'groups']

    name = models.CharField(max_length=100)
    permission = models.CharField(
        max_length=50,
        choices=[('full', 'Full'), ('read', 'Read'), ('write', 'Write'), ('execute', 'Execute')],
    )
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='JobPermissionMemberUser',
        through_fields=('permission', 'user'),
    )
    groups = models.ManyToManyField(
        Group,
        through='JobPermissionMemberGroup',
        through_fields=('permission', 'group'),
    )

    def __str__(self) -> str:
        return f"Permission '{self.name}' - {self.permission}"


class JobPermissionMemberUser(BareModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.ForeignKey(JobPermission, on_delete=models.CASCADE)


class JobPermissionMemberGroup(BareModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    permission = models.ForeignKey(JobPermission, on_delete=models.CASCADE)


class Job(BaseModel):
    field_list = ['job_id', 'name', 'inventory', 'playbook', 'schedule', 'permission']

    job_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=150)
    inventory = models.CharField(max_length=150)
    playbook = models.CharField(max_length=150)
    schedule = models.CharField(max_length=50, validators=[CronTab])
    permission = models.ForeignKey(JobPermission, on_delete=models.SET_NULL, null=True)

    def __str__(self) -> str:
        return f"Job '{self.name}' ('{self.playbook}')"


class JobExecution(BareModel):
    field_list = [
        'user', 'start', 'fin', 'error',
        'result_ok', 'result_changed', 'result_unreachable', 'result_failed', 'result_skipped',
        'result_rescued', 'result_ignored',
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True,
        related_name=f"jobexec_fk_user"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name=f"jobexec_fk_job")
    start = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(blank=True, null=True, default=None)
    error = models.ForeignKey(JobError, on_delete=models.CASCADE, related_name=f"jobexec_fk_error")
    warning = models.ForeignKey(JobWarning, on_delete=models.CASCADE, related_name=f"jobexec_fk_warning")
    result_ok = models.PositiveSmallIntegerField(default=0)
    result_changed = models.PositiveSmallIntegerField(default=0)
    result_unreachable = models.PositiveSmallIntegerField(default=0)
    result_failed = models.PositiveSmallIntegerField(default=0)
    result_skipped = models.PositiveSmallIntegerField(default=0)
    result_rescued = models.PositiveSmallIntegerField(default=0)
    result_ignored = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        result = 'success' if self.warning is None else 'warning'
        if self.error is not None:
            result = 'failed'

        return f"Job '{self.job.name}' execution {self.created}: {result}"