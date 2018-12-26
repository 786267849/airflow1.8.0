# -*- coding: utf-8 -*-
from airflow.models import JollyBaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.utils.state import State
from airflow.models import TaskInstance
import logging
from airflow import settings
from airflow.exceptions import AirflowException
from datetime import timedelta






class JollySensor(JollyBaseOperator):
    """
    Waits for a task to complete in a different DAG

    :param external_dag_id: The dag_id that contains the task you want to
        wait for
    :type external_dag_id: string
    :param external_task_id: The task_id that contains the task you want to
        wait for
    :type external_task_id: string
    :param allowed_states: list of allowed states, default is ``['success']``
    :type allowed_states: list
    :param execution_delta: time difference with the previous execution to
        look at, the default is the same execution_date as the current task.
        For yesterday, use [positive!] datetime.timedelta(days=1). Either
        execution_delta or execution_date_fn can be passed to
        ExternalTaskSensor, but not both.
    :type execution_delta: datetime.timedelta
    :param execution_date_fn: function that receives the current execution date
        and returns the desired execution date to query. Either execution_delta
        or execution_date_fn can be passed to ExternalTaskSensor, but not both.
    :type execution_date_fn: callable
    """
    ui_color = '#19647e'

    @apply_defaults
    def __init__(
            self,
            external_dag_id,
            external_task_id,
            allowed_states=None,
            execution_delta=None,
            execution_date_fn=None,
            *args, **kwargs):
        super(JollySensor, self).__init__(*args, **kwargs)
        self.allowed_states = allowed_states or [State.SUCCESS]
        if execution_delta is not None and execution_date_fn is not None:
            raise ValueError(
                'Only one of `execution_date` or `execution_date_fn` may'
                'be provided to ExternalTaskSensor; not both.')

        self.execution_delta = execution_delta
        self.execution_date_fn = execution_date_fn
        self.external_dag_id = external_dag_id
        self.external_task_id = external_task_id

    def poke(self, context):
        if self.execution_delta:
            # 判断execution时间差值是否小于一天，若小于则按照具体时间差查询依赖的task执行后的状态
            if self.execution_delta < timedelta(days=1):
                dttm = context['execution_date'] - self.execution_delta
            else:#若大于一天则认为所依赖task运行间隔以天为单位，查询在设置一整天内task的执行状态
                dttm = (context['execution_date'] - self.execution_delta).date()
        # elif self.execution_date_fn:
        #     dttm = self.execution_date_fn(context['execution_date'])
        else:#若没有设置dexcution_delta,则默认验证本task_execution_date一天内所依赖的task的执行状态
            dttm = context['execution_date'].date()
        logging.info(
            'Poking for '
            '{self.external_dag_id}.'
            '{self.external_task_id} on '
            '{dttm} ... '.format(**locals()))
        TI = TaskInstance

        session = settings.Session()
        if isinstance(self.external_task_id,str):
            self.external_task_id = (self.external_task_id,)
        else:
            self.external_task_id = tuple(self.external_task_id)
        #以具体时间查询,求count
        if self.execution_delta and self.execution_delta < timedelta(days=1):
            count = session.query(TI).filter(
                TI.dag_id == self.external_dag_id,
                TI.task_id.in_(self.external_task_id),
                TI.state.in_(self.allowed_states),
                TI.execution_date == dttm,
            ).count()
        else:#以一天范围查找，求count
            count = session.query(TI).filter(
                TI.dag_id == self.external_dag_id,
                TI.task_id.in_(self.external_task_id),
                TI.state.in_(self.allowed_states),
                TI.execution_date.between(dttm,dttm+timedelta(days=1)),
            ).group_by(TI.task_id).count()
        session.commit()
        session.close()
        return True if count == len(self.external_task_id) else False

    def execute(self, context):
        if not self.poke(context):
            raise AirflowException('Failed criteria met.')
        else:
            logging.info("Success criteria met. Exiting.")