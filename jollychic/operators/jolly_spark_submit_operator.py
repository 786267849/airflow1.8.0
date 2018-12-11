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
#
import logging
import requests

from airflow.jollychic.hooks.jolly_spark_submit_hook import JollySparkSubmitHook
from airflow.models import JollyBaseOperator
from airflow.utils.decorators import apply_defaults
import json
from airflow import configuration
log = logging.getLogger(__name__)


class JollySparkSubmitOperator(JollyBaseOperator):
    """
    This hook is a wrapper around the spark-submit binary to kick off a spark-submit job.
    It requires that the "spark-submit" binary is in the PATH.
    :param application: The application that submitted as a job, either jar or py file.
    :type application: str
    :param conf: Arbitrary Spark configuration properties
    :type conf: dict
    :param conn_id: The connection id as configured in Airflow administration. When an
                    invalid connection_id is supplied, it will default to yarn.
    :type conn_id: str
    :param files: Upload additional files to the container running the job, separated by a
                  comma. For example hive-site.xml.
    :type files: str
    :param py_files: Additional python files used by the job, can be .zip, .egg or .py.
    :type py_files: str
    :param jars: Submit additional jars to upload and place them in executor classpath.
    :type jars: str
    :param executor_cores: Number of cores per executor (Default: 2)
    :type executor_cores: int
    :param executor_memory: Memory per executor (e.g. 1000M, 2G) (Default: 1G)
    :type executor_memory: str
    :param keytab: Full path to the file that contains the keytab
    :type keytab: str
    :param principal: The name of the kerberos principal used for keytab
    :type principal: str
    :param name: Name of the job (default airflow-spark)
    :type name: str
    :param num_executors: Number of executors to launch
    :type num_executors: int
    :param verbose: Whether to pass the verbose flag to spark-submit process for debugging
    :type verbose: bool
    """
    template_fields = ('params_list',)

    @apply_defaults
    def __init__(self,
                 application='',
                 params_list=None,
                 conf=None,
                 conn_id='spark_default',
                 files=None,
                 py_files=None,
                 jars=None,
                 executor_cores=None,
                 executor_memory=None,
                 keytab=None,
                 principal=None,
                 name='airflow-spark',
                 num_executors=None,
                 java_class=None,
                 driver_memory=None,
                 verbose=False,
                 *args,
                 **kwargs):
        super(JollySparkSubmitOperator, self).__init__(*args, **kwargs)
        self._application = application
        self.params_list = params_list
        self._conf = conf
        self._files = files
        self._py_files = py_files
        self._jars = jars
        self._executor_cores = executor_cores
        self._executor_memory = executor_memory
        self._keytab = keytab
        self._principal = principal
        self._name = name
        self._java_class = java_class
        self._driver_memory = driver_memory
        self._num_executors = num_executors
        self._verbose = verbose
        self._hook = None
        self._conn_id = conn_id
    def execute(self, context):
        """
        Call the SparkSubmitHook to run the provided spark job
        """
        self._hook = JollySparkSubmitHook(
            conf=self._conf,
            conn_id=self._conn_id,
            files=self._files,
            py_files=self._py_files,
            jars=self._jars,
            executor_cores=self._executor_cores,
            executor_memory=self._executor_memory,
            keytab=self._keytab,
            principal=self._principal,
            name=self._name,
            java_class=self._java_class,
            driver_memory=self._driver_memory,
            num_executors=self._num_executors,
            verbose=self._verbose,
            run_user = self.run_user
        )
        self._hook.submit(self._application, self.params_list)

    def on_kill(self):
        self._hook.on_kill()
