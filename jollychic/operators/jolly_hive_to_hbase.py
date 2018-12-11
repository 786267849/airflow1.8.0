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


from airflow.jollychic.hooks.jolly_hbase_hook import JollyHiveToHbaseHook
from airflow.models import JollyBaseOperator
from airflow.utils.decorators import apply_defaults

from tempfile import NamedTemporaryFile


class JollyHiveToHbaseOpreator(JollyBaseOperator):
    """
    支持借助于临时表将hive表数据导入hbase中
    sql:生成临时表需要的sql查询语句，select * from hive_database.hive_table
        type:str
    hbase_table:需要生成的hbase_table_name
        type:str
    column_family:hbase表列族名
        type:str
    map_memory: map内存资源
        type:str
    reduce_memory: reduce内存资源
        type:str
    queque: 遵循queque
        type:str
    ssh_hook: 远程连接hbase的SSHHook实例对象
        type：SSHHook
    hiveserver2_conn_id:导出hive表连接名
        type:str
    """
    template_ext = ('.sql',)
    ui_color = '#a0e08c'

    @apply_defaults
    def __init__(
            self,
            sql,
            hbase_table,
            column_family,
            num_region,
            map_memory=None,
            reduce_memory=None,
            queue=None,
            ssh_hook=None,
            hiveserver2_conn_id='hiveserver2_default',
            *args, **kwargs):
        super(JollyHiveToHbaseOpreator, self).__init__(*args, **kwargs)
        self.sql = sql
        self.hiveserver2_conn_id = hiveserver2_conn_id
        self.hbase_table = hbase_table
        self.column_family = column_family
        self.num_region = num_region
        self.map_memory = map_memory
        self.reduce_memory = reduce_memory
        self.queue = queue
        self.ssh_hook = ssh_hook



    def execute(self, context):

        hbase = JollyHiveToHbaseHook(column_family=self.column_family,hbase_table=self.hbase_table,sql=self.sql,
                                     ssh_hook=self.ssh_hook, hiveserver2_conn_id=self.hiveserver2_conn_id)

        hbase.get_hive_file(self.map_memory, self.reduce_memory, self.queue)

        hbase.import_hbase(num_region=self.num_region,
                           map_memory=self.map_memory,
                           reduce_memory=self.reduce_memory,
                           queue=self.queue)

        logging.info("Done.")
