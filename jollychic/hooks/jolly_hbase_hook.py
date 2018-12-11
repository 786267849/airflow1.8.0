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
import re

from airflow.hooks.base_hook import BaseHook
from airflow.exceptions import AirflowException
from copy import deepcopy
import logging
import subprocess
from airflow.contrib.operators.ssh_execute_operator import SSHTempFileContent
from airflow import configuration
from airflow.jollychic.hooks.jolly_hive_hooks import JollyHiveServer2Hook

log = logging.getLogger(__name__)


class JollyHiveToHbaseHook(BaseHook):

    def __init__(self, column_family, hbase_table, sql, hiveserver2_conn_id='hiveserver2_default',
                 tmp_hive_table='tmp_hive_table',namenodes=['stream-master1', 'stream-master2'], ssh_hook=None):
        self.column_family = column_family
        self.hbase_table = hbase_table
        self.sql = sql
        self.hiveserver2_conn_id = hiveserver2_conn_id
        self.tmp_hive_table = tmp_hive_table
        self.namenodes = namenodes
        self.ssh_hook = ssh_hook

    def get_hive_conn(self,schema=None):
        hive = JollyHiveServer2Hook(hiveserver2_conn_id=self.hiveserver2_conn_id)
        return hive.get_conn(schema=schema)

    def get_hive_file(self,map_memory, reduce_memory, queue):
        cur = self.get_hive_conn().cursor()
        #若该表名已存在，则删除
        cur.execute("drop table if exists zybiro.{}".format(self.tmp_hive_table))
        # 用as形式在创建表的同时导入数据
        cur.execute(
            "create table zybiro.{0} row format delimited fields terminated by '\\t' stored as textfile as {1}".format(
                self.tmp_hive_table, self.sql))
        logging.info('create temporary hive_table sucess')

        if self.ssh_hook:
            active_namenode = self.get_active_namenode()
            # subprocess.Popen('hadoop fs -rm -r hdfs://{0}:8020/user/bulkload/textfile/{1}'.format(self.get_active_namenode(),self.tmp_hive_table), shell=True)
            cmd = 'hadoop distcp  hdfs:///user/hive/warehouse/zybiro.db/{0} hdfs://{1}:8020/user/bulkload/textfile'.format(self.tmp_hive_table,active_namenode)
            self.Popen(cmd,shell=True)
            cur.execute("drop table zybiro.{}".format(self.tmp_hive_table))


    def create_hbase_table(self, num_region):
        create_table_cmd = """
hbase shell << TTT
create "{hbase_table}",{{NAME => "{column_family}", BLOCKCACHE => "true", BLOOMFILTER => "ROWCOL", COMPRESSION => "snappy" }}, {{NUMREGIONS => {num_region}, SPLITALGO => "HexStringSplit"}}
TTT""".format(hbase_table=self.hbase_table,column_family=self.column_family,num_region=num_region)
        if self.ssh_hook:
             self.ssh_Popen(create_table_cmd)
        else:
            self.Popen(create_table_cmd,shell=True)


    def get_hfile(self, map_memory, reduce_memory, queue):
        cmd = ['hbase --config /opt/cloudera/parcels/CDH/lib/hbase/conf org.apache.hadoop.hbase.mapreduce.ImportTsv']
        if map_memory:
            cmd += ['-Dmapreduce.map.memory.mb='+ map_memory]
        if reduce_memory:
            cmd += ['-Dmapreduce.reduce.memory.mb='+ reduce_memory]
        if queue:
            cmd += ['-Dmapreduce.job.queuename='+ queue]
        cmd += ['-Dimporttsv.bulk.output=hdfs:///user/bulkload/hfile/' + self.tmp_hive_table]
        columns = re.match('select (.*) from',self.sql).group(1).split(',')
        hbase_columns = 'HBASE_ROW_KEY,'
        if len(columns) == 1:
            cur = self.get_hive_conn().cursor()
            cur.execute('desc employee')
            hive_desc = cur.fetchall()
            for column in hive_desc:
                hbase_columns += "{0}:{1},".format(self.column_family,column[0])
        else:
            for columns  in columns[1:]:
                hbase_columns += "{0}:{1}".format(self.column_family, columns)
        if self.ssh_hook:
            cmd += ['-Dimporttsv.columns="{0}" {1} hdfs:///user/bulkload/textfile/{2}'.format(hbase_columns, self.hbase_table, self.tmp_hive_table)]
            active_namenode = self.get_active_namenode()
            subprocess.Popen('hadoop fs -rm -r hdfs://{0}:8020/user/bulkload/hfile/{1}'.format(active_namenode, self.tmp_hive_table),shell=True)
            masked_cmd = ' '.join(cmd)
            self.ssh_Popen(masked_cmd)
        else:
            cmd += ['-Dimporttsv.columns="{0}" {1} hdfs:///user/hive/warehouse/zybiro.db/{2}'.format(hbase_columns, self.hbase_table, self.tmp_hive_table)]
            subprocess.Popen('hadoop fs -rm -r hdfs:///user/bulkload/hfile/{}'.format(self.tmp_hive_table),shell=True)
            masked_cmd = ' '.join(cmd)
            self.Popen(masked_cmd,shell=True)


    def import_hbase(self, num_region, map_memory,
                     reduce_memory, queue):

        self.create_hbase_table(num_region)

        self.get_hfile(map_memory, reduce_memory, queue)

        cmd = ['hbase', '--config', '/opt/cloudera/parcels/CDH/lib/hbase/conf', 'org.apache.hadoop.hbase.mapreduce.LoadIncrementalHFiles']
        cmd += ['hdfs:///user/bulkload/hfile/' + self.tmp_hive_table, self.hbase_table]
        if self.ssh_hook:
            cmd = ' '.join(cmd)
            self.ssh_Popen(cmd)
            self.Popen('hadoop fs -rm -r hdfs://{0}:8020/user/bulkload/hfile/{1}'.format(self.get_active_namenode(),self.tmp_hive_table),shell=True)
            self.Popen('hadoop fs -rm -r hdfs://{0}:8020/user/bulkload/textfile/{1}'.format(self.get_active_namenode(),self.tmp_hive_table),shell=True)
        else:
            self.Popen(cmd)
            self.Popen('hadoop fs -rm -r hdfs:///user/bulkload/hfile/{}'.format(self.tmp_hive_table),shell=True)
            self.Popen('hive -e "drop table zybiro.{}"'.format(self.tmp_hive_table),shell=True)


    def get_active_namenode(self):
        for namenode in self.namenodes:
            cmd = 'hadoop fs - test - d hdfs: //{}:8020'.format(namenode)
            sp = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True)
            if not sp.returncode:
                return namenode
        else:
            raise AirflowException("no active_namenode in {}".format(",".join(self.namenodes)))


    def Popen(self, cmd, **kwargs):
        masked_cmd = cmd
        if isinstance(cmd,list):
            masked_cmd = ' '.join(cmd)
        logging.info("Executing command: {}".format(masked_cmd))
        sp = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs)

        for line in iter(sp.stdout):
            logging.info(line.strip())

        sp.wait()
        if sp.returncode:
            raise AirflowException("Command failed: {}".format(masked_cmd))

    def ssh_Popen(self, cmd):
        hook = self.ssh_hook
        host = hook._host_ref()
        with SSHTempFileContent(hook, cmd) as remote_file_path:
            logging.info("Temporary script "
                         "location : {0}:{1}".format(host, remote_file_path))
            logging.info("Running command: " + cmd)
            sp = hook.Popen(
                ['-q', 'bash', remote_file_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            for line in iter(sp.stdout):
                logging.info(line.strip())

            sp.wait()

            if sp.returncode:
                raise AirflowException("Command failed: {}".format(cmd))
