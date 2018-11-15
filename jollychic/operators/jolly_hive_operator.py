# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re

from airflow.jollychic.hooks.jolly_hive_hooks import JollyHiveCliHook
from airflow.models import JollyBaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.utils.operator_helpers import context_to_airflow_vars


class JollyHiveOperator(JollyBaseOperator):
    """
    Executes hql code in a specific Hive database.

    :param hql: the hql to be executed
    :type hql: string
    :param hive_cli_conn_id: reference to the Hive database
    :type hive_cli_conn_id: string
    :param hiveconf_jinja_translate: when True, hiveconf-type templating
        ${var} gets translated into jinja-type templating {{ var }}. Note that
        you may want to use this along with the
        ``DAG(user_defined_macros=myargs)`` parameter. View the DAG
        object documentation for more details.
    :type hiveconf_jinja_translate: boolean
    :param script_begin_tag: If defined, the operator will get rid of the
        part of the script before the first occurrence of `script_begin_tag`
    :type script_begin_tag: str
    :param mapred_queue: queue used by the Hadoop CapacityScheduler
    :type  mapred_queue: string
    :param mapred_queue_priority: priority within CapacityScheduler queue.
        Possible settings include: VERY_HIGH, HIGH, NORMAL, LOW, VERY_LOW
    :type  mapred_queue_priority: string
    :param mapred_job_name: This name will appear in the jobtracker.
        This can make monitoring easier.
    :type  mapred_job_name: string
    """

    template_fields = ('hql', 'schema')
    template_ext = ('.hql', '.sql',)
    ui_color = '#f0e4ec'

    @apply_defaults
    def __init__(
            self, hql='',
            hql_file=None,
            hive_cli_conn_id='hive_cli_default',
            schema='default',
            hiveconf_jinja_translate=False,
            script_begin_tag=None,
            run_as_owner=False,
            mapred_queue=None,
            mapred_queue_priority=None,
            mapred_job_name=None,
            *args, **kwargs):

        super(JollyHiveOperator, self).__init__(*args, **kwargs)
        self.hiveconf_jinja_translate = hiveconf_jinja_translate
        self.hql = hql
        if hql_file:
            with open(hql_file,'r')as f:
                self.hql += f.read()
        self.schema = schema
        self.hive_cli_conn_id = hive_cli_conn_id
        self.script_begin_tag = script_begin_tag
        self.run_as = None
        if run_as_owner:
            self.run_as = self.dag.owner

        self.mapred_queue = mapred_queue
        self.mapred_queue_priority = mapred_queue_priority
        self.mapred_job_name = mapred_job_name

    def get_hook(self):
        return JollyHiveCliHook(
                        hive_cli_conn_id=self.hive_cli_conn_id,
                        run_as=self.run_as,
                        mapred_queue=self.mapred_queue,
                        mapred_queue_priority=self.mapred_queue_priority,
                        mapred_job_name=self.mapred_job_name)

    def prepare_template(self):
        if self.hiveconf_jinja_translate:
            self.hql = re.sub(
                "(\$\{([ a-zA-Z0-9_]*)\})", "{{ \g<2> }}", self.hql)
        if self.script_begin_tag and self.script_begin_tag in self.hql:
            self.hql = "\n".join(self.hql.split(self.script_begin_tag)[1:])

    def execute(self, context):
        logging.info('Executing: ' + self.hql)
        self.hook = self.get_hook()
        self.hook.run_cli(hql=self.hql, schema=self.schema,
                          hive_conf=context_to_airflow_vars(context))

    def dry_run(self):
        self.hook = self.get_hook()
        self.hook.test_hql(hql=self.hql)

    def on_kill(self):
        self.hook.kill()